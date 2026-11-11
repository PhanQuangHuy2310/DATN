from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.workflow import insights
from api_core.workflow.reporting import get_request_metrics_report
from api_core.workflow.service import CommandError


def _actor(*roles: str) -> Actor:
    return Actor(
        id=str(uuid4()),
        email="person@eas.com",
        display_name="Person",
        department_id=str(uuid4()),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


class _DbPatchedTestCase(SimpleTestCase):
    # Required so SimpleTestCase lets tests replace connection.cursor.
    databases: ClassVar[set[str]] = {"default"}


def _cursor_ctx(target: str):
    cursor = MagicMock()
    patcher = patch(target)
    ctx = patcher.start()
    ctx.return_value.__enter__.return_value = cursor
    return patcher, cursor


class RequestProgressTests(SimpleTestCase):
    def _progress(self, status, steps, workflow=None, sla=None, names=None):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            "Requester",
            "Nghỉ phép",
            "Phòng Kế toán",
            [
                {
                    "kind": "APPROVAL",
                    "outcome": "NEEDS_INFO",
                    "reason": "Thiếu ngày bắt đầu",
                    "decided_at": "2026-10-01T01:00:00+00:00",
                }
            ],
            [],
            sla,
            names or {},
        )
        return insights.build_request_progress(
            cursor,
            request_id=str(uuid4()),
            status=status,
            steps=steps,
            workflow=workflow,
            requester_id="req-1",
            now=datetime(2026, 10, 2, tzinfo=timezone.utc),
        )

    def test_pending_approval_reports_active_and_next_approver(self):
        steps = [
            {
                "assignee_id": "a1",
                "state": "APPROVED",
                "resolver_code": "DIRECT_MANAGER",
            },
            {
                "assignee_id": "a2",
                "state": "ACTIVE",
                "resolver_code": "FINANCE",
                "assignee_name": "Finance",
            },
            {
                "assignee_id": "a3",
                "state": "WAITING",
                "resolver_code": "DIRECTOR",
                "assignee_name": "Director",
            },
        ]
        due = datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat()
        result = self._progress(
            "PENDING_APPROVAL", steps, sla={"kind": "APPROVAL", "due_at": due}
        )
        self.assertEqual(result["stage"], "APPROVAL")
        self.assertEqual(result["current_assignee"]["name"], "Finance")
        self.assertEqual(result["current_assignee"]["resolver_code"], "FINANCE")
        self.assertEqual(result["next_assignee"]["name"], "Director")
        self.assertTrue(result["deadline"]["overdue"])
        self.assertEqual(result["deadline"]["remaining_seconds"], -86400)
        self.assertEqual(result["decisions"][0]["reason"], "Thiếu ngày bắt đầu")

    def test_last_approval_step_hands_over_to_executor_for_lifecycle_b(self):
        steps = [{"assignee_id": "a1", "state": "ACTIVE", "resolver_code": "IT"}]
        workflow = {
            "lifecycle": "B",
            "planned_executor_id": "e1",
            "acceptor_id": None,
            "attempt": None,
        }
        result = self._progress(
            "PENDING_APPROVAL", steps, workflow, names={"e1": "Executor"}
        )
        self.assertEqual(result["next_assignee"]["role"], "EXECUTOR")
        self.assertEqual(result["next_assignee"]["name"], "Executor")

    def test_revision_and_closed_states(self):
        revision = self._progress("NEEDS_INFO", [])
        self.assertEqual(revision["current_assignee"]["role"], "REQUESTER")
        closed = self._progress(
            "COMPLETED", [], sla={"kind": "ACCEPTANCE", "due_at": "2026-10-01T00:00:00"}
        )
        self.assertEqual(closed["stage"], "CLOSED")
        self.assertIsNone(closed["current_assignee"])
        self.assertIsNone(closed["deadline"])


