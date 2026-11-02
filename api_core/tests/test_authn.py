import json
from typing import ClassVar
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import Client, SimpleTestCase, override_settings

from api_core.authn.models import Actor, AuthUser
from api_core.authn.service import PasswordChangeError, validate_new_password
from api_core.authn.views import _email_recipients, _normalized_login_email


@override_settings(EAS_LOGIN_MAX_ATTEMPTS=2, EAS_LOGIN_WINDOW_SECONDS=60)
class AuthenticationEndpointTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    @override_settings(EAS_EMAIL_TEST_RECIPIENT="")
    def test_email_recipients_use_actual_recipients_by_default(self):
        self.assertEqual(_email_recipients(["employee@eas.com"]), ["employee@eas.com"])

    @override_settings(EAS_EMAIL_TEST_RECIPIENT="test-inbox@gmail.com")
    def test_email_recipients_can_be_redirected_for_local_testing(self):
        self.assertEqual(
            _email_recipients(["employee@eas.com"]), ["test-inbox@gmail.com"]
        )

    @override_settings(EAS_LOGIN_EMAIL_DOMAIN="gmail.com")
    def test_login_email_domain_can_be_configured_for_gmail_aliases(self):
        self.assertEqual(
            _normalized_login_email(" Tester+demo@gmail.com "),
            "tester+demo@gmail.com",
        )
        self.assertEqual(
            _normalized_login_email(" employee@eas.com "), "employee@eas.com"
        )
        self.assertIsNone(_normalized_login_email("employee@example.org"))

    def setUp(self):
        cache.clear()
        self.user = AuthUser(
            id=str(uuid4()),
            email="employee@eas.com",
            display_name="Employee",
            department_id=str(uuid4()),
            password_hash=make_password("Correct-Horse-2026", hasher="pbkdf2_sha256"),
            auth_version=3,
            is_active=True,
            must_change_password=False,
        )

    @patch("api_core.authn.views.find_user")
    def test_login_is_generic_and_creates_versioned_session(self, find_user):
        find_user.return_value = self.user
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": " Employee@EAS.com ", "password": "Correct-Horse-2026"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["user_id"], self.user.id)
        self.assertEqual(self.client.session["auth_version"], 3)
        session_id = self.client.session["session_id"]
        self.assertEqual(cache.get(f"eas:session:{session_id}"), f"{self.user.id}:3")
        self.assertEqual(cache.get(f"eas:idle:{session_id}"), f"{self.user.id}:3")
        self.assertNotIn("password_hash", response.json()["user"])

        find_user.return_value = None
        invalid = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "unknown@eas.com", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json()["error"]["code"], "INVALID_CREDENTIALS")

    @patch("api_core.authn.views.find_user", return_value=None)
    def test_login_rate_limit_returns_retry_after(self, _find_user):
        for _ in range(2):
            self.client.post(
                "/api/v1/auth/login",
                data=json.dumps({"email": "employee@eas.com", "password": "wrong"}),
                content_type="application/json",
            )
        limited = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "employee@eas.com", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers["Retry-After"], "60")

    @override_settings(
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        EAS_LOGIN_MAX_IP_ATTEMPTS=2,
        EAS_LOGIN_MAX_ATTEMPTS=10,
    )
    @patch("api_core.authn.views.find_user", return_value=None)
    def test_login_rate_limit_uses_client_ip_behind_trusted_proxy(self, _find_user):
        for _ in range(2):
            self.client.post(
                "/api/v1/auth/login",
                data=json.dumps({"email": "user1@eas.com", "password": "wrong"}),
                content_type="application/json",
                REMOTE_ADDR="10.0.0.1",
                HTTP_X_FORWARDED_FOR="198.51.100.1",
            )
        throttled_ip1 = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "user1@eas.com", "password": "wrong"}),
            content_type="application/json",
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="198.51.100.1",
        )
        self.assertEqual(throttled_ip1.status_code, 429)

        different_ip = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "user2@eas.com", "password": "wrong"}),
            content_type="application/json",
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="198.51.100.2",
        )
        self.assertEqual(different_ip.status_code, 401)

    def test_login_requires_csrf_in_real_client_mode(self):
        client = Client(enforce_csrf_checks=True)
        rejected = client.post(
            "/api/v1/auth/login",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 403)
        csrf = client.get("/api/v1/auth/csrf")
        token = csrf.cookies["csrftoken"].value
        accepted_by_csrf = client.post(
            "/api/v1/auth/login",
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(accepted_by_csrf.status_code, 401)

    @override_settings(
        EMAIL_HOST="smtp.test",
        DEFAULT_FROM_EMAIL="EAS Support <mailer@eas.com>",
    )
    @patch("api_core.authn.views.send_mail")
    @patch("api_core.authn.views.connection")
    def test_password_reset_request_is_queued_and_notifies_global_admins(
        self, connection, send_mail
    ):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (self.user.id, self.user.display_name),
            None,
            ("reset-id",),
        ]
        cursor.fetchall.return_value = [("ops@eas.com",)]
        requested = self.client.post(
            "/api/v1/auth/password-reset/request",
            data=json.dumps({"email": "EMPLOYEE@EAS.COM"}),
            content_type="application/json",
        )
        self.assertEqual(requested.status_code, 202)
        send_mail.assert_called_once()
        self.assertTrue(
            any(
                "INSERT INTO eas.password_reset_request" in call.args[0]
                for call in cursor.execute.call_args_list
            )
        )
        self.assertEqual(send_mail.call_args.kwargs["recipient_list"], ["ops@eas.com"])
        self.assertIn(self.user.email, send_mail.call_args.kwargs["message"])

    @override_settings(
        EMAIL_HOST="smtp.test",
        DEFAULT_FROM_EMAIL="EAS Support <mailer@eas.com>",
    )
    @patch("api_core.authn.views.send_mail")
    @patch("api_core.authn.views.connection")
    @patch("api_core.authn.service.load_actor_from_session")
    @patch("api_core.workflow.service._append_admin_audit")
    def test_global_admin_approval_sends_random_temporary_password_and_forces_change(
        self, _append_audit, load_actor, connection, send_mail
    ):
        admin = Actor(
            id=str(uuid4()),
            email="ops@eas.com",
            display_name="System admin",
            department_id=self.user.department_id,
            auth_version=1,
            roles=frozenset({"OPS_ADMIN"}),
            must_change_password=False,
        )
        load_actor.return_value = admin
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (True,),
            (
                self.user.id,
                self.user.email,
                self.user.email,
                self.user.display_name,
                self.user.department_id,
                self.user.auth_version,
            ),
        ]
        reset_id = str(uuid4())
        approved = self.client.post(
            f"/api/v1/auth/password-reset/requests/{reset_id}/approve",
            data=json.dumps({"reason": "Identity verified through the HR desk."}),
            content_type="application/json",
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "approved")
        self.assertEqual(
            send_mail.call_args.kwargs["recipient_list"], [self.user.email]
        )
        temporary_password = (
            send_mail.call_args.kwargs["message"]
            .split("Mật khẩu tạm thời: ", 1)[1]
            .splitlines()[0]
        )
        self.assertNotEqual(temporary_password, "Password@123456")
        self.assertEqual(
            validate_new_password(temporary_password, self.user.email),
            temporary_password,
        )
        self.assertTrue(
            any(
                "must_change_password=true" in call.args[0]
                for call in cursor.execute.call_args_list
            )
        )

    @patch("api_core.authn.views.connection")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_scoped_ops_admin_cannot_review_password_reset_requests(
        self, load_actor, connection
    ):
        load_actor.return_value = Actor(
            id=str(uuid4()),
            email="scoped-ops@eas.com",
            display_name="Scoped admin",
            department_id=self.user.department_id,
            auth_version=1,
            roles=frozenset({"OPS_ADMIN"}),
            must_change_password=False,
        )
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            False,
        )
        response = self.client.get("/api/v1/auth/password-reset/requests")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "FORBIDDEN")

    @override_settings(EMAIL_HOST="", DEFAULT_FROM_EMAIL="")
    def test_password_reset_fails_when_mail_delivery_is_not_configured(self):
        response = self.client.post(
            "/api/v1/auth/password-reset/request",
            data=json.dumps({"email": "employee@eas.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)

    @patch("api_core.authn.views.connection")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_me_returns_only_current_authorized_actor(self, load_actor, connection):
        load_actor.return_value = Actor(
            id=self.user.id,
            email=self.user.email,
            display_name=self.user.display_name,
            department_id=self.user.department_id,
            auth_version=3,
            roles=frozenset({"REQUESTER", "APPROVER"}),
            must_change_password=False,
        )
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            False,
        )
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["roles"], ["APPROVER", "REQUESTER"])
        self.assertEqual(
            response.json()["user"]["capabilities"], {"identity_manage": False}
        )

    @patch("api_core.authn.service.load_actor_from_session", return_value=None)
    def test_me_fails_closed_for_revoked_session(self, _load_actor):
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)

    @patch("api_core.authn.views.find_user")
    def test_logout_revokes_server_side_session(self, find_user):
        find_user.return_value = self.user
        self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": "employee@eas.com", "password": "Correct-Horse-2026"}
            ),
            content_type="application/json",
        )
        session_id = self.client.session["session_id"]
        self.assertIsNotNone(cache.get(f"eas:session:{session_id}"))
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(cache.get(f"eas:session:{session_id}"))
        self.assertIsNone(cache.get(f"eas:idle:{session_id}"))

    @patch("api_core.authn.service.connection")
    @patch("api_core.authn.views.find_user")
    def test_session_idle_timeout_fails_closed_without_extending_absolute_ttl(
        self, find_user, conn
    ):
        find_user.return_value = self.user
        self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {
                    "email": "employee@eas.com",
                    "password": "Correct-Horse-2026",
                }
            ),
            content_type="application/json",
        )
        session_id = self.client.session["session_id"]
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            self.user.id,
            self.user.email,
            self.user.display_name,
            self.user.department_id,
            3,
            False,
        )
        conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [
            ("REQUESTER",)
        ]
        # Do not need a live DB to check revoked inactivity before SQL access.
        cache.delete(f"eas:idle:{session_id}")
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_password_policy_rejects_weak_or_email_localpart_derived_values(self):
        for invalid in (
            "short",
            "Abcdefgh1234!",
            "alllowercase123!",
            "EMPLOYEE-Strong-123!",
            "Password123456!A",
        ):
            with self.subTest(password=invalid), self.assertRaises(PasswordChangeError):
                validate_new_password(invalid, "employee@eas.com")
        self.assertEqual(
            validate_new_password("Different-Strong-123!", "employee@eas.com"),
            "Different-Strong-123!",
        )


class NoDefaultPasswordTests(SimpleTestCase):
    """Demo/seed accounts must never accept a built-in password (README_VI.md)."""

    @override_settings(ENVIRONMENT="development")
    def test_disabled_and_placeholder_hashes_reject_former_default(self):
        from api_core.authn.service import verify_user_password

        for disabled in (
            "!UNUSABLE_DEMO_REQUESTER",
            "pbkdf2_sha256$600000$seed$TempHashForDevOnly00000000000000000000000000000=",
        ):
            self.assertFalse(verify_user_password("Admin@123456", disabled), disabled)

    def test_real_hash_still_verifies(self):
        from api_core.authn.service import verify_user_password

        hashed = make_password("Correct-horse-battery-9")
        self.assertTrue(verify_user_password("Correct-horse-battery-9", hashed))
        self.assertFalse(verify_user_password("wrong", hashed))
