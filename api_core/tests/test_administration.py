from datetime import datetime, timezone
from io import StringIO
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, override_settings

from api_core.administration.service import (
    TABLES,
    authorize,
    mutate,
    serialize,
    validate,
)
from api_core.administration.views import records
from api_core.authn.models import Actor
from api_core.workflow.service import CommandError


class AdministrationTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.actor = Actor(
            str(uuid4()), "ops", "Ops", str(uuid4()), 1, frozenset({"OPS_ADMIN"}), False
        )

    def test_global_scope_checked_from_database(self):
        c = MagicMock()
        c.fetchone.return_value = (False,)
        with self.assertRaises(CommandError) as e:
            authorize(c, self.actor)
        self.assertEqual(e.exception.status, 403)
        self.assertIn("m.scope_kind='GLOBAL'", c.execute.call_args.args[0])
        self.assertIn("m.type_scope='ALL'", c.execute.call_args.args[0])

    def test_role_scope_and_window_validation(self):
        base = {
            "user_id": str(uuid4()),
            "role": "REQUESTER",
            "scope_kind": "GLOBAL",
            "type_scope": "ALL",
        }
        self.assertIsNone(validate("memberships", base)["department_id"])
        for patch_value in [
            {"role": "ROOT"},
            {"type_scope": "TYPE"},
            {"department_id": str(uuid4())},
            {"type_scope": "ONE"},
            {
                "valid_from": "2026-01-02T00:00:00+00:00",
                "valid_to": "2026-01-01T00:00:00+00:00",
            },
        ]:
            with self.assertRaises(CommandError):
                validate("memberships", base | patch_value)

    def test_password_never_in_serialized_record(self):
        values = (str(uuid4()), "person", "Person", str(uuid4()), None, True, 1, True)
        result = serialize(TABLES["users"][1], values)
        self.assertNotIn("password_hash", result)
        self.assertEqual(len(result["revision"]), 64)

    def test_mass_assignment_rejected(self):
        with self.assertRaises(CommandError):
            validate("users", {"auth_version": 100})
        with self.assertRaises(CommandError):
            validate("departments", {"is_active": "false"})

    def test_password_policy_and_hash(self):
        v = validate(
            "users",
            {
                "email": "person@eas.com",
                "display_name": "Person",
                "department_id": str(uuid4()),
                "password": "Abcd!92873#long",
            },
        )
        self.assertTrue(v["password_hash"].startswith("argon2"))
        self.assertNotIn("password", v)

    @override_settings(EAS_LOGIN_EMAIL_DOMAIN="gmail.com")
    def test_user_validation_uses_configured_email_domain(self):
        valid = validate(
            "users",
            {
                "email": "person+test@gmail.com",
                "display_name": "Person",
                "department_id": str(uuid4()),
                "password": "Abcd!92873#long",
            },
        )
        self.assertEqual(valid["email"], "person+test@gmail.com")
        with self.assertRaises(CommandError) as error:
            validate(
                "users",
                {
                    "email": "person@eas.com",
                    "display_name": "Person",
                    "department_id": str(uuid4()),
                    "password": "Abcd!92873#long",
                },
            )
        self.assertEqual(error.exception.code, "INVALID_EMAIL_DOMAIN")

    def test_membership_owner_immutable(self):
        with self.assertRaises(CommandError):
            validate(
                "memberships", {"user_id": str(uuid4())}, {"user_id": str(uuid4())}
            )

    def test_stale_update_is_rejected(self):
        id = str(uuid4())
        c = MagicMock()
        c.fetchone.side_effect = [(True,), (id, "HR", "Human resources", None, True)]
        with (
            patch("api_core.administration.service.transaction.atomic"),
            patch("api_core.administration.service.connection.cursor") as cm,
            patch(
                "api_core.administration.service._execute_idempotent",
                side_effect=lambda **kw: kw["operation"](c),
            ),
        ):
            cm.return_value.__enter__.return_value = c
            with self.assertRaises(CommandError) as e:
                mutate(
                    self.actor,
                    "departments",
                    id,
                    {
                        "reason": "Update test department",
                        "expected_revision": "old",
                        "name": "New",
                    },
                    "PATCH",
                    "test",
                    "corr",
                )
            self.assertEqual(e.exception.code, "VERSION_CONFLICT")

    def test_create_department_records_audit(self):
        c = MagicMock()
        c.fetchone.side_effect = [
            (True,),
            ("id", "TEST", "Test department", None, True),
        ]
        with (
            patch("api_core.administration.service.transaction.atomic"),
            patch("api_core.administration.service.connection.cursor") as cm,
            patch(
                "api_core.administration.service._execute_idempotent",
                side_effect=lambda **kw: kw["operation"](c),
            ),
            patch("api_core.administration.service._append_admin_audit") as audit,
        ):
            cm.return_value.__enter__.return_value = c
            body, status, _ = mutate(
                self.actor,
                "departments",
                None,
                {
                    "reason": "Create department for testing",
                    "code": "TEST",
                    "name": "Test department",
                },
                "POST",
                "test",
                "corr",
            )
            self.assertEqual(status, 201)
            self.assertEqual(body["item"]["code"], "TEST")
            audit.assert_called_once()

    def test_readonly_role_cannot_call_admin(self):
        actor = Actor(
            str(uuid4()),
            "audit",
            "Audit",
            str(uuid4()),
            1,
            frozenset({"AUDITOR"}),
            False,
        )
        req = RequestFactory().get("/api/v1/admin/users")
        with patch(
            "api_core.authn.service.load_actor_from_session", return_value=actor
        ):
            self.assertEqual(records(req, "users").status_code, 403)

    def test_unknown_resource_is_not_interpolated(self):
        req = RequestFactory().get("/api/v1/admin/anything")
        with patch(
            "api_core.authn.service.load_actor_from_session", return_value=self.actor
        ):
            self.assertEqual(records(req, "users; DROP TABLE").status_code, 404)

    def test_revoke_keeps_history_and_invalidates_session(self):
        id = str(uuid4())
        subject = str(uuid4())
        old = (
            id,
            subject,
            "REQUESTER",
            "GLOBAL",
            None,
            "ALL",
            None,
            datetime.now(timezone.utc),
            None,
            None,
        )
        record = serialize(TABLES["memberships"][1], old)
        c = MagicMock()
        c.fetchone.side_effect = [
            (True,),
            old,
            (False,),  # target is not a system account
            old[:-1] + (datetime.now(timezone.utc),),
        ]
        with (
            patch("api_core.administration.service.transaction.atomic"),
            patch("api_core.administration.service.connection.cursor") as cm,
            patch(
                "api_core.administration.service._execute_idempotent",
                side_effect=lambda **kw: kw["operation"](c),
            ),
            patch("api_core.administration.service._append_admin_audit"),
        ):
            cm.return_value.__enter__.return_value = c
            mutate(
                self.actor,
                "memberships",
                id,
                {
                    "reason": "Revoke assigned permission",
                    "expected_revision": record["revision"],
                },
                "DELETE",
                "test",
                "corr",
            )
        sql = " ".join(x.args[0] for x in c.execute.call_args_list)
        self.assertNotIn("DELETE FROM", sql)
        self.assertIn("SET revoked_at=", sql)
        self.assertIn("auth_version=auth_version+1", sql)

    def test_admin_search_filter_values_are_parameterized(self):
        from api_core.administration.service import _list_filters

        injected = "' OR true --"
        clause, params = _list_filters(
            "users", {"q": injected, "active": "true", "role": "APPROVER"}
        )
        self.assertNotIn(injected, clause)
        self.assertIn("ILIKE %s", clause)
        self.assertIn("rm.role=%s", clause)
        # params[0] hides system accounts (EAS AI) unless include_system=true.
        self.assertEqual(params[0], settings.EAS_AI_SYSTEM_USER_ID)
        self.assertEqual(params[1], f"%{injected}%")
        self.assertEqual(params[3], True)
        self.assertEqual(params[4], "APPROVER")
        with self.assertRaises(CommandError):
            _list_filters("users", {"role": "ROOT"})
        with self.assertRaises(CommandError):
            _list_filters("memberships", {"active": "false"})
        with self.assertRaises(CommandError):
            _list_filters("users", {"q": "x" * 101})

    def test_read_user_detail_has_role_memberships_no_password(self):
        from api_core.administration.service import read_record

        user_id = str(uuid4())
        dept_id = str(uuid4())
        membership_id = str(uuid4())
        user = (user_id, "testuser", "Test user", dept_id, None, True, 1, False)
        membership = (
            membership_id,
            user_id,
            "APPROVER",
            "DEPARTMENT",
            dept_id,
            "ONE",
            str(uuid4()),
            datetime.now(timezone.utc),
            None,
            None,
        )
        c = MagicMock()
        c.fetchone.side_effect = [(True,), user]
        c.fetchall.return_value = [membership]
        with (
            patch("api_core.administration.service.transaction.atomic"),
            patch("api_core.administration.service.connection.cursor") as cm,
        ):
            cm.return_value.__enter__.return_value = c
            out = read_record(self.actor, "users", user_id)
        self.assertEqual(out["item"]["memberships"][0]["role"], "APPROVER")
        self.assertNotIn("password_hash", str(out))

    def test_api_catalog_and_matrix_are_readonly(self):
        from api_core.administration.catalog import access_matrix, api_catalog

        self.assertFalse(api_catalog()["mutable"])
        self.assertEqual(len(access_matrix()["items"]), 7)
        self.assertTrue(
            any(i["path"] == "/api/v1/admin/users" for i in api_catalog()["items"])
        )
        self.assertEqual(
            len({(i["method"], i["path"]) for i in api_catalog()["items"]}),
            len(api_catalog()["items"]),
        )
        self.assertNotIn("password_hash", str(api_catalog()))

    def test_api_catalog_checks_global_ops_scope(self):
        from api_core.administration.views import api_catalog_view

        req = RequestFactory().get("/api/v1/admin/api-catalog")
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=self.actor,
            ),
            patch("api_core.administration.views.transaction.atomic"),
            patch("api_core.administration.views.connection.cursor") as cm,
        ):
            cursor = MagicMock()
            cm.return_value.__enter__.return_value = cursor
            cursor.fetchone.return_value = (False,)
            response = api_catalog_view(req)
        self.assertEqual(response.status_code, 403)

    def test_enforce_initial_passwords_command(self):
        out = StringIO()
        with (
            patch(
                "api_core.management.commands.enforce_initial_passwords.connection"
            ) as conn,
            patch(
                "api_core.management.commands.enforce_initial_passwords.transaction.atomic"
            ),
            patch(
                "api_core.management.commands.enforce_initial_passwords._append_admin_audit"
            ) as audit,
        ):
            cursor = MagicMock()
            conn.cursor.return_value.__enter__.return_value = cursor
            conn.vendor = "postgresql"
            cursor.fetchall.return_value = [
                ("u1", "seeded_user", "d1", 1),
                ("u2", "admin", "d1", 2),
            ]
            cursor.fetchone.return_value = ("op-uuid",)
            call_command(
                "enforce_initial_passwords",
                operator="operator_user",
                approval="CHG-001",
                exclude="admin",
                stdout=out,
            )
            self.assertIn(
                "Successfully enforced password rotation on 1 accounts", out.getvalue()
            )
            audit.assert_called_once()


