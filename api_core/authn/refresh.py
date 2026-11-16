"""Refresh tokens that keep a user signed in after the short session expires.

The session (cookie ``eas_session``) still lasts 30 minutes idle / 8 hours at
most. Next to it, login sets an opaque refresh token in its own HttpOnly cookie
whose path is limited to ``/api/v1/auth/``. When the session is gone the browser
calls ``POST /api/v1/auth/refresh`` and gets a fresh session plus a NEW refresh
token (rotation); the old one stops working.

Storage is the shared cache (Redis), so no database migration is needed:

* ``eas:refresh:<id>``          the live token: digest of its secret, user,
                                auth_version, family, family expiry.
* ``eas:refresh:used:<id>``     a rotated token. Presenting it again outside the
                                short race window means the token was stolen:
                                the whole family is revoked.
* ``eas:refresh:revoked:<fam>`` a revoked family (logout, reuse detection).

A password change, admin reset or role revocation bumps ``auth_version`` and
every refresh token issued before it is refused.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

COOKIE_PATH = "/api/v1/auth/"
# Two tabs may refresh with the same token at the same moment; the loser of
# that race is not treated as a stolen token for a few seconds.
RACE_WINDOW_SECONDS = 30


def cookie_name() -> str:
    return getattr(settings, "EAS_REFRESH_COOKIE_NAME", "eas_refresh")


def _key(token_id: str) -> str:
    return f"eas:refresh:{token_id}"


def _used_key(token_id: str) -> str:
    return f"eas:refresh:used:{token_id}"


def _revoked_key(family: str) -> str:
    return f"eas:refresh:revoked:{family}"


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def lifetime_seconds(remember: bool) -> int:
    if remember:
        return int(getattr(settings, "EAS_REFRESH_REMEMBER_SECONDS", 7 * 24 * 3600))
    return int(getattr(settings, "EAS_REFRESH_SESSION_SECONDS", 12 * 3600))


@dataclass(frozen=True)
class RefreshGrant:
    user_id: str
    auth_version: int
    family: str
    family_expires_at: float
    remember: bool
    portal: str | None


def issue(
    response: HttpResponse,
    *,
    user_id: str,
    auth_version: int,
    remember: bool,
    portal: str | None,
    family: str | None = None,
    family_expires_at: float | None = None,
) -> None:
    """Store a new token and set its cookie on ``response``."""
    now = time.time()
    family = family or uuid4().hex
    expires_at = family_expires_at or now + lifetime_seconds(remember)
    ttl = int(expires_at - now)
    if ttl <= 0:
        clear_cookie(response)
        return
    token_id = uuid4().hex
    secret = secrets.token_urlsafe(32)
    cache.set(
        _key(token_id),
        {
            "digest": _digest(secret),
            "user_id": user_id,
            "auth_version": auth_version,
            "family": family,
            "family_expires_at": expires_at,
            "remember": remember,
            "portal": portal,
        },
        timeout=ttl,
    )
    response.set_cookie(
        cookie_name(),
        f"{token_id}.{secret}",
        # Without "remember me" the cookie dies with the browser.
        max_age=ttl if remember else None,
        path=COOKIE_PATH,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )


def clear_cookie(response: HttpResponse) -> None:
    response.delete_cookie(cookie_name(), path=COOKIE_PATH, samesite="Lax")


def _split(raw: str | None) -> tuple[str, str] | None:
    if not raw or raw.count(".") != 1:
        return None
    token_id, secret = raw.split(".")
    if len(token_id) != 32 or not secret or len(secret) > 128:
        return None
    return token_id, secret


class RefreshRejected(Exception):
    """The token is missing, expired, revoked or replayed."""


class RefreshRaced(Exception):
    """Another tab rotated this token a moment ago; its new cookie is already set."""


def consume(request: HttpRequest) -> RefreshGrant:
    """Validate the cookie and retire the token (one use). Raises on failure."""
    parts = _split(request.COOKIES.get(cookie_name()))
    if parts is None:
        raise RefreshRejected
    token_id, secret = parts
    stored: dict[str, Any] | None = cache.get(_key(token_id))
    if stored is None:
        used = cache.get(_used_key(token_id))
        if used and hmac.compare_digest(used["digest"], _digest(secret)):
            if time.time() - used["rotated_at"] <= RACE_WINDOW_SECONDS:
                raise RefreshRaced
            # A rotated token came back: someone else holds a copy.
            revoke_family(used["family"], used["ttl"])
        raise RefreshRejected
    if not hmac.compare_digest(stored["digest"], _digest(secret)):
        raise RefreshRejected
    if cache.get(_revoked_key(stored["family"])):
        cache.delete(_key(token_id))
        raise RefreshRejected
    ttl = max(1, int(stored["family_expires_at"] - time.time()))
    cache.delete(_key(token_id))
    cache.set(
        _used_key(token_id),
        {
            "digest": stored["digest"],
            "family": stored["family"],
            "rotated_at": time.time(),
            "ttl": ttl,
        },
        timeout=ttl,
    )
    return RefreshGrant(
        user_id=stored["user_id"],
        auth_version=int(stored["auth_version"]),
        family=stored["family"],
        family_expires_at=float(stored["family_expires_at"]),
        remember=bool(stored["remember"]),
        portal=stored.get("portal"),
    )


def revoke_family(family: str, ttl: int | None = None) -> None:
    cache.set(
        _revoked_key(family),
        "1",
        timeout=ttl or lifetime_seconds(True),
    )


def reissue(
    request: HttpRequest, response: HttpResponse, *, user_id: str, auth_version: int
) -> None:
    """After the user changes their own password: retire the old family and give
    this browser a new token bound to the new auth_version (same remember choice
    and portal). Without a valid token nothing is issued."""
    parts = _split(request.COOKIES.get(cookie_name()))
    if parts is None:
        return
    token_id, secret = parts
    stored = cache.get(_key(token_id))
    if (
        not stored
        or stored["user_id"] != user_id
        or not hmac.compare_digest(stored["digest"], _digest(secret))
    ):
        return
    revoke_family(stored["family"])
    cache.delete(_key(token_id))
    issue(
        response,
        user_id=user_id,
        auth_version=auth_version,
        remember=bool(stored["remember"]),
        portal=stored.get("portal"),
    )


def revoke_from_request(request: HttpRequest) -> None:
    """Logout: the presented token and every token rotated from it stop working."""
    parts = _split(request.COOKIES.get(cookie_name()))
    if parts is None:
        return
    token_id, secret = parts
    stored = cache.get(_key(token_id))
    if stored and hmac.compare_digest(stored["digest"], _digest(secret)):
        revoke_family(stored["family"])
        cache.delete(_key(token_id))
