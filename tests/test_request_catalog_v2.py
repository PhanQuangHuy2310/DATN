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
# 12 groups by nature of the request (docs/PHAN_LOAI_YEU_CAU.md, migration 17).
GROUPS = [
    "ABSENCE",
    "WORKTIME",
    "BORROW",
    "PROVISION",
    "PAYMENT",
    "PROCUREMENT",
    "PEOPLE",
    "SUPPORT",
    "WORK",
    "LEGAL",
    "SALES",
    "ASSET",
]
# Department-based groups written by migration 09 (replaced by migration 17).
LEGACY_GROUPS = [
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
    def test_twelve_groups_58_active_13_new_8_deprecated(self):
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


CATALOG_SQL = (MIGRATIONS / "09_request_catalog_v2.sql").read_text(encoding="utf-8")


def catalog_part(number: int) -> str:
    """Section 'Part N' of the consolidated catalogue migration."""
    start = CATALOG_SQL.index(f"-- ==== Part {number}:")
    nxt = CATALOG_SQL.find(f"-- ==== Part {number + 1}:", start)
    return CATALOG_SQL[start : nxt if nxt != -1 else len(CATALOG_SQL)]


class MigrationConsistencyTests(unittest.TestCase):
    def test_regroup_covers_every_type_and_ten_groups(self):
        part = catalog_part(1)
        # All 66 codes, including the 13 new ones (restores them after a rollback).
        # Migration 09 still writes the legacy department groups.
        for item in CATALOG["items"]:
            active = "true" if item["status"] == "ACTIVE" else "false"
            self.assertRegex(
                part,
                re.escape(f"('{item['code']}', '{item['name']}', '")
                + r"[A-Z]+"
                + re.escape(
                    f"', {item['risk_weight']}, {item['approval_level']}, {active})"
                ),
            )
        constraint = re.search(
            r"ADD CONSTRAINT request_type_category_valid\s+(CHECK.*);", part
        ).group(1)
        self.assertEqual(
            re.findall(r"'([A-Z]+)'::character varying", constraint), LEGACY_GROUPS
        )

    def test_new_types_part_inserts_exactly_the_13_types(self):
        part = catalog_part(2)
        values = part[part.index("(VALUES") : part.index(") AS v(")]
        self.assertEqual(
            set(re.findall(r"^\s+\('([A-Z_]+)'", values, re.MULTILINE)), NEW_CODES
        )
        self.assertIn("'PUBLISHED'", part)

    def test_it_support_part_publishes_it_executor(self):
        part = catalog_part(3)
        self.assertIn('"EXECUTOR_IT"', part)
        self.assertIn("SET active_release_id", part)

    def test_every_migration_has_a_rollback(self):
        for name in sorted(p.stem for p in MIGRATIONS.glob("*.sql")):
            if name < "08":
                continue  # 04-07 were applied before rollbacks were required
            with self.subTest(migration=name):
                self.assertTrue(
                    (MIGRATIONS / "rollback" / f"{name}_rollback.sql").exists()
                )

    def test_consolidated_migrations_are_single_transactions(self):
        for path in [*MIGRATIONS.glob("0[89]_*.sql"), *MIGRATIONS.glob("1*_*.sql")]:
            sql = path.read_text(encoding="utf-8")
            with self.subTest(migration=path.name):
                self.assertEqual(sql.count("\nBEGIN;"), 1)
                self.assertEqual(sql.count("\nCOMMIT;"), 1)
                self.assertEqual(sql.count("security_epoch"), 1)


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
