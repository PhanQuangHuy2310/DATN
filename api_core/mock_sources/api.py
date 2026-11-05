"""Mock Systems API: the simulated external systems (HRM, assets, facilities, ITSM,
ERP finance, procurement, CRM, travel).

Runs as its own service (EAS_SERVICE=mock) with its own database role
(eas_mock). This module is the *external* side: it alone reads and writes the
mock_* schemas. EAS reaches it only over HTTP through api_core/integrations.
See docs/TICH_HOP_HE_THONG_NGOAI.md.

Every write is idempotent on ``source_request_id`` (the EAS request id).
"""

from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from functools import wraps
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .service import RESOURCES, QueryValidationError, list_resource

ACTIVE_LOAN = ["RESERVED", "ACTIVE", "OVERDUE"]
ACTIVE_RESERVATION = ["TENTATIVE", "CONFIRMED", "CHECKED_IN"]
VN = ZoneInfo("Asia/Ho_Chi_Minh")
READ_ALL = frozenset({"OPS_ADMIN"})  # list_resource role gate: service is trusted


def _this_year() -> int:
    return datetime.now(VN).year


class ApiError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code, self.status = code, status


def _error(code: str, status: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code}}, status=status)


def integration_api(methods: tuple[str, ...]):
    """Shared-secret auth (service to service), JSON in/out, uniform errors."""

    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            supplied = request.headers.get("X-Integration-Secret") or ""
            if not hmac.compare_digest(supplied, settings.EAS_MOCK_API_SECRET):
                return _error("UNAUTHORIZED", 401)
            if request.method not in methods:
                return _error("METHOD_NOT_ALLOWED", 405)
            body: dict[str, Any] = {}
            if request.method == "POST":
                try:
                    body = json.loads(request.body or b"{}")
                except ValueError:
                    return _error("INVALID_JSON", 400)
                if not isinstance(body, dict):
                    return _error("INVALID_JSON", 400)
            try:
                return JsonResponse(view(request, body, *args, **kwargs))
            except ApiError as exc:
                return _error(exc.code, exc.status)
            except QueryValidationError as exc:
                return _error(str(exc), 400)

        return wrapped

    return decorator


