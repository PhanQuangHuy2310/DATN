from __future__ import annotations

import unittest
from uuid import uuid4

from api_core.catalog.plan_catalog import (
    enterprise_catalog,
    enterprise_item,
    enterprise_items,
    enterprise_options,
    five_level_framework,
    resolve_five_level_metadata,
)
from api_core.domain import resolve_route, validate_config_release_payload
from api_core.domain.plan_constraints import plan_business_errors
from api_core.workflow.policy_helpers import initial_policy_draft


class EnterpriseFiveLevelCatalogTests(unittest.TestCase):
    def test_twelve_enterprise_types_span_all_five_levels(self):
        items = enterprise_items()
        options = enterprise_options()
        self.assertEqual(len(items), 12)
        self.assertEqual(len(options), 12)

        risk_levels_seen = {item["risk_weight"] for item in items}
        approval_levels_seen = {item["approval_level"] for item in items}
        self.assertEqual(risk_levels_seen, {1, 2, 3, 4, 5})
        self.assertEqual(approval_levels_seen, {1, 2, 3, 4, 5})

        for item in items:
            self.assertEqual(len(item["approver_resolvers"]), item["approval_level"])
            draft = initial_policy_draft(item["code"], item["lifecycle"])
            self.assertEqual(draft["source"], "ENTERPRISE_5LEVEL_DRAFT")
            errs = validate_config_release_payload(
                lifecycle=item["lifecycle"],
                form_schema=draft["form_schema"],
                route_rules=draft["route_rules"],
                actor_bindings=draft["actor_bindings"],
                sla_profile=draft["sla_profile"],
            )
            self.assertEqual(errs, [], f"Validation failed for {item['code']}: {errs}")

    def test_five_level_framework_and_53_type_matrix(self):
        fw = five_level_framework()
        self.assertEqual(len(fw["risk_levels"]), 5)
        self.assertEqual(len(fw["approval_levels"]), 5)

        matrix = enterprise_catalog()["type_level_matrix"]
        self.assertEqual(len(matrix), 53)
        for code, meta in matrix.items():
            rw, al = resolve_five_level_metadata(code)
            self.assertTrue(1 <= rw <= 5, f"Invalid risk_weight for {code}")
            self.assertTrue(1 <= al <= 5, f"Invalid approval_level for {code}")
            self.assertEqual((rw, al), (meta["risk_weight"], meta["approval_level"]))

    def test_four_and_five_level_route_resolution(self):
        dept = str(uuid4())
        requester = str(uuid4())
        manager = str(uuid4())
        bindings = {
            "schema_version": 1,
            "departments": {
                dept: {
                    "PROJECT_MANAGER": str(uuid4()),
                    "OPERATIONS_MANAGER": str(uuid4()),
                    "FINANCE": str(uuid4()),
                    "DIRECTOR": str(uuid4()),
                    "IT_MANAGER": str(uuid4()),
                    "SECURITY": str(uuid4()),
                    "CISO": str(uuid4()),
                    "CTO": str(uuid4()),
                    "HR_MANAGER": str(uuid4()),
                    "EXECUTOR_FINANCE": str(uuid4()),
                    "EXECUTOR_TECH": str(uuid4()),
                    "EXECUTOR_HR": str(uuid4()),
                }
            },
        }
        for code, expected_levels in [
            ("RECRUITMENT_REQ", 4),
            ("BUDGET_REALLOCATION", 5),
            ("SECURITY_INCIDENT_HOTFIX", 5),
        ]:
            item = enterprise_item(code)
            draft = initial_policy_draft(code, item["lifecycle"])
            decision = resolve_route(
                route_rules=draft["route_rules"],
                actor_bindings=bindings,
                department_id=dept,
                requester_id=requester,
                manager_id=manager,
                payload={"title": "Test 5-level routing"},
            )
            self.assertEqual(len(decision.approver_ids), expected_levels)
            self.assertEqual(
                [step["step_no"] for step in decision.resolved_route],
                list(range(1, expected_levels + 1)),
            )

    def test_enterprise_cross_field_constraints(self):
        errs = plan_business_errors(
            "BUDGET_REALLOCATION",
            {"source_budget_code": "FIN-Q4", "target_budget_code": "fin-q4"},
        )
        self.assertIn("SOURCE_AND_TARGET_BUDGET_MUST_DIFFER", errs.get("target_budget_code", []))

        errs2 = plan_business_errors(
            "SPECIAL_DISCOUNT",
            {"deal_value_vnd": 100_000_000, "amount_vnd": 120_000_000},
        )
        self.assertIn("DISCOUNT_EXCEEDS_DEAL_VALUE", errs2.get("amount_vnd", []))


if __name__ == "__main__":
    unittest.main()

