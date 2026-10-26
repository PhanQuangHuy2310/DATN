import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "api_core/catalog/plan_types.json").read_text(encoding="utf-8"))
ITEMS = DATA["items"]

class PlanCatalogTests(unittest.TestCase):
    def test_exact_codes_in_four_source_groups(self):
        expected = {
            "LEAVE_ANNUAL", "LEAVE_LONG", "RESIGNATION", "OVERTIME_REQ", "WFH_REQ", "ROOM_VEHICLE",
            "ADVANCE_SMALL", "ADVANCE_MEDIUM", "ADVANCE_LARGE", "REIMBURSEMENT", "VENDOR_PAYMENT",
            "LAPTOP_PROVISION", "SOFTWARE_ACCESS", "PROD_DATA_ACCESS", "SAAS_LICENSE_BUY",
            "OFFICE_SUPPLIES", "ASSET_PURCHASE", "FACILITY_REPAIR",
        }
        self.assertEqual(DATA["count"], 18)
        self.assertEqual({x["code"] for x in ITEMS}, expected)
        self.assertEqual(len(ITEMS),len(expected))

    def test_source_mapped_form_fields(self):
        for item in ITEMS:
            with self.subTest(item=item["code"]):
                schema=item["form_schema"]
                self.assertEqual(schema["schema_version"],1)
                self.assertEqual(schema["type"],"object")
                self.assertIs(schema["additionalProperties"],False)
                self.assertEqual(schema["required"],["title"]+item["required_fields"])
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
                for field,spec in schema["properties"].items():
                    self.assertIn(spec["type"],("string","integer"))
                    self.assertLessEqual(len(field),48)
                self.assertTrue(re.fullmatch(r"[A-Z][A-Z0-9_]{1,29}",item["code"]))

    def test_nothing_auto_publishes_or_auto_approves(self):
        for item in ITEMS:
            self.assertTrue(item["requires_policy_binding"])
            self.assertFalse(item["ai_auto_approve_enabled"])
            self.assertIn(item["lifecycle"],("A","B","C"))

    def test_human_review_of_conflicting_plan_rules(self):
        d={x["code"]:x for x in ITEMS}
        for code in ("OFFICE_SUPPLIES","ROOM_VEHICLE"):
            self.assertEqual(d[code]["lifecycle"],"B")
            self.assertTrue(any("AUTO_APPROVAL_CONFLICT" in w for w in d[code]["activation_warnings"]))
        self.assertEqual(d["RESIGNATION"]["sla_hours"],168)
        self.assertEqual(d["ASSET_PURCHASE"]["sla_hours"],120)
        self.assertEqual(d["PROD_DATA_ACCESS"]["lifecycle"],"C")

    def test_sql_registration_is_inactive(self):
        text=(ROOT/"database/report_migrations/02_plan_18_type_registration_DBA_REVIEW_ONLY.sql").read_text()
        self.assertEqual(text.count("INSERT INTO eas.request_type"),18)
        self.assertEqual(text.count(",false,"),18)
        self.assertEqual(text.count("ON CONFLICT (code) DO NOTHING"),18)
        self.assertIn("type_p0",text)
        self.assertNotIn("UPDATE eas.request_type SET is_active=true",text)

if __name__ == '__main__':
    unittest.main()