def _rows(sql: str, params: list | None = None) -> list[dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def _ts(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(f"INVALID_{field.upper()}") from None
    if parsed.tzinfo is None:
        raise ApiError(f"INVALID_{field.upper()}")
    return parsed


def _uuid(value: Any, field: str = "source_request_id") -> str:
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise ApiError(f"INVALID_{field.upper()}") from None


def _employee(email: Any) -> str:
    rows = _rows(
        "SELECT id::text AS id FROM mock_hr.employee WHERE lower(work_email) = lower(%s)",
        [str(email or "")],
    )
    if not rows:
        raise ApiError("UNKNOWN_EMPLOYEE", 422)
    return rows[0]["id"]


# --------------------------------------------------------------------------
# HRM
# --------------------------------------------------------------------------
@integration_api(("GET",))
def hr_departments(request, _body):
    return {
        "items": _rows(
            """
            SELECT d.code, d.name, p.code AS parent_code, d.cost_center, d.status
            FROM mock_hr.department d LEFT JOIN mock_hr.department p ON p.id = d.parent_id
            ORDER BY d.code
            """
        )
    }


@integration_api(("GET",))
def hr_employees(request, _body):
    return {
        "items": _rows(
            """
            SELECT e.employee_code, e.display_name, e.work_email, d.code AS department_code,
                   m.employee_code AS manager_code, e.job_title, e.employment_status
            FROM mock_hr.employee e
            JOIN mock_hr.department d ON d.id = e.department_id
            LEFT JOIN mock_hr.employee m ON m.id = e.manager_id
            ORDER BY e.employee_code
            """
        )
    }


@integration_api(("GET",))
def hr_leave_balances(request, _body):
    year = int(request.GET.get("year") or _this_year())
    return {
        "items": _rows(
            """
            SELECT b.leave_type, b.year, b.entitled_days, b.used_days,
                   b.entitled_days - b.used_days AS remaining_days
            FROM mock_hr.leave_balance b JOIN mock_hr.employee e ON e.id = b.employee_id
            WHERE lower(e.work_email) = lower(%s) AND b.year = %s
            ORDER BY b.leave_type
            """,
            [request.GET.get("employee_email", ""), year],
        )
    }


@integration_api(("POST",))
def hr_leave_usages(request, body):
    source = _uuid(body.get("source_request_id"))
    days = body.get("days")
    if isinstance(days, bool) or not isinstance(days, (int, float)) or days <= 0:
        raise ApiError("INVALID_DAYS")
    employee = _employee(body.get("employee_email"))
    year = int(body.get("year") or _this_year())
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM mock_hr.leave_usage WHERE source_request_id = %s", [source]
        )
        if cur.fetchone():
            return {"status": "ALREADY_RECORDED"}
        cur.execute(
            """
            UPDATE mock_hr.leave_balance SET used_days = used_days + %s,
              updated_at = statement_timestamp()
            WHERE employee_id = %s AND leave_type = %s AND year = %s
              AND entitled_days - used_days >= %s
            RETURNING entitled_days - used_days
            """,
            [days, employee, body.get("leave_type"), year, days],
        )
        row = cur.fetchone()
        if not row:
            raise ApiError("LEAVE_BALANCE_EXCEEDED", 409)
        cur.execute(
            """
            INSERT INTO mock_hr.leave_usage(employee_id, leave_type, year, days, source_request_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [employee, body.get("leave_type"), year, days, source],
        )
    return {"status": "RECORDED", "remaining_days": float(row[0])}


# --------------------------------------------------------------------------
# Assets and facilities (borrowing)
# --------------------------------------------------------------------------
def _window(request) -> tuple[datetime, datetime]:
    start, end = _ts(request.GET.get("from"), "from"), _ts(request.GET.get("to"), "to")
    if end <= start:
        raise ApiError("INVALID_WINDOW")
    return start, end


@integration_api(("GET",))
def asset_categories(request, _body):
    return {
        "items": _rows(
            """
            SELECT c.code, c.name, count(a.id) AS total,
                   count(a.id) FILTER (WHERE a.availability_status = 'AVAILABLE') AS available_now
            FROM mock_assets.asset_category c
            LEFT JOIN mock_assets.asset a ON a.category_id = c.id
            WHERE c.code <> 'VEHICLE'
            GROUP BY c.code, c.name ORDER BY c.code
            """
        )
    }


def _free_assets(cur, code: str, start: datetime, end: datetime) -> list[str]:
    cur.execute(
        """
        SELECT a.id::text FROM mock_assets.asset a
        JOIN mock_assets.asset_category c ON c.id = a.category_id
        WHERE c.code = %s AND a.availability_status NOT IN ('MAINTENANCE', 'RETIRED')
          AND NOT EXISTS (
            SELECT 1 FROM mock_assets.asset_loan l
            WHERE l.asset_id = a.id AND l.status = ANY(%s)
              AND tstzrange(l.starts_at, l.due_at, '[)') && tstzrange(%s, %s, '[)'))
        ORDER BY a.asset_code
        """,
        [code, ACTIVE_LOAN, start, end],
    )
    return [row[0] for row in cur.fetchall()]


@integration_api(("GET",))
def asset_availability(request, _body, code):
    start, end = _window(request)
    with connection.cursor() as cur:
        free = _free_assets(cur, code, start, end)
    holders = _rows(
        """
        SELECT l.source_request_id::text AS source_request_id, count(*) AS count
        FROM mock_assets.asset_loan l
        JOIN mock_assets.asset a ON a.id = l.asset_id
        JOIN mock_assets.asset_category c ON c.id = a.category_id
        WHERE c.code = %s AND l.status = ANY(%s) AND l.source_request_id IS NOT NULL
          AND tstzrange(l.starts_at, l.due_at, '[)') && tstzrange(%s, %s, '[)')
        GROUP BY l.source_request_id
        """,
        [code, ACTIVE_LOAN, start, end],
    )
    return {"code": code, "free": len(free), "holders": holders}


def _sync_assets(cur, asset_ids: list[str]) -> None:
    cur.execute(
        """
        UPDATE mock_assets.asset a
        SET availability_status = CASE WHEN EXISTS (
              SELECT 1 FROM mock_assets.asset_loan l
              WHERE l.asset_id = a.id AND l.status IN ('ACTIVE', 'OVERDUE')
                AND l.starts_at <= statement_timestamp() AND l.due_at > statement_timestamp())
            THEN 'ON_LOAN' ELSE 'AVAILABLE' END,
            updated_at = statement_timestamp()
        WHERE a.id = ANY(%s::uuid[]) AND a.availability_status IN ('AVAILABLE', 'ON_LOAN', 'RESERVED')
        """,
        [asset_ids],
    )


@integration_api(("POST",))
def asset_loans(request, body):
    source = _uuid(body.get("source_request_id"))
    start, end = (
        _ts(body.get("starts_at"), "starts_at"),
        _ts(body.get("due_at"), "due_at"),
    )
    quantity = body.get("quantity")
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or not 1 <= quantity <= 50
    ):
        raise ApiError("INVALID_QUANTITY")
    borrower = _employee(body.get("borrower_email"))
    code = str(body.get("category_code") or "")
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            """
            SELECT a.asset_code FROM mock_assets.asset_loan l JOIN mock_assets.asset a ON a.id = l.asset_id
            WHERE l.source_request_id = %s AND l.status = ANY(%s) ORDER BY 1
            """,
            [source, ACTIVE_LOAN],
        )
        existing = [row[0] for row in cur.fetchall()]
        if existing:
            return {"status": "ALREADY_ALLOCATED", "items": existing}
        cur.execute(
            """
            SELECT a.id FROM mock_assets.asset a JOIN mock_assets.asset_category c ON c.id = a.category_id
            WHERE c.code = %s ORDER BY a.id FOR UPDATE OF a
            """,
            [code],
        )
        free = _free_assets(cur, code, start, end)
        if len(free) < quantity:
            raise ApiError("RESOURCE_UNAVAILABLE", 409)
        chosen = free[:quantity]
        state = "ACTIVE" if start <= datetime.now(timezone.utc) else "RESERVED"
        for asset_id in chosen:
            cur.execute(
                """
                INSERT INTO mock_assets.asset_loan(id, asset_id, borrower_employee_id,
                  source_request_id, starts_at, due_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [str(uuid4()), asset_id, borrower, source, start, end, state],
            )
        _sync_assets(cur, chosen)
        cur.execute(
            "SELECT asset_code FROM mock_assets.asset WHERE id = ANY(%s::uuid[]) ORDER BY 1",
            [chosen],
        )
        return {"status": "ALLOCATED", "items": [row[0] for row in cur.fetchall()]}


@integration_api(("GET",))
def facility_resources(request, _body):
    kind = request.GET.get("type")
    return {
        "items": _rows(
            """
            SELECT r.resource_code AS code, r.name, r.resource_type AS type, r.capacity,
                   r.availability_status AS status, s.site_code
            FROM mock_facilities.resource r JOIN mock_facilities.site s ON s.id = r.site_id
            WHERE %s::text IS NULL OR r.resource_type = %s
            ORDER BY r.resource_code
            """,
            [kind, kind],
        )
    }


def _resource(cur, code: str, lock: bool = False):
    cur.execute(
        "SELECT id::text, capacity, availability_status FROM mock_facilities.resource "
        "WHERE resource_code = %s" + (" FOR UPDATE" if lock else ""),
        [code],
    )
    row = cur.fetchone()
    if not row:
        raise ApiError("UNKNOWN_RESOURCE", 404)
    return row


def _resource_holders(resource_id: str, start: datetime, end: datetime) -> list[dict]:
    return _rows(
        """
        SELECT r.source_request_id::text AS source_request_id
        FROM mock_facilities.reservation r
        WHERE r.resource_id = %s AND r.status = ANY(%s)
          AND tstzrange(r.starts_at, r.ends_at, '[)') && tstzrange(%s, %s, '[)')
        """,
        [resource_id, ACTIVE_RESERVATION, start, end],
    )


@integration_api(("GET",))
def facility_availability(request, _body, code):
    start, end = _window(request)
    with connection.cursor() as cur:
        resource_id, capacity, status = _resource(cur, code)
    return {
        "code": code,
        "status": status,
        "capacity": capacity,
        "holders": _resource_holders(resource_id, start, end),
    }


@integration_api(("POST",))
def facility_reservations(request, body):
    source = _uuid(body.get("source_request_id"))
    start, end = (
        _ts(body.get("starts_at"), "starts_at"),
        _ts(body.get("ends_at"), "ends_at"),
    )
    requester = _employee(body.get("requester_email"))
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM mock_facilities.reservation WHERE source_request_id = %s AND status = ANY(%s)",
            [source, ACTIVE_RESERVATION],
        )
        if cur.fetchone():
            return {"status": "ALREADY_ALLOCATED", "items": [body.get("resource_code")]}
        resource_id, _capacity, status = _resource(
            cur, str(body.get("resource_code")), lock=True
        )
        if status in {"MAINTENANCE", "INACTIVE"}:
            raise ApiError("RESOURCE_OUT_OF_SERVICE", 409)
        if _resource_holders(resource_id, start, end):
            raise ApiError("RESOURCE_UNAVAILABLE", 409)
        cur.execute(
            """
            INSERT INTO mock_facilities.reservation(id, resource_id, requester_employee_id,
              source_request_id, starts_at, ends_at, status, purpose)
            VALUES (%s, %s, %s, %s, %s, %s, 'CONFIRMED', %s)
            """,
            [
                str(uuid4()),
                resource_id,
                requester,
                source,
                start,
                end,
                str(body.get("purpose") or "EAS")[:300],
            ],
        )
    return {"status": "ALLOCATED", "items": [body.get("resource_code")]}


def _start_due_loans(cur) -> None:
    cur.execute(
        """
        UPDATE mock_assets.asset_loan SET status = 'ACTIVE', updated_at = statement_timestamp()
        WHERE status = 'RESERVED' AND starts_at <= statement_timestamp()
        RETURNING asset_id::text
        """
    )
    _sync_assets(cur, [row[0] for row in cur.fetchall()])


@integration_api(("GET",))
def allocations(request, _body):
    """source_request_ids holding something: state=active, or state=ended&before=ts."""
    state = request.GET.get("state", "active")
    with transaction.atomic(), connection.cursor() as cur:
        _start_due_loans(cur)
    if state == "ended":
        before = _ts(request.GET.get("before"), "before")
        cond_loan, cond_res, params = "AND due_at <= %s", "AND ends_at <= %s", [before]
    elif state == "active" and request.GET.get("before"):
        # Orphan reconciliation only looks at allocations untouched for a while.
        before = _ts(request.GET.get("before"), "before")
        cond_loan, cond_res, params = (
            "AND updated_at <= %s",
            "AND updated_at <= %s",
            [before],
        )
    elif state == "active":
        cond_loan = cond_res = ""
        params = []
    else:
        raise ApiError("INVALID_STATE")
    rows = _rows(
        f"""
        SELECT DISTINCT source_request_id::text AS source_request_id FROM mock_assets.asset_loan
        WHERE source_request_id IS NOT NULL AND status = ANY(%s) {cond_loan}
        UNION
        SELECT DISTINCT source_request_id::text FROM mock_facilities.reservation
        WHERE source_request_id IS NOT NULL AND status = ANY(%s) {cond_res}
        """,  # NOSONAR python:S2077 - fixed fragments
        [ACTIVE_LOAN, *params, ACTIVE_RESERVATION, *params],
    )
    return {"items": [row["source_request_id"] for row in rows]}


@integration_api(("POST",))
def allocation_action(request, body, action):
    if action not in {"cancel", "return"}:
        raise ApiError("UNKNOWN_ACTION", 404)
    source = _uuid(body.get("source_request_id"))
    returned = action == "return"
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            """
            UPDATE mock_assets.asset_loan l
            SET status = %s,
                returned_at = CASE WHEN %s THEN greatest(statement_timestamp(), l.starts_at) END,
                updated_at = statement_timestamp()
            FROM mock_assets.asset a
            WHERE a.id = l.asset_id AND l.source_request_id = %s AND l.status = ANY(%s)
            RETURNING a.id::text, a.asset_code
            """,
            ["RETURNED" if returned else "CANCELLED", returned, source, ACTIVE_LOAN],
        )
        assets = cur.fetchall()
        _sync_assets(cur, [row[0] for row in assets])
        cur.execute(
            """
            UPDATE mock_facilities.reservation r
            SET status = %s, updated_at = statement_timestamp()
            FROM mock_facilities.resource f
            WHERE f.id = r.resource_id AND r.source_request_id = %s AND r.status = ANY(%s)
            RETURNING f.resource_code
            """,
            ["COMPLETED" if returned else "CANCELLED", source, ACTIVE_RESERVATION],
        )
        rooms = [row[0] for row in cur.fetchall()]
    return {"released": [row[1] for row in assets] + rooms}


