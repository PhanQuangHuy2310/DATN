from __future__ import annotations

import json
from typing import ClassVar
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from api_core.authn.models import Actor, AuthUser
from api_core.maintenance import (
    complete_maintenance,
    get_maintenance_info,
    is_maintenance_active,
    reset_maintenance_for_test,
    start_maintenance,
)


@override_settings(EAS_LOGIN_MAX_ATTEMPTS=5, EAS_LOGIN_WINDOW_SECONDS=60)
class MaintenanceModeTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        cache.clear()
        reset_maintenance_for_test()
        self.non_admin_user = AuthUser(
            id=str(uuid4()),
            username="requester1",
            display_name="Nguyen Van A",
            department_id=str(uuid4()),
            password_hash=make_password("UserPass-2026!", hasher="pbkdf2_sha256"),
            auth_version=1,
            is_active=True,
            must_change_password=False,
        )
        self.admin_user = AuthUser(
            id=str(uuid4()),
            username="policy_admin",
            display_name="Tran Thi B (Admin)",
            department_id=str(uuid4()),
            password_hash=make_password("AdminPass-2026!", hasher="pbkdf2_sha256"),
            auth_version=1,
            is_active=True,
            must_change_password=False,
        )

    def tearDown(self):
        reset_maintenance_for_test()

    def test_maintenance_module_state_transitions(self):
        # 1. Ban đầu: trạng thái bình thường
        self.assertFalse(is_maintenance_active())
        info = get_maintenance_info()
        self.assertEqual(info["status"], "NORMAL")
        self.assertFalse(info["active"])

        # 2. Bắt đầu bảo trì cập nhật quy định
        start_maintenance(
            actor_id="admin-123",
            release_id="rel-456",
            message="Hệ thống đang bảo trì để cập nhật quy định mới.",
            admin_message="Hệ thống đang cập nhật quy định mới cho web-admin.",
        )
        self.assertTrue(is_maintenance_active())
        info = get_maintenance_info()
        self.assertEqual(info["status"], "UPDATING")
        self.assertTrue(info["active"])
        self.assertEqual(info["release_id"], "rel-456")

        # 3. Hoàn tất cập nhật
        complete_maintenance(
            actor_id="admin-123",
            admin_message="Đã cập nhật xong quy định mới.",
        )
        self.assertFalse(is_maintenance_active())
        info = get_maintenance_info()
        self.assertEqual(info["status"], "COMPLETED")
        self.assertFalse(info["active"])
        self.assertEqual(info["admin_message"], "Đã cập nhật xong quy định mới.")

    @patch("api_core.authn.views.find_user")
    @patch("api_core.maintenance.is_admin_user_id", return_value=False)
    def test_non_admin_login_blocked_during_maintenance(self, _is_admin, find_user):
        find_user.return_value = self.non_admin_user
        start_maintenance(
            actor_id="admin-1",
            message="Hệ thống đang bảo trì để cập nhật quy định mới, vui lòng quay lại sau.",
        )

        # Cố đăng nhập khi hệ thống đang bảo trì
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"username": "requester1", "password": "UserPass-2026!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["error"]["code"], "SYSTEM_UNDER_MAINTENANCE")
        self.assertIn("Hệ thống đang bảo trì", body["error"]["fields"]["message"][0])
        self.assertNotIn("user_id", self.client.session)

    @patch("api_core.authn.views.find_user")
    @patch("api_core.maintenance.is_admin_user_id", return_value=True)
    def test_admin_login_allowed_during_maintenance(self, _is_admin, find_user):
        find_user.return_value = self.admin_user
        start_maintenance(
            actor_id="admin-1",
            admin_message="Hệ thống đang trong quá trình cập nhật quy định mới. Chỉ quản trị viên mới có thể truy cập web-admin.",
        )

        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"username": "policy_admin", "password": "AdminPass-2026!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user"]["username"], "policy_admin")
        self.assertTrue(body["maintenance"]["active"])
        self.assertEqual(body["maintenance"]["status"], "UPDATING")
        self.assertIn("quá trình cập nhật", body["maintenance"]["message"])

    @patch("api_core.authn.service.load_actor_from_session")
    def test_require_actor_blocks_non_admin_during_maintenance(self, load_actor):
        # Giả lập user thường đã có session từ trước
        non_admin_actor = Actor(
            id=self.non_admin_user.id,
            username="requester1",
            display_name="Nguyen Van A",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"REQUESTER"}),
            must_change_password=False,
        )
        load_actor.return_value = non_admin_actor
        start_maintenance(actor_id="admin-1")

        # Gọi endpoint /api/v1/me
        response = self.client.get("/api/v1/me")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "SYSTEM_UNDER_MAINTENANCE")

    @patch("api_core.authn.service.load_actor_from_session")
    def test_require_actor_allows_admin_during_maintenance(self, load_actor):
        admin_actor = Actor(
            id=self.admin_user.id,
            username="policy_admin",
            display_name="Tran Thi B (Admin)",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"POLICY_ADMIN"}),
            must_change_password=False,
        )
        load_actor.return_value = admin_actor
        start_maintenance(
            actor_id="admin-1",
            admin_message="Hệ thống đang cập nhật quy định mới.",
        )

        response = self.client.get("/api/v1/me")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user"]["username"], "policy_admin")
        self.assertTrue(body["maintenance"]["active"])
        self.assertEqual(body["maintenance"]["status"], "UPDATING")

    def test_system_maintenance_get_endpoint(self):
        start_maintenance(actor_id="admin-1", release_id="rel-test-123")
        response = self.client.get("/api/v1/system/maintenance")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["maintenance"]["active"])
        self.assertEqual(body["maintenance"]["release_id"], "rel-test-123")

    @patch("api_core.authn.service.load_actor_from_session")
    @patch("api_core.workflow.service._append_admin_audit")
    def test_complete_maintenance_endpoint(self, mock_audit, load_actor):
        admin_actor = Actor(
            id=self.admin_user.id,
            username="policy_admin",
            display_name="Tran Thi B (Admin)",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"POLICY_ADMIN"}),
            must_change_password=False,
        )
        load_actor.return_value = admin_actor
        start_maintenance(actor_id=admin_actor.id)
        self.assertTrue(is_maintenance_active())

        # Admin hoàn tất cập nhật
        response = self.client.post(
            "/api/v1/system/maintenance/complete",
            data=json.dumps({"admin_message": "Hệ thống đã cập nhật xong quy định mới."}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertFalse(body["maintenance"]["active"])
        self.assertEqual(body["maintenance"]["status"], "COMPLETED")
        self.assertFalse(is_maintenance_active())

    @patch("api_core.authn.views.find_user")
    @patch("api_core.maintenance.is_admin_user_id", return_value=False)
    def test_non_admin_can_login_after_maintenance_completed(self, _is_admin, find_user):
        find_user.return_value = self.non_admin_user
        # Bảo trì đã hoàn tất
        start_maintenance(actor_id="admin-1")
        complete_maintenance(actor_id="admin-1")
        self.assertFalse(is_maintenance_active())

        # User thường đăng nhập lại bình thường
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"username": "requester1", "password": "UserPass-2026!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], "requester1")
