"""Tests for policy authoring; NO writes to a live database."""
import json
import unittest
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from api_core.domain.routing import resolve_route, APPROVER_SLOTS, EXECUTOR_SLOTS, ACCEPTOR_SLOTS, RoutingError
from api_core.domain.validation import validate_config_release_payload

ROOT=Path(__file__).resolve().parents[1]
POLICIES=json.loads((ROOT/'docs/APPROVAL_MENU_POLICY_DRAFTS.json').read_text(encoding='utf8'))['drafts']
USER=str(uuid5(NAMESPACE_DNS,'test-user'))
MANAGER=str(uuid5(NAMESPACE_DNS,'test-manager'))
DEPT=str(uuid5(NAMESPACE_DNS,'test-department'))

class RoutingTests(unittest.TestCase):
    def test_all_eighteen_authoring_blueprints_pass_json_validation(self):
        self.assertEqual(len(POLICIES),18)
        for item in POLICIES:
            with self.subTest(code=item['code']):
                errors=validate_config_release_payload(
                    lifecycle=item['lifecycle'],form_schema=item['form_schema'],
                    route_rules=item['route_rules'],actor_bindings=item['actor_bindings'],
                    sla_profile=item['sla_profile'])
                self.assertEqual(errors,[])
                self.assertEqual(item['activation_state'],'DRAFT_SUGGESTION')
                self.assertFalse(item['actor_bindings']['departments'])

    def test_roles_resolve_without_assigning_a_requester_as_approver(self):
        slots=APPROVER_SLOTS | {s for s in EXECUTOR_SLOTS if s} | {s for s in ACCEPTOR_SLOTS if s}
        bindings={'schema_version':1,'departments':{DEPT:{slot:str(uuid5(NAMESPACE_DNS,f'role-{slot}')) for slot in slots}}}
        for item in POLICIES:
            with self.subTest(code=item['code']):
                rule=item['route_rules']
                route=resolve_route(route_rules=rule,actor_bindings=bindings,
                                   department_id=DEPT,requester_id=USER,manager_id=MANAGER,
                                   amount_vnd=10_000_000)
                self.assertTrue(route.approver_ids)
                self.assertNotIn(USER, route.approver_ids)
                if item['lifecycle']=='A':
                    self.assertIsNone(route.executor_id)
                    self.assertIsNone(route.acceptor_id)
                if item['lifecycle']=='B':
                    self.assertIsNotNone(route.executor_id)
                    self.assertIsNone(route.acceptor_id)
                if item['lifecycle']=='C':
                    self.assertIsNotNone(route.executor_id)
                    self.assertIsNotNone(route.acceptor_id)
                    self.assertNotEqual(route.executor_id,route.acceptor_id)

    def test_purchase_routes_three_band_limits(self):
        rule=next(x['route_rules'] for x in POLICIES if x['code']=='PURCHASE_REQUEST')
        bind={'schema_version':1,'departments':{DEPT:{slot:str(uuid5(NAMESPACE_DNS,slot)) for slot in APPROVER_SLOTS | {s for s in EXECUTOR_SLOTS if s}}}}
        for amount,n in [(4_999_999,1),(5_000_000,2),(50_000_000,2),(50_000_001,3)]:
            route=resolve_route(route_rules=rule,actor_bindings=bind,department_id=DEPT,
                                requester_id=USER,manager_id=MANAGER,amount_vnd=amount)
            self.assertEqual(len(route.approver_ids),n)

    def test_invalid_slots_fail_closed(self):
        rule={'schema_version':1,'rules':[{'id':'BAD','default':True,'approvers':['ROOT_ADMIN']}],
              'executor':None,'acceptor':None}
        with self.assertRaises(RoutingError):
            resolve_route(route_rules=rule,actor_bindings={'schema_version':1,'departments':{DEPT:{}}},
                          department_id=DEPT,requester_id=USER,manager_id=MANAGER,amount_vnd=None)

if __name__=='__main__': unittest.main()