# --------------------------------------------------------------------------
# ITSM
# --------------------------------------------------------------------------
@integration_api(("GET",))
def it_applications(request, _body):
    return {
        "items": _rows(
            """
            SELECT app_code AS code, name, data_classification, status
            FROM mock_it.application ORDER BY app_code
            """
        )
    }


@integration_api(("GET",))
def it_access_roles(request, _body):
    app = request.GET.get("app_code")
    return {
        "items": _rows(
            """
            SELECT r.role_code AS code, r.name, a.app_code, r.risk_level, r.requires_sod_review,
                   r.status
            FROM mock_it.access_role r JOIN mock_it.application a ON a.id = r.application_id
            WHERE %s::text IS NULL OR a.app_code = %s
            ORDER BY a.app_code, r.role_code
            """,
            [app, app],
        )
    }


@integration_api(("POST",))
def it_user_access(request, body):
    source = _uuid(body.get("source_request_id"))
    employee = _employee(body.get("employee_email"))
    expires = _ts(body["expires_at"], "expires_at") if body.get("expires_at") else None
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM mock_it.user_access WHERE source_request_id = %s", [source]
        )
        if cur.fetchone():
            return {"status": "ALREADY_GRANTED"}
        cur.execute(
            "SELECT id FROM mock_it.access_role WHERE role_code = %s AND status = 'ACTIVE'",
            [body.get("role_code")],
        )
        role = cur.fetchone()
        if not role:
            raise ApiError("UNKNOWN_ACCESS_ROLE", 422)
        try:
            cur.execute(
                """
                INSERT INTO mock_it.user_access(id, employee_id, access_role_id, source_request_id,
                  granted_at, expires_at, status)
                VALUES (%s, %s, %s, %s, statement_timestamp(), %s, 'ACTIVE')
                """,
                [str(uuid4()), employee, role[0], source, expires],
            )
        except IntegrityError:
            raise ApiError("ACCESS_ALREADY_ACTIVE", 409) from None
    return {"status": "GRANTED"}


