"""Org chart, user management and RBAC matrix (admin portal, phase 4).

Reads and writes only the core identity tables (app_user, department,
role_membership, role, modules, role_module_permission, user_permissions);
the parallel eas.users/roles/... set was retired by migration 11.
User create/update/lock goes through administration.service.mutate so it gets
the same validation, password policy, idempotency and audit chain as the
identity API. AUDITOR is read-only; every write is recorded in admin_event.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.http import JsonResponse

from api_core.authn.module_access import ADMIN_ROLES, NEVER_FOR_EMPLOYEES, can
from api_core.authn.service import require_actor
from api_core.http import JsonBodyError, api_error, correlation_id, parse_json_object
from api_core.workflow.service import CommandError, _append_admin_audit

from .service import mutate, read_record, system_account_sql

VN_TZ = timezone(timedelta(hours=7))
READ_ROLES = ("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
WRITE_ROLES = frozenset({"OPS_ADMIN", "POLICY_ADMIN"})
PERMISSION_FIELDS = ("can_view", "can_create", "can_update", "can_delete")
LEAVE_TYPES = {"PAID_LEAVE", "UNPAID_LEAVE", "LATE_IN", "EARLY_OUT", "BUSINESS_TRIP"}
# Business roles an employee account may hold (admin roles live on admin accounts).
EMPLOYEE_ROLES = ("APPROVER", "EXECUTOR", "ACCEPTOR", "REQUESTER")
# Roles the user screen may grant. AUDITOR (global read-only audit) is an
# employee duty too (M3), but like APPROVER only an administrator grants it.
ASSIGNABLE_ROLES = (*EMPLOYEE_ROLES, "AUDITOR")
ADMIN_GRANTED_ROLES = frozenset({"APPROVER", "AUDITOR"})
DEPARTMENT_SCOPED_ROLES = {"APPROVER", "EXECUTOR"}
# The most senior role is shown as the user's role/job title.
ROLE_PRIORITY = (
    "OPS_ADMIN",
    "POLICY_ADMIN",
    "AUDITOR",
    "APPROVER",
    "EXECUTOR",
    "ACCEPTOR",
    "REQUESTER",
)
STAGE_SQL = """CASE r.status
    WHEN 'DRAFT' THEN 'YEU_CAU' WHEN 'NEEDS_INFO' THEN 'YEU_CAU'
    WHEN 'PENDING_APPROVAL' THEN 'PHE_DUYET'
    WHEN 'READY_FOR_EXECUTION' THEN 'THUC_HIEN' WHEN 'IN_PROGRESS' THEN 'THUC_HIEN'
    WHEN 'WAITING_FOR_ACCEPTANCE' THEN 'NGHIEM_THU'
    ELSE 'HOAN_THANH' END"""
STAGE_LABELS = {
    "YEU_CAU": "Yêu cầu",
    "PHE_DUYET": "Phê duyệt",
    "THUC_HIEN": "Thực hiện",
    "NGHIEM_THU": "Nghiệm thu",
    "HOAN_THANH": "Hoàn thành",
}
JOINED_AS_LABELS = {
    "REQUESTER": "Người yêu cầu",
    "APPROVER": "Người phê duyệt",
    "EXECUTOR": "Người thực hiện",
}
ACTIVE_MEMBERSHIP = (
    "m.revoked_at IS NULL AND m.valid_from <= statement_timestamp() "
    "AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())"
)
# Employees only: admin accounts and the AI system account are managed elsewhere.
EMPLOYEE_FILTER = (
    "COALESCE(u.account_type, 'EMPLOYEE') = 'EMPLOYEE' AND NOT "
    + system_account_sql("u")
)
# Department head = active member whose manager is outside the department.
DEPARTMENT_HEAD_SQL = """
    SELECT h.id FROM eas.app_user h
    LEFT JOIN eas.app_user hm ON hm.id = h.manager_id
    WHERE h.department_id = %s AND h.is_active
      AND (hm.id IS NULL OR hm.department_id IS DISTINCT FROM h.department_id)
    ORDER BY h.created_at, h.id LIMIT 1