class TeamReportTests(_DbPatchedTestCase):
    period: ClassVar[dict[str, str]] = {
        "created_from": "2026-01-01T00:00:00+07:00",
        "created_to": "2026-06-01T00:00:00+07:00",
    }

    def test_requires_approver_or_auditor(self):
        with self.assertRaises(CommandError) as raised:
            insights.team_report(_actor("REQUESTER"), self.period)
        self.assertEqual(raised.exception.status, 403)

    def test_rejects_period_without_timezone(self):
        with self.assertRaises(CommandError) as raised:
            insights.team_report(
                _actor("APPROVER"),
                {"created_from": "2026-01-01T00:00", "created_to": "2026-02-01T00:00"},
            )
        self.assertEqual(raised.exception.code, "PERIOD_INVALID")

    def test_groups_employee_rows_by_department_and_scopes_query(self):
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        cursor.fetchall.return_value = [
            ("d1", "Kế toán", "u1", "An", 3, 1, 1, 1, 0, 0, 1, 1, 7200, 3600),
            ("d1", "Kế toán", "u2", "Bình", 2, 0, 0, 1, 1, 0, 0, 0, None, None),
        ]
        actor = _actor("APPROVER")
        report = insights.team_report(actor, self.period)["report"]
        self.assertEqual(report["totals"]["total"], 5)
        self.assertEqual(report["departments"][0]["employees"], 2)
        self.assertEqual(report["employees"][0]["avg_completion_hours"], 2.0)
        self.assertIsNone(report["employees"][1]["avg_completion_hours"])
        sql, params = cursor.execute.call_args.args
        # The actor's own requests are excluded and the read predicate applies.
        self.assertIn("r.requester_id <> %s", sql)
        self.assertIn("request_participant", sql)
        self.assertEqual(params.count(actor.id), 5)


class OrgChartTests(_DbPatchedTestCase):
    def test_manager_outside_visible_set_is_not_disclosed(self):
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = (
            False,
            [{"id": "d1", "name": "Kế toán"}],
            [
                {
                    "id": "u1",
                    "display_name": "A",
                    "department_id": "d1",
                    "manager_id": "m-hidden",
                },
                {
                    "id": "u2",
                    "display_name": "B",
                    "department_id": "d1",
                    "manager_id": "u1",
                },
            ],
        )
        chart = insights.org_chart(_actor("REQUESTER"))
        self.assertEqual(chart["scope"], "department")
        managers = {u["id"]: u["manager_id"] for u in chart["users"]}
        self.assertIsNone(managers["u1"])
        self.assertEqual(managers["u2"], "u1")


class RoutePreviewTests(_DbPatchedTestCase):
    def test_unconfigured_type_is_conflict(self):
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = None
        with self.assertRaises(CommandError) as raised:
            insights.preview_route(_actor("REQUESTER"), {"type_code": "LEAVE"})
        self.assertEqual(raised.exception.code, "REQUEST_TYPE_NOT_CONFIGURED")

    def test_resolves_steps_and_flags_unauthorized_actor(self):
        actor = _actor("REQUESTER")
        manager, finance = str(uuid4()), str(uuid4())
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        rules = {
            "schema_version": 1,
            "rules": [
                {
                    "id": "DEFAULT",
                    "default": True,
                    "approvers": ["DIRECT_MANAGER", "FINANCE"],
                }
            ],
            "executor": None,
            "acceptor": None,
        }
        bindings = {
            "schema_version": 1,
            "departments": {actor.department_id: {"FINANCE": finance}},
        }
        cursor.fetchone.return_value = (
            "type-1",
            "A",
            "release-1",
            rules,
            bindings,
            {"approval_hours": 24},
            manager,
        )
        cursor.fetchall.return_value = [
            (manager, "Quản lý", True, ["APPROVER"]),
            (finance, "Tài chính", True, []),
        ]
        preview = insights.preview_route(actor, {"type_code": "LEAVE", "payload": {}})
        self.assertFalse(preview["resolvable"])
        self.assertEqual(preview["problem"], "ROUTE_ACTOR_INACTIVE")
        self.assertEqual(
            [
                (s["level"], s["assignee_name"], s["authorized"])
                for s in preview["steps"]
            ],
            [(1, "Quản lý", True), (2, "Tài chính", False)],
        )
        self.assertEqual(preview["sla_hours"]["approval"], 24)


