import unittest

from api_core.health.request_type_readiness import (
    assess_request_types, catalog_readiness_summary,
)
from api_core.health.schema_contract import (
    REQUIRED_EAS_TABLES, has_required_eas_tables,
)

P0 = [("LEAVE", "A", True), ("ACCESS", "B", True), ("EQUIPMENT", "C", True)]


class CatalogReadinessTests(unittest.TestCase):
    def test_32_tables_satisfy_30_mandatory(self):
        self.assertTrue(has_required_eas_tables(
            REQUIRED_EAS_TABLES | {"role", "lifecycle"}))

    def test_missing_required_table_is_not_hidden_by_count(self):
        missing_one = (REQUIRED_EAS_TABLES - {"audit_event"}) | {"role", "lifecycle", "new_table"}
        self.assertFalse(has_required_eas_tables(missing_one))

    def test_exact_user_diagnostic_scenario(self):
        extra_codes = [
            ("ACCESS_FACILITY", "B", False),
            ("BUSINESS_TRIP", "B", False),
            ("EQUIPMENT_BORROW", "C", False),
            ("EXPENSE_CLAIM", "A", False),
            ("IT_SUPPORT", "B", False),
            ("LEAVE_SPECIAL", "A", False),
            ("ROOM_BOOKING", "A", False),
        ]
        rows = P0 + extra_codes
        checks = assess_request_types(rows, require_active_releases=True)
        summary = catalog_readiness_summary(rows)
        self.assertTrue(checks["request_types_match_p0"])
        self.assertTrue(checks["p0_active_types_configured"])
        self.assertFalse(checks["all_active_types_configured"])
        self.assertEqual(summary["active_type_count"], 10)
        self.assertEqual(summary["unconfigured_active_type_count"], 7)

    def test_missing_p0_release_always_fails(self):
        rows = [("LEAVE", "A", False), ("ACCESS", "B", True), ("EQUIPMENT", "C", True)]
        result = assess_request_types(rows, require_active_releases=True)
        self.assertFalse(result["p0_active_types_configured"])

    def test_missing_p0_type_fails_even_when_optional_release_check_off(self):
        result = assess_request_types(P0[:2], require_active_releases=False)
        self.assertFalse(result["request_types_match_p0"])

    def test_no_active_types_never_fully_configured(self):
        result = catalog_readiness_summary([])
        self.assertFalse(result["all_active_types_configured"])

if __name__ == "__main__":
    unittest.main()