"""
USERS_SQL = f"""
    WITH roles AS (
        SELECT m.user_id, array_agg(DISTINCT m.role) AS roles
        FROM eas.role_membership m WHERE {ACTIVE_MEMBERSHIP} GROUP BY m.user_id
    ), involved AS (
        SELECT p.user_id, {STAGE_SQL} AS stage, count(DISTINCT r.id)::int AS n
        FROM eas.request_participant p JOIN eas.request r ON r.id = p.request_id
        WHERE p.read_revoked_at IS NULL
        GROUP BY 1, 2
    )
    SELECT u.id::text, u.employee_code, u.display_name, u.email,
           u.department_id::text, d.name, u.is_active, COALESCE(ro.roles, '{{}}'),
           ws.status_code, ws.status_label, ws.detail_reason,
           (SELECT jsonb_object_agg(i.stage, i.n) FROM involved i WHERE i.user_id = u.id),
           u.manager_id::text
    FROM eas.app_user u
    LEFT JOIN eas.department d ON d.id = u.department_id
    LEFT JOIN roles ro ON ro.user_id = u.id
    LEFT JOIN LATERAL eas.get_user_working_status(u.id, now()) ws ON true
    WHERE {EMPLOYEE_FILTER}
"""


def _role_names(cur) -> dict[str, str]:
    cur.execute("SELECT code, name FROM eas.role")
    return dict(cur.fetchall())


def _primary_role(roles) -> str | None:
    return next((r for r in ROLE_PRIORITY if r in (roles or ())), None)


def _serialize_user(row, role_names: dict[str, str]) -> dict:
    roles = list(row[7] or [])
    primary = _primary_role(roles)
    stages = row[11] or {}
    return {
        "id": row[0],
        "employee_code": row[1],
        "full_name": row[2],
        "email": row[3],
        "department_id": row[4],
        "department_name": row[5] or "Chưa phân bổ",
        "is_active": row[6],
        "roles": sorted(roles),
        "role_id": primary,
        "role_code": primary,
        "role_name": role_names.get(primary, primary) if primary else None,
        "job_title": role_names.get(primary, "Nhân viên") if primary else "Nhân viên",
        "working_status_code": row[8] or "DANG_LAM",
        "working_status_label": row[9] or "Đang làm",
        "working_status_detail": row[10] or "",
        "stage_counts": {
            "yeu_cau": stages.get("YEU_CAU", 0),
            "phe_duyet": stages.get("PHE_DUYET", 0),
            "thuc_hien": stages.get("THUC_HIEN", 0),
            "nghiem_thu": stages.get("NGHIEM_THU", 0),
            "hoan_thanh": stages.get("HOAN_THANH", 0),
        },
        "total_involved_requests": sum(stages.values()),
        "manager_id": row[12],
    }


def _fetch_users(cur, where: str = "", params: list | None = None) -> list[dict]:
    names = _role_names(cur)
    cur.execute(  # NOSONAR python:S2077 - only constant SQL fragments are joined
        USERS_SQL + where + " ORDER BY u.employee_code NULLS LAST, u.email",
        [settings.EAS_AI_SYSTEM_USER_ID, *(params or [])],
    )
    return [_serialize_user(r, names) for r in cur.fetchall()]


def _users_authorizer(request, action: str):
    """Identity writes: admin, or an employee the admin granted `users` rights."""

    def check(_cursor, _actor) -> None:
        if not can(request, "users", action):
            raise CommandError("MODULE_FORBIDDEN", status=403)

    return check


def _forbidden_unless_users(request, action: str):
    if not can(request, "users", action):
        return api_error(request, "MODULE_FORBIDDEN", status=403)
    return None


def _forbidden_unless_writer(request):
    if not request.actor.roles & WRITE_ROLES:
        return api_error(request, "FORBIDDEN", status=403)
    return None


def _reason(payload: dict, default: str) -> str:
    reason = str(payload.get("reason") or "").strip()
    return reason if len(reason) >= 10 else default


def _audit(
    cur,
    request,
    *,
    action: str,
    target_type: str,
    target_id: str,
    details: dict,
    reason: str,
):
    _append_admin_audit(
        cur,
        actor_id=request.actor.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        reason=reason,
        correlation_id=correlation_id(request),
    )


def _command_errors(view):
    """Map service/validation errors to API errors instead of 500."""

    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except CommandError as exc:
            return api_error(request, exc.code, status=exc.status, fields=exc.fields)
        except JsonBodyError as exc:
            return api_error(request, str(exc), status=400)
        except IntegrityError:
            return api_error(request, "CONSTRAINT_CONFLICT", status=409)

    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


def _assert_employee(cur, user_id: str) -> None:
    cur.execute(  # NOSONAR python:S2077 - constant SQL fragment
        f"SELECT 1 FROM eas.app_user u WHERE u.id = %s::uuid AND {EMPLOYEE_FILTER}",
        [user_id, settings.EAS_AI_SYSTEM_USER_ID],
    )
    if not cur.fetchone():
        raise CommandError("USER_NOT_FOUND", status=404)


# ==============================================================================
# 1. ORG CHART TREE
# ==============================================================================


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR", "APPROVER", "REQUESTER")
def org_chart_tree_view(request):
    """Departments with head, roster and working-status summary."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)

    with connection.cursor() as cur:
        raw_users = _fetch_users(cur, " AND u.is_active")
        cur.execute(
            "SELECT id::text, code, name, parent_id::text FROM eas.department WHERE is_active ORDER BY code"
        )
        departments = cur.fetchall()

    is_privileged = bool(
        request.actor.roles & {"OPS_ADMIN", "POLICY_ADMIN", "AUDITOR", "APPROVER"}
    ) or can(request, "users", "view")

    if is_privileged:
        users = raw_users
    else:
        users = [
            {
                "id": u["id"],
                "employee_code": u["employee_code"],
                "full_name": u["full_name"],
                "email": u["email"],
                "department_id": u["department_id"],
                "department_name": u["department_name"],
                "is_active": u["is_active"],
                "job_title": u["job_title"],
                "working_status_code": u["working_status_code"],
                "working_status_label": u["working_status_label"],
                "manager_id": u["manager_id"],
            }
            for u in raw_users
        ]

    by_id = {u["id"]: u for u in users}
    by_dept: dict[str, list[dict]] = {}
    for u in users:
        by_dept.setdefault(u["department_id"] or "UNASSIGNED", []).append(u)

    nodes = []
    for dept_id, code, name, parent_id in departments:
        members = by_dept.get(dept_id, [])
        head = next(
            (
                u
                for u in members
                if not u["manager_id"]
                or by_id.get(u["manager_id"], {}).get("department_id") != dept_id
            ),
            None,
        )
        nodes.append(
            {
                "id": dept_id,
                "code": code,
                "name": name,
                "parent_id": parent_id,
                "manager_name": head["full_name"] if head else "Chưa bổ nhiệm",
                "description": "",
                "employee_count": len(members),
                "employees": members,
            }
        )

    node_map = {n["id"]: {**n, "children": []} for n in nodes}
    tree = []
    for n in nodes:
        parent = node_map.get(n["parent_id"]) if n["parent_id"] else None
        (parent["children"] if parent else tree).append(node_map[n["id"]])

    status_count = {"DANG_LAM": 0, "NGHI_LAM": 0, "CONG_TAC": 0, "NGOAI_GIO": 0}
    for u in users:
        status_count[u["working_status_code"]] = (
            status_count.get(u["working_status_code"], 0) + 1
        )
    return JsonResponse(
        {
            "summary": {
                "total_departments": len(nodes),
                "total_employees": len(users),
                "working_count": status_count["DANG_LAM"],
                "leave_count": status_count["NGHI_LAM"],
                "trip_count": status_count["CONG_TAC"],
                "off_hours_count": status_count["NGOAI_GIO"],
            },
            "departments": nodes,
            "tree": tree,
        }
    )


