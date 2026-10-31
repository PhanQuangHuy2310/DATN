from __future__ import annotations

from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from api_core.http import JsonBodyError, api_error, correlation_id, parse_json_object
from api_core.middleware import client_ip

from .login_throttle import (
    clear_account_failures,
    is_throttled,
    register_login_failure,
    throttle_keys,
)
from .service import (
    PasswordChangeError,
    change_password,
    find_user,
    load_actor_from_session,
    require_actor,
    verify_user_password,
)


@ensure_csrf_cookie
@require_GET
def csrf(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "correlation_id": correlation_id(request)})


def _parse_credentials(request: HttpRequest) -> tuple[str, str] | JsonResponse:
    try:
        body = parse_json_object(request, max_bytes=8 * 1024)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    if set(body) != {"username", "password"}:
        return api_error(request, "INVALID_CREDENTIALS", status=401)
    username = body.get("username")
    password = body.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return api_error(request, "INVALID_CREDENTIALS", status=401)
    return username.strip().lower(), password


def _check_maintenance_login(
    request: HttpRequest, user_id: str
) -> tuple[JsonResponse | None, dict[str, Any] | None]:
    from api_core.maintenance import (
        MAINTENANCE_MSG_ADMIN_ACTIVE,
        MAINTENANCE_MSG_USER,
        get_maintenance_info,
        is_admin_user_id,
    )

    m_info = get_maintenance_info()
    is_admin = False
    if m_info.get("active") or m_info.get("status") == "COMPLETED":
        is_admin = is_admin_user_id(user_id)

    if m_info.get("active") and not is_admin:
        err = api_error(
            request,
            "SYSTEM_UNDER_MAINTENANCE",
            status=503,
            fields={"message": [m_info.get("message") or MAINTENANCE_MSG_USER]},
        )
        return err, None

    m_payload = None
    if m_info.get("active"):
        m_payload = {
            "active": True,
            "status": m_info.get("status", "UPDATING"),
            "message": m_info.get("admin_message") or MAINTENANCE_MSG_ADMIN_ACTIVE,
        }
    elif m_info.get("status") == "COMPLETED" and is_admin:
        m_payload = {
            "active": False,
            "status": "COMPLETED",
            "message": m_info.get("admin_message"),
        }
    return None, m_payload


def _establish_user_session(request: HttpRequest, user) -> None:
    request.session.flush()
    request.session.cycle_key()
    request.session["user_id"] = user.id
    request.session["auth_version"] = user.auth_version
    session_id = str(uuid4())
    request.session["session_id"] = session_id
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    cache.set(
        f"eas:session:{session_id}",
        f"{user.id}:{user.auth_version}",
        timeout=settings.SESSION_COOKIE_AGE,
    )
    cache.set(
        f"eas:idle:{session_id}",
        f"{user.id}:{user.auth_version}",
        timeout=settings.EAS_SESSION_IDLE_SECONDS,
    )


@require_POST
def login(request: HttpRequest) -> JsonResponse:
    parsed = _parse_credentials(request)
    if isinstance(parsed, JsonResponse):
        return parsed
    username, password = parsed

    keys = throttle_keys(username, client_ip(request))
    if is_throttled(
        cache,
        keys,
        account_limit=settings.EAS_LOGIN_MAX_ATTEMPTS,
        ip_limit=getattr(settings, "EAS_LOGIN_MAX_IP_ATTEMPTS", 30),
    ):
        return api_error(
            request,
            "LOGIN_RATE_LIMITED",
            status=429,
            headers={"Retry-After": str(settings.EAS_LOGIN_WINDOW_SECONDS)},
        )

    user = find_user(username)
    valid = bool(
        user and user.is_active and verify_user_password(password, user.password_hash)
    )
    if not valid:
        register_login_failure(
            cache, keys, window_seconds=settings.EAS_LOGIN_WINDOW_SECONDS
        )
        return api_error(request, "INVALID_CREDENTIALS", status=401)

    m_err, m_payload = _check_maintenance_login(request, user.id)
    if m_err:
        return m_err

    clear_account_failures(cache, keys)
    _establish_user_session(request, user)

    payload = {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "must_change_password": user.must_change_password,
        },
        "correlation_id": correlation_id(request),
    }
    if m_payload:
        payload["maintenance"] = m_payload
    return JsonResponse(payload)


