"""Regression tests for thesis-alignment decisions (A4/R07, A6, B1/B2, B3, C3)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.domain import resolve_route
from api_core.domain.delegation import apply_delegations
from api_core.domain.routing import RoutingError, SodEscalationError
from api_core.domain.thesis_mapping import (
    ACCEPTANCE_OUTCOME_TO_THESIS,
    REQUEST_STATUS_TO_THESIS,
    thesis_acceptance_outcome,
    thesis_status,
)
from api_core.worker import (
    SQL_DUE_SLA_STAGES,
    _recipients,
    classify_sla_alert,
    reminder_fraction,
    sla_stage_params,
)
from api_core.workflow import insights
from api_core.workflow.service import (
    SQL_ACTIVE_DELEGATIONS,
    SQL_MANAGER_CHAIN,
    CommandError,
    _resolve_and_verify_route_actors,
)

SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "EAS_Supabase_SQL"
    / "00_eas_supabase_schema.sql"
)


def _id() -> str:
    return str(uuid4())


def _actor(*roles: str) -> Actor:
    return Actor(
        id=_id(),
        email="person@eas.com",
        display_name="Person",
        department_id=_id(),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


class SodEscalationRoutingTests(SimpleTestCase):
    """Thesis Table 2.6 R07: requester never approves; escalate upward."""

    def setUp(self):
        self.department = _id()
        self.requester = _id()
        self.manager = _id()
        self.director = _id()
        self.ceo = _id()
        self.executor = _id()
        self.rules = {
            "schema_version": 1,
            "rules": [
                {
                    "id": "MID",
                    "priority": 10,
                    "when": {"amount_gte": 10_000_000},
                    "approvers": ["DIRECT_MANAGER", "FINANCE"],
                },
                {"id": "LOW", "default": True, "approvers": ["FINANCE"]},
            ],
            "executor": "EXECUTOR_ASSET",
            "acceptor": "REQUESTER",
        }
        # The requester is the department's FINANCE approver.
        self.bindings = {
            "schema_version": 1,
            "departments": {
                self.department: {
                    "FINANCE": self.requester,
                    "EXECUTOR_ASSET": self.executor,
                }
            },
        }

    def resolve(self, amount, chain=None, eligible=None):
        return resolve_route(
            route_rules=self.rules,
            actor_bindings=self.bindings,
            department_id=self.department,
            requester_id=self.requester,
            manager_id=self.manager,
            amount_vnd=amount,
            manager_chain=chain,
            is_eligible=eligible,
        )

    def test_without_chain_self_approval_is_still_rejected(self):
        with self.assertRaisesRegex(RoutingError, "approve own"):
            self.resolve(1)

    def test_escalates_to_direct_superior(self):
        decision = self.resolve(1, chain=[self.manager, self.director])
        self.assertEqual(decision.approver_ids, (self.manager,))
        (escalation,) = decision.escalations
        self.assertEqual(escalation["rule"], "R07")
        self.assertEqual(escalation["step_no"], 1)
        self.assertEqual(escalation["slot"], "FINANCE")
        self.assertEqual(escalation["original_assignee_id"], self.requester)
        self.assertEqual(escalation["chain_depth"], 1)
        self.assertEqual(
            decision.resolved_route[0]["escalation"],
            {"rule": "R07", "chain_depth": 1},
        )

    def test_skips_superior_already_on_route(self):
        decision = self.resolve(10_000_000, chain=[self.manager, self.director])
        self.assertEqual(decision.approver_ids, (self.manager, self.director))
        escalation = decision.escalations[0]
        self.assertEqual(escalation["step_no"], 2)
        self.assertEqual(escalation["chain_depth"], 2)
        self.assertEqual(
            escalation["skipped"],
            [{"user_id": self.manager, "reason": "ALREADY_ON_ROUTE"}],
        )

    def test_skips_ineligible_and_executor_candidates(self):
        chain = [self.executor, self.manager, self.director]
        decision = self.resolve(
            1, chain=chain, eligible=lambda user: user != self.manager
        )
        self.assertEqual(decision.approver_ids, (self.director,))
        self.assertEqual(
            [s["reason"] for s in decision.escalations[0]["skipped"]],
            ["IS_EXECUTOR", "NOT_ELIGIBLE"],
        )

    def test_unresolvable_escalation_never_picks_an_arbitrary_approver(self):
        with self.assertRaises(SodEscalationError):
            self.resolve(1, chain=[])
        with self.assertRaises(SodEscalationError):
            self.resolve(1, chain=[self.manager], eligible=lambda _user: False)

    def test_normal_route_is_unchanged_when_chain_given(self):
        self.bindings["departments"][self.department]["FINANCE"] = self.ceo
        decision = self.resolve(10_000_000, chain=[self.manager, self.director])
        self.assertEqual(decision.approver_ids, (self.manager, self.ceo))
        self.assertEqual(decision.escalations, ())
        self.assertNotIn("escalation", decision.resolved_route[0])

    def test_executor_self_execution_is_not_escalated(self):
        self.bindings["departments"][self.department]["FINANCE"] = self.ceo
        self.bindings["departments"][self.department]["EXECUTOR_ASSET"] = self.requester
        with self.assertRaisesRegex(RoutingError, "execute own"):
            self.resolve(1, chain=[self.manager])


class SubmitRoutingWiringTests(SimpleTestCase):
    RULES: ClassVar[dict] = {
        "schema_version": 1,
        "rules": [{"id": "D", "default": True, "approvers": ["FINANCE"]}],
        "executor": None,
        "acceptor": None,
    }

    def test_manager_chain_sql_is_bounded_and_cycle_safe(self):
        self.assertIn("WITH RECURSIVE", SQL_MANAGER_CHAIN)
        self.assertIn("c.depth < 10", SQL_MANAGER_CHAIN)
        self.assertIn("NOT m.manager_id = ANY", SQL_MANAGER_CHAIN)

    def test_unresolved_escalation_maps_to_dedicated_conflict(self):
        actor = _actor("REQUESTER")
        bindings = {
            "schema_version": 1,
            "departments": {actor.department_id: {"FINANCE": actor.id}},
        }
        cursor = MagicMock()
        cursor.fetchall.return_value = []  # no superiors
        with self.assertRaises(CommandError) as raised:
            _resolve_and_verify_route_actors(
                cursor, self.RULES, bindings, actor, None, _id(), {}, None
            )
        self.assertEqual(raised.exception.code, "ROUTE_SOD_ESCALATION_UNRESOLVED")
        self.assertEqual(raised.exception.status, 409)

    def test_escalation_candidate_must_pass_approver_grant_check(self):
        actor = _actor("REQUESTER")
        superior = _id()
        bindings = {
            "schema_version": 1,
            "departments": {actor.department_id: {"FINANCE": actor.id}},
        }
        cursor = MagicMock()
        cursor.fetchall.return_value = [(superior,)]
        # Eligibility query (non-admin APPROVER grant) answers False.
        cursor.fetchone.return_value = (False,)
        with self.assertRaises(CommandError) as raised:
            _resolve_and_verify_route_actors(
                cursor, self.RULES, bindings, actor, None, _id(), {}, None
            )
        self.assertEqual(raised.exception.code, "ROUTE_SOD_ESCALATION_UNRESOLVED")
        eligibility_sql = cursor.execute.call_args_list[1].args[0]
        self.assertIn("rm.role = %s", eligibility_sql)
        self.assertIn("'OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR'", eligibility_sql)
        self.assertEqual(cursor.execute.call_args_list[1].args[1][1], "APPROVER")

    def test_delegation_lookup_is_skipped_while_disabled(self):
        actor = _actor("REQUESTER")
        manager = _id()
        rules = {
            "schema_version": 1,
            "rules": [{"id": "D", "default": True, "approvers": ["DIRECT_MANAGER"]}],
            "executor": None,
            "acceptor": None,
        }
        bindings = {"schema_version": 1, "departments": {actor.department_id: {}}}
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.fetchone.side_effect = [(1,), (True,)]
        with patch.dict(os.environ, {"EAS_APPROVAL_DELEGATION": ""}):
            decision = _resolve_and_verify_route_actors(
                cursor, rules, bindings, actor, manager, _id(), {}, None
            )
        self.assertEqual(decision.approver_ids, (manager,))
        executed = " ".join(c.args[0] for c in cursor.execute.call_args_list)
        self.assertNotIn("approval_delegation", executed)


class DelegationTests(SimpleTestCase):
    def setUp(self):
        self.requester = _id()
        self.manager = _id()
        self.deputy = _id()
        self.finance = _id()
        dept = _id()
        self.decision = resolve_route(
            route_rules={
                "schema_version": 1,
                "rules": [
                    {
                        "id": "D",
                        "default": True,
                        "approvers": ["DIRECT_MANAGER", "FINANCE"],
                    }
                ],
                "executor": None,
                "acceptor": None,
            },
            actor_bindings={
                "schema_version": 1,
                "departments": {dept: {"FINANCE": self.finance}},
            },
            department_id=dept,
            requester_id=self.requester,
            manager_id=self.manager,
        )

    def apply(self, delegations, eligible=lambda _u: True):
        return apply_delegations(
            self.decision,
            requester_id=self.requester,
            delegations=delegations,
            is_eligible=eligible,
        )

    def test_active_delegation_reassigns_step_and_is_recorded(self):
        result = self.apply({self.manager: [("dlg-1", self.deputy)]})
        self.assertEqual(result.approver_ids, (self.deputy, self.finance))
        self.assertEqual(
            result.delegations,
            (
                {
                    "step_no": 1,
                    "delegation_id": "dlg-1",
                    "delegator_id": self.manager,
                    "delegate_id": self.deputy,
                },
            ),
        )
        self.assertEqual(
            result.resolved_route[0]["delegation"],
            {"delegation_id": "dlg-1", "delegator_id": self.manager},
        )

    def test_delegate_violating_sod_or_permissions_keeps_original(self):
        for delegate, eligible in (
            (self.requester, lambda _u: True),  # requester cannot approve self
            (self.finance, lambda _u: True),  # already a later approver
            (self.deputy, lambda _u: False),  # lacks APPROVER grant / admin
        ):
            result = self.apply({self.manager: [("dlg", delegate)]}, eligible)
            self.assertIs(result, self.decision)

    def test_first_eligible_delegate_wins_and_delegation_is_not_transitive(self):
        other = _id()
        result = self.apply(
            {
                self.manager: [("a", self.requester), ("b", self.deputy)],
                self.deputy: [("c", other)],
            }
        )
        self.assertEqual(result.approver_ids, (self.deputy, self.finance))
        self.assertEqual(result.delegations[0]["delegation_id"], "b")

    def test_active_delegation_sql_enforces_time_window_and_revocation(self):
        self.assertIn("d.revoked_at IS NULL", SQL_ACTIVE_DELEGATIONS)
        self.assertIn("d.valid_from <= statement_timestamp()", SQL_ACTIVE_DELEGATIONS)
        self.assertIn("d.valid_to > statement_timestamp()", SQL_ACTIVE_DELEGATIONS)


class SlaThesisPolicyTests(SimpleTestCase):
    start = datetime(2026, 10, 9, tzinfo=timezone.utc)
    due = start + timedelta(hours=10)

    def classify(self, hours, **kwargs):
        kwargs.setdefault("breached_at", None)
        return classify_sla_alert(
            started_at=self.start,
            due_at=self.due,
            now=self.start + timedelta(hours=hours),
            **kwargs,
        )

    def test_default_behaviour_is_unchanged(self):
        self.assertIsNone(self.classify(4.9))
        self.assertEqual(self.classify(5), "REMINDER")
        self.assertEqual(self.classify(10), "BREACH")
        self.assertIsNone(self.classify(20, breached_at=self.due))

    def test_release_fraction_moves_reminder_to_80_percent(self):
        self.assertIsNone(self.classify(7.9, fraction=0.8))
        self.assertEqual(self.classify(8, fraction=0.8), "REMINDER")

    def test_l2_only_when_enabled_once_and_after_150_percent(self):
        breached = {"breached_at": self.due, "escalation_levels": True}
        self.assertIsNone(self.classify(14.9, **breached))
        self.assertEqual(self.classify(15, **breached), "ESCALATE")
        self.assertIsNone(self.classify(30, escalated=True, **breached))
        self.assertIsNone(self.classify(30, breached_at=self.due))

    def test_invalid_release_fraction_falls_back_to_contract(self):
        for value in (None, 0, 1, 1.5, -0.2, True, "0.8", float("nan")):
            self.assertEqual(reminder_fraction(value), 0.5)
        self.assertEqual(reminder_fraction(0.8), 0.8)

    def test_stage_query_is_inert_for_l2_while_disabled(self):
        now = self.start
        params = sla_stage_params(now, False, 50)
        self.assertEqual(SQL_DUE_SLA_STAGES.count("%s"), len(params))
        self.assertIs(params[3], False)
        self.assertEqual(params[-1], 50)
        self.assertIn("al.kind='ESCALATE'", SQL_DUE_SLA_STAGES)
        self.assertIn("FOR UPDATE OF s SKIP LOCKED", SQL_DUE_SLA_STAGES)

    def test_breach_adds_head_only_when_levels_enabled(self):
        item = MagicMock(event_type="SLA_BREACH", payload={"stage_id": "s"})
        item.request_id = "r"
        assignee, head = _id(), _id()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(assignee,)]
        with patch.dict(os.environ, {"EAS_SLA_ESCALATION_LEVELS": ""}):
            self.assertEqual([r[0] for r in _recipients(cursor, item)], [assignee])
        cursor.fetchone.side_effect = [(assignee,), (head,), ("REQ-1",)]
        with patch.dict(os.environ, {"EAS_SLA_ESCALATION_LEVELS": "1"}):
            self.assertEqual(
                [r[0] for r in _recipients(cursor, item)], [assignee, head]
            )


class ThesisMappingTests(SimpleTestCase):
    def _check_values(self, table: str, column: str) -> set[str]:
        sql = SCHEMA.read_text(encoding="utf-8")
        block = re.search(rf"CREATE TABLE eas\.{table} \((.*?)\n\);", sql, re.DOTALL)
        match = re.search(rf"{column} varchar\(\d+\)[^\n]*?IN \(([^)]*)\)", block[1])
        return set(re.findall(r"'([A-Z_]+)'", match[1]))

    def test_every_stored_request_status_has_a_thesis_state(self):
        self.assertEqual(
            set(REQUEST_STATUS_TO_THESIS), self._check_values("request", "status")
        )
        self.assertEqual(thesis_status("PENDING_APPROVAL"), "IN_REVIEW")
        self.assertEqual(thesis_status("WAITING_FOR_ACCEPTANCE"), "SUBMITTED_ACCEPT")
        with self.assertRaises(ValueError):
            thesis_status("SUBMITTED")

    def test_acceptance_outcomes_map_to_pass_fail(self):
        self.assertEqual(
            set(ACCEPTANCE_OUTCOME_TO_THESIS),
            self._check_values("acceptance_decision", "outcome"),
        )
        self.assertEqual(thesis_acceptance_outcome("ACCEPT"), "PASS")
        self.assertEqual(thesis_acceptance_outcome("REWORK"), "FAIL")


class AdminSystemOnlyTests(SimpleTestCase):
    """Owner decision A6: admin accounts never create business requests."""

    @patch("api_core.authn.service.load_actor_from_session")
    def test_admin_with_historic_requester_grant_cannot_create_or_submit(
        self, load_actor
    ):
        for admin_role in ("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR"):
            load_actor.return_value = _actor(admin_role, "REQUESTER")
            for path in (
                "/api/v1/requests",
                "/api/v1/requests/route-preview",
                f"/api/v1/requests/{uuid4()}/submit",
            ):
                response = self.client.post(
                    path, data="{}", content_type="application/json"
                )
                self.assertEqual(response.status_code, 403, (admin_role, path))
                self.assertEqual(response.json()["error"]["code"], "ADMIN_PORTAL_ONLY")


class PreviewEscalationTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def test_preview_reports_unresolved_escalation(self):
        actor = _actor("REQUESTER")
        cursor = MagicMock()
        patcher = patch("api_core.workflow.insights.connection.cursor")
        patcher.start().return_value.__enter__.return_value = cursor
        self.addCleanup(patcher.stop)
        cursor.fetchone.return_value = (
            "type-1",
            "A",
            "release-1",
            SubmitRoutingWiringTests.RULES,
            {
                "schema_version": 1,
                "departments": {actor.department_id: {"FINANCE": actor.id}},
            },
            {"approval_hours": 24},
            None,
        )
        cursor.fetchall.return_value = []
        preview = insights.preview_route(actor, {"type_code": "EXPENSE_CLAIM"})
        self.assertFalse(preview["resolvable"])
        self.assertEqual(preview["problem"], "ROUTE_SOD_ESCALATION_UNRESOLVED")