# ==============================================================================
# 2. USER MANAGEMENT
# ==============================================================================


def _role_grants(user_id: str, department_id: str, role: str) -> list[dict]:
    scoped = role in DEPARTMENT_SCOPED_ROLES
    return [
        {
            "user_id": user_id,
            "role": role,
            "scope_kind": "DEPARTMENT" if scoped else "GLOBAL",
            "department_id": department_id if scoped else None,
            "type_scope": "ALL",
            "type_id": None,
        }
    ]


def _grant_role(
    request,
    user_id: str,
    department_id: str,
    role: str,
    key: str,
    reason: str,
    action: str = "update",
) -> None:
    """Grant role unless the user already holds it (as any active membership)."""
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT 1 FROM eas.role_membership m WHERE m.user_id = %s AND m.role = %s AND {ACTIVE_MEMBERSHIP}",
            [user_id, role],
        )
        if cur.fetchone():
            return
    for i, grant in enumerate(_role_grants(user_id, department_id, role)):
        mutate(
            request.actor,
            "memberships",
            None,
            {**grant, "reason": reason},
            "POST",
            str(uuid5(UUID(key), f"role:{role}:{i}")),
            correlation_id(request),
            authorizer=_users_authorizer(request, action),
        )


def _validated_role(value, request=None) -> str | None:
    if value in (None, ""):
        return None
    if value not in ASSIGNABLE_ROLES:
        raise CommandError("INVALID_ROLE", status=422)
    # Approval and audit authority are granted by the administrator only.
    if (
        value in ADMIN_GRANTED_ROLES
        and request is not None
        and not request.actor.roles & ADMIN_ROLES
    ):
        raise CommandError(f"{value}_ROLE_ADMIN_ONLY", status=403)
    return value