# --------------------------------------------------------------------------
# ERP finance
# --------------------------------------------------------------------------
@integration_api(("GET",))
def finance_expense_categories(request, _body):
    return {
        "items": _rows(
            """
            SELECT category_code AS code, name, receipt_required_above_minor,
                   daily_limit_minor, currency, status
            FROM mock_finance.expense_category ORDER BY category_code
            """
        )
    }


@integration_api(("GET",))
def finance_budgets(request, _body):
    year = int(request.GET.get("year") or _this_year())
    rows = _rows(
        """
        SELECT b.cost_center, b.fiscal_year, b.currency, b.approved_minor, b.committed_minor,
               b.spent_minor, b.approved_minor - b.committed_minor - b.spent_minor AS available_minor
        FROM mock_finance.cost_center_budget b
        JOIN mock_hr.department d ON d.cost_center = b.cost_center
        WHERE d.code = %s AND b.fiscal_year = %s
        """,
        [request.GET.get("department_code", ""), year],
    )
    if not rows:
        raise ApiError("BUDGET_NOT_FOUND", 404)
    return rows[0]


@integration_api(("POST",))
def finance_commitments(request, body):
    source = _uuid(body.get("source_request_id"))
    amount = body.get("amount_minor")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ApiError("INVALID_AMOUNT")
    year = int(body.get("fiscal_year") or _this_year())
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM mock_finance.budget_commitment WHERE source_request_id = %s",
            [source],
        )
        if cur.fetchone():
            return {"status": "ALREADY_COMMITTED"}
        cur.execute(
            """
            UPDATE mock_finance.cost_center_budget b
            SET committed_minor = committed_minor + %s, updated_at = statement_timestamp()
            FROM mock_hr.department d
            WHERE d.cost_center = b.cost_center AND d.code = %s AND b.fiscal_year = %s
              AND b.approved_minor - b.committed_minor - b.spent_minor >= %s
            RETURNING b.cost_center, b.approved_minor - b.committed_minor - b.spent_minor
            """,
            [amount, body.get("department_code"), year, amount],
        )
        row = cur.fetchone()
        if not row:
            raise ApiError("BUDGET_EXCEEDED", 409)
        cur.execute(
            """
            INSERT INTO mock_finance.budget_commitment(cost_center, fiscal_year, amount_minor,
              source_request_id)
            VALUES (%s, %s, %s, %s)
            """,
            [row[0], year, amount, source],
        )
    return {"status": "COMMITTED", "available_minor": row[1]}


# --------------------------------------------------------------------------
# Read-only catalogues (CRM, procurement, travel, IT services) for AI context
# --------------------------------------------------------------------------
@integration_api(("GET",))
def catalogue(request, _body, resource):
    if resource not in RESOURCES:
        raise ApiError("RESOURCE_NOT_FOUND", 404)
    return list_resource(resource, request.GET, roles=READ_ALL)


@integration_api(("GET",))
def health(request, _body):
    with connection.cursor() as cur:
        cur.execute("SELECT version FROM mock_hr.schema_migration ORDER BY version")
        versions = [row[0] for row in cur.fetchall()]
    return {"status": "ok", "schema_versions": versions}
