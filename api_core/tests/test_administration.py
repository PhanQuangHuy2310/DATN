from datetime import datetime, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

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
                "username": "person",
                "display_name": "Person",
                "department_id": str(uuid4()),
                "password": "Abcd!92873#long",
            },
        )
        self.assertTrue(v["password_hash"].startswith("argon2"))
        self.assertNotIn("password", v)

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