def _idempotency_key(request) -> str:
    """Client UUID key when sent (safe retries), otherwise a fresh one."""
    try:
        return str(UUID(request.headers.get("Idempotency-Key", "").strip()))
    except ValueError:
        return str(uuid4())


@require_actor(*READ_ROLES)
@_command_errors
def users_management_list(request):
    """GET employees with working status and request stage counts; POST create."""
    if request.method == "GET":
        where, params = "", []
        q = request.GET.get("q", "").strip()
        if q:
            where += " AND (u.display_name ILIKE %s OR u.email ILIKE %s OR u.employee_code ILIKE %s)"
            params += [f"%{q}%"] * 3
        dept_id = request.GET.get("department_id", "").strip()
        if dept_id:
            where += " AND u.department_id::text = %s"
            params.append(dept_id)
        active = request.GET.get("active", "").strip().lower()
        if active in ("true", "1", "false", "0"):
            where += " AND u.is_active = %s"
            params.append(active in ("true", "1"))
        with connection.cursor() as cur:
            items = _fetch_users(cur, where, params)
        role = request.GET.get("role_id", "").strip()
        if role:
            items = [u for u in items if role in u["roles"]]
        status = request.GET.get("status", "").strip().upper()
        if status in ("DANG_LAM", "NGHI_LAM", "CONG_TAC", "NGOAI_GIO"):
            items = [u for u in items if u["working_status_code"] == status]
        return JsonResponse({"items": items, "total": len(items)})

    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_users(request, "create"):
        return denied

    payload = parse_json_object(request)
    role = _validated_role(payload.get("role_id"), request)
    department_id = payload.get("department_id")
    key = _idempotency_key(request)
    reason = _reason(payload, "Tạo tài khoản nhân viên từ trang Quản lý người dùng")
    manager_id = payload.get("manager_id")
    if not manager_id and department_id:
        with connection.cursor() as cur:
            cur.execute(DEPARTMENT_HEAD_SQL, [department_id])
            row = cur.fetchone()
            manager_id = str(row[0]) if row else None

    with transaction.atomic():
        created = mutate(
            request.actor,
            "users",
            None,
            {
                "email": payload.get("email"),
                "display_name": payload.get("full_name") or payload.get("display_name"),
                "department_id": department_id,
                "manager_id": manager_id,
                "password": payload.get("password"),
                "reason": reason,
            },
            "POST",
            key,
            correlation_id(request),
            authorizer=_users_authorizer(request, "create"),
        )
        user_id = created.body["item"]["id"]
        # Every employee can create and accept their own requests.
        for granted in dict.fromkeys(("REQUESTER", "ACCEPTOR", role)):
            if granted:
                _grant_role(
                    request, user_id, department_id, granted, key, reason, "create"
                )

    return JsonResponse(
        {
            "success": True,
            "message": f"Tạo người dùng {created.body['item']['display_name']} thành công",
            "id": user_id,
        },
        status=201,
    )


