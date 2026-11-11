"""Pure routing regression tests, runnable without a database or Django setup."""

import importlib.util
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROUTING_FILE = Path(__file__).resolve().parents[1] / "api_core/domain/routing.py"
SPEC = importlib.util.spec_from_file_location("eas_standalone_routing", ROUTING_FILE)
routing = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = routing
SPEC.loader.exec_module(routing)


class R07ApprovalEscalationTests(unittest.TestCase):
    def setUp(self):
        self.department, self.requester, self.manager, self.finance, self.director, self.executor = (
            str(uuid4()) for _ in range(6)
        )
        self.bindings = {
            "schema_version": 1,
            "departments": {
                self.department: {
                    "FINANCE": self.finance,
                    "DIRECTOR": self.requester,
                    "EXECUTOR_IT": self.executor,
                }
            },
        }
        self.rules = {
            "schema_version": 1,
            "rules": [
                {
                    "id": "HIGH",
                    "priority": 1,
                    "when": {"amount_gt": 50_000_000},
                    "approvers": ["DIRECT_MANAGER", "FINANCE", "DIRECTOR"],
                },
                {"id": "LOW", "default": True, "approvers": ["DIRECT_MANAGER"]},
            ],
            "executor": "EXECUTOR_IT",
            "acceptor": "REQUESTER",
        }

    def decide(self, **kwargs):
        return routing.resolve_route(
            route_rules=self.rules,
            actor_bindings=self.bindings,
            department_id=self.department,
            requester_id=self.requester,
            manager_id=self.manager,
            amount_vnd=60_000_000,
            **kwargs,
        )

    def test_ordinary_routing_rejects_self_approval_without_verified_superiors(self):
        with self.assertRaisesRegex(routing.RoutingError, "own request"):
            self.decide()

    def test_nearest_available_superior_is_used_and_annotated(self):
        result = self.decide(eligible_superiors=(self.manager, self.finance, self.director))
        self.assertEqual(result.approver_ids, (self.manager, self.finance, self.director))
        self.assertEqual(result.sod_escalations, ((3, self.requester, self.director),))
        self.assertEqual(result.resolved_route[-1]["sod_escalated"], True)
        self.assertEqual(len(set(result.approver_ids)), 3)
        self.assertTrue(all(uid != self.requester for uid in result.approver_ids))

    def test_no_independent_superior_fails_closed(self):
        with self.assertRaisesRegex(
            routing.RoutingError, "ROUTE_SOD_ESCALATION_UNRESOLVED"
        ):
            self.decide(eligible_superiors=(self.manager, self.finance))

    def test_other_route_guardrails_still_apply(self):
        self.bindings["departments"][self.department]["EXECUTOR_IT"] = self.requester
        with self.assertRaisesRegex(routing.RoutingError, "execute own"):
            self.decide(eligible_superiors=(self.director,))


if __name__ == "__main__":
    unittest.main()
