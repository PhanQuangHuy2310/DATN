"""Request workflow acceptance scenarios (routing, reject paths, permissions).

Each test documents the current behaviour of one business scenario so a
regression or a behaviour change shows up as a failing test.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from api_core.administration.service import TABLES, mutate
from api_core.authn.models import Actor
from api_core.domain.routing import resolve_route
from api_core.workflow.auto_approval import try_auto_approve
from api_core.workflow.service import (
    CommandError,
    _apply_acceptance_decision,
    _handle_approval_approved,
    _handle_approval_rejected_or_needs_info,
    _pick_present_executor,
    _validate_approval_decision_input,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _actor(roles, actor_id=None, department_id=None):
    return Actor(
        id=actor_id or str(uuid4()),
        email="actor@eas.com",
        display_name="Actor",
        department_id=department_id or str(uuid4()),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


def _sql(cursor) -> str:
    return " ".join(call.args[0] for call in cursor.execute.call_args_list)


class TwoWayRoutingTests(SimpleTestCase):
    """Scenario 1: requests travel up to managers and work travels down."""

    def setUp(self):
        self.dept = str(uuid4())
        self.staff = str(uuid4())
        self.manager = str(uuid4())
        self.director = str(uuid4())
        self.executor = str(uuid4())
        self.rules = {
            "schema_version": 1,
            "executor": "EXECUTOR_IT",
            "acceptor": "REQUESTER",
            "rules": [
                {
                    "id": "big",
                    "priority": 1,
                    "when": {"amount_gt": 10_000_000},
                    "approvers": ["DIRECT_MANAGER", "DIRECTOR"],
                },
                {"id": "default", "default": True, "approvers": ["DIRECT_MANAGER"]},
            ],
        }
        self.bindings = {
            "schema_version": 1,
            "departments": {
                self.dept: {"DIRECTOR": self.director, "EXECUTOR_IT": self.executor}
            },
        }

    def resolve(self, requester, manager, amount=None):
        return resolve_route(
            route_rules=self.rules,
            actor_bindings=self.bindings,
            department_id=self.dept,
            requester_id=requester,
            manager_id=manager,
            amount_vnd=amount,
        )

    def test_subordinate_request_goes_up_to_direct_manager(self):
        decision = self.resolve(self.staff, self.manager)
        self.assertEqual(decision.approver_ids, (self.manager,))

    def test_large_amount_escalates_up_the_chain(self):
        decision = self.resolve(self.staff, self.manager, amount=50_000_000)
        self.assertEqual(decision.approver_ids, (self.manager, self.director))

    def test_approved_work_is_assigned_down_to_executor_and_back_to_requester(self):
        decision = self.resolve(self.staff, self.manager)
        self.assertEqual(decision.executor_id, self.executor)
        self.assertEqual(decision.acceptor_id, self.staff)

    def test_manager_request_routes_to_own_manager_not_subordinate(self):
        # A manager's own request goes to their superior; a subordinate is
        # never resolved as approver of a superior's request.
        decision = self.resolve(self.manager, self.director)
        self.assertEqual(decision.approver_ids, (self.director,))
        self.assertNotIn(self.staff, decision.approver_ids)


class AssignDownTests(SimpleTestCase):
    """Scenario 1 (downward): the final approver hands work to a direct report."""

    def setUp(self):
        self.approver = str(uuid4())
        self.subordinate = str(uuid4())
        self.requester = str(uuid4())
        self.planned = str(uuid4())

    def approve(self, cursor, lifecycle="B", assigned=None, assignment=None):
        return _handle_approval_approved(
            cursor,
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            lifecycle,
            self.planned,
            None,
            {"approval_hours": 8, "execution_hours": 8},
            datetime.now(timezone.utc),
            approver_id=self.approver,
            requester_id=self.requester,
            assigned_executor_id=assigned,
            assignment=assignment,
        )

    def test_final_approver_assigns_direct_report_as_executor(self):
        cursor = MagicMock()
        # no next step, is direct report, has EXECUTOR role, executor still valid
        cursor.fetchone.side_effect = [None, (1,), (True,), (True,)]
        assignment = {}
        status, *_ = self.approve(
            cursor, assigned=self.subordinate, assignment=assignment
        )
        self.assertEqual(status, "READY_FOR_EXECUTION")
        calls = cursor.execute.call_args_list
        update = next(c for c in calls if "SET planned_executor_id" in c.args[0])
        self.assertEqual(update.args[1][0], self.subordinate)
        attempt = next(
            c for c in calls if "INSERT INTO eas.execution_attempt" in c.args[0]
        )
        self.assertEqual(attempt.args[1][-1], self.subordinate)
        self.assertEqual(assignment["reason"], "ASSIGNED_BY_APPROVER")

    def test_cannot_assign_someone_who_is_not_a_direct_report(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [None, None]
        with self.assertRaises(CommandError) as raised:
            self.approve(cursor, assigned=self.subordinate)
        self.assertEqual(raised.exception.code, "ASSIGNEE_INVALID")

    def test_assignment_only_at_last_approval_step(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(str(uuid4()), str(uuid4()))]
        with self.assertRaises(CommandError) as raised:
            self.approve(cursor, assigned=self.subordinate)
        self.assertEqual(raised.exception.code, "EXECUTOR_ASSIGNMENT_NOT_ALLOWED")

    def test_executor_id_is_rejected_on_negative_outcomes(self):
        with self.assertRaises(CommandError):
            _validate_approval_decision_input(
                {
                    "outcome": "REJECT",
                    "reason": "Không đủ điều kiện",
                    "expected_version": 1,
                    "executor_id": self.subordinate,
                }
            )


@override_settings(
    EAS_AI_AUTO_APPROVE_ENABLED=True,
    EAS_AI_AUTO_APPROVAL_POLICY_APPROVED=True,
)
class AutoApproveIntegrationTests(SimpleTestCase):
    """Scenario 2: only an explicitly approved policy may let AI approve."""

    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.request_id = str(uuid4())
        self.context = {
            "status": "PENDING_APPROVAL",
            "lock_version": 3,
            "risk_weight": 2,
            "type_code": "IT_ACCESS",
            "lifecycle": "A",
            "requester_name": "Staff",
            "department_code": "TECH",
            "step_id": str(uuid4()),
            "assignee_id": str(uuid4()),
            "amount_vnd": None,
            "ai_allowed": True,
        }

    def run_auto_approve(self, context, decision="auto_approve"):
        cursor = MagicMock()
        cursor.fetchone.return_value = (context["step_id"],)
        with (
            patch(
                "api_core.workflow.auto_approval._load_context", return_value=context
            ),
            patch(
                "api_core.integrations.ai_service.ai_client_sync.evaluate_auto_approve",
                return_value={"decision": decision, "reason": "ok"},
            ) as ai,
            patch("api_core.workflow.auto_approval.transaction.atomic"),
            patch("api_core.workflow.auto_approval.connection.cursor") as cm,
            patch("api_core.workflow.auto_approval._append_request_audit") as audit,
            patch("api_core.workflow.auto_approval.decide_approval") as decide,
        ):
            cm.return_value.__enter__.return_value = cursor
            try_auto_approve(self.request_id, "corr")
        return ai, decide, audit, cursor

    @override_settings(EAS_AI_AUTO_APPROVAL_POLICY_APPROVED=False)
    def test_ai_cannot_sign_without_business_policy_approval(self):
        ai, decide, _, _ = self.run_auto_approve(self.context)
        ai.assert_not_called()
        decide.assert_not_called()

    @override_settings(EAS_AI_AUTO_APPROVE_ENABLED=False)
    def test_ai_cannot_sign_when_auto_approval_is_off(self):
        ai, decide, _, _ = self.run_auto_approve(self.context)
        ai.assert_not_called()
        decide.assert_not_called()

    def test_weight_two_is_approved_by_ai_system_account(self):
        ai, decide, audit, cursor = self.run_auto_approve(self.context)
        ai.assert_called_once()
        takeover = cursor.execute.call_args_list[0]
        self.assertIn("SET assignee_id=%s", takeover.args[0])
        self.assertEqual(takeover.args[1][2], self.context["assignee_id"])
        self.assertEqual(audit.call_args.kwargs["action"], "AI_AUTO_APPROVE_TAKEOVER")
        kwargs = decide.call_args.kwargs
        self.assertEqual(kwargs["actor"].id, settings.EAS_AI_SYSTEM_USER_ID)
        self.assertEqual(kwargs["body"]["outcome"], "APPROVE")
        self.assertEqual(kwargs["body"]["expected_version"], 3)

    def test_weight_three_never_calls_ai(self):
        ai, decide, _, _ = self.run_auto_approve({**self.context, "risk_weight": 3})
        ai.assert_not_called()
        decide.assert_not_called()

    def test_ai_escalation_leaves_human_approver(self):
        _, decide, _, cursor = self.run_auto_approve(
            self.context, decision="escalate_to_human"
        )
        decide.assert_not_called()
        cursor.execute.assert_not_called()

    def test_worker_asks_api_before_notifying_approver(self):
        from api_core.worker import OutboxItem, run_outbox_batch

        item = OutboxItem(
            id=str(uuid4()),
            request_id=self.request_id,
            event_type="APPROVAL_REQUESTED",
            payload={},
            attempts=0,
            lease_token=str(uuid4()),
        )
        order = []
        with (
            patch("api_core.worker.claim_outbox", return_value=[item]),
            patch(
                "api_core.worker.acknowledge_outbox",
                side_effect=lambda _item: order.append("notify"),
            ),
            patch(
                "api_core.worker.request_ai_auto_approval",
                side_effect=lambda _id: order.append("auto-approve"),
            ),
        ):
            run_outbox_batch()
        self.assertEqual(order, ["auto-approve", "notify"])

    def test_worker_falls_back_to_human_when_api_is_unreachable(self):
        import httpx

        from api_core.worker import request_ai_auto_approval

        with patch("httpx.post", side_effect=httpx.ConnectError("down")):
            self.assertFalse(request_ai_auto_approval(self.request_id))

    def test_internal_endpoint_requires_worker_secret(self):
        from django.test import RequestFactory

        from api_core.workflow.views import internal_auto_approve_view

        factory = RequestFactory()
        with patch("api_core.workflow.auto_approval.try_auto_approve") as auto:
            denied = internal_auto_approve_view(
                factory.post("/x", HTTP_X_INTERNAL_SECRET="wrong"), self.request_id
            )
            auto.return_value = {"request": {"status": "COMPLETED"}}
            allowed = internal_auto_approve_view(
                factory.post(
                    "/x", HTTP_X_INTERNAL_SECRET=settings.EAS_WORKER_INTERNAL_SECRET
                ),
                self.request_id,
            )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        self.assertIn(b'"approved": true', allowed.content)
        auto.assert_called_once()


class RejectPathTests(SimpleTestCase):
    """Scenarios 3 and 4: who can reject and where the request goes next."""

    def test_approver_reject_is_terminal_and_skips_remaining_steps(self):
        cursor = MagicMock()
        status = _handle_approval_rejected_or_needs_info(
            cursor, str(uuid4()), str(uuid4()), "REJECT", datetime.now(timezone.utc)
        )
        self.assertEqual(status, "REJECTED")
        sql = _sql(cursor)
        self.assertIn("UPDATE eas.workflow_instance SET state=%s", sql)
        self.assertIn("SET state='SKIPPED'", sql)
        self.assertEqual(cursor.execute.call_args_list[0].args[1][0], "REJECTED")
        self.assertNotIn("draft_attachment", sql)

    def test_approver_needs_info_returns_request_to_requester(self):
        cursor = MagicMock()
        status = _handle_approval_rejected_or_needs_info(
            cursor, str(uuid4()), str(uuid4()), "NEEDS_INFO", datetime.now(timezone.utc)
        )
        self.assertEqual(status, "NEEDS_INFO")
        # Attachments are copied back into the requester's editable draft.
        self.assertIn("INSERT INTO eas.draft_attachment", _sql(cursor))

    @patch("api_core.workflow.service._is_actor_valid_for_role", return_value=True)
    def test_acceptor_rework_returns_to_previous_step_executor(self, _valid):
        cursor = MagicMock()
        # requester/acceptor lookup, then no attendance feed: executor kept
        cursor.fetchone.side_effect = [(str(uuid4()), None), (False,)]
        executor = str(uuid4())
        status, completed_at, attempt_id = _apply_acceptance_decision(
            cursor,
            "REWORK",
            str(uuid4()),
            str(uuid4()),
            1,
            executor,
            str(uuid4()),
            str(uuid4()),
            {"execution_hours": 8},
            datetime.now(timezone.utc),
        )
        self.assertEqual(status, "READY_FOR_EXECUTION")
        self.assertIsNone(completed_at)
        self.assertIsNotNone(attempt_id)
        insert = next(
            c
            for c in cursor.execute.call_args_list
            if "INSERT INTO eas.execution_attempt" in c.args[0]
        )
        self.assertEqual(insert.args[1][3:], [2, executor])

    def test_acceptor_has_no_terminal_reject_outcome(self):
        from api_core.workflow.service import CommandError, _validate_acceptance_input

        with self.assertRaises(CommandError):
            _validate_acceptance_input(
                {"outcome": "REJECT", "reason": "x" * 20, "expected_version": 1}
            )


class PermissionChangeTests(SimpleTestCase):
    """Scenarios 7 and 8: permission changes take effect without re-login."""

    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.admin = _actor({"OPS_ADMIN"})
        self.subject = str(uuid4())
        self.membership_id = str(uuid4())
        self.row = (
            self.membership_id,
            self.subject,
            "APPROVER",
            "GLOBAL",
            None,
            "ALL",
            None,
            datetime.now(timezone.utc),
            None,
            None,
        )

    def _mutate(self, method, body):
        c = MagicMock()
        c.fetchone.return_value = self.row
        with (
            patch("api_core.administration.service.transaction.atomic"),
            patch("api_core.administration.service.connection.cursor") as cm,
            patch(
                "api_core.administration.service._execute_idempotent",
                side_effect=lambda **kw: kw["operation"](c),
            ),
            patch("api_core.administration.service._append_admin_audit"),
        ):
            cm.return_value.__enter__.return_value = c
            mutate(
                self.admin,
                "memberships",
                None if method == "POST" else self.membership_id,
                body,
                method,
                "key",
                "corr",
            )
        return _sql(c)

    def test_roles_are_reloaded_from_database_on_every_request(self):
        source = (REPO_ROOT / "api_core/authn/service.py").read_text(encoding="utf-8")
        loader = source[source.index("def load_actor_from_session") :]
        loader = loader[: loader.index("\ndef ")]
        self.assertIn("FROM eas.role_membership", loader)
        self.assertNotIn('cache.get(f"eas:roles', loader)

    def test_granting_a_role_keeps_the_employee_signed_in(self):
        sql = self._mutate(
            "POST",
            {
                "reason": "Promote employee to approver",
                "user_id": self.subject,
                "role": "APPROVER",
                "scope_kind": "GLOBAL",
                "type_scope": "ALL",
            },
        )
        self.assertIn("INSERT INTO eas.role_membership", sql)
        self.assertNotIn("auth_version=auth_version+1", sql)

    def test_revoking_a_role_still_ends_existing_sessions(self):
        from api_core.administration.service import serialize

        record = serialize(TABLES["memberships"][1], self.row)
        sql = self._mutate(
            "DELETE",
            {
                "reason": "Remove approver permission",
                "expected_revision": record["revision"],
            },
        )
        self.assertIn("auth_version=auth_version+1", sql)


class AbsentAssigneeTests(SimpleTestCase):
    """Scenario 9: absent executors are replaced using HRM attendance."""

    def pick(self, fetches):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetches
        self.planned = str(uuid4())
        result = _pick_present_executor(
            cursor,
            planned_executor_id=self.planned,
            instance_id=str(uuid4()),
            requester_id=str(uuid4()),
            acceptor_id=None,
            department_id=str(uuid4()),
            type_id=str(uuid4()),
        )
        return result, cursor

    def test_absent_executor_is_replaced_by_present_colleague(self):
        substitute = str(uuid4())
        (executor, reason), cursor = self.pick([(True,), ("ABSENT",), (substitute,)])
        self.assertEqual(executor, substitute)
        self.assertEqual(reason, "PLANNED_EXECUTOR_ABSENT")
        candidate_sql = cursor.execute.call_args_list[-1].args[0]
        self.assertIn("COALESCE(a.status, 'PRESENT') = 'PRESENT'", candidate_sql)
        self.assertIn("rm.role = 'EXECUTOR'", candidate_sql)

    def test_executor_on_leave_without_substitute_keeps_assignment(self):
        (executor, reason), _ = self.pick([(True,), ("LEAVE",), None])
        self.assertEqual(executor, self.planned)
        self.assertEqual(reason, "NO_PRESENT_SUBSTITUTE")

    def test_present_or_unrecorded_executor_is_kept(self):
        for fetches in ([(True,), ("PRESENT",)], [(True,), None]):
            with self.subTest(fetches=fetches):
                (executor, reason), _ = self.pick(fetches)
                self.assertEqual(executor, self.planned)
                self.assertIsNone(reason)

    def test_without_attendance_feed_everyone_counts_as_present(self):
        (executor, _reason), cursor = self.pick([(False,)])
        self.assertEqual(executor, self.planned)
        self.assertEqual(cursor.execute.call_count, 1)

    def test_handoff_after_approval_records_substitution(self):
        cursor = MagicMock()
        substitute = str(uuid4())
        planned = str(uuid4())
        # no next step, attendance feed ok, planned absent, substitute, role valid
        cursor.fetchone.side_effect = [
            None,
            (True,),
            ("ABSENT",),
            (substitute,),
            (True,),
        ]
        assignment = {}
        _handle_approval_approved(
            cursor,
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            "B",
            planned,
            None,
            {"approval_hours": 8, "execution_hours": 8},
            datetime.now(timezone.utc),
            requester_id=str(uuid4()),
            assignment=assignment,
        )
        self.assertEqual(
            assignment,
            {
                "planned_executor_id": planned,
                "executor_id": substitute,
                "reason": "PLANNED_EXECUTOR_ABSENT",
            },
        )


class PolicyPublicationLatencyTests(SimpleTestCase):
    """Scenario 6: time from loading a new policy to it being applied."""

    @patch("api_core.workflow.service.unavailable_notice", return_value=None)
    def test_published_workflow_release_applies_to_next_submission(self, _notice):
        from time import perf_counter

        from api_core.workflow.service import _fetch_submit_config

        cursor = MagicMock()
        releases = iter(["release-v1", "release-v2"])

        def fetch():
            return ("type", "A", next(releases), {}, {}, {}, {}, "IT")

        cursor.fetchone.side_effect = fetch
        self.assertEqual(
            _fetch_submit_config(cursor, "IT_ACCESS", None)[2], "release-v1"
        )
        started = perf_counter()
        # A new release is published between two submissions: no cache to expire.
        self.assertEqual(
            _fetch_submit_config(cursor, "IT_ACCESS", None)[2], "release-v2"
        )
        self.assertLess(perf_counter() - started, 0.5)

    def publish(self, roles, stored=None):
        from django.test import RequestFactory

        from api_core.workflow.policy_views import publish_ai_policy_rules

        request = RequestFactory().post(
            "/api/v1/policies/ai-rules",
            data='{"version": "QD-2026-11", "rules": []}',
            content_type="application/json",
        )
        request._dont_enforce_csrf_checks = True
        actor = _actor(roles)
        stored = stored or {
            "id": str(uuid4()),
            "version": "QD-2026-11",
            "rules": [],
            "activated": True,
        }
        with (
            patch("api_core.authn.service.load_actor_from_session", return_value=actor),
            patch("api_core.maintenance.is_maintenance_active", return_value=False),
            patch(
                "api_core.workflow.ai_policy.publish_version", return_value=stored
            ) as store,
            patch(
                "api_core.workflow.ai_policy.push_to_ai",
                return_value={"version": "QD-2026-11"},
            ) as ai,
        ):
            return publish_ai_policy_rules(request), store, ai

    def test_policy_admin_stores_version_in_db_then_refreshes_ai_cache(self):
        response, store, ai = self.publish({"POLICY_ADMIN"})
        self.assertEqual(response.status_code, 201)
        store.assert_called_once()
        ai.assert_called_once()
        self.assertIn(b'"ai_cache_refreshed": true', response.content)

    def test_inactive_version_is_not_pushed_to_ai(self):
        stored = {"id": "x", "version": "v", "rules": [], "activated": False}
        response, _, ai = self.publish({"POLICY_ADMIN"}, stored=stored)
        self.assertEqual(response.status_code, 201)
        ai.assert_not_called()

    def test_other_roles_cannot_publish_ai_rules(self):
        response, store, ai = self.publish({"APPROVER"})
        self.assertEqual(response.status_code, 403)
        store.assert_not_called()
        ai.assert_not_called()


class AiPolicyStoreTests(SimpleTestCase):
    """Item 1.4: eas.ai_policy_version is the source of truth for AI rules."""

    databases: ClassVar[set[str]] = {"default"}

    def test_document_validation(self):
        from api_core.workflow.ai_policy import validate_document

        ok = validate_document(
            {
                "version": " QD-1 ",
                "rules": [{"id": "r1", "amount_gt": 5_000_000, "min_risk": 4}],
            }
        )
        self.assertEqual(ok["version"], "QD-1")
        for bad in (
            {"version": "v", "rules": [{"id": "r1"}]},
            {"version": "v", "rules": [{"id": "r1", "min_risk": 9}]},
            {"version": "v", "rules": [{"id": "r", "auto_approve": False}] * 2},
            {"version": "v", "rules": [{"id": "r", "auto_approve": False, "x": 1}]},
            {"version": "", "rules": []},
            {"rules": []},
        ):
            with self.subTest(bad=bad), self.assertRaises(CommandError):
                validate_document(bad)

    def _store(self, fetches, body):
        from api_core.workflow import ai_policy

        cursor = MagicMock()
        cursor.fetchone.side_effect = fetches
        with (
            patch("api_core.workflow.ai_policy.transaction.atomic"),
            patch("api_core.workflow.ai_policy.connection.cursor") as cm,
            patch("api_core.workflow.ai_policy._append_admin_audit") as audit,
        ):
            cm.return_value.__enter__.return_value = cursor
            result = ai_policy.publish_version(
                actor=_actor({"POLICY_ADMIN"}), body=body, correlation_id="c"
            )
        return result, cursor, audit

    def test_publish_inserts_and_activates_single_version(self):
        result, cursor, audit = self._store(
            [None, (str(uuid4()),), ("QD-2",)], {"version": "QD-2", "rules": []}
        )
        sql = _sql(cursor)
        self.assertIn("INSERT INTO eas.ai_policy_version", sql)
        self.assertIn("SET state='INACTIVE' WHERE state='ACTIVE'", sql)
        self.assertIn("SET state='ACTIVE'", sql)
        self.assertTrue(result["activated"])
        actions = [c.kwargs["action"] for c in audit.call_args_list]
        self.assertEqual(actions, ["AI_POLICY_CREATED", "AI_POLICY_ACTIVATED"])

    def test_duplicate_version_is_rejected(self):
        with self.assertRaises(CommandError) as raised:
            self._store([(1,)], {"version": "QD-2", "rules": []})
        self.assertEqual(raised.exception.code, "POLICY_VERSION_EXISTS")

    def test_store_without_activation(self):
        result, cursor, _ = self._store(
            [None, (str(uuid4()),)], {"version": "QD-3", "rules": [], "activate": False}
        )
        self.assertFalse(result["activated"])
        self.assertNotIn("SET state='ACTIVE'", _sql(cursor))

    def test_internal_endpoint_serves_active_version_to_ai_only(self):
        from django.test import RequestFactory

        from api_core.workflow.policy_views import internal_active_ai_policy

        factory = RequestFactory()
        with patch(
            "api_core.workflow.ai_policy.active_document",
            return_value={"version": "QD-2", "rules": []},
        ):
            denied = internal_active_ai_policy(factory.get("/x"))
            allowed = internal_active_ai_policy(
                factory.get(
                    "/x", HTTP_X_INTERNAL_SECRET=settings.EAS_AI_INTERNAL_SECRET
                )
            )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        self.assertIn(b"QD-2", allowed.content)


class LegacyPolicyEndpointTests(SimpleTestCase):
    """Item 4.2: CSRF-exempt legacy policy/maintenance views are gone."""

    def test_legacy_views_removed(self):
        from api_core.workflow import policy_views

        for name in (
            "ingest_policy",
            "toggle_maintenance",
            "maintenance_status",
            "_trigger_ai_retraining",
        ):
            self.assertFalse(hasattr(policy_views, name), name)