@require_actor(*READ_ROLES)
@_command_errors
def user_management_detail(request, user_id):
    """GET one employee; PATCH profile/role/active; DELETE locks the account."""
    u_str = str(user_id)
    if request.method == "GET":
        with connection.cursor() as cur:
            items = _fetch_users(cur, " AND u.id = %s::uuid", [u_str])
        if not items:
            return api_error(request, "USER_NOT_FOUND", status=404)
        return JsonResponse({"item": items[0]})

    if request.method not in ("PATCH", "PUT", "DELETE"):
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    payload = parse_json_object(request) if request.method != "DELETE" else {}
    # Locking/unlocking an account is a delete-level right.
    action = (
        "delete" if request.method == "DELETE" or "is_active" in payload else "update"
    )
    if denied := _forbidden_unless_users(request, action):
        return denied
    if request.actor.id == u_str:
        return api_error(request, "SELF_ADMIN_CHANGE_FORBIDDEN", status=403)

    with connection.cursor() as cur:
        _assert_employee(cur, u_str)
    key = _idempotency_key(request)
    authorizer = _users_authorizer(request, action)
    current = read_record(request.actor, "users", u_str, authorizer)["item"]

    if request.method == "DELETE":
        result = mutate(
            request.actor,
            "users",
            u_str,
            {
                "reason": _reason(
                    payload, "Khoá tài khoản từ trang Quản lý người dùng"
                ),
                "expected_revision": current["revision"],
            },
            "DELETE",
            key,
            correlation_id(request),
            authorizer=authorizer,
        )
        item = result.body["item"]
        return JsonResponse(
            {"success": True, "message": f"Đã khóa tài khoản {item['display_name']}"}
        )

    role = _validated_role(payload.get("role_id"), request)
    reason = _reason(payload, "Cập nhật tài khoản từ trang Quản lý người dùng")
    changes = {}
    if payload.get("full_name"):
        changes["display_name"] = payload["full_name"]
    if payload.get("department_id"):
        changes["department_id"] = payload["department_id"]
    if "manager_id" in payload:
        # Empty value removes the manager; service.mutate validates the UUID,
        # that the manager is an active user, and rejects self/cyclic chains.
        changes["manager_id"] = payload["manager_id"] or None
    if "is_active" in payload:
        changes["is_active"] = payload["is_active"]
    if payload.get("password"):
        changes["password"] = payload["password"]

    with transaction.atomic():
        item = current
        if changes:
            item = mutate(
                request.actor,
                "users",
                u_str,
                {**changes, "reason": reason, "expected_revision": current["revision"]},
                "PATCH",
                key,
                correlation_id(request),
                authorizer=authorizer,
            ).body["item"]
        if role:
            _grant_role(
                request, u_str, item["department_id"], role, key, reason, action
            )

    if not changes and not role:
        return JsonResponse({"success": True, "message": "Không có thay đổi"})
    return JsonResponse(
        {
            "success": True,
            "id": u_str,
            "full_name": item["display_name"],
            "is_active": item["is_active"],
        }
    )


