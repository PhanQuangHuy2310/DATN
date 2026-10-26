import unittest
from api_core.health.schema_contract import (
    REQUIRED_EAS_TABLES, has_required_eas_tables, missing_required_eas_tables,
)


class RequiredSchemaTableTests(unittest.TestCase):
    def test_source_has_thirty_required_tables(self):
        self.assertEqual(len(REQUIRED_EAS_TABLES), 30)

    def test_all_thirty_pass(self):
        self.assertTrue(has_required_eas_tables(REQUIRED_EAS_TABLES))

    def test_extra_lookup_tables_do_not_fail(self):
        schema32 = set(REQUIRED_EAS_TABLES) | {'role', 'lifecycle'}
        self.assertTrue(has_required_eas_tables(schema32))

    def test_missing_required_table_fails_even_if_count_is_thirty(self):
        missing = set(REQUIRED_EAS_TABLES) - {'request_revision'}
        missing |= {'role', 'lifecycle'}
        self.assertFalse(has_required_eas_tables(missing))
        self.assertEqual(missing_required_eas_tables(missing), ['request_revision'])


if __name__ == '__main__':
    unittest.main()
