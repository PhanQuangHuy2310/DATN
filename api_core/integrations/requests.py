"""Request types that use data of the external systems (docs/TICH_HOP_HE_THONG_NGOAI.md).

* Pickers: form fields whose allowed values live in an external catalogue.
* Submit checks: the picked code exists and is usable; leave balance (HRM);
  budget of the requester's cost centre and expense daily limits (ERP).
* Final approval: leave usage recorded in HRM, budget committed in ERP.
* Completion: IT access granted in ITSM.
Every call goes through api_core.integrations.client (never SQL on mock_*).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from api_core.catalog.integrations import BUDGET_TYPES
from api_core.integrations import client
from api_core.workflow.errors import CommandError

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def _this_year() -> int:
    return datetime.now(VN).year


def _room(item):
    return f"{item['name']} — {item['capacity']} chỗ"


# (type, field) -> (system, path, query, label builder, usable statuses)
PICKERS: dict[tuple[str, str], tuple] = {
    ("ROOM_BOOKING", "room_code"): (
        "facilities",
        "facilities/resources",
        {"type": "MEETING_ROOM"},
        _room,
        {"AVAILABLE", "RESERVED"},
    ),
    ("VEHICLE_BOOKING", "vehicle_code"): (
        "facilities",
        "facilities/resources",
        {"type": "VEHICLE"},
        _room,
        {"AVAILABLE", "RESERVED"},
    ),
    ("EQUIPMENT_BORROW", "asset_category"): (
        "assets",
        "assets/categories",
        {},
        lambda i: f"{i['name']} (còn {i['available_now']}/{i['total']})",
        None,
    ),
    ("ACCESS", "app_code"): (
        "it",
        "it/applications",
        {},
        lambda i: f"{i['name']} ({i['code']})",
        {"ACTIVE"},
    ),
    ("ACCESS", "requested_role"): (
        "it",
        "it/access-roles",
        {},
        lambda i: f"{i['name']} — {i['app_code']}, rủi ro {i['risk_level']}",
        {"ACTIVE"},
    ),
    ("EXPENSE_CLAIM", "expense_category"): (
        "finance",
        "finance/expense-categories",
        {},
        lambda i: i["name"],
        {"ACTIVE"},
    ),
}
PICKER_TYPES = {type_code for type_code, _field in PICKERS}
# LEAVE_SPECIAL kinds that consume an HRM leave quota.
SPECIAL_LEAVE_QUOTA = {"THAI_SAN": "PARENTAL", "NGHI_OM_DAI_NGAY": "SICK"}


def _catalogue(type_code: str, field: str) -> list[dict[str, Any]]:
    system, path, query, _label, _ok = PICKERS[(type_code, field)]
    return client.get(system, path, **query)["items"]


def options(type_code: str) -> dict[str, list[dict[str, Any]]]:
    """Picker values for a form, read live from the external systems."""
    out = {}
    for (code, field), (_s, _p, _q, label, usable) in PICKERS.items():
        if code != type_code:
            continue
        out[field] = [
            {
                "value": item["code"],
                "label": label(item),
                "available": usable is None or item.get("status") in usable,
                **({"app_code": item["app_code"]} if "app_code" in item else {}),
            }
            for item in _catalogue(code, field)
        ]
    return out


def _requester(cursor, user_id: str) -> tuple[str, str]:
    cursor.execute(
        """
        SELECT u.email, d.code FROM eas.app_user u
        JOIN eas.department d ON d.id = u.department_id WHERE u.id = %s
        """,
        [user_id],
    )
    return cursor.fetchone()


def _leave_need(type_code: str, payload: dict[str, Any]) -> tuple[str, int, int] | None:
    """(HRM leave type, days, year) when the request consumes a leave quota."""
    if type_code == "LEAVE" and payload.get("leave_kind") == "CO_LUONG":
        quota = "ANNUAL"
    elif type_code == "LEAVE_SPECIAL":
        quota = SPECIAL_LEAVE_QUOTA.get(payload.get("special_leave_type"))
    else:
        quota = None
    try:
        start = date.fromisoformat(str(payload.get("start_date")))
        end = date.fromisoformat(str(payload.get("end_date")))
    except ValueError:
        return None
    if not quota or end < start:
        return None
    return quota, (end - start).days + 1, start.year


def validate_submit(
    cursor,
    *,
    type_code: str,
    payload: dict[str, Any],
    amount: int | None,
    requester_id: str,
) -> None:
    errors: dict[str, list[str]] = {}
    found: dict[str, dict[str, Any]] = {}
    for (code, field), (_s, _p, _q, _label, usable) in PICKERS.items():
        if code != type_code or not payload.get(field):
            continue
        item = next(
            (i for i in _catalogue(code, field) if i["code"] == payload[field]), None
        )
        if item is None:
            errors.setdefault(field, []).append("UNKNOWN_EXTERNAL_CODE")
        elif usable is not None and item.get("status") not in usable:
            errors.setdefault(field, []).append("EXTERNAL_CODE_INACTIVE")
        else:
            found[field] = item
    role = found.get("requested_role")
    if role and payload.get("app_code") and role["app_code"] != payload["app_code"]:
        errors.setdefault("requested_role", []).append("ROLE_NOT_IN_APPLICATION")
    category = found.get("expense_category")
    limit = (category or {}).get("daily_limit_minor")
    if amount and limit and amount > limit:
        errors.setdefault("amount_vnd", []).append("EXPENSE_DAILY_LIMIT_EXCEEDED")
    if errors:
        raise CommandError("VALIDATION_FAILED", fields=errors)

    email, department = _requester(cursor, requester_id)
    leave = _leave_need(type_code, payload)
    if leave:
        quota, days, year = leave
        balances = client.get(
            "hr", "hr/leave-balances", employee_email=email, year=year
        )["items"]
        remaining = next(
            (float(b["remaining_days"]) for b in balances if b["leave_type"] == quota),
            0,
        )
        if days > remaining:
            raise CommandError(
                "LEAVE_BALANCE_EXCEEDED",
                status=409,
                fields={"end_date": [f"Quỹ {quota} còn {remaining:g} ngày"]},
            )
    if type_code in BUDGET_TYPES and amount:
        budget = client.get(
            "finance", "finance/budgets", department_code=department, year=_this_year()
        )
        if amount > budget["available_minor"]:
            raise CommandError("BUDGET_EXCEEDED", status=409)


def on_final_approval(
    cursor,
    *,
    request_id: str,
    type_code: str,
    payload: dict[str, Any],
    amount: int | None,
    requester_id: str,
) -> dict[str, Any]:
    """External writes when the last approval is given (idempotent per request)."""
    done: dict[str, Any] = {}
    leave = _leave_need(type_code, payload)
    budget = type_code in BUDGET_TYPES and amount
    if not leave and not budget:
        return done
    email, department = _requester(cursor, requester_id)
    if leave:
        quota, days, year = leave
        done["leave_usage"] = client.post(
            "hr",
            "hr/leave-usages",
            {
                "employee_email": email,
                "leave_type": quota,
                "days": days,
                "year": year,
                "source_request_id": request_id,
            },
        )
    if budget:
        done["budget_commitment"] = client.post(
            "finance",
            "finance/commitments",
            {
                "department_code": department,
                "fiscal_year": _this_year(),
                "amount_minor": amount,
                "source_request_id": request_id,
            },
        )
    return done


def on_completed(
    cursor,
    *,
    request_id: str,
    type_code: str,
    payload: dict[str, Any],
    requester_id: str,
) -> dict[str, Any]:
    """External writes when the work is done (ACCESS: grant in ITSM)."""
    if type_code != "ACCESS" or not payload.get("requested_role"):
        return {}
    email, _department = _requester(cursor, requester_id)
    days = payload.get("duration_days")
    expires = (
        (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        if isinstance(days, int) and days > 0
        else None
    )
    return {
        "it_access": client.post(
            "it",
            "it/user-access",
            {
                "employee_email": email,
                "role_code": payload["requested_role"],
                "expires_at": expires,
                "source_request_id": request_id,
            },
        )
    }