@require_actor(*READ_ROLES)
def user_requests_detail_view(request, user_id):
    """Requests the user takes part in, grouped by the 5 business stages."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)

    u_str = str(user_id)
    with connection.cursor() as cur:
        users = _fetch_users(cur, " AND u.id = %s::uuid", [u_str])
        if not users:
            return api_error(request, "USER_NOT_FOUND", status=404)
        cur.execute(
            f"""
            SELECT r.id::text, r.code, COALESCE(r.draft_payload->>'title', rt.name), rt.name,
                   rt.lifecycle, {STAGE_SQL}, r.status,
                   array_agg(DISTINCT p.joined_as), r.created_at
            FROM eas.request_participant p
            JOIN eas.request r ON r.id = p.request_id
            JOIN eas.request_type rt ON rt.id = r.type_id
            WHERE p.user_id = %s::uuid AND p.read_revoked_at IS NULL
            GROUP BY r.id, rt.name, rt.lifecycle
            ORDER BY r.created_at DESC
            """,
            [u_str],
        )
        rows = cur.fetchall()

    stage_counts = dict.fromkeys(STAGE_LABELS, 0)
    items = []
    for rid, code, title, type_name, lifecycle, stage, status, joined, created in rows:
        stage_counts[stage] += 1
        items.append(
            {
                "id": rid,
                "code": code,
                "request_id": rid,
                "request_code": code,
                "title": title,
                "content": "",
                "request_type": type_name,
                "category_code": lifecycle,
                "current_stage": stage,
                "current_stage_label": STAGE_LABELS[stage],
                "final_status": status,
                "user_role_in_request": ", ".join(
                    JOINED_AS_LABELS.get(j, j) for j in joined
                ),
                "created_at": created.isoformat() if created else None,
            }
        )
    user = users[0]
    return JsonResponse(
        {
            "user": {
                k: user[k]
                for k in ("id", "full_name", "email", "job_title", "department_name")
            },
            "summary": {
                "total_requests": len(items),
                "stage_1_yeu_cau": stage_counts["YEU_CAU"],
                "stage_2_phe_duyet": stage_counts["PHE_DUYET"],
                "stage_3_thuc_hien": stage_counts["THUC_HIEN"],
                "stage_4_nghiem_thu": stage_counts["NGHIEM_THU"],
                "stage_5_hoan_thanh": stage_counts["HOAN_THANH"],
            },
            "items": items,
        }
    )


@require_actor(*READ_ROLES)
@_command_errors
def user_leave_trip_manage(request, user_id):
    """Record an approved leave/business trip, or cancel today's, to set working status."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_users(request, "update"):
        return denied

    u_str = str(user_id)
    payload = parse_json_object(request)
    raw_action = payload.get("action")
    action = str(raw_action if raw_action is not None else "create").strip().upper()
    if action not in {"CREATE", "ADD", "SET", "CANCEL_TODAY", "RESET_TODAY"}:
        raise CommandError("INVALID_LEAVE_ACTION", status=422)
    with transaction.atomic(), connection.cursor() as cur:
        _assert_employee(cur, u_str)
        if action in ("CANCEL_TODAY", "RESET_TODAY"):
            cur.execute(
                "DELETE FROM eas.user_leave_and_trips WHERE user_id = %s::uuid "
                "AND now() BETWEEN start_time AND end_time RETURNING id::text",
                [u_str],
            )
            details = {"cancelled": [r[0] for r in cur.fetchall()]}
            message = (
                "Đã hủy đơn nghỉ/công tác hôm nay. Trạng thái trở về Đang làm việc."
            )
        else:
            raw_type = payload.get("type")
            leave_type = (
                str(raw_type if raw_type is not None else "PAID_LEAVE").strip().upper()
            )
            if leave_type not in LEAVE_TYPES:
                raise CommandError("INVALID_LEAVE_TYPE", status=422)
            title = str(
                payload.get("title") or payload.get("reason") or "Đơn nghỉ/công tác"
            ).strip()[:300]
            now_vn = datetime.now(VN_TZ)
            try:
                start = (
                    datetime.fromisoformat(payload["start_time"])
                    if payload.get("start_time")
                    else now_vn - timedelta(hours=1)
                )
                end = (
                    datetime.fromisoformat(payload["end_time"])
                    if payload.get("end_time")
                    else now_vn + timedelta(hours=8)
                )
            except (TypeError, ValueError):
                raise CommandError("INVALID_TIME_RANGE", status=422) from None
            if end <= start:
                raise CommandError("INVALID_TIME_RANGE", status=422)
            cur.execute(
                """
                INSERT INTO eas.user_leave_and_trips
                    (id, user_id, type, title, start_time, end_time, approval_status, approved_by, created_at)
                VALUES (gen_random_uuid(), %s::uuid, %s, %s, %s, %s, 'APPROVED', %s, now())
                RETURNING id::text
                """,
                [u_str, leave_type, title, start, end, request.actor.display_name],
            )
            details = {"id": cur.fetchone()[0], "type": leave_type, "title": title}
            message = f"Đã cập nhật đơn {leave_type} ({title}) thành công."
        _audit(
            cur,
            request,
            action="ADMIN_LEAVE_TRIP_"
            + ("CANCEL" if "cancelled" in details else "CREATE"),
            target_type="app_user",
            target_id=u_str,
            details=details,
            reason=_reason(payload, "Cập nhật trạng thái làm việc của nhân viên"),
        )
        cur.execute(
            "SELECT status_code, status_label, detail_reason FROM eas.get_user_working_status(%s::uuid, now())",
            [u_str],
        )
        status_row = cur.fetchone() or ("DANG_LAM", "Đang làm", "")

    return JsonResponse(
        {
            "success": True,
            "message": message,
            "status_label": status_row[1],
            "new_status": {
                "working_status_code": status_row[0],
                "working_status_label": status_row[1],
                "working_status_detail": status_row[2],
            },
        }
    )


# ==============================================================================
# 3. RBAC MATRIX AND PER-USER OVERRIDES
# ==============================================================================


