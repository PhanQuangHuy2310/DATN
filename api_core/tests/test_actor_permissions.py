"""Module permissions come from eas.get_effective_user_permissions keyed by the
app_user id (migration 2026-11-03_01), with the role-derived matrix as fallback."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.db import DatabaseError
from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.authn.views import _get_actor_permissions


def _actor(*roles):
    return Actor(
        id=str(uuid4()),
        email="employee@eas.com",
        display_name="Employee",
        department_id=str(uuid4()),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


def _row(code, view):
    return (
        code,
        code,
        "group",
        "/" + code,
        "Icon",
        "BOTH",
        view,
        False,
        False,
        False,
        view,
        "ROLE_DEFAULT",
    )


class ActorPermissionTests(SimpleTestCase):
    def _cursor(self, rows=None, error=None):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        if error:
            cursor.execute.side_effect = error
        cursor.fetchall.return_value = rows or []
        return cursor

    def test_database_matrix_is_queried_by_app_user_id(self):
        actor = _actor("REQUESTER")
        cursor = self._cursor([_row("dashboard", True), _row("users", False)])
        with patch("api_core.authn.views.connection") as conn:
            conn.cursor.return_value = cursor
            result = _get_actor_permissions(actor)
        sql, params = cursor.execute.call_args.args
        self.assertIn("get_effective_user_permissions", sql)
        self.assertNotIn("eas.users", sql)
        self.assertEqual(params, [actor.id])
        self.assertEqual(
            [m["module_code"] for m in result["modules"]], ["dashboard", "users"]
        )
        self.assertFalse(result["by_module"]["users"]["can_view"])

    def test_matrix_granting_nothing_falls_back_to_roles(self):
        cursor = self._cursor([_row("dashboard", False), _row("users", False)])
        with patch("api_core.authn.views.connection") as conn:
            conn.cursor.return_value = cursor
            result = _get_actor_permissions(_actor("OPS_ADMIN"))
        self.assertTrue(result["by_module"]["users"]["can_view"])
        self.assertTrue(result["by_module"]["dashboard"]["can_view"])

    def test_database_error_falls_back_to_roles(self):
        cursor = self._cursor(error=DatabaseError("function does not exist"))
        with patch("api_core.authn.views.connection") as conn:
            conn.cursor.return_value = cursor
            result = _get_actor_permissions(_actor("REQUESTER"))
        self.assertTrue(result["by_module"]["dashboard"]["can_view"])
        self.assertFalse(result["by_module"]["users"]["can_view"])