@require_POST
def logout(request: HttpRequest) -> JsonResponse:
    session_id = request.session.get("session_id")
    if isinstance(session_id, str):
        cache.delete(f"eas:session:{session_id}")
        cache.delete(f"eas:idle:{session_id}")
        cache.set(
            f"eas:session:revoked:{session_id}",
            "1",
            timeout=settings.SESSION_COOKIE_AGE,
        )
    request.session.flush()
    return JsonResponse(
        {"status": "logged_out", "correlation_id": correlation_id(request)}
    )


@require_GET
@require_actor()
def me(request: HttpRequest) -> JsonResponse:
    from api_core.maintenance import (
        MAINTENANCE_MSG_ADMIN_ACTIVE,
        MAINTENANCE_MSG_USER,
        get_maintenance_info,
        is_admin_actor,
    )

    actor = request.actor
    m_info = get_maintenance_info()
    is_admin = is_admin_actor(actor)

    # UC17 can only be operated by GLOBAL / ALL OPS membership; mere
    # OPS_ADMIN membership is not enough. Backend administration APIs still
    # perform their own authorization checks on every operation.
    can_manage_identity = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT EXISTS (
                      SELECT 1 FROM eas.role_membership rm
                      WHERE rm.user_id = %s AND rm.role = 'OPS_ADMIN'
                        AND rm.revoked_at IS NULL
                        AND rm.valid_from <= statement_timestamp()
                        AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                        AND rm.scope_kind = 'GLOBAL' AND rm.type_scope = 'ALL'
                   )""",
                [actor.id],
            )
            row = cursor.fetchone()
            can_manage_identity = bool(row[0]) if row else False
    except (DatabaseError, AttributeError):
        can_manage_identity = False

    payload = {
        "user": {
            "id": actor.id,
            "username": actor.username,
            "display_name": actor.display_name,
            "department_id": actor.department_id,
            "roles": sorted(actor.roles),
            "capabilities": {"identity_manage": can_manage_identity},
            "must_change_password": actor.must_change_password,
        },
        "correlation_id": correlation_id(request),
    }
    if m_info.get("active"):
        payload["maintenance"] = {
            "active": True,
            "status": m_info.get("status", "UPDATING"),
            "message": (
                m_info.get("admin_message") or MAINTENANCE_MSG_ADMIN_ACTIVE
                if is_admin
                else m_info.get("message") or MAINTENANCE_MSG_USER
            ),
        }
    elif m_info.get("status") == "COMPLETED" and is_admin:
        payload["maintenance"] = {
            "active": False,
            "status": "COMPLETED",
            "message": m_info.get("admin_message"),
        }
    return JsonResponse(payload)


@require_POST
def password(request: HttpRequest) -> JsonResponse:
    actor = load_actor_from_session(request)
    if actor is None:
        request.session.flush()
        return api_error(request, "AUTHENTICATION_REQUIRED", status=401)
    try:
        body = parse_json_object(request, max_bytes=8 * 1024)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    old_pwd = body.get("current_password") or body.get("old_password")
    new_pwd = body.get("new_password")
    if not isinstance(old_pwd, str) or not isinstance(new_pwd, str):
        return api_error(request, "INVALID_PASSWORD_CHANGE", status=400)
    allowed_keys = {"current_password", "old_password", "new_password"}
    if not set(body).issubset(allowed_keys):
        return api_error(request, "INVALID_PASSWORD_CHANGE", status=400)
    try:
        new_version = change_password(
            actor=actor,
            current_password=old_pwd,
            new_password=new_pwd,
            correlation_id=correlation_id(request),
        )
    except PasswordChangeError as exc:
        code = str(exc)
        status = 401 if code == "INVALID_CURRENT_PASSWORD" else 400
        return api_error(request, code, status=status)
    request.session["auth_version"] = new_version
    session_id = request.session.get("session_id")
    if not isinstance(session_id, str):
        request.session.flush()
        return api_error(request, "AUTHENTICATION_REQUIRED", status=401)
    cache.set(
        f"eas:session:{session_id}",
        f"{actor.id}:{new_version}",
        timeout=settings.SESSION_COOKIE_AGE,
    )
    cache.set(
        f"eas:idle:{session_id}",
        f"{actor.id}:{new_version}",
        timeout=settings.EAS_SESSION_IDLE_SECONDS,
    )
    request.session.cycle_key()
    return JsonResponse(
        {"status": "password_changed", "correlation_id": correlation_id(request)}
    )
