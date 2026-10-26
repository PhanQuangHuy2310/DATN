"""No DB writes: published-policy drafts and actor binding safety cases."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase
from uuid import uuid4

from api_core.workflow.policy_helpers import binding_errors, initial_policy_draft
from api_core.domain.validation import validate_config_release_payload


class PolicyPublicationTests(TestCase):
    def test_all_18_plan_drafts_are_proper_structures(self):
        root = Path(__file__).resolve().parents[1]
        plans = json.loads((root / 'api_core/catalog/plan_types.json').read_text(encoding='utf-8'))['items']
        self.assertEqual(18, len(plans))
        for item in plans:
            with self.subTest(type_code=item['code']):
                data = initial_policy_draft(item['code'], item['lifecycle'])
                self.assertIn(data['source'], ('PLAN_DRAFT','PLAN_FORM_ROUTE_SUGGESTION'))
                self.assertEqual(1, data['form_schema']['schema_version'])
                self.assertIn('title', data['form_schema']['properties'])
                self.assertIn('reason', data['form_schema']['properties']) if item['code'] == 'LEAVE_ANNUAL' else None
                self.assertEqual({}, data['actor_bindings']['departments'])
                self.assertEqual([], validate_config_release_payload(
                    lifecycle=item['lifecycle'], form_schema=data['form_schema'],
                    route_rules=data['route_rules'], actor_bindings=data['actor_bindings'],
                    sla_profile=data['sla_profile']))
                self.assertTrue(binding_errors(data['route_rules'], data['actor_bindings']))

    def test_seven_existing_extra_codes_make_starters_without_fake_person(self):
        for code, lifecycle in [('ACCESS_FACILITY', 'B'), ('BUSINESS_TRIP','B'),
                                ('EQUIPMENT_BORROW','C'),('EXPENSE_CLAIM','A'),
                                ('IT_SUPPORT','B'),('LEAVE_SPECIAL','A'),('ROOM_BOOKING','A')]:
            with self.subTest(code=code):
                data = initial_policy_draft(code,lifecycle)
                self.assertEqual('SAFE_STARTER', data['source'])
                self.assertEqual({}, data['actor_bindings']['departments'])
                self.assertEqual([], validate_config_release_payload(
                    lifecycle=lifecycle, form_schema=data['form_schema'],
                    route_rules=data['route_rules'], actor_bindings=data['actor_bindings'],
                    sla_profile=data['sla_profile']))

    def test_missing_department_rejected(self):
        draft = initial_policy_draft('ACCESS_FACILITY','B')
        self.assertTrue(binding_errors(draft['route_rules'], draft['actor_bindings']))

    def test_executor_missing_or_invalid_rejected(self):
        draft = initial_policy_draft('IT_SUPPORT','B')
        dept = str(uuid4())
        draft['actor_bindings']['departments'][dept] = {}
        self.assertIn('EXECUTOR_ADMIN', ' '.join(binding_errors(draft['route_rules'],draft['actor_bindings'])))
        draft['actor_bindings']['departments'][dept] = {'EXECUTOR_ADMIN':'not-a-uuid'}
        self.assertTrue(binding_errors(draft['route_rules'],draft['actor_bindings']))
        draft['actor_bindings']['departments'][dept] = {'EXECUTOR_ADMIN':str(uuid4())}
        self.assertEqual([], binding_errors(draft['route_rules'],draft['actor_bindings']))

    def test_three_level_route_rejects_missing_roles(self):
        doc = {'schema_version':1, 'rules':[{'id':'p','default':True,'approvers':['DIRECT_MANAGER','FINANCE','DIRECTOR']}],
               'executor':'EXECUTOR_PROCUREMENT', 'acceptor':'REQUESTER'}
        dept = str(uuid4())
        values = {'schema_version':1,'departments':{dept:{'FINANCE':str(uuid4())}}}
        errs = binding_errors(doc,values)
        self.assertIn('DIRECTOR', str(errs))
        self.assertIn('EXECUTOR_PROCUREMENT', str(errs))
        values['departments'][dept].update({'DIRECTOR':str(uuid4()),'EXECUTOR_PROCUREMENT':str(uuid4())})
        self.assertEqual([], binding_errors(doc,values))

    def test_binding_helper_is_non_mutating(self):
        input_data = {'schema_version':1, 'departments':{str(uuid4()):{}}}
        before = json.dumps(input_data,sort_keys=True)
        binding_errors({'schema_version':1,'rules':[]},input_data)
        self.assertEqual(before,json.dumps(input_data,sort_keys=True))

class GrantChecks(TestCase):
    def test_revoked_or_scoped_role_rejected(self):
        from api_core.workflow.policy_helpers import role_grant_errors
        from unittest.mock import MagicMock
        dept, approver, executor, type_id = [str(uuid4()) for _ in range(4)]
        route = {'schema_version':1,'rules':[{'id':'x','default':True,'approvers':['FINANCE']}],
                 'executor':'EXECUTOR_FINANCE','acceptor':None}
        bindings={'schema_version':1,'departments':{dept:{'FINANCE':approver,'EXECUTOR_FINANCE':executor}}}
        c = MagicMock()
        c.fetchone.side_effect = [(True,), (True,), (False,)]
        errors = role_grant_errors(c, type_id,route,bindings)
        self.assertTrue(any('requires active' in x for x in errors))
        self.assertEqual(3,c.execute.call_count)

    def test_valid_roles_are_accepted(self):
        from api_core.workflow.policy_helpers import role_grant_errors
        from unittest.mock import MagicMock
        dept, approver, executor, type_id = [str(uuid4()) for _ in range(4)]
        route={'rules':[{'id':'x','default':True,'approvers':['FINANCE']}], 'executor':'EXECUTOR_FINANCE','acceptor':None}
        bindings={'departments':{dept:{'FINANCE':approver,'EXECUTOR_FINANCE':executor}}}
        c=MagicMock()
        c.fetchone.side_effect=[(True,), (True,), (True,)]
        self.assertEqual([],role_grant_errors(c,type_id,route,bindings))