class AiAssessmentTests(_DbPatchedTestCase):
    def _row(self, status="PENDING_APPROVAL"):
        return (
            "id",
            "REQ-1",
            status,
            "requester",
            "LEAVE",
            "Nghỉ phép",
            "A",
            2,
            {"start_date": "2026-11-03"},
            None,
            "Kế toán",
            {"required": ["start_date", "end_date"]},
            0,
        )

    def test_draft_cannot_be_assessed(self):
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = self._row("DRAFT")
        with self.assertRaises(CommandError) as raised:
            insights.run_ai_assessment(_actor("APPROVER"), str(uuid4()), str(uuid4()))
        self.assertEqual(raised.exception.status, 409)

    @patch("api_core.workflow.insights._append_request_audit")
    @patch("api_core.workflow.insights.transaction.atomic")
    @patch("api_core.integrations.ai_service.ai_client_sync")
    def test_fallbacks_are_recorded_honestly_and_persisted(self, ai, _atomic, append):
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = self._row()
        cursor.fetchall.return_value = [(1, "ACTIVE", "DIRECT_MANAGER", "Quản lý")]
        ai.classify_request.return_value = {
            "fallback_used": True,
            "method": "keyword_heuristic",
        }
        ai.score_risk.return_value = {"risk_score": 2, "fallback_used": False}
        ai.evaluate_auto_approve.return_value = {
            "decision": "escalate_to_human",
            "reason": "AI Service không khả dụng",
            "fallback_used": True,
        }
        result = insights.run_ai_assessment(
            _actor("APPROVER"), str(uuid4()), str(uuid4())
        )
        stages = {s["key"]: s for s in result["assessment"]["stages"]}
        self.assertEqual(stages["VALIDATING"]["missing_fields"], ["end_date"])
        self.assertEqual(stages["CLASSIFICATION"]["status"], "FALLBACK")
        self.assertEqual(stages["RISK_ANALYSIS"]["status"], "DONE")
        self.assertEqual(stages["RECOMMENDATION"]["method"], "unavailable")
        self.assertEqual(stages["OCR"]["status"], "NOT_APPLICABLE")
        self.assertEqual(stages["HUMAN_REVIEW"]["status"], "PENDING")
        self.assertTrue(result["assessment"]["fallback_used"])
        self.assertTrue(result["assessment"]["advisory_only"])
        self.assertEqual(
            append.call_args.kwargs["action"], insights.AI_ASSESSMENT_ACTION
        )


class AiAssessmentOutageTests(_DbPatchedTestCase):
    @patch("api_core.workflow.insights._append_request_audit")
    @patch("api_core.workflow.insights.transaction.atomic")
    @patch("api_core.integrations.ai_service.ai_client_sync")
    def test_unreachable_service_skips_recommendation_call(self, ai, _atomic, append):
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = AiAssessmentTests._row(None)
        cursor.fetchall.return_value = []
        ai.classify_request.return_value = {"fallback_used": True}
        ai.score_risk.return_value = {"risk_score": 2, "fallback_used": True}
        result = insights.run_ai_assessment(
            _actor("APPROVER"), str(uuid4()), str(uuid4())
        )
        ai.evaluate_auto_approve.assert_not_called()
        stages = {s["key"]: s for s in result["assessment"]["stages"]}
        self.assertEqual(stages["RECOMMENDATION"]["method"], "unavailable")
        self.assertEqual(stages["RECOMMENDATION"]["decision"], "escalate_to_human")
        self.assertEqual(stages["ROUTING"]["status"], "NOT_AVAILABLE")
        append.assert_called_once()


class MetricsDurationTests(_DbPatchedTestCase):
    @patch("api_core.workflow.reporting.connection.cursor")
    def test_average_hours_are_weighted_across_groups(self, ctx):
        cursor = MagicMock()
        ctx.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = [
            ("A", "A", "COMPLETED", 2, 2, 2, 2 * 3600 * 10, 2, 2 * 3600 * 4, 2),
            ("B", "B", "PENDING_APPROVAL", 1, 1, 0, None, 0, None, 0),
        ]
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        report = get_request_metrics_report(
            _actor("REQUESTER"),
            {
                "created_from": (now - timedelta(days=30)).isoformat(),
                "created_to": now.isoformat(),
            },
        )["report"]
        self.assertEqual(report["avg_completion_hours"], 10.0)
        self.assertEqual(report["avg_approval_hours"], 4.0)


