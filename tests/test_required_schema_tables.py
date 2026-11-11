import unittest

from api_core.health.schema_contract import (
    REQUIRED_EAS_TABLES,
    has_required_eas_tables,
    missing_required_eas_tables,
)


class RequiredSchemaTableTests(unittest.TestCase):
    def test_contract_includes_core_required_tables(self):
        core_tables = {
            "app_user",
            "audit_event",
            "request",
            "request_revision",
            "request_type",
        }
        self.assertTrue(core_tables.issubset(REQUIRED_EAS_TABLES))

    def test_complete_required_set_passes(self):
        self.assertTrue(has_required_eas_tables(REQUIRED_EAS_TABLES))

    def test_extra_lookup_tables_do_not_fail(self):
        schema_with_extra_tables = set(REQUIRED_EAS_TABLES) | {"role", "lifecycle"}
        self.assertTrue(has_required_eas_tables(schema_with_extra_tables))

    def test_missing_required_table_fails_even_with_extra_tables(self):
        missing = set(REQUIRED_EAS_TABLES) - {"request_revision"}
        missing |= {"role", "lifecycle"}
        self.assertFalse(has_required_eas_tables(missing))
        self.assertEqual(missing_required_eas_tables(missing), ["request_revision"])


if __name__ == "__main__":
    unittest.main()
