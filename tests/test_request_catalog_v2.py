"""Approved 10-group request catalogue (catalog_v2.json) and its migrations."""

import json
import re
import unittest
from pathlib import Path

from api_core.domain import resolve_route, validate_config_release_payload
from api_core.domain.routing import RoutingError

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads(
    (ROOT / "api_core/catalog/catalog_v2.json").read_text(encoding="utf-8")
)
BINDINGS = json.loads(
    (ROOT / "tests/fixtures/department_bindings.json").read_text(encoding="utf-8")
)
MIGRATIONS = ROOT / "database/migrations"
GROUPS = [
    "FINANCE",
    "RESOURCE",
    "FACILITY",
    "WORK",
    "HR",
    "TIME",
    "IT",
    "LEGAL",
    "SALES",
    "ADMIN",
]
NEW_CODES = {
    "PROMOTION_REQ",
    "REWARD_REQ",
    "TASK_REQUEST",
    "VEHICLE_BOOKING",
    "SALARY_ADVANCE",
    "RESOURCE_REVOKE",
    "CROSS_DEPT_SUPPORT",
    "PROJECT_INITIATION",
    "DISCIPLINE_REQ",
    "SALARY_ADJUSTMENT",
    "HR_CERTIFICATE",
    "DOCUMENT_SEAL",
    "POLICY_ISSUANCE",
}
DEPRECATED = {
    "ASSET_PURCHASE",
    "SOFTWARE_ACCESS",
    "ROOM_STUDIO",
    "ROOM_VEHICLE",
    "LEAVE_ANNUAL",
    "LEAVE_LONG",
    "OVERTIME_APPROVAL",
    "FACILITY_MAINTENANCE",
}
ACTIVE = [i for i in CATALOG["items"] if i["status"] == "ACTIVE"]
REQUESTER = "00000000-0000-4000-8000-0000000000ff"
MANAGER = "00000000-0000-4000-8000-0000000000fe"


def bindings_doc():
    return {"schema_version": 1, "departments": BINDINGS["departments"]}


class CatalogShapeTests(unittest.TestCase):
    def test_ten_groups_58_active_13_new_8_deprecated(self):
        self.assertEqual([g["code"] for g in CATALOG["groups"]], GROUPS)
        self.assertEqual(len(ACTIVE), 58)
        self.assertEqual({i["code"] for i in CATALOG["items"] if i["new"]}, NEW_CODES)
        deprecated = {
            i["code"] for i in CATALOG["items"] if i["status"] == "DEPRECATED"
        }
        self.assertEqual(deprecated, DEPRECATED)
        codes = {i["code"] for i in ACTIVE}
        for item in CATALOG["items"]:
            if item["status"] == "DEPRECATED":
                self.assertIn(item["merged_into"], codes)

    def test_every_group_is_used_and_every_type_has_a_valid_group(self):
        used = {i["category"] for i in ACTIVE}
        self.assertEqual(used, set(GROUPS))
        for item in CATALOG["items"]:
            self.assertIn(item["category"], GROUPS, item["code"])

    def test_declared_approval_level_equals_longest_route(self):
        for item in CATALOG["items"]:
            longest = max(len(r["approvers"]) for r in item["route_rules"]["rules"])
            with self.subTest(code=item["code"]):
                self.assertEqual(item["approval_level"], longest)
                self.assertTrue(1 <= item["risk_weight"] <= 5)

    def test_approved_weight_changes(self):
        weights = {i["code"]: i["risk_weight"] for i in ACTIVE}
        self.assertEqual(weights["LAPTOP_PROVISION"], 2)
        self.assertEqual(weights["PURCHASE_REQUEST"], 3)
        self.assertEqual(weights["ATTENDANCE_ADJUSTMENT"], 1)
        self.assertEqual(weights["SALARY_ADJUSTMENT"], 5)
        self.assertEqual(weights["TASK_REQUEST"], 1)

    def test_it_support_is_executed_by_it(self):
        item = next(i for i in ACTIVE if i["code"] == "IT_SUPPORT")
        self.assertEqual(item["route_rules"]["executor"], "EXECUTOR_IT")


