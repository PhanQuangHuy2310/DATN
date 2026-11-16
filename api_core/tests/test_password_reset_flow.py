"""Password reset: one admin e-mail per request, two ways to issue the
temporary password (generated or entered by the admin) and rejection."""

import json
from typing import ClassVar
from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from api_core.authn.models import Actor
from api_core.authn.service import validate_new_password
from api_core.authn.views import _admin_reset_notice

MAIL = {
    "EMAIL_HOST": "smtp.test",
    "DEFAULT_FROM_EMAIL": "EAS Support <mailer@eas.com>",
    "EAS_EMAIL_TEST_RECIPIENT": "",
}
USER_ID = str(uuid4())
DEPT_ID = str(uuid4())


def _admin():
    return Actor(
        id=str(uuid4()),
        email="ops@eas.com",
        display_name="System admin",
        department_id=DEPT_ID,
        auth_version=1,
        roles=frozenset({"OPS_ADMIN"}),
        must_change_password=False,
    )


@override_settings(**MAIL)
class ResetRequestNoticeTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        cache.clear()

    @patch("api_core.authn.views.send_mail")
    @patch("api_core.authn.views.connection")
    def test_repeat_request_reuses_the_pending_one_without_a_second_mail(
        self, connection, send_mail
    ):
        cursor = connection.cursor.return_value.__enter__.return_value
        # active user, then an existing PENDING request
        cursor.fetchone.side_effect = [(USER_ID, "Employee"), ("pending-id",)]
        cursor.fetchall.return_value = [("ops@eas.com",)]
        response = self.client.post(
            "/api/v1/auth/password-reset/request",
            data=json.dumps({"email": "employee@eas.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        send_mail.assert_not_called()

    @override_settings(EAS_ADMIN_PORTAL_URL="http://127.0.0.1:8081")
    def test_admin_notice_points_to_the_users_screen(self):
        notice = _admin_reset_notice("Mai Ngọc Anh", "anh.mai@eas.com", "rid")
        self.assertIn("http://127.0.0.1:8081/#/users > Người dùng", notice)
        self.assertIn("Yêu cầu đặt lại mật khẩu", notice)
        self.assertNotIn("Danh tính & phân quyền", notice)


@override_settings(**MAIL)
@patch("api_core.maintenance.is_maintenance_active", new=lambda: False)
@patch("api_core.workflow.service._append_admin_audit")
@patch(
    "api_core.authn.service.load_actor_from_session", side_effect=lambda _r: _admin()
)
@patch("api_core.authn.views.connection")
@patch("api_core.authn.views.send_mail")
class ResetDecisionTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        cache.clear()

    def _approve(self, connection, body):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (True,),  # global OPS admin
            (USER_ID, "employee@eas.com", "employee@eas.com", "Employee", DEPT_ID, 3),
        ]
        response = self.client.post(
            f"/api/v1/auth/password-reset/requests/{uuid4()}/approve",
            data=json.dumps(body),
            content_type="application/json",
        )
        return response, cursor

    def test_admin_entered_password_is_mailed_and_forces_change(
        self, send_mail, connection, _actor, _audit
    ):
        chosen = "Tam-Thoi#2026-Nhan-Vien"
        response, cursor = self._approve(
            connection,
            {
                "reason": "Đã xác minh trực tiếp tại phòng nhân sự.",
                "mode": "manual",
                "temporary_password": chosen,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "manual")
        self.assertIn(
            f"Mật khẩu tạm thời: {chosen}", send_mail.call_args.kwargs["message"]
        )
        self.assertTrue(
            any(
                "must_change_password=true" in c.args[0]
                for c in cursor.execute.call_args_list
            )
        )

    def test_admin_entered_password_must_meet_the_policy(
        self, send_mail, connection, _actor, _audit
    ):
        response, _ = self._approve(
            connection,
            {
                "reason": "Đã xác minh trực tiếp tại phòng nhân sự.",
                "mode": "manual",
                "temporary_password": "short",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "TEMPORARY_PASSWORD_POLICY")
        send_mail.assert_not_called()

    def test_generated_password_is_still_the_default(
        self, send_mail, connection, _actor, _audit
    ):
        response, _ = self._approve(
            connection, {"reason": "Đã xác minh trực tiếp tại phòng nhân sự."}
        )
        self.assertEqual(response.status_code, 200)
        sent = (
            send_mail.call_args.kwargs["message"]
            .split("Mật khẩu tạm thời: ", 1)[1]
            .splitlines()[0]
        )
        self.assertEqual(validate_new_password(sent, "employee@eas.com"), sent)

    def test_unknown_mode_is_rejected(self, send_mail, connection, _actor, _audit):
        response, _ = self._approve(
            connection, {"reason": "Đã xác minh trực tiếp.", "mode": "default"}
        )
        self.assertEqual(response.status_code, 400)

    def test_reject_closes_the_request_and_tells_the_employee(
        self, send_mail, connection, _actor, _audit
    ):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (True,),
            (USER_ID, "employee@eas.com", "Employee", DEPT_ID),
        ]
        response = self.client.post(
            f"/api/v1/auth/password-reset/requests/{uuid4()}/reject",
            data=json.dumps(
                {"reason": "Không xác minh được danh tính qua điện thoại."}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        update = next(
            c
            for c in cursor.execute.call_args_list
            if "SET status='EXPIRED'" in c.args[0]
        )
        self.assertTrue(update.args[1][1].startswith("Từ chối: "))
        self.assertEqual(
            send_mail.call_args.kwargs["recipient_list"], ["employee@eas.com"]
        )
        self.assertIn("không thay đổi", send_mail.call_args.kwargs["message"])

    def test_reject_requires_a_reason(self, send_mail, connection, _actor, _audit):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(True,)]
        response = self.client.post(
            f"/api/v1/auth/password-reset/requests/{uuid4()}/reject",
            data=json.dumps({"reason": "ngắn"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
