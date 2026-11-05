from __future__ import annotations

import hmac
import logging
import secrets
import smtplib
from typing import Any
from uuid import UUID, uuid4

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import DatabaseError, connection, transaction
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
    verify_login_password,
)

logger = logging.getLogger(__name__)


def _email_recipients(recipients: list[str]) -> list[str]:
    test_recipient = settings.EAS_EMAIL_TEST_RECIPIENT
    return [test_recipient] if test_recipient else recipients


def _normalized_login_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    accepted_domains = {settings.EAS_LOGIN_EMAIL_DOMAIN, "eas.com"}
    if not any(email.endswith(f"@{domain}") for domain in accepted_domains):
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


@ensure_csrf_cookie
@require_GET
def csrf(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "correlation_id": correlation_id(request)})


def _parse_credentials(
    request: HttpRequest,
) -> tuple[str, str, str | None] | JsonResponse:
    try:
        body = parse_json_object(request, max_bytes=8 * 1024)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    valid_keys = {"email", "password", "portal"}
    if not (
        {"email", "password"}.issubset(set(body)) and set(body).issubset(valid_keys)
    ):
        return api_error(request, "INVALID_CREDENTIALS", status=401)
    email = _normalized_login_email(body.get("email"))
    password = body.get("password")
    portal = body.get("portal") if isinstance(body.get("portal"), str) else None
    if email is None or not isinstance(password, str):
        return api_error(request, "INVALID_CREDENTIALS", status=401)
    return email, password, portal


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
    email, password, portal_body = parsed
    portal = request.headers.get("X-EAS-Portal") or portal_body
    if portal == "admin" and email != "admin@eas.com":
        return api_error(
            request,
            "ACCESS_DENIED",
            status=403,
            fields={
                "portal": [
                    "Tài khoản nhân viên không được phép đăng nhập vào Cổng Quản trị (8081). Vui lòng đăng nhập tại Cổng Nhân viên (8080)."
                ]
            },
        )
    if portal == "client" and email == "admin@eas.com":
        return api_error(
            request,
            "ACCESS_DENIED",
            status=403,
            fields={
                "portal": [
                    "Tài khoản Quản trị viên (admin@eas.com) không được phép đăng nhập vào Cổng Nhân viên (8080). Vui lòng sử dụng Cổng Quản trị (8081)."
                ]
            },
        )

    keys = throttle_keys(email, client_ip(request))
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

    user = find_user(email)
    if not verify_login_password(user, password):
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
            "email": user.email,
            "display_name": user.display_name,
            "must_change_password": user.must_change_password,
        },
        "correlation_id": correlation_id(request),
    }
    if m_payload:
        payload["maintenance"] = m_payload
    return JsonResponse(payload)


def _password_reset_request_key(email: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode(), email.encode(), "sha256"
    ).hexdigest()
    return f"eas:password-reset-request:{digest}"


def _temporary_password(email: str) -> str:
    import string

    from .service import validate_new_password

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-+="
    for _ in range(10):
        password = "".join(secrets.choice(alphabet) for _ in range(28))
        try:
            validate_new_password(password, email)
            return password
        except PasswordChangeError:
            continue
    raise RuntimeError("Unable to generate a valid temporary password.")