class SystemAccountTests(SimpleTestCase):
    """Item 4.1: the EAS AI account is hidden by default and cannot be changed."""

    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.actor = Actor(
            str(uuid4()), "ops", "Ops", str(uuid4()), 1, frozenset({"OPS_ADMIN"}), False
        )

    def test_system_accounts_hidden_unless_requested(self):
        from api_core.administration.service import _list_filters

        hidden, params = _list_filters("users", {})
        self.assertIn("NOT (COALESCE((to_jsonb(t)->>'is_system_account')", hidden)
        self.assertEqual(params, [settings.EAS_AI_SYSTEM_USER_ID])
        shown, params = _list_filters("users", {"include_system": "true"})
        self.assertEqual((shown, params), ("", []))
        memberships, _ = _list_filters("memberships", {})
        self.assertIn("eas.app_user su", memberships)
        with self.assertRaises(CommandError):
            _list_filters("departments", {"include_system": "true"})

    def _mutate_system(self, kind, record_id, body, method):
        c = MagicMock()
        fetches = [(True,)]
        if method != "POST":
            fetches.append(self.old_row(kind))
        fetches.append((True,))  # target is the system account
        c.fetchone.side_effect = fetches
        with (
            patch("api_core.administration.service.transaction.atomic"),
            patch("api_core.administration.service.connection.cursor") as cm,
            patch(
                "api_core.administration.service._execute_idempotent",
                side_effect=lambda **kw: kw["operation"](c),
            ),
            patch("api_core.administration.service._append_admin_audit"),
        ):
            cm.return_value.__enter__.return_value = c
            with self.assertRaises(CommandError) as raised:
                mutate(self.actor, kind, record_id, body, method, "k", "c")
        return raised.exception

    DEPARTMENT = "00000001-0000-4000-8000-000000000001"

    def old_row(self, kind):
        if kind == "users":
            return (
                settings.EAS_AI_SYSTEM_USER_ID,
                "ai.system@eas.com",
                "EAS AI",
                self.DEPARTMENT,
                None,
                True,
                0,
                False,
            )
        return (
            str(uuid4()),
            settings.EAS_AI_SYSTEM_USER_ID,
            "APPROVER",
            "GLOBAL",
            None,
            "ALL",
            None,
            datetime.now(timezone.utc),
            None,
            None,
        )

    def test_cannot_disable_system_account(self):
        old = serialize(TABLES["users"][1], self.old_row("users"))
        error = self._mutate_system(
            "users",
            settings.EAS_AI_SYSTEM_USER_ID,
            {"reason": "Disable the AI account", "expected_revision": old["revision"]},
            "DELETE",
        )
        self.assertEqual((error.code, error.status), ("SYSTEM_ACCOUNT_LOCKED", 403))

    def test_cannot_grant_roles_to_system_account(self):
        error = self._mutate_system(
            "memberships",
            None,
            {
                "reason": "Grant ops admin to the AI",
                "user_id": settings.EAS_AI_SYSTEM_USER_ID,
                "role": "OPS_ADMIN",
                "scope_kind": "GLOBAL",
                "type_scope": "ALL",
            },
            "POST",
        )
        self.assertEqual(error.code, "SYSTEM_ACCOUNT_LOCKED")
