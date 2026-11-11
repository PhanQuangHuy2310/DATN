"""Regression tests for the 04/11/2026 code/data audit (docs/KIEM_TOAN_CODE_DATA_2026-11-04.md).

S1  request-type configuration needs POLICY_ADMIN, not only a module right.
L1  a takeover conflict on the AI account never surfaces as HTTP 500.
L2  the risk weight in force comes from eas.request_type, not the static JSON.
L3  a requester without a direct manager can still submit.
L4  a slot that resolves to the requester escalates to the requester's manager.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.db import IntegrityError
from django.test import SimpleTestCase

from api_core.administration import workflows
from api_core.domain.routing import TOP_LEVEL_SLOT, RoutingError, resolve_route
from api_core.workflow.auto_approval import try_auto_approve
from api_core.workflow.service import CommandError, _type_risk_weight


def _request(*roles: str, method: str = "PATCH"):
    return SimpleNamespace(method=method, actor=SimpleNamespace(roles=frozenset(roles)))


class RequestTypeConfigurationNeedsPolicyAdminTests(SimpleTestCase):
    """S1: approvers hold `requests_workflows:update` but are not policy admins."""

    @patch("api_core.administration.workflows.can", return_value=True)
    def test_approver_with_module_update_is_forbidden(self, _can):
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            with self.subTest(method=method), self.assertRaises(CommandError) as ctx:
                workflows._require_writer(
                    _request("APPROVER", "REQUESTER", method=method)
                )
            self.assertEqual(ctx.exception.status, 403)

    @patch("api_core.administration.workflows.can", return_value=True)
    def test_policy_admin_with_module_right_may_configure(self, _can):
        workflows._require_writer(_request("POLICY_ADMIN"))

    @patch("api_core.administration.workflows.can", return_value=False)
    def test_policy_admin_without_module_right_is_still_forbidden(self, _can):
        with self.assertRaises(CommandError):
            workflows._require_writer(_request("POLICY_ADMIN"))


class AutoApproveTakeoverConflictTests(SimpleTestCase):
    """L1: UNIQUE(instance_id, assignee_id) on old schemas must not leak a 500."""

    databases: ClassVar[set[str]] = {"default"}

    def test_integrity_error_leaves_step_to_human(self):
        context = {
            "status": "PENDING_APPROVAL",
            "lock_version": 4,
            "risk_weight": 1,
            "type_code": "LEAVE",
            "lifecycle": "A",
            "requester_name": "Staff",
            "department_code": "TECH",
            "step_id": str(uuid4()),
            "assignee_id": str(uuid4()),
            "amount_vnd": None,
            "ai_allowed": True,
        }
        cursor = MagicMock()
        cursor.execute.side_effect = IntegrityError(
            "duplicate key approval_step_instance_id_assignee_id_key"
        )
        with (
            patch(
                "api_core.workflow.auto_approval._load_context", return_value=context
            ),
            patch(
                "api_core.integrations.ai_service.ai_client_sync.evaluate_auto_approve",
                return_value={"decision": "auto_approve", "reason": "ok"},
            ),
            patch("api_core.workflow.auto_approval.transaction.atomic"),
            patch("api_core.workflow.auto_approval.connection.cursor") as cm,
            patch("api_core.workflow.auto_approval.decide_approval") as decide,
        ):
            cm.return_value.__enter__.return_value = cursor
            self.assertIsNone(try_auto_approve(str(uuid4()), "corr"))
        decide.assert_not_called()


class RiskWeightSourceTests(SimpleTestCase):
    """L2: the request-type row wins over catalog_v2.json."""

    def test_database_weight_is_used(self):
        cursor = MagicMock()
        # catalog_v2.json says ATTENDANCE_ADJUSTMENT = 1; the admin set 4.
        cursor.fetchone.return_value = (4, 1)
        self.assertEqual(
            _type_risk_weight(cursor, str(uuid4()), "ATTENDANCE_ADJUSTMENT"), 4
        )

    def test_catalog_is_only_a_fallback(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        self.assertEqual(
            _type_risk_weight(cursor, str(uuid4()), "ATTENDANCE_ADJUSTMENT"), 1
        )

    def test_out_of_range_database_value_falls_back(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (9, 1)
        self.assertEqual(
            _type_risk_weight(cursor, str(uuid4()), "ATTENDANCE_ADJUSTMENT"), 1
        )


class RoutingAdjustmentTests(SimpleTestCase):
    """L3/L4: route repairs keep SoD and are recorded for the audit trail."""

    def setUp(self):
        self.department = str(uuid4())
        self.requester = str(uuid4())
        self.manager = str(uuid4())
        self.finance = str(uuid4())
        self.director = str(uuid4())
        self.bindings = {
            "schema_version": 1,
            "departments": {
                self.department: {"FINANCE": self.finance, "DIRECTOR": self.director}
            },
        }

    def resolve(self, approvers, manager="default"):
        rules = {
            "schema_version": 1,
            "rules": [{"id": "ONLY", "default": True, "approvers": approvers}],
        }
        return resolve_route(
            route_rules=rules,
            actor_bindings=self.bindings,
            department_id=self.department,
            requester_id=self.requester,
            manager_id=self.manager if manager == "default" else manager,
        )

    def reasons(self, decision):
        return [a["reason"] for a in decision.adjustments]

    def test_normal_route_has_no_adjustment(self):
        decision = self.resolve(["DIRECT_MANAGER", "FINANCE"])
        self.assertEqual(decision.approver_ids, (self.manager, self.finance))
        self.assertEqual(decision.adjustments, ())
        self.assertNotIn("adjusted", decision.resolved_route[0])

    def test_finance_head_paying_himself_escalates_to_his_manager(self):
        self.bindings["departments"][self.department]["FINANCE"] = self.requester
        decision = self.resolve(["FINANCE", "DIRECTOR"])
        self.assertEqual(decision.approver_ids, (self.manager, self.director))
        self.assertEqual(self.reasons(decision), ["SOD_ESCALATED"])
        self.assertEqual(decision.resolved_route[0]["adjusted"], "SOD_ESCALATED")
        self.assertNotIn(self.requester, decision.approver_ids)

    def test_escalation_onto_existing_approver_requires_verified_superior(self):
        self.bindings["departments"][self.department]["FINANCE"] = self.requester
        # Duplicating the manager at the FINANCE step must not silently
        # remove a required approval. The workflow service will fetch
        # eligible superiors and retry with a distinct approver.
        with self.assertRaisesRegex(RoutingError, "own request"):
            self.resolve(["DIRECT_MANAGER", "FINANCE", "DIRECTOR"])

    def test_top_level_requester_skips_direct_manager(self):
        decision = self.resolve(["DIRECT_MANAGER", "FINANCE"], manager=None)
        self.assertEqual(decision.approver_ids, (self.finance,))
        self.assertEqual(self.reasons(decision), ["TOP_LEVEL_SKIPPED"])

    def test_top_level_requester_uses_configured_fallback(self):
        chairman = str(uuid4())
        self.bindings["departments"][self.department][TOP_LEVEL_SLOT] = chairman
        decision = self.resolve(["DIRECT_MANAGER"], manager=None)
        self.assertEqual(decision.approver_ids, (chairman,))
        self.assertEqual(decision.resolved_route[0]["adjusted"], "TOP_LEVEL_FALLBACK")

    def test_route_without_any_approver_is_rejected(self):
        with self.assertRaisesRegex(RoutingError, "No approver available"):
            self.resolve(["DIRECT_MANAGER"], manager=None)

    def test_top_level_acceptor_falls_back_to_requester(self):
        rules = {
            "schema_version": 1,
            "rules": [{"id": "ONLY", "default": True, "approvers": ["FINANCE"]}],
            "executor": "EXECUTOR_IT",
            "acceptor": "DIRECT_MANAGER",
        }
        executor = str(uuid4())
        self.bindings["departments"][self.department]["EXECUTOR_IT"] = executor
        decision = resolve_route(
            route_rules=rules,
            actor_bindings=self.bindings,
            department_id=self.department,
            requester_id=self.requester,
            manager_id=None,
        )
        self.assertEqual(decision.acceptor_id, self.requester)
        self.assertNotEqual(decision.acceptor_id, decision.executor_id)

    def test_requester_never_approves_even_without_manager(self):
        self.bindings["departments"][self.department]["FINANCE"] = self.requester
        # The workflow service catches this, looks up verified superiors and
        # answers ROUTE_SOD_ESCALATION_UNRESOLVED when none exists.
        with self.assertRaisesRegex(RoutingError, "own request"):
            self.resolve(["FINANCE"], manager=None)