def _global_ops_admin(request: HttpRequest) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT EXISTS (
                 SELECT 1 FROM eas.role_membership
                 WHERE user_id=%s AND role='OPS_ADMIN'
                   AND scope_kind='GLOBAL' AND type_scope='ALL'
                   AND revoked_at IS NULL
                   AND valid_from <= statement_timestamp()
                   AND (valid_to IS NULL OR valid_to > statement_timestamp())
               )""",
            [request.actor.id],
        )
        return bool(cursor.fetchone()[0])


def _password_reset_admin_emails(cursor) -> list[str]:
    cursor.execute(
        """SELECT DISTINCT u.email
           FROM eas.app_user u
           JOIN eas.role_membership rm ON rm.user_id=u.id
           WHERE u.is_active AND rm.role='OPS_ADMIN'
             AND rm.scope_kind='GLOBAL' AND rm.type_scope='ALL'
             AND rm.revoked_at IS NULL
             AND rm.valid_from <= statement_timestamp()
             AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
           ORDER BY u.email"""
    )
    return [row[0] for row in cursor.fetchall()]


@require_POST
def password_reset_request(request: HttpRequest) -> JsonResponse:
    try:
        body = parse_json_object(request, max_bytes=8 * 1024)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    email = _normalized_login_email(body.get("email"))
    if email is None:
        return api_error(request, "INVALID_EMAIL", status=400)
    if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
        return api_error(request, "EMAIL_DELIVERY_UNAVAILABLE", status=503)

    throttle_key = _password_reset_request_key(email)
    cooldown_key = f"{throttle_key}:cooldown"
    ip_digest = hmac.new(
        settings.SECRET_KEY.encode(),
        (client_ip(request).strip() or "unknown").encode(),
        "sha256",
    ).hexdigest()
    ip_key = f"eas:password-reset:ip:{ip_digest}"
    if not cache.add(ip_key, 1, timeout=3600):
        try:
            if cache.incr(ip_key) > 20:
                return JsonResponse(
                    {
                        "status": "accepted",
                        "message": "Nếu tài khoản tồn tại, yêu cầu sẽ được xem xét theo quy trình quản trị.",
                    },
                    status=202,
                )
        except ValueError:
            cache.add(ip_key, 1, timeout=3600)
    if not cache.add(cooldown_key, "1", timeout=300):
        return JsonResponse(
            {
                "status": "accepted",
                "message": "Nếu tài khoản tồn tại, yêu cầu sẽ được xem xét theo quy trình quản trị.",
            },
            status=202,
        )

    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT id::text, display_name FROM eas.app_user WHERE email=%s AND is_active",
                [email],
            )
            user = cursor.fetchone()
            if not user:
                return JsonResponse(
                    {
                        "status": "accepted",
                        "message": "Nếu tài khoản tồn tại, yêu cầu sẽ được xem xét theo quy trình quản trị.",
                    },
                    status=202,
                )
            cursor.execute(
                """UPDATE eas.password_reset_request
                   SET status='EXPIRED', resolved_at=statement_timestamp()
                   WHERE user_id=%s AND status='PENDING'
                     AND expires_at <= statement_timestamp()""",
                [user[0]],
            )
            cursor.execute(
                """SELECT id::text FROM eas.password_reset_request
                   WHERE user_id=%s AND status='PENDING'
                     AND expires_at > statement_timestamp()
                   FOR UPDATE""",
                [user[0]],
            )
            existing = cursor.fetchone()
            if existing:
                request_id = existing[0]
            else:
                cursor.execute(
                    """INSERT INTO eas.password_reset_request
                       (user_id, requested_email, expires_at)
                       VALUES (%s,%s,statement_timestamp()+interval '24 hours')
                       ON CONFLICT (user_id) WHERE status='PENDING' DO NOTHING
                       RETURNING id::text""",
                    [user[0], email],
                )
                created = cursor.fetchone()
                if created:
                    request_id = created[0]
                else:
                    cursor.execute(
                        """SELECT id::text FROM eas.password_reset_request
                           WHERE user_id=%s AND status='PENDING'
                             AND expires_at > statement_timestamp()""",
                        [user[0]],
                    )
                    pending = cursor.fetchone()
                    if not pending:
                        raise DatabaseError(
                            "Password reset request conflict was not recoverable."
                        )
                    request_id = pending[0]
            admin_emails = _password_reset_admin_emails(cursor)
            if not admin_emails:
                logger.error(
                    "password_reset_admin_unavailable",
                    extra={"correlation_id": correlation_id(request)},
                )
                return JsonResponse(
                    {
                        "status": "accepted",
                        "message": "Nếu tài khoản tồn tại, yêu cầu sẽ được xem xét theo quy trình quản trị.",
                    },
                    status=202,
                )
        try:
            send_mail(
                subject="Yêu cầu xác nhận đặt lại mật khẩu EAS",
                message=(
                    f"Nhân viên {user[1]} ({email}) đã yêu cầu đặt lại mật khẩu.\n"
                    "Hãy đăng nhập cổng quản trị EAS, mở Danh tính & phân quyền "
                    "và xác minh danh tính trước khi phê duyệt.\n"
                    f"Mã yêu cầu: {request_id}\n"
                    "Không trả lời email này để gửi mật khẩu."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=_email_recipients(admin_emails),
                fail_silently=False,
            )
        except (OSError, smtplib.SMTPException) as exc:
            cache.delete(cooldown_key)
            logger.error(
                "password_reset_admin_notification_failed",
                extra={
                    "correlation_id": correlation_id(request),
                    "error_type": type(exc).__name__,
                },
            )
            return JsonResponse(
                {
                    "status": "accepted",
                    "message": "Nếu tài khoản tồn tại, yêu cầu sẽ được xem xét theo quy trình quản trị.",
                },
                status=202,
            )
    except DatabaseError:
        cache.delete(cooldown_key)
        raise

    return JsonResponse(
        {
            "status": "accepted",
            "message": "Nếu tài khoản tồn tại, yêu cầu sẽ được xem xét theo quy trình quản trị.",
        },
        status=202,
    )


@require_GET
@require_actor("OPS_ADMIN")
def password_reset_requests(request: HttpRequest) -> JsonResponse:
    if not _global_ops_admin(request):
        return api_error(request, "FORBIDDEN", status=403)
    with connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """SELECT pr.id::text, u.email, u.display_name, d.name,
                      pr.requested_at, pr.expires_at
               FROM eas.password_reset_request pr
               JOIN eas.app_user u ON u.id=pr.user_id
               JOIN eas.department d ON d.id=u.department_id
               WHERE pr.status='PENDING'
                 AND pr.expires_at > statement_timestamp()
               ORDER BY pr.requested_at, pr.id"""
        )
        rows = cursor.fetchall()
    return JsonResponse(
        {
            "items": [
                {
                    "id": row[0],
                    "email": row[1],
                    "display_name": row[2],
                    "department": row[3],
                    "requested_at": row[4].isoformat(),
                    "expires_at": row[5].isoformat(),
                }
                for row in rows
            ]
        }
    )


@require_POST
@require_actor("OPS_ADMIN")
def password_reset_approve(request: HttpRequest, request_id: str) -> JsonResponse:
    if not _global_ops_admin(request):
        return api_error(request, "FORBIDDEN", status=403)
    try:
        body = parse_json_object(request, max_bytes=8 * 1024)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    reason = body.get("reason")
    if (
        set(body) != {"reason"}
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2000
    ):
        return api_error(request, "RESET_APPROVAL_REASON_REQUIRED", status=400)

    from django.contrib.auth.hashers import make_password
    from django.db import transaction

    from api_core.workflow.service import _append_admin_audit

    temporary_password = None
    target_email = ""
    target_name = ""
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(true)")
        cursor.execute(
            """SELECT pr.user_id::text, pr.requested_email, u.email,
                      u.display_name, u.department_id::text, u.auth_version
               FROM eas.password_reset_request pr
               JOIN eas.app_user u ON u.id=pr.user_id
               WHERE pr.id=%s AND pr.status='PENDING'
                 AND pr.expires_at > statement_timestamp()
                 AND u.is_active
               FOR UPDATE OF pr,u""",
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            return api_error(request, "RESET_REQUEST_NOT_FOUND_OR_EXPIRED", status=404)
        (
            user_id,
            requested_email,
            target_email,
            target_name,
            department_id,
            auth_version,
        ) = row
        if request.actor.id == user_id:
            return api_error(request, "CANNOT_APPROVE_OWN_RESET", status=403)
        if target_email != requested_email:
            return api_error(request, "RESET_REQUEST_EMAIL_CHANGED", status=409)
        temporary_password = _temporary_password(target_email)
        new_version = auth_version + 1
        cursor.execute(
            """UPDATE eas.app_user
               SET password_hash=%s, auth_version=%s, must_change_password=true
               WHERE id=%s""",
            [make_password(temporary_password, hasher="argon2"), new_version, user_id],
        )
        cursor.execute(
            """UPDATE eas.password_reset_request
               SET status='APPROVED', resolved_at=statement_timestamp(),
                   resolved_by=%s, resolution_reason=%s
               WHERE id=%s""",
            [request.actor.id, reason.strip(), request_id],
        )
        cursor.execute(
            "UPDATE eas.security_epoch SET version=version+1,updated_at=statement_timestamp() WHERE id=1"
        )
        _append_admin_audit(
            cursor,
            actor_id=request.actor.id,
            actor_kind="HUMAN",
            action="PASSWORD_RESET_APPROVED",
            target_type="app_user",
            target_id=user_id,
            department_id=department_id,
            details={"request_id": request_id, "auth_version": new_version},
            reason=reason.strip(),
            correlation_id=correlation_id(request),
        )

    try:
        send_mail(
            subject="Mật khẩu tạm thời cho tài khoản EAS",
            message=(
                f"Xin chào {target_name},\n\n"
                "Yêu cầu đặt lại mật khẩu của bạn đã được quản trị viên xác nhận.\n"
                f"Mật khẩu tạm thời: {temporary_password}\n\n"
                "Đăng nhập bằng email nhân viên và mật khẩu tạm này. Hệ thống sẽ "
                "bắt buộc bạn đổi mật khẩu riêng ngay sau khi đăng nhập.\n"
                "Nếu bạn không yêu cầu thay đổi, hãy liên hệ quản trị viên."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=_email_recipients([target_email]),
            fail_silently=False,
        )
    except (OSError, smtplib.SMTPException) as exc:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(true)")
            cursor.execute(
                """UPDATE eas.password_reset_request
                   SET status='PENDING', resolved_at=NULL, resolved_by=NULL
                   WHERE id=%s AND status='APPROVED'""",
                [request_id],
            )
        logger.error(
            "password_reset_temporary_password_delivery_failed",
            extra={
                "correlation_id": correlation_id(request),
                "request_id": request_id,
                "error_type": type(exc).__name__,
            },
        )
        return api_error(request, "PASSWORD_RESET_DELIVERY_FAILED", status=503)

    return JsonResponse({"status": "approved", "email": target_email})


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


def _is_valid_uuid(val: Any) -> bool:
    if not val:
        return False
    try:
        UUID(str(val))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


JOB_TITLES = (
    ("OPS_ADMIN", "Quản trị hệ thống"),
    ("POLICY_ADMIN", "Quản trị chính sách"),
    ("APPROVER", "Người phê duyệt"),
    ("EXECUTOR", "Người thực hiện"),
)
# REQUESTER/ACCEPTOR are held by every employee, so they read "Nhân viên".


def _job_title(roles) -> str:
    """Most senior role, shown as the job title in the header."""
    return next((title for role, title in JOB_TITLES if role in roles), "Nhân viên")


def _get_actor_permissions(actor: Any) -> dict[str, Any]:
    modules_list = []
    by_module: dict[str, dict[str, bool]] = {}

    # Module permissions are keyed by eas.app_user (migration 2026-11-03_01:
    # role_module_permission + user_permissions). The legacy eas.users table
    # was quarantined, so the actor id is passed directly.
    user_uuid = actor.id if _is_valid_uuid(getattr(actor, "id", None)) else None
    try:
        with connection.cursor() as cursor:
            if user_uuid:
                cursor.execute(
                    """SELECT module_code, module_name, group_name, route_path, icon_name,
                              target_app, can_view, can_create, can_update, can_delete,
                              show_on_sidebar, permission_source
                       FROM eas.get_effective_user_permissions(%s::uuid)""",
                    [user_uuid],
                )
                for r in cursor.fetchall():
                    mod_data = {
                        "module_code": r[0],
                        "module_name": r[1],
                        "group_name": r[2],
                        "route_path": r[3],
                        "icon_name": r[4],
                        "target_app": r[5],
                        "can_view": bool(r[6]),
                        "can_create": bool(r[7]),
                        "can_update": bool(r[8]),
                        "can_delete": bool(r[9]),
                        "show_on_sidebar": bool(r[10]),
                        "permission_source": r[11],
                    }
                    modules_list.append(mod_data)
                    by_module[r[0]] = {
                        "can_view": mod_data["can_view"],
                        "can_create": mod_data["can_create"],
                        "can_update": mod_data["can_update"],
                        "can_delete": mod_data["can_delete"],
                    }
    except DatabaseError as exc:
        logger.warning(
            "Error fetching effective permissions for actor %s: %s",
            getattr(actor, "email", ""),
            exc,
        )

    # A database without role defaults (e.g. before the migration ran) yields
    # rows that grant nothing; fall back to the role-derived matrix below.
    if modules_list:
        return {"modules": modules_list, "by_module": by_module}
    modules_list, by_module = [], {}

    actor_roles = getattr(actor, "roles", frozenset())
    is_admin = bool({"OPS_ADMIN", "POLICY_ADMIN", "ADMIN"}.intersection(actor_roles))
    is_auditor = "AUDITOR" in actor_roles
    is_manager = bool({"APPROVER", "MANAGER"}.intersection(actor_roles))

    STANDARD_MODULES = [
        (
            "dashboard",
            "Tổng quan",
            "Giám sát",
            "/dashboard",
            "LayoutDashboard",
            "BOTH",
            True,
            is_admin,
            is_admin,
            is_admin,
        ),
        (
            "requests_workflows",
            "Yêu cầu & Quy trình",
            "Luồng công việc",
            "/requests-workflows",
            "GitPullRequest",
            "BOTH",
            True,
            True,
            is_admin or is_manager,
            is_admin,
        ),
        (
            "org_chart",
            "Sơ đồ công ty",
            "Tổ chức & Nhân sự",
            "/org-chart",
            "Network",
            "BOTH",
            True,
            is_admin,
            is_admin,
            is_admin,
        ),
        (
            "users",
            "Người dùng",
            "Tổ chức & Nhân sự",
            "/users",
            "Users",
            "ADMIN",
            is_admin,
            is_admin,
            is_admin,
            is_admin,
        ),
        (
            "permissions",
            "Phân quyền",
            "Tổ chức & Nhân sự",
            "/permissions",
            "ShieldCheck",
            "ADMIN",
            is_admin,
            is_admin,
            is_admin,
            is_admin,
        ),
        (
            "regulations",
            "Quy định",
            "Tri thức & AI",
            "/regulations",
            "BookOpenCheck",
            "BOTH",
            True,
            is_admin or "POLICY_ADMIN" in actor_roles,
            is_admin or "POLICY_ADMIN" in actor_roles,
            is_admin,
        ),
        (
            "ai_engine",
            "Quản trị AI",
            "Tri thức & AI",
            "/ai-engine",
            "BrainCircuit",
            "ADMIN",
            is_admin or "POLICY_ADMIN" in actor_roles,
            is_admin or "POLICY_ADMIN" in actor_roles,
            is_admin or "POLICY_ADMIN" in actor_roles,
            is_admin,
        ),
        (
            "api_management",
            "Quản lý API",
            "Hệ thống & Tích hợp",
            "/api-management",
            "Webhook",
            "ADMIN",
            is_admin,
            is_admin,
            is_admin,
            is_admin,
        ),
        (
            "system_versions",
            "Phiên bản hệ thống",
            "Hệ thống & Tích hợp",
            "/system-versions",
            "History",
            "ADMIN",
            is_admin or is_auditor,
            is_admin,
            is_admin,
            is_admin,
        ),
    ]

    for (
        code,
        name,
        grp,
        route,
        icon,
        target,
        can_v,
        can_c,
        can_u,
        can_d,
    ) in STANDARD_MODULES:
        show_sb = can_v or can_c or can_u or can_d
        m_item = {
            "module_code": code,
            "module_name": name,
            "group_name": grp,
            "route_path": route,
            "icon_name": icon,
            "target_app": target,
            "can_view": can_v,
            "can_create": can_c,
            "can_update": can_u,
            "can_delete": can_d,
            "show_on_sidebar": show_sb,
            "permission_source": "ROLE_FALLBACK",
        }
        modules_list.append(m_item)
        by_module[code] = {
            "can_view": can_v,
            "can_create": can_c,
            "can_update": can_u,
            "can_delete": can_d,
        }

    return {"modules": modules_list, "by_module": by_module}


@require_GET
@require_actor()
def permissions_me(request: HttpRequest) -> JsonResponse:
    perms = _get_actor_permissions(request.actor)
    return JsonResponse(
        {"permissions": perms, "correlation_id": correlation_id(request)}
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
    profile: dict[str, Any] = {}
    try:
        with connection.cursor() as cursor:
            # One round trip: identity capability + profile shown in the header & profile page.
            cursor.execute(
                """SELECT EXISTS (
                      SELECT 1 FROM eas.role_membership rm
                      WHERE rm.user_id = u.id AND rm.role = 'OPS_ADMIN'
                        AND rm.revoked_at IS NULL
                        AND rm.valid_from <= statement_timestamp()
                        AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                        AND rm.scope_kind = 'GLOBAL' AND rm.type_scope = 'ALL'
                   ), u.employee_code, d.code, d.name,
                   ws.status_code, ws.status_label, ws.detail_reason,
                   u.manager_id::text, m.display_name
                   FROM eas.app_user u
                   LEFT JOIN eas.department d ON d.id = u.department_id
                   LEFT JOIN eas.app_user m ON m.id = u.manager_id
                   LEFT JOIN LATERAL eas.get_user_working_status(u.id, now()) ws ON true
                   WHERE u.id = %s""",
                [actor.id],
            )
            row = cursor.fetchone()
            can_manage_identity = bool(row[0]) if row else False
            if row and len(row) >= 7:
                profile = {
                    "employee_code": row[1],
                    "department_code": row[2],
                    "department_name": row[3],
                    "working_status": {
                        "code": row[4] or "DANG_LAM",
                        "label": row[5] or "Đang làm",
                        "detail": row[6] or "",
                    },
                    "manager_id": row[7] if len(row) > 7 else None,
                    "manager_name": row[8] if len(row) > 8 else None,
                }
    except (DatabaseError, AttributeError):
        can_manage_identity = False

    payload = {
        "user": {
            "id": actor.id,
            "email": actor.email,
            "display_name": actor.display_name,
            "department_id": actor.department_id,
            "roles": sorted(actor.roles),
            "job_title": _job_title(actor.roles),
            **profile,
            "capabilities": {"identity_manage": can_manage_identity},
            "must_change_password": actor.must_change_password,
            "permissions": _get_actor_permissions(actor),
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
    # A stolen session must not become an oracle for guessing the current
    # password: reuse the login account+IP budget for wrong current passwords.
    keys = throttle_keys(actor.email, client_ip(request))
    if is_throttled(
        cache,
        keys,
        account_limit=settings.EAS_LOGIN_MAX_ATTEMPTS,
        ip_limit=getattr(settings, "EAS_LOGIN_MAX_IP_ATTEMPTS", 30),
    ):
        return api_error(
            request,
            "PASSWORD_CHANGE_RATE_LIMITED",
            status=429,
            headers={"Retry-After": str(settings.EAS_LOGIN_WINDOW_SECONDS)},
        )
    try:
        new_version = change_password(
            actor=actor,
            current_password=old_pwd,
            new_password=new_pwd,
            correlation_id=correlation_id(request),
        )
    except PasswordChangeError as exc:
        code = str(exc)
        if code == "INVALID_CURRENT_PASSWORD":
            register_login_failure(
                cache, keys, window_seconds=settings.EAS_LOGIN_WINDOW_SECONDS
            )
            return api_error(request, code, status=401)
        return api_error(request, code, status=400)
    clear_account_failures(cache, keys)
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
