"""Database adapter for the C2 resource guard (see api_core.domain.resource_guard).

Configuration (all optional):
  EAS_RESOURCE_GUARD = off | advisory (default) | enforce
  EAS_RESOURCE_AUTHORITATIVE_SOURCES = comma list of sources the owner has
      confirmed as systems of record. Empty by default: mock_hr / mock_finance
      are simulation sources and never block on their own.
  EAS_RESOURCE_MAX_AGE_HOURS = freshness limit (default 24).

Linkage is strict: leave balances match the requester by exact e-mail;
budgets match the department code to the mock HR cost center. In-flight EAS
requests are counted as reservations, and submit serializes per requester /
cost center with transaction-scoped advisory locks.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from django.db import DatabaseError, transaction

from api_core.domain.resource_guard import (
    UNVERIFIED,
    Balance,
    GuardResult,
    evaluate,
)
from api_core.domain.routing import _extract_days

LEAVE_SOURCE = "mock_hr.leave_balance"
BUDGET_SOURCE = "mock_finance.cost_center_budget"

# Proposed mapping (owner to confirm): leave types that consume annual leave,
# and request types that consume department budget.
LEAVE_TYPE_MAP = {"LEAVE": "ANNUAL", "LEAVE_ANNUAL": "ANNUAL", "LEAVE_LONG": "ANNUAL"}
BUDGET_TYPES = frozenset(
    {
        "PURCHASE_REQUEST",
        "EQUIPMENT",
        "ASSET_PURCHASE",
        "SAAS_LICENSE_BUY",
        "OFFICE_SUPPLIES",
        "EXPENSE_CLAIM",
        "REIMBURSEMENT",
        "VENDOR_PAYMENT",
        "BUSINESS_TRIP",
        "MARKETING_CAMPAIGN",
        "TRAINING_COURSE",
        "ADVANCE_SMALL",
        "ADVANCE_MEDIUM",
        "ADVANCE_LARGE",
    }
)
IN_FLIGHT = [
    "PENDING_APPROVAL",
    "NEEDS_INFO",
    "READY_FOR_EXECUTION",
    "IN_PROGRESS",
    "WAITING_FOR_ACCEPTANCE",
]


def guard_mode() -> str:
    mode = os.environ.get("EAS_RESOURCE_GUARD", "advisory").strip().lower()
    return mode if mode in ("off", "advisory", "enforce") else "advisory"


def authoritative_sources() -> frozenset[str]:
    raw = os.environ.get("EAS_RESOURCE_AUTHORITATIVE_SOURCES", "")
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def max_age() -> timedelta:
    try:
        hours = int(os.environ.get("EAS_RESOURCE_MAX_AGE_HOURS", "24"))
    except ValueError:
        hours = 24
    return timedelta(hours=max(1, hours))


def _year(payload: dict[str, Any], now: datetime) -> int:
    start = payload.get("start_date")
    if isinstance(start, str):
        try:
            return date.fromisoformat(start).year
        except ValueError:
            pass
    return now.year


def _unavailable(kind: str, requested: Decimal, source: str) -> GuardResult:
    return GuardResult(
        kind=kind,
        status=UNVERIFIED,
        reason="SOURCE_UNAVAILABLE",
        message="Không đọc được nguồn số dư lúc này; chưa xác nhận được.",
        requested=requested,
        available=None,
        reserved=Decimal(0),
        source=source,
        blocking=False,
    )


def _leave(cursor, *, actor_id, leave_type, days, year, request_id, lock, now, mode):
    requested = Decimal(days)
    if lock:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"resource:leave:{actor_id}:{year}"],
        )
    cursor.execute(
        """
        SELECT lb.entitled_days - lb.used_days, lb.updated_at
        FROM mock_hr.leave_balance lb
        JOIN mock_hr.employee_directory e ON e.id = lb.employee_id
        JOIN eas.app_user u ON lower(u.email) = lower(e.work_email)
        WHERE u.id = %s AND lb.leave_type = %s AND lb.year = %s
        """,
        [actor_id, leave_type, year],
    )
    row = cursor.fetchone()
    cursor.execute(
        """
        SELECT v.payload FROM eas.request r
        JOIN eas.request_type rt ON rt.id = r.type_id
        JOIN eas.request_revision v ON v.id = r.current_revision_id
        WHERE r.requester_id = %s AND rt.code = ANY(%s) AND r.status = ANY(%s)
          AND r.id IS DISTINCT FROM %s::uuid
        """,
        [actor_id, list(LEAVE_TYPE_MAP), IN_FLIGHT, request_id],
    )
    reserved = Decimal(sum(_extract_days(p or {}) or 0 for (p,) in cursor.fetchall()))
    balance = (
        Balance(
            LEAVE_SOURCE,
            Decimal(row[0]),
            row[1],
            LEAVE_SOURCE in authoritative_sources(),
        )
        if row
        else None
    )
    return evaluate(
        kind="LEAVE",
        requested=requested,
        balance=balance,
        reserved=reserved,
        now=now,
        max_age=max_age(),
        mode=mode,
    )


def _budget(cursor, *, department_id, amount, year, request_id, lock, now, mode):
    requested = Decimal(amount)
    cursor.execute(
        """
        SELECT m.cost_center FROM eas.department d
        JOIN mock_hr.department m ON m.code = d.code WHERE d.id = %s
        """,
        [department_id],
    )
    cost_center = cursor.fetchone()
    balance = None
    reserved = Decimal(0)
    if cost_center:
        if lock:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [f"resource:budget:{cost_center[0]}:{year}"],
            )
        cursor.execute(
            """
            SELECT approved_minor - committed_minor - spent_minor, updated_at
            FROM mock_finance.cost_center_budget
            WHERE cost_center = %s AND fiscal_year = %s AND currency = 'VND'
            """,
            [cost_center[0], year],
        )
        row = cursor.fetchone()
        cursor.execute(
            """
            SELECT COALESCE(sum(v.amount_vnd), 0) FROM eas.request r
            JOIN eas.request_type rt ON rt.id = r.type_id
            JOIN eas.request_revision v ON v.id = r.current_revision_id
            WHERE v.department_id = %s AND rt.code = ANY(%s) AND r.status = ANY(%s)
              AND r.id IS DISTINCT FROM %s::uuid
            """,
            [department_id, sorted(BUDGET_TYPES), IN_FLIGHT, request_id],
        )
        reserved = Decimal(cursor.fetchone()[0])
        if row:
            # ISO 4217: VND has no minor unit, so *_minor values are VND.
            balance = Balance(
                BUDGET_SOURCE,
                Decimal(row[0]),
                row[1],
                BUDGET_SOURCE in authoritative_sources(),
            )
    return evaluate(
        kind="BUDGET",
        requested=requested,
        balance=balance,
        reserved=reserved,
        now=now,
        max_age=max_age(),
        mode=mode,
    )


def check_resources(
    cursor,
    *,
    actor_id: str,
    department_id: str,
    type_code: str,
    payload: dict[str, Any],
    amount: int | None,
    request_id: str | None = None,
    lock: bool = False,
) -> list[GuardResult]:
    mode = guard_mode()
    if mode == "off":
        return []
    now = datetime.now(timezone.utc)
    year = _year(payload, now)
    checks = []
    leave_type = LEAVE_TYPE_MAP.get(type_code)
    days = _extract_days(payload) if leave_type else None
    if leave_type and days:
        checks.append(
            (
                "LEAVE",
                Decimal(days),
                LEAVE_SOURCE,
                lambda: _leave(
                    cursor,
                    actor_id=actor_id,
                    leave_type=leave_type,
                    days=days,
                    year=year,
                    request_id=request_id,
                    lock=lock,
                    now=now,
                    mode=mode,
                ),
            )
        )
    if type_code in BUDGET_TYPES and amount:
        checks.append(
            (
                "BUDGET",
                Decimal(amount),
                BUDGET_SOURCE,
                lambda: _budget(
                    cursor,
                    department_id=department_id,
                    amount=amount,
                    year=year,
                    request_id=request_id,
                    lock=lock,
                    now=now,
                    mode=mode,
                ),
            )
        )
    results = []
    for kind, requested, source, run in checks:
        try:
            # A missing or unreadable source must not abort the submit.
            with transaction.atomic():
                results.append(run())
        except DatabaseError:
            results.append(_unavailable(kind, requested, source))
    return results