@require_actor(*READ_ROLES)
def rbac_roles_list(request):
    """Role catalog; the role code is used as its id."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    with connection.cursor() as cur:
        cur.execute("SELECT code, name, description, is_system FROM eas.role")
        rows = {r[0]: r for r in cur.fetchall()}
    order = [c for c in ROLE_PRIORITY[::-1] if c in rows] + sorted(
        set(rows) - set(ROLE_PRIORITY)
    )
    return JsonResponse(
        {
            "items": [
                {
                    "id": code,
                    "code": code,
                    "name": rows[code][1],
                    "description": rows[code][2] or "",
                    "is_system": rows[code][3],
                    "assignable": code in ASSIGNABLE_ROLES,
                }
                for code in order
            ]
        }
    )


def _modules(cur) -> list[dict]:
    cur.execute(
        "SELECT code, name, group_name, route_path, icon_name, target_app FROM eas.modules ORDER BY sort_order, code"
    )
    keys = ("code", "name", "group_name", "route_path", "icon_name", "target_app")
    return [dict(zip(keys, r)) for r in cur.fetchall()]


@require_actor(*READ_ROLES)
def rbac_matrix_view(request):
    """Module permissions for one role (?role_id=CODE) or for all roles."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    role = request.GET.get("role_id")
    with connection.cursor() as cur:
        modules = _modules(cur)
        cur.execute(
            "SELECT role_code, module_code, can_view, can_create, can_update, can_delete FROM eas.role_module_permission"
            + (" WHERE role_code = %s" if role else ""),
            [role] if role else [],
        )
        rows = cur.fetchall()
    if role:
        perms = {r[1]: dict(zip(PERMISSION_FIELDS, r[2:])) for r in rows}
        empty = dict.fromkeys(PERMISSION_FIELDS, False)
        return JsonResponse(
            {
                "role_id": role,
                "modules": [{**m, **perms.get(m["code"], empty)} for m in modules],
            }
        )
    return JsonResponse(
        {
            "modules": modules,
            "permissions": [
                {
                    "role_id": r[0],
                    "role_code": r[0],
                    "module_code": r[1],
                    **dict(zip(PERMISSION_FIELDS, r[2:])),
                }
                for r in rows
            ],
        }
    )


SYSTEM_LOCKED_MODULES = frozenset(
    {"permissions", "ai_engine", "api_management", "system_versions"}
)


def _permission_payload(payload: dict, id_field: str) -> tuple[str, str, str, bool]:
    target, module, field = (
        payload.get(id_field),
        payload.get("module_code"),
        payload.get("permission_type") or payload.get("field"),
    )
    if (
        not target
        or not module
        or field not in PERMISSION_FIELDS
        or not isinstance(payload.get("value"), bool)
    ):
        raise CommandError("INVALID_RBAC_PAYLOAD", status=400)
    if module in SYSTEM_LOCKED_MODULES:
        raise CommandError(
            "SYSTEM_MODULE_LOCKED",
            "4 chức năng hệ thống (Phân quyền, Quản trị AI, Quản lý API, Phiên bản hệ thống) được khóa cứng bảo mật; không thể cấp quyền cho vai trò hoặc nhân viên.",
            status=400,
        )
    return str(target), str(module), field, payload["value"]


def _assert_grantable(cur, module: str, value: bool, *, employee: bool) -> None:
    """System modules can never be granted to employees (roles or overrides)."""
    cur.execute("SELECT 1 FROM eas.modules WHERE code = %s", [module])
    if not cur.fetchone():
        raise CommandError("MODULE_NOT_FOUND", status=404)
    if employee and value and module in NEVER_FOR_EMPLOYEES:
        raise CommandError("ADMIN_MODULE_NOT_GRANTABLE", status=422)


def _bump_epoch(cur) -> None:
    cur.execute(
        "UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1"
    )


