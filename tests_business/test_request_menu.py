"""No DB connection or Django dependency required. Static contract regression tests."""
import json
import unittest
from pathlib import Path
from api_core.domain.plan_constraints import plan_business_errors

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT/'api_core/catalog/approval_menu.json').read_text(encoding='utf-8'))

class MenuTests(unittest.TestCase):
    def test_exact_business_rows_and_deduplicated_codes(self):
        self.assertEqual(len(DATA['options']), 20)
        self.assertEqual(len(DATA['types']), 18)
        self.assertEqual(len({x['code'] for x in DATA['types']}), 18)
        self.assertEqual(len({x['group'] for x in DATA['options']}), 4)

    def test_templates_and_schemas_match_menu(self):
        forms = {x['code']: x for x in DATA['types']}
        for choice in DATA['options']:
            with self.subTest(choice=choice['label']):
                self.assertEqual(forms[choice['code']]['lifecycle'], choice['lifecycle'])
                self.assertIn(choice['lifecycle'], {'A','B','C'})
        for form in forms.values():
            schema=form['form_schema']
            self.assertEqual(schema['schema_version'],1)
            self.assertFalse(schema['additionalProperties'])
            self.assertTrue(set(schema['required']).issubset(schema['properties']))
            self.assertIn('title',schema['required'])

    def test_no_duplicate_laptop_or_long_leave_codes(self):
        counts = {c:sum(x['code']==c for x in DATA['options']) for c in ('LAPTOP_PROVISION','LEAVE_LONG')}
        self.assertEqual(counts, {'LAPTOP_PROVISION':2,'LEAVE_LONG':2})

    def test_leave_short_and_long(self):
        self.assertIn('end_date',plan_business_errors('LEAVE_ANNUAL',{'start_date':'2026-11-01','end_date':'2026-11-03'}))
        self.assertNotIn('end_date',plan_business_errors('LEAVE_ANNUAL',{'start_date':'2026-11-01','end_date':'2026-11-02'}))
        self.assertIn('end_date',plan_business_errors('LEAVE_LONG',{'start_date':'2026-11-01','end_date':'2026-11-02'}))

    def test_room_and_warehouse_rules(self):
        self.assertIn('end_time',plan_business_errors('ROOM_STUDIO',{'start_time':'17:00','end_time':'16:00'}))
        self.assertIn('destination_warehouse',plan_business_errors('WAREHOUSE_TRANSFER',{'source_warehouse':'Kho A','destination_warehouse':'kho a'}))

    def test_submission_cannot_assign_an_arbitrary_role(self):
        text=(ROOT/'api_core/workflow/service.py').read_text(encoding='utf-8')
        self.assertIn('decision = resolve_route(',text)
        self.assertIn('role="APPROVER"',text)
        self.assertIn('role="EXECUTOR"',text)
        self.assertIn('role="ACCEPTOR"',text)
        self.assertIn('RETURNING code',text)
        self.assertIn('ROUTE_CONFIGURATION_INVALID',text)

    def test_ui_has_no_manual_request_code(self):
        text=(ROOT/'web_client/src/components/RequestEditor.jsx').read_text(encoding='utf-8')
        self.assertNotIn('name="request_code"',text)
        self.assertIn('record?.code',text)
        self.assertIn('RequestTypeMenu',text)

if __name__ == '__main__': unittest.main()