class InsightRoutesTests(SimpleTestCase):
    @patch("api_core.authn.service.load_actor_from_session")
    def test_route_preview_requires_requester_role(self, load_actor):
        load_actor.return_value = _actor("APPROVER")
        response = self.client.post(
            "/api/v1/requests/route-preview",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    @patch("api_core.authn.service.load_actor_from_session")
    def test_ai_assessment_rejects_unsupported_method(self, load_actor):
        load_actor.return_value = _actor("APPROVER")
        response = self.client.delete(f"/api/v1/requests/{uuid4()}/ai-assessments")
        self.assertEqual(response.status_code, 405)

    def test_new_routes_require_authentication(self):
        for path in ("/api/v1/reports/team", "/api/v1/meta/org-chart"):
            self.assertEqual(self.client.get(path).status_code, 401, path)


class AdministrativeIdentityExclusionTests(_DbPatchedTestCase):
    """Admins are system-only: they can never be routed or reassigned business work."""

    def test_target_validation_excludes_administrative_grants(self):
        from api_core.workflow.service import _is_actor_valid_for_role

        cursor = MagicMock()
        cursor.fetchone.return_value = (False,)
        valid = _is_actor_valid_for_role(
            cursor,
            actor_id=str(uuid4()),
            role="APPROVER",
            department_id=str(uuid4()),
            type_id=str(uuid4()),
        )
        self.assertFalse(valid)
        sql = cursor.execute.call_args.args[0]
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("'OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR'", sql)

    def test_submit_routing_rejects_administrative_actor(self):
        from api_core.workflow.service import _resolve_and_verify_route_actors

        actor = _actor("REQUESTER")
        manager = str(uuid4())
        cursor = MagicMock()
        # The active, non-administrative count misses the routed manager.
        cursor.fetchone.return_value = (0,)
        rules = {
            "schema_version": 1,
            "rules": [{"id": "D", "default": True, "approvers": ["DIRECT_MANAGER"]}],
            "executor": None,
            "acceptor": None,
        }
        bindings = {"schema_version": 1, "departments": {actor.department_id: {}}}
        with self.assertRaises(CommandError) as raised:
            _resolve_and_verify_route_actors(
                cursor, rules, bindings, actor, manager, str(uuid4()), {}, None
            )
        self.assertEqual(raised.exception.code, "ROUTE_ACTOR_INACTIVE")
        self.assertIn(
            "'OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR'", cursor.execute.call_args.args[0]
        )

    def test_submit_route_checks_all_approver_grants_in_one_batch(self):
        from api_core.workflow.service import _resolve_and_verify_route_actors

        actor = _actor("REQUESTER")
        manager = str(uuid4())
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)  # one active non-admin assignee
        cursor.fetchall.return_value = [(manager, "APPROVER")]
        rules = {
            "schema_version": 1,
            "rules": [{"id": "D", "default": True, "approvers": ["DIRECT_MANAGER"]}],
            "executor": None,
            "acceptor": None,
        }
        bindings = {"schema_version": 1, "departments": {actor.department_id: {}}}
        decision = _resolve_and_verify_route_actors(
            cursor, rules, bindings, actor, manager, str(uuid4()), {}, None
        )
        self.assertEqual(decision.approver_ids, (manager,))
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn(
            "SELECT DISTINCT rm.user_id::text", cursor.execute.call_args.args[0]
        )

    def test_submit_route_rejects_out_of_scope_batch_grant(self):
        from api_core.workflow.service import _resolve_and_verify_route_actors

        actor = _actor("REQUESTER")
        manager = str(uuid4())
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.fetchall.return_value = []  # no matching grant in this department/type
        rules = {
            "schema_version": 1,
            "rules": [{"id": "D", "default": True, "approvers": ["DIRECT_MANAGER"]}],
            "executor": None,
            "acceptor": None,
        }
        bindings = {"schema_version": 1, "departments": {actor.department_id: {}}}
        with self.assertRaises(CommandError) as raised:
            _resolve_and_verify_route_actors(
                cursor, rules, bindings, actor, manager, str(uuid4()), {}, None
            )
        self.assertEqual(raised.exception.code, "FORBIDDEN")
        self.assertEqual(raised.exception.status, 403)

    def test_preview_marks_administrative_actor_unauthorized(self):
        actor = _actor("REQUESTER")
        manager = str(uuid4())
        patcher, cursor = _cursor_ctx("api_core.workflow.insights.connection.cursor")
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = (
            "type-1",
            "A",
            "release-1",
            {
                "schema_version": 1,
                "rules": [
                    {"id": "D", "default": True, "approvers": ["DIRECT_MANAGER"]}
                ],
                "executor": None,
                "acceptor": None,
            },
            {"schema_version": 1, "departments": {actor.department_id: {}}},
            {"approval_hours": 24},
            manager,
        )
        cursor.fetchall.return_value = [(manager, "Giám đốc", True, ["APPROVER"], True)]
        preview = insights.preview_route(actor, {"type_code": "LEAVE"})
        self.assertFalse(preview["steps"][0]["authorized"])
        self.assertEqual(preview["problem"], "ROUTE_ACTOR_INACTIVE")

    @patch("api_core.workflow.views.run_ai_assessment")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_auditor_cannot_write_ai_assessment_but_can_read(self, load_actor, run):
        load_actor.return_value = _actor("AUDITOR", "APPROVER")
        request_id = uuid4()
        response = self.client.post(
            f"/api/v1/requests/{request_id}/ai-assessments",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        run.assert_not_called()
        with patch(
            "api_core.workflow.views.list_ai_assessments", return_value={"items": []}
        ):
            response = self.client.get(f"/api/v1/requests/{request_id}/ai-assessments")
        self.assertEqual(response.status_code, 200)


class AdminOverviewAndDiagnosticsTests(_DbPatchedTestCase):
    PERIOD = "created_from=2026-01-01T00:00:00%2B07:00&created_to=2026-02-01T00:00:00%2B07:00"

    @patch("api_core.authn.service.load_actor_from_session")
    def test_overview_rejects_unknown_status_before_querying(self, load_actor):
        load_actor.return_value = _actor("OPS_ADMIN")
        response = self.client.get(
            f"/api/v1/admin/overview?{self.PERIOD}&status=HACKED"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATUS")

    @patch("api_core.authn.service.load_actor_from_session")
    def test_diagnostics_requires_ops_admin(self, load_actor):
        load_actor.return_value = _actor("REQUESTER")
        self.assertEqual(self.client.get("/api/v1/admin/diagnostics").status_code, 403)

    @patch("api_core.administration.overview.authorize")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_overview_groups_departments_and_users(self, load_actor, _authorize):
        load_actor.return_value = _actor("OPS_ADMIN")
        patcher, cursor = _cursor_ctx(
            "api_core.administration.overview.connection.cursor"
        )
        self.addCleanup(patcher.stop)
        cursor.fetchall.return_value = [
            ("LEAVE", "Nghỉ phép", "COMPLETED", "d1", "Kế toán", 3, 0, 40, 42),
            ("LEAVE", "Nghỉ phép", "PENDING_APPROVAL", "d1", "Kế toán", 2, 1, 40, 42),
            ("ACCESS", "Quyền", "PENDING_APPROVAL", "d2", "CNTT", 1, 1, 40, 42),
        ]
        with patch("api_core.administration.overview.transaction.atomic"):
            response = self.client.get(f"/api/v1/admin/overview?{self.PERIOD}")
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["total"], 6)
        self.assertEqual(body["overdue"], 2)
        self.assertEqual(body["users"], {"active": 40, "total": 42})
        first = body["by_department"][0]
        self.assertEqual(
            (
                first["department_name"],
                first["total"],
                first["completed"],
                first["pending"],
            ),
            ("Kế toán", 5, 3, 2),
        )

    @patch("api_core.administration.overview.authorize")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_diagnostics_reports_backlog_honestly(self, load_actor, _authorize):
        load_actor.return_value = _actor("OPS_ADMIN")
        patcher, cursor = _cursor_ctx(
            "api_core.administration.overview.connection.cursor"
        )
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = (
            {"PENDING": 3, "DEAD": 1},
            900.0,
            None,
            [{"id": "e1"}],
            5,
            2,
            {"BREACH": 1},
        )

        async def unreachable():
            return False

        with (
            patch("api_core.administration.overview.transaction.atomic"),
            patch(
                "api_core.integrations.ai_service.ai_client.health_check",
                side_effect=unreachable,
            ),
        ):
            body = self.client.get("/api/v1/admin/diagnostics").json()
        self.assertFalse(body["worker"]["backlog_ok"])
        self.assertEqual(body["outbox"]["oldest_pending_seconds"], 900)
        self.assertFalse(body["ai_service"]["healthy"])
        self.assertEqual(body["sla"]["overdue_stages"], 2)

    def test_list_and_ops_search_match_title_within_scope(self):
        import inspect

        from api_core.workflow import ops_service, views

        for source in (
            inspect.getsource(views.request_list),
            inspect.getsource(ops_service.list_ops_metadata),
        ):
            self.assertIn("payload->>'title'", source)