@require_actor(*READ_ROLES)
@_command_errors
def rbac_role_permission_update(request):
    """Set one permission flag of a role on a module."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_writer(request):
        return denied
    payload = parse_json_object(request)
    role, module, field, value = _permission_payload(payload, "role_id")

    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SELECT eas.lock_security(true)")
        cur.execute("SELECT 1 FROM eas.role WHERE code = %s", [role])
        if not cur.fetchone():
            raise CommandError("ROLE_NOT_FOUND", status=404)
        _assert_grantable(cur, module, value, employee=role in EMPLOYEE_ROLES)
        # field is one of PERMISSION_FIELDS (validated above).
        cur.execute(  # NOSONAR python:S2077
            f"""
            INSERT INTO eas.role_module_permission (role_code, module_code, {field}, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (role_code, module_code)
            DO UPDATE SET {field} = EXCLUDED.{field}, updated_at = now()
            """,
            [role, module, value],
        )
        _bump_epoch(cur)
        _audit(
            cur,
            request,
            action="ADMIN_ROLE_PERMISSION_SET",
            target_type="role_module_permission",
            target_id=f"{role}:{module}",
            details={"role": role, "module": module, field: value},
            reason=_reason(payload, f"Phân quyền vai trò {role} trên mô-đun {module}"),
        )
    return JsonResponse(
        {
            "success": True,
            "message": f"Cập nhật quyền {field} = {value} cho vai trò thành công.",
            "role_id": role,
            "module_code": module,
            "permission_type": field,
            "value": value,
        }
    )


@require_actor(*READ_ROLES)
def rbac_user_permissions_view(request, user_id):
    """Effective permissions (role defaults + per-user overrides) of a user."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    u_str = str(user_id)
    with connection.cursor() as cur:
        users = _fetch_users(cur, " AND u.id = %s::uuid", [u_str])
        if not users:
            return api_error(request, "USER_NOT_FOUND", status=404)
        cur.execute(
            """
            SELECT module_code, module_name, group_name, route_path, icon_name, target_app,
                   can_view, can_create, can_update, can_delete, show_on_sidebar, permission_source
            FROM eas.get_effective_user_permissions(%s::uuid)
            """,
            [u_str],
        )
        rows = cur.fetchall()
    keys = (
        "module_code",
        "module_name",
        "group_name",
        "route_path",
        "icon_name",
        "target_app",
        "can_view",
        "can_create",
        "can_update",
        "can_delete",
        "show_on_sidebar",
        "permission_source",
    )
    modules = []
    for r in rows:
        m = dict(zip(keys, r))
        modules.append(
            {
                **m,
                "code": m["module_code"],
                "name": m["module_name"],
                "is_user_override": m["permission_source"] == "USER_OVERRIDE",
            }
        )
    user = users[0]
    return JsonResponse(
        {
            "user": {
                k: user[k]
                for k in ("id", "full_name", "email", "role_name", "department_name")
            },
            "modules": modules,
        }
    )


@require_actor(*READ_ROLES)
@_command_errors
def rbac_user_permission_update(request):
    """Override one permission flag for a single user."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_writer(request):
        return denied
    payload = parse_json_object(request)
    user_id, module, field, value = _permission_payload(payload, "user_id")

    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SELECT eas.lock_security(true)")
        _assert_employee(cur, user_id)
        _assert_grantable(cur, module, value, employee=True)
        # Start the override from the current effective permissions.
        cur.execute(
            "SELECT can_view, can_create, can_update, can_delete FROM eas.get_effective_user_permissions(%s::uuid) WHERE module_code = %s",
            [user_id, module],
        )
        base = cur.fetchone()
        if not base:
            raise CommandError("MODULE_NOT_FOUND", status=404)
        perms = dict(zip(PERMISSION_FIELDS, base))
        perms[field] = value
        cur.execute(
            """
            INSERT INTO eas.user_permissions
                (id, user_id, module_code, can_view, can_create, can_update, can_delete, granted_by, updated_at)
            VALUES (gen_random_uuid(), %s::uuid, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (user_id, module_code) DO UPDATE SET
                can_view = EXCLUDED.can_view, can_create = EXCLUDED.can_create,
                can_update = EXCLUDED.can_update, can_delete = EXCLUDED.can_delete,
                granted_by = EXCLUDED.granted_by, updated_at = now()
            """,
            [user_id, module, *perms.values(), request.actor.display_name],
        )
        _bump_epoch(cur)
        _audit(
            cur,
            request,
            action="ADMIN_USER_PERMISSION_SET",
            target_type="user_permissions",
            target_id=user_id,
            details={"module": module, **perms},
            reason=_reason(payload, f"Cấp quyền riêng trên mô-đun {module}"),
        )
    return JsonResponse(
        {
            "success": True,
            "message": f"Đã cấp quyền riêng {field} = {value} cho nhân viên.",
            "user_id": user_id,
            "module_code": module,
            "permission_type": field,
            "value": value,
        }
    )


@require_actor(*READ_ROLES)
@_command_errors
def rbac_user_permission_reset(request, user_id):
    """Drop all per-user overrides so role defaults apply again."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_writer(request):
        return denied
    u_str = str(user_id)
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SELECT eas.lock_security(true)")
        _assert_employee(cur, u_str)
        cur.execute(
            "DELETE FROM eas.user_permissions WHERE user_id = %s::uuid RETURNING module_code",
            [u_str],
        )
        removed = [r[0] for r in cur.fetchall()]
        if removed:
            _bump_epoch(cur)
            _audit(
                cur,
                request,
                action="ADMIN_USER_PERMISSION_RESET",
                target_type="user_permissions",
                target_id=u_str,
                details={"removed_modules": removed},
                reason="Khôi phục phân quyền về mặc định theo vai trò",
            )
    return JsonResponse(
        {
            "success": True,
            "message": "Đã khôi phục toàn bộ phân quyền về chuẩn Chức vụ mặc định.",
        }
    )
