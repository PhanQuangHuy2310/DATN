import json
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import Client, SimpleTestCase, override_settings

from api_core.authn.models import Actor, AuthUser
from api_core.authn.service import PasswordChangeError, validate_new_password


@override_settings(EAS_LOGIN_MAX_ATTEMPTS=2, EAS_LOGIN_WINDOW_SECONDS=60)
class AuthenticationEndpointTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.user = AuthUser(
            id=str(uuid4()),
            username="employee",
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
                {"username": " Employee ", "password": "Correct-Horse-2026"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["user_id"], self.user.id)
        self.assertEqual(self.client.session["auth_version"], 3)
        session_id = self.client.session["session_id"]
        self.assertEqual(cache.get(f"eas:session:{session_id}"), f"{self.user.id}:3")
        self.assertNotIn("password_hash", response.json()["user"])

        find_user.return_value = None
        invalid = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"username": "unknown", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json()["error"]["code"], "INVALID_CREDENTIALS")

    @patch("api_core.authn.views.find_user", return_value=None)
    def test_login_rate_limit_returns_retry_after(self, _find_user):
        for _ in range(2):
            self.client.post(
                "/api/v1/auth/login",
                data=json.dumps({"username": "employee", "password": "wrong"}),
                content_type="application/json",
            )
        limited = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"username": "employee", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers["Retry-After"], "60")

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

    @patch("api_core.authn.service.load_actor_from_session")
    def test_me_returns_only_current_authorized_actor(self, load_actor):
        load_actor.return_value = Actor(
            id=self.user.id,
            username=self.user.username,
            display_name=self.user.display_name,
            department_id=self.user.department_id,
            auth_version=3,
            roles=frozenset({"REQUESTER", "APPROVER"}),
            must_change_password=False,
        )
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["roles"], ["APPROVER", "REQUESTER"])

    @patch("api_core.authn.service.load_actor_from_session", return_value=None)
    def test_me_fails_closed_for_revoked_session(self, _load_actor):
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)

    @patch("api_core.authn.views.find_user")
    def test_logout_revokes_server_side_session(self, find_user):
        find_user.return_value = self.user
        self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"username": "employee", "password": "Correct-Horse-2026"}),
            content_type="application/json",
        )
        session_id = self.client.session["session_id"]
        self.assertIsNotNone(cache.get(f"eas:session:{session_id}"))
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(cache.get(f"eas:session:{session_id}"))

    def test_password_policy_rejects_weak_or_username_derived_values(self):
        for invalid in ("short", "alllowercase123!", "EMPLOYEE-Strong-123!"):
            with self.subTest(password=invalid), self.assertRaises(PasswordChangeError):
                validate_new_password(invalid, "employee")
        self.assertEqual(
            validate_new_password("Different-Strong-123!", "employee"),
            "Different-Strong-123!",
        )
