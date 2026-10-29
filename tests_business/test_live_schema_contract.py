"""Regression checks for the user-provided live schema snapshot (offline)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT/'database/schema_live_export_20261026_REFERENCE_ONLY.sql').read_text(encoding='utf-8')

class LiveSchemaContract(unittest.TestCase):
    def test_request_type_columns(self):
        ddl = SCHEMA.split('CREATE TABLE eas.request_type (', 1)[1].split('\n);', 1)[0]
        for field in ('name','description','category'):
            self.assertRegex(ddl, r'(?m)^  '+field+r'\s+character varying NOT NULL')
        self.assertNotRegex(ddl,r'(?m)^  created_at\s+')

    def test_admin_insert_requires_metadata(self):
        src=(ROOT/'api_core/administration/service.py').read_text(encoding='utf-8')
        self.assertIn('"code", "lifecycle", "name", "description", "category", "is_active"',src)
        self.assertIn('TYPE_RELEASE_REQUIRED',src)
        self.assertIn('REQUEST_TYPE_CATEGORIES',src)

    def test_policy_no_unknown_updated_at(self):
        src=(ROOT/'api_core/workflow/config_service.py').read_text(encoding='utf-8')
        self.assertNotIn('updated_at = statement_timestamp()',src)

    def test_plan_seed_inserts_metadata(self):
        for name in ('02_plan_18_type_registration_DBA_REVIEW_ONLY.sql','03_business_menu_registration_DBA_REVIEW_ONLY.sql'):
            source=(ROOT/'database/report_migrations'/name).read_text(encoding='utf-8')
            self.assertEqual(source.count('INSERT INTO eas.request_type('),18)
            for line in source.splitlines():
                if line.startswith('INSERT INTO eas.request_type('):
                    self.assertIn('name,description,category',line)
                    self.assertIn(',false,',line)

    def test_frontend_metadata_controls(self):
        source=(ROOT/'web_client/src/components/IdentityAdmin.jsx').read_text(encoding='utf-8')
        for name in ('name="name"','name="description"','name="category"'):
            self.assertIn(name,source)

    def test_code_generation_is_server_side(self):
        source=(ROOT/'api_core/workflow/service.py').read_text(encoding='utf-8')
        self.assertIn('RETURNING code',source)
        ddl=SCHEMA.split('CREATE TABLE eas.request (',1)[1].split('\n);',1)[0]
        self.assertIn('DEFAULT eas.next_request_code()',ddl)

if __name__ == '__main__':unittest.main()
