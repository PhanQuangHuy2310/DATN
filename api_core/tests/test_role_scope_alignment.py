"""Regression: OPS request metadata follows role + type + department scope.

The read-side SQL must apply the same authorization boundary as reassign;
a global OPS menu by itself never grants data access across departments.
"""
from unittest.mock import patch
from uuid import uuid4
from django.test import SimpleTestCase
from api_core.authn.models import Actor
from api_core.workflow.ops_service import list_ops_metadata


class _FakeCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params):
        self.queries.append((query, params))

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class OpsMetadataAuthorizationTests(SimpleTestCase):
    @patch("api_core.workflow.ops_service.connection")
    def test_ops_list_checks_scope_and_validity_in_query(self, connection):
        cursor = _FakeCursor()
        connection.cursor.return_value = cursor
        actor = Actor(id=str(uuid4()), username="ops", display_name="Ops", department_id=str(uuid4()),
                      auth_version=1, roles=frozenset({"OPS_ADMIN"}), must_change_password=False)
        result = list_ops_metadata(actor, {"limit": "20", "offset": "0"})
        self.assertEqual(result["items"], [])
        self.assertEqual(len(cursor.queries), 1)
        query, params = cursor.queries[0]
        self.assertIn("rm.scope_kind = 'GLOBAL'", query)
        self.assertIn("rm.department_id = COALESCE(v.department_id, u.department_id)", query)
        self.assertIn("rm.type_scope = 'ALL' OR rm.type_id = r.type_id", query)
        self.assertIn("rm.valid_from <= statement_timestamp()", query)
        self.assertIn(actor.id, params)

class AuditEventScopeTests(SimpleTestCase):
    @patch("api_core.workflow.reporting.connection")
    def test_admin_events_are_filtered_by_role_membership_scope(self, connection):
        from api_core.workflow.reporting import list_admin_events

        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql, values):
                self.calls.append((sql, values))

            def fetchone(self):
                return (True,)

            def fetchall(self):
                return []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        cursor = Cursor()
        connection.cursor.return_value = cursor
        actor = Actor(id=str(uuid4()), username="auditor", display_name="Auditor", department_id=str(uuid4()),
                      auth_version=1, roles=frozenset({"AUDITOR"}), must_change_password=False)
        result = list_admin_events(actor, {"limit": "20", "offset": "0"})
        self.assertEqual(result["items"], [])
        self.assertEqual(len(cursor.calls), 2)
        query, params = cursor.calls[1]
        self.assertIn("rm.scope_kind = 'GLOBAL'", query)
        self.assertIn("rm.department_id = e.department_id", query)
        self.assertIn("rm.type_id = e.type_id", query)
        self.assertIn(actor.id, params)