class PublishedConfigurationTests(unittest.TestCase):
    """Every active type has a configuration that passes release validation."""

    def test_every_active_type_has_a_publishable_configuration(self):
        for item in ACTIVE:
            with self.subTest(code=item["code"]):
                rules = item["route_rules"]
                self.assertEqual(rules["rules"][-1].get("default"), True)
                sla = item["sla_profile"]
                self.assertIsInstance(sla.get("approval_hours"), int)
                if item["lifecycle"] in ("B", "C"):
                    self.assertTrue(rules.get("executor"))
                if item["lifecycle"] == "C":
                    self.assertTrue(rules.get("acceptor"))
                if item["new"]:
                    errors = validate_config_release_payload(
                        lifecycle=item["lifecycle"],
                        form_schema=item["form_schema"],
                        route_rules=rules,
                        actor_bindings=bindings_doc(),
                        sla_profile=sla,
                    )
                    self.assertEqual(errors, [])

    def test_new_types_resolve_a_route_for_every_department(self):
        for item in (i for i in ACTIVE if i["new"] or i["code"] == "IT_SUPPORT"):
            for dept in BINDINGS["departments"]:
                with self.subTest(code=item["code"], dept=dept):
                    decision = resolve_route(
                        route_rules=item["route_rules"],
                        actor_bindings=bindings_doc(),
                        department_id=dept,
                        requester_id=REQUESTER,
                        manager_id=MANAGER,
                        amount_vnd=50_000_000,
                    )
                    self.assertEqual(len(decision.approver_ids), item["approval_level"])
                    if item["lifecycle"] != "A":
                        self.assertIsNotNone(decision.executor_id)

    def test_every_active_type_resolves_for_every_department(self):
        failures = []
        for item in ACTIVE:
            for dept in BINDINGS["departments"]:
                try:
                    resolve_route(
                        route_rules=item["route_rules"],
                        actor_bindings=bindings_doc(),
                        department_id=dept,
                        requester_id=REQUESTER,
                        manager_id=MANAGER,
                        amount_vnd=1_000_000,
                        payload={"app_code": "CRM"},
                    )
                except RoutingError as exc:
                    failures.append((item["code"], dept, str(exc)))
        self.assertEqual(failures, [])


class MigrationConsistencyTests(unittest.TestCase):
    def test_regroup_migration_covers_existing_types_and_ten_groups(self):
        sql = (MIGRATIONS / "11_request_category_regroup.sql").read_text(
            encoding="utf-8"
        )
        for item in CATALOG["items"]:
            if not item["new"]:
                active = "true" if item["status"] == "ACTIVE" else "false"
                self.assertIn(
                    f"('{item['code']}', '{item['name']}', '{item['category']}', "
                    f"{item['risk_weight']}, {item['approval_level']}, {active})",
                    sql,
                )
        constraint = re.search(
            r"ADD CONSTRAINT request_type_category_valid\s+(CHECK.*);", sql
        ).group(1)
        self.assertEqual(
            re.findall(r"'([A-Z]+)'::character varying", constraint), GROUPS
        )

    def test_new_types_migration_inserts_exactly_the_13_types(self):
        sql = (MIGRATIONS / "12_request_types_new.sql").read_text(encoding="utf-8")
        values = sql[sql.index("(VALUES") : sql.index(") AS v(")]
        self.assertEqual(
            set(re.findall(r"^\s+\('([A-Z_]+)'", values, re.MULTILINE)), NEW_CODES
        )
        self.assertIn("'PUBLISHED'", sql)

    def test_it_support_migration_publishes_it_executor(self):
        sql = (MIGRATIONS / "13_it_support_executor.sql").read_text(encoding="utf-8")
        self.assertIn('"EXECUTOR_IT"', sql)
        self.assertIn("SET active_release_id", sql)

    def test_every_migration_has_a_rollback(self):
        for number in ("08", "09", "10", "11", "12", "13"):
            with self.subTest(migration=number):
                self.assertTrue(
                    list((MIGRATIONS / "rollback").glob(f"{number}_*_rollback.sql"))
                )


class FrontendCatalogSyncTests(unittest.TestCase):
    def test_generated_ui_catalog_matches_json(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "generate_catalog_js", ROOT / "scripts/generate_catalog_js.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        current = (ROOT / "web_client/src/catalogV2.js").read_text(encoding="utf-8")
        self.assertEqual(
            current, module.render(), "Run python scripts/generate_catalog_js.py"
        )


if __name__ == "__main__":
    unittest.main()
