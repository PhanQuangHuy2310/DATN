"""H8: admin can change an employee's direct manager; cycles are rejected."""

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

from api_core.administration import org_users_rbac
from api_core.administration.service import check_cycle
from api_core.authn.models import Actor
from api_core.workflow.errors import CommandError


class ManagerChangeTests(SimpleTestCase):
    def setUp(self):
        self.admin = Actor(
            str(uuid4()),
            "admin@eas.com",
            "Admin",
            str(uuid4()),
            1,
            frozenset({"OPS_ADMIN"}),
            False,
        )
        self.user_id = str(uuid4())
        self.manager_id = str(uuid4())

    def _patch(self, body):
        request = RequestFactory().patch(
            f"/api/v1/admin/users-management/{self.user_id}",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )
        request.actor = self.admin
        mutated = MagicMock()
        mutated.body = {
            "item": {
                "id": self.user_id,
                "department_id": str(uuid4()),
                "display_name": "Nhân viên",
                "is_active": True,
                "manager_id": None,
                "email": "nv@eas.com",
            }
        }
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=self.admin,
            ),
            patch("api_core.maintenance.is_maintenance_active", return_value=False),
            patch.object(org_users_rbac, "_forbidden_unless_users", return_value=None),
            patch.object(org_users_rbac, "connection", MagicMock()),
            patch.object(org_users_rbac, "_assert_employee"),
            patch.object(org_users_rbac, "_users_authorizer"),
            patch.object(
                org_users_rbac,
                "read_record",
                return_value={"item": {"revision": 3, "department_id": str(uuid4())}},
            ),
            patch.object(org_users_rbac, "transaction"),
            patch.object(org_users_rbac, "mutate", return_value=mutated) as mutate,
        ):
            response = org_users_rbac.user_management_detail(request, self.user_id)
        return response, mutate

    def test_manager_id_is_sent_to_the_validated_mutation(self):
        response, mutate = self._patch({"manager_id": self.manager_id})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Không có thay đổi", response.content.decode())
        changes = mutate.call_args.args[3]
        self.assertEqual(changes["manager_id"], self.manager_id)
        self.assertEqual(changes["expected_revision"], 3)

    def test_empty_manager_id_removes_the_manager(self):
        _, mutate = self._patch({"manager_id": ""})
        self.assertIsNone(mutate.call_args.args[3]["manager_id"])

    def test_self_manager_is_rejected_before_any_query(self):
        cursor = MagicMock()
        with self.assertRaises(CommandError) as ctx:
            check_cycle(cursor, "app_user", "manager_id", self.user_id, self.user_id)
        self.assertEqual(ctx.exception.code, "HIERARCHY_CYCLE")
        cursor.execute.assert_not_called()

    def test_user_cycle_walks_app_user_manager_chain(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        with self.assertRaises(CommandError):
            check_cycle(cursor, "app_user", "manager_id", self.user_id, self.manager_id)
        sql = cursor.execute.call_args.args[0]
        self.assertIn("eas.app_user", sql)
        self.assertIn("manager_id", sql)
        self.assertNotIn("eas.department", sql)


class AuditorRoleAssignmentTests(SimpleTestCase):
    """M3: AUDITOR can be assigned from the user screen, by an administrator only."""

    def _request(self, roles):
        req = RequestFactory().patch("/x")
        req.actor = Actor(
            str(uuid4()), "a@eas.com", "A", str(uuid4()), 1, frozenset(roles), False
        )
        return req

    def test_admin_can_assign_auditor(self):
        self.assertEqual(
            org_users_rbac._validated_role("AUDITOR", self._request({"OPS_ADMIN"})),
            "AUDITOR",
        )

    def test_non_admin_cannot_assign_auditor(self):
        with self.assertRaises(CommandError) as ctx:
            org_users_rbac._validated_role("AUDITOR", self._request({"AUDITOR"}))
        self.assertEqual(ctx.exception.code, "AUDITOR_ROLE_ADMIN_ONLY")

    def test_system_admin_roles_stay_unassignable(self):
        for role in ("OPS_ADMIN", "POLICY_ADMIN"):
            with self.assertRaises(CommandError):
                org_users_rbac._validated_role(role, self._request({"OPS_ADMIN"}))

    def test_auditor_is_a_global_grant(self):
        grant = org_users_rbac._role_grants(str(uuid4()), str(uuid4()), "AUDITOR")[0]
        self.assertEqual(
            (grant["scope_kind"], grant["department_id"]), ("GLOBAL", None)
        )
