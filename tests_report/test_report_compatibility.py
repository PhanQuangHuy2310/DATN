import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def module_from_file(name,relative):
    spec=importlib.util.spec_from_file_location(name, ROOT/relative)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

class ReportCompatibilityTests(unittest.TestCase):
    def test_report_use_cases_are_exactly_from_table(self):
        matrix=json.loads((ROOT/'docs/REPORT_V1_SOURCE_MATRIX.json').read_text(encoding='utf8'))
        codes=[row['code'] for row in matrix['use_cases']]
        self.assertEqual(len(codes),16)
        self.assertEqual(codes[-1],'UC17')
        self.assertNotIn('UC16',codes)
        self.assertEqual(len(matrix['rbac']),9)
        self.assertEqual(len(matrix['business_rules']),7)

    def test_expansion_is_schema_driven_and_rejects_unknown_fields(self):
        from api_core.domain import validation as val  # load as a package so relative imports resolve
        schema={'schema_version':1,'type':'object','additionalProperties':False,
          'properties':{'title':{'type':'string','minLength':5,'maxLength':120},
                        'cost':{'type':'integer','minimum':0,'maximum':500000000}},
          'required':['title','cost']}
        result=val.validate_payload(type_code='TRAVEL_EXPENSE',payload={'title':'Chi phí công tác','cost':1200000},form_schema=schema,requester_id='00000000-0000-4000-8000-000000000001')
        self.assertEqual(result['cost'],1200000)
        with self.assertRaises(val.PayloadValidationError):
            val.validate_payload(type_code='TRAVEL_EXPENSE',payload={'title':'Xin thanh toán','cost':9,'is_admin':True},form_schema=schema,requester_id='00000000-0000-4000-8000-000000000001')
        with self.assertRaises(val.PayloadValidationError):
            val.validate_payload(type_code='trick;DROP_TABLE',payload={},form_schema=schema,requester_id='00000000-0000-4000-8000-000000000001')

    def test_db_migration_is_opt_in(self):
        settings=(ROOT/'api_core/config/settings.py').read_text(encoding='utf8')
        self.assertIn('EAS_ALLOW_REPORT_CATALOG_EXPANSION',settings)
        self.assertIn('"false"',settings)
        migration=(ROOT/'database/report_migrations/01_request_catalog_expansion_REVIEW_BEFORE_RUN.sql').read_text(encoding='utf8')
        self.assertIn('DROP CONSTRAINT type_p0',migration)

    def test_catalog_requires_scope_and_published_release(self):
        source=(ROOT/'api_core/catalog/views.py').read_text(encoding='utf8')
        self.assertIn('@require_actor("REQUESTER")',source)
        self.assertIn("cr.state='PUBLISHED'",source)
        self.assertIn("m.revoked_at IS NULL",source)
        self.assertIn("m.type_scope='ONE'",source)

if __name__=='__main__':unittest.main()
