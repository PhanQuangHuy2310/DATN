"""Refresh token: keeps a user signed in after the 30-minute session expires,
rotates on every use, and is refused after logout, replay or a password change."""

import json
import time
from dataclasses import replace
from typing import ClassVar
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import SimpleTestCase

from api_core.authn import refresh as refresh_tokens
from api_core.authn.models import Actor, AuthUser

PASSWORD = "Correct-Horse-2026"


@patch("api_core.authn.views._check_maintenance_login", new=lambda _r, _u: (None, None))
class RefreshTokenTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        cache.clear()
        self.user = AuthUser(
            id=str(uuid4()),
            email="employee@eas.com",
            display_name="Employee",
            department_id=str(uuid4()),
            password_hash=make_password(PASSWORD, hasher="pbkdf2_sha256"),
            auth_version=3,
            is_active=True,
            must_change_password=False,
        )
        patcher = patch("api_core.authn.views.find_user", return_value=self.user)
        patcher.start()
        self.addCleanup(patcher.stop)
        by_id = patch(
            "api_core.authn.views.find_user_by_id", side_effect=lambda _id: self.user
        )
        by_id.start()
        self.addCleanup(by_id.stop)

    def _login(self, **extra):
        return self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": self.user.email, "password": PASSWORD, **extra}),
            content_type="application/json",
        )

    def _expire_session(self):
        session_id = self.client.session["session_id"]
        cache.delete(f"eas:idle:{session_id}")
        cache.delete(f"eas:session:{session_id}")

    def _refresh(self):
        return self.client.post("/api/v1/auth/refresh")

    def test_login_sets_a_restricted_httponly_cookie(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies["eas_refresh"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/api/v1/auth/")
        self.assertEqual(int(cookie["max-age"]), 7 * 24 * 3600)
        self.assertNotIn("eas_refresh", response.content.decode())

    def test_without_remember_me_the_cookie_ends_with_the_browser(self):
        cookie = self._login(remember=False).cookies["eas_refresh"]
        self.assertEqual(cookie["max-age"], "")

    def test_expired_session_is_renewed_and_the_token_rotates(self):
        self._login()
        first = self.client.cookies["eas_refresh"].value
        self._expire_session()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

        response = self._refresh()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], self.user.id)
        second = self.client.cookies["eas_refresh"].value
        self.assertNotEqual(first, second)
        session_id = self.client.session["session_id"]
        self.assertEqual(cache.get(f"eas:idle:{session_id}"), f"{self.user.id}:3")

    def test_replayed_token_revokes_the_whole_family(self):
        self._login()
        stolen = self.client.cookies["eas_refresh"].value
        self.assertEqual(self._refresh().status_code, 200)
        current = self.client.cookies["eas_refresh"].value

        later = time.time() + refresh_tokens.RACE_WINDOW_SECONDS + 5
        with patch("api_core.authn.refresh.time.time", return_value=later):
            self.client.cookies["eas_refresh"] = stolen
            self.assertEqual(self._refresh().status_code, 401)
        # The legitimate holder is signed out too: the family is revoked.
        self.client.cookies["eas_refresh"] = current
        self.assertEqual(self._refresh().status_code, 401)

    def test_two_tabs_refreshing_at_once_do_not_sign_the_user_out(self):
        self._login()
        old = self.client.cookies["eas_refresh"].value
        self.assertEqual(self._refresh().status_code, 200)
        self.client.cookies["eas_refresh"] = old
        response = self._refresh()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "refreshed_elsewhere")

    def test_password_change_invalidates_existing_tokens(self):
        self._login()
        self.user = replace(self.user, auth_version=4)
        response = self._refresh()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.cookies["eas_refresh"].value, "")

    @patch("api_core.authn.views.change_password", return_value=4)
    @patch("api_core.authn.views.load_actor_from_session")
    def test_own_password_change_keeps_this_browser_signed_in(
        self, load_actor, _change
    ):
        self._login()
        old = self.client.cookies["eas_refresh"].value
        load_actor.return_value = Actor(
            id=self.user.id,
            email=self.user.email,
            display_name="Employee",
            department_id=self.user.department_id,
            auth_version=3,
            roles=frozenset({"REQUESTER"}),
            must_change_password=False,
        )
        response = self.client.post(
            "/api/v1/auth/password",
            data=json.dumps(
                {"current_password": PASSWORD, "new_password": "New-Strong-Pass-2026!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        new = self.client.cookies["eas_refresh"].value
        self.assertNotEqual(old, new)
        self.user = replace(self.user, auth_version=4)
        self._expire_session()
        self.assertEqual(self._refresh().status_code, 200)
        # The token from before the change is dead (another device holding it).
        self.client.cookies["eas_refresh"] = old
        self.assertEqual(self._refresh().status_code, 401)

    def test_locked_account_cannot_refresh(self):
        self._login()
        self.user = replace(self.user, is_active=False)
        self.assertEqual(self._refresh().status_code, 401)

    def test_logout_revokes_the_refresh_token(self):
        self._login()
        token = self.client.cookies["eas_refresh"].value
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.cookies["eas_refresh"].value, "")
        self.client.cookies["eas_refresh"] = token
        self.assertEqual(self._refresh().status_code, 401)

    def test_missing_or_forged_cookie_is_rejected(self):
        self.assertEqual(self._refresh().status_code, 401)
        self._login()
        token_id = self.client.cookies["eas_refresh"].value.split(".")[0]
        self.client.cookies["eas_refresh"] = f"{token_id}.forged-secret"
        self.assertEqual(self._refresh().status_code, 401)

    def test_refresh_never_outlives_the_family_lifetime(self):
        self._login(remember=False)
        later = time.time() + 13 * 3600
        with patch("api_core.authn.refresh.time.time", return_value=later):
            # Cache entries carry their own TTL; emulate expiry for LocMem.
            cache.clear()
            self.assertEqual(self._refresh().status_code, 401)
