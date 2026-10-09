from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from uuid import UUID, uuid4

from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import connection, transaction
from django.http import HttpRequest, HttpResponse
from psycopg.types.json import Jsonb

from api_core.audit import canonical_sha256
from api_core.http import api_error

from .models import Actor, AuthUser


class PasswordChangeError(ValueError):
    pass


def validate_new_password(password: object, username: str) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise PasswordChangeError("PASSWORD_POLICY_VIOLATION")
    if username.lower() in password.lower():
        raise PasswordChangeError("PASSWORD_POLICY_VIOLATION")
    required = (
        any(char.islower() for char in password),
        any(char.isupper() for char in password),
        any(char.isdigit() for char in password),
        any(not char.isalnum() for char in password),
    )
    if not all(required):
        raise PasswordChangeError("PASSWORD_POLICY_VIOLATION")
    return password


def change_password(
    *, actor: Actor, current_password: object, new_password: object, correlation_id: str
) -> int:
    new_password = validate_new_password(new_password, actor.username)
    now = datetime.now(timezone.utc)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(true)")
        cursor.execute(
            """
            SELECT password_hash,auth_version FROM eas.app_user
            WHERE id=%s AND is_active FOR UPDATE
            """,
            [actor.id],
        )
        row = cursor.fetchone()
        if (
            not row
            or not isinstance(current_password, str)
            or not check_password(current_password, row[0])
        ):
            raise PasswordChangeError("INVALID_CURRENT_PASSWORD")
        if check_password(new_password, row[0]):
            raise PasswordChangeError("PASSWORD_REUSE_NOT_ALLOWED")
        new_version = row[1] + 1
        cursor.execute(
            """
            UPDATE eas.app_user SET password_hash=%s,auth_version=%s,
              must_change_password=false WHERE id=%s
            """,
            [make_password(new_password, hasher="argon2"), new_version, actor.id],
        )
        cursor.execute(
            "UPDATE eas.security_epoch SET version=version+1,updated_at=%s WHERE id=1",
            [now],
        )
        cursor.execute("SELECT seq,last_hash FROM eas.lock_audit_head('ADMIN')")
        head = cursor.fetchone()
        if not head:
            raise PasswordChangeError("AUDIT_HEAD_MISSING")
        event_id = str(uuid4())
        sequence = head[0] + 1
        previous_hash = head[1]
        occurred_at = now.isoformat(timespec="microseconds").replace("+00:00", "Z")
        reason = "User changed their own password."
        details = {"auth_version": new_version}
        event = {
            "action": "PASSWORD_CHANGED",
            "actor_id": actor.id,
            "actor_kind": "HUMAN",
            "correlation_id": correlation_id,
            "department_id": actor.department_id,
            "details": details,
            "hash_version": 1,
            "id": event_id,
            "occurred_at": occurred_at,
            "prev_hash": previous_hash,
            "reason": reason,
            "scope_key": "ADMIN",
            "seq": str(sequence),
            "target_id": actor.id,
            "target_type": "app_user",
            "type_id": None,
        }
        cursor.execute(
            """
            INSERT INTO eas.admin_event(
              id,seq,actor_id,actor_kind,action,target_type,target_id,department_id,
              type_id,details,reason,correlation_id,occurred_at,hash_version,prev_hash,hash
            ) VALUES (%s,%s,%s,'HUMAN','PASSWORD_CHANGED','app_user',%s,%s,
                      NULL,%s,%s,%s,%s,1,%s,%s)
            """,
            [
                event_id,
                sequence,
                actor.id,
                actor.id,
                actor.department_id,
                Jsonb(details),
                reason,
                correlation_id,
                now,
                previous_hash,
                canonical_sha256(event),
            ],
        )
    return new_version


def find_user(username: str) -> AuthUser | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text, username, display_name, department_id::text,
                   password_hash, auth_version, is_active, must_change_password
            FROM eas.app_user
            WHERE username = %s
            """,
            [username],
        )
        row = cursor.fetchone()
    return AuthUser(*row) if row else None


def load_actor_from_session(request: HttpRequest) -> Actor | None:
    user_id = request.session.get("user_id")
    auth_version = request.session.get("auth_version")
    session_id = request.session.get("session_id")
    if (
        not isinstance(user_id, str)
        or not isinstance(auth_version, int)
        or not isinstance(session_id, str)
    ):
        return None
    try:
        session_id = str(UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        return None
    active_session = cache.get(f"eas:session:{session_id}")
    if active_session != f"{user_id}:{auth_version}":
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text, username, display_name, department_id::text,
                   auth_version, must_change_password
            FROM eas.app_user
            WHERE id = %s AND is_active AND auth_version = %s
            """,
            [user_id, auth_version],
        )
        user = cursor.fetchone()
        if not user:
            return None
        cursor.execute(
            """
            SELECT DISTINCT role
            FROM eas.role_membership
            WHERE user_id = %s
              AND revoked_at IS NULL
              AND valid_from <= statement_timestamp()
              AND (valid_to IS NULL OR valid_to > statement_timestamp())
            """,
            [user_id],
        )
        roles = frozenset(row[0] for row in cursor.fetchall())
    return Actor(
        id=user[0],
        username=user[1],
        display_name=user[2],
        department_id=user[3],
        auth_version=user[4],
        roles=roles,
        must_change_password=user[5],
    )


def require_actor(*required_roles: str) -> Callable:
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            actor = load_actor_from_session(request)
            if actor is None:
                request.session.flush()
                return api_error(request, "AUTHENTICATION_REQUIRED", status=401)
            if actor.must_change_password and request.path != "/api/v1/auth/password":
                return api_error(request, "PASSWORD_CHANGE_REQUIRED", status=403)
            if required_roles and not actor.roles.intersection(required_roles):
                return api_error(request, "FORBIDDEN", status=403)
            request.actor = actor
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
