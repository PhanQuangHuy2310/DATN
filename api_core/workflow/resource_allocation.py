"""Borrowing company resources: meeting rooms, vehicles, equipment.

The asset and facility systems are external (simulated by the Mock Systems
API). EAS decides *who* gets a resource; the external systems hold the stock.
Every read and write goes through api_core.integrations.client.
See docs/TICH_HOP_HE_THONG_NGOAI.md §4.2.

Rules (project owner, 04/11/2026):
* First request to be fully approved gets the resource: the final approval
  books it in the external system.
* When the period written in the request ends, the worker returns it.
* The board of directors (department BOD) has priority: when nothing is free,
  an employee's allocation is cancelled, that request becomes REJECTED and the
  employee is notified. A request already handed over and awaiting acceptance
  is never taken back, nor is another board member's allocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from api_core.integrations import client
from api_core.integrations.client import IntegrationError
from api_core.workflow.errors import CommandError

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DAY_START, DAY_END = time(8, 0), time(17, 30)
PRIORITY_DEPARTMENT = "BOD"
PREEMPTABLE_STATUSES = ("READY_FOR_EXECUTION", "IN_PROGRESS", "COMPLETED")
HOLDING_STATUSES = (*PREEMPTABLE_STATUSES, "WAITING_FOR_ACCEPTANCE")
# Orphan allocations (EAS transaction rolled back after the API call) are only
# cancelled once untouched for this long, so in-flight approvals are safe.
ORPHAN_GRACE = timedelta(minutes=10)

SQL_CLOSE_OPEN_SLA = """
    UPDATE eas.sla_stage SET closed_at=%s
    WHERE request_id=%s AND closed_at IS NULL
"""


class ResourceUnavailable(Exception):
    """Nothing free for the requested window (and no allowed preemption)."""


@dataclass(frozen=True)
class Need:
    kind: str  # FACILITY | ASSET
    code: str  # resource code (room / vehicle) or asset category code
    quantity: int
    starts_at: datetime
    ends_at: datetime
    headcount: int | None
    purpose: str

    @property
    def system(self) -> str:
        return "facilities" if self.kind == "FACILITY" else "assets"

    def availability(self) -> dict[str, Any]:
        code = quote(self.code, safe="")  # a path segment, never a path
        path = (
            f"facilities/resources/{code}/availability"
            if self.kind == "FACILITY"
            else f"assets/categories/{code}/availability"
        )
        try:
            return client.get(
                self.system,
                path,
                **{"from": self.starts_at.isoformat(), "to": self.ends_at.isoformat()},
            )
        except IntegrationError as exc:
            if exc.status == 404:
                raise CommandError("RESOURCE_UNKNOWN", status=422) from None
            raise


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _clock(value: Any) -> time | None:
    try:
        return time.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def need_for(type_code: str, payload: dict[str, Any]) -> Need | None:
    """What a request asks for, or None when it borrows nothing (old forms too)."""
    title = str(payload.get("title") or type_code)[:300]
    if type_code == "ROOM_BOOKING" and payload.get("room_code"):
        day = _day(payload.get("booking_date"))
        start, end = _clock(payload.get("start_time")), _clock(payload.get("end_time"))
        if not day or not start or not end or end <= start:
            return None
        return Need(
            "FACILITY",
            payload["room_code"],
            1,
            datetime.combine(day, start, VN_TZ),
            datetime.combine(day, end, VN_TZ),
            payload.get("attendees_count"),
            title,
        )
    if type_code in {"VEHICLE_BOOKING", "EQUIPMENT_BORROW"}:
        code = payload.get("vehicle_code") or payload.get("asset_category")
        start, end = _day(payload.get("start_date")), _day(payload.get("end_date"))
        if not code or not start or not end or end < start:
            return None
        window = (
            datetime.combine(start, DAY_START, VN_TZ),
            datetime.combine(end, DAY_END, VN_TZ),
        )
        if type_code == "VEHICLE_BOOKING":
            return Need("FACILITY", code, 1, *window, payload.get("passengers"), title)
        return Need(
            "ASSET", code, int(payload.get("quantity") or 1), *window, None, title
        )
    return None


def is_priority(cursor, user_id: str) -> bool:
    cursor.execute(
        """
        SELECT d.code FROM eas.app_user u JOIN eas.department d ON d.id = u.department_id
        WHERE u.id = %s
        """,
        [user_id],
    )
    row = cursor.fetchone()
    return bool(row and row[0] == PRIORITY_DEPARTMENT)


def _holder_requests(cursor, holder_ids: list[str]) -> list[tuple[str, str, bool]]:
    """(request id, status, held by board?) of EAS requests holding the resource."""
    if not holder_ids:
        return []
    cursor.execute(
        """
        SELECT q.id::text, q.status, d.code = %s
        FROM eas.request q
        JOIN eas.app_user u ON u.id = q.requester_id
        JOIN eas.department d ON d.id = u.department_id
        WHERE q.id = ANY(%s::uuid[])
        ORDER BY q.approved_at DESC NULLS LAST, q.id
        """,
        [PRIORITY_DEPARTMENT, holder_ids],
    )
    return cursor.fetchall()


def check_request(cursor, *, need: Need, requester_id: str) -> str | None:
    """Submit-time check; returns an error code or None.

    Board members are only stopped by an unknown or out-of-service resource: a
    busy one can still be taken back at approval time.
    """
    data = need.availability()
    if need.kind == "FACILITY":
        if data["status"] in {"MAINTENANCE", "INACTIVE"}:
            return "RESOURCE_OUT_OF_SERVICE"
        if need.headcount and need.headcount > data["capacity"]:
            return "RESOURCE_CAPACITY_EXCEEDED"
        busy = bool(data["holders"])
    else:
        busy = data["free"] < need.quantity
    if busy and not is_priority(cursor, requester_id):
        return "RESOURCE_UNAVAILABLE"
    return None


def _close_workflow(
    cursor, request_id: str, revision_id: str | None, now: datetime
) -> None:
    if not revision_id:
        return
    cursor.execute(
        """
        UPDATE eas.workflow_instance SET state = 'REJECTED', closed_at = %s
        WHERE revision_id = %s AND state = 'ACTIVE'
        """,
        [now, revision_id],
    )
    cursor.execute(
        """
        UPDATE eas.approval_step SET state = 'SKIPPED', closed_at = %s
        WHERE request_id = %s AND state IN ('WAITING', 'ACTIVE')
        """,
        [now, request_id],
    )
    # An attempt can only finish from RUNNING (guard_attempt).
    cursor.execute(
        """
        UPDATE eas.execution_attempt SET state = 'RUNNING', started_at = %s
        WHERE request_id = %s AND state = 'READY'
        """,
        [now, request_id],
    )
    cursor.execute(
        """
        UPDATE eas.execution_attempt
        SET state = 'FINISHED', closure_kind = 'REASSIGNED', closed_at = %s
        WHERE request_id = %s AND state = 'RUNNING'
        """,
        [now, request_id],
    )
    cursor.execute(SQL_CLOSE_OPEN_SLA, [now, request_id])


def preempt(
    cursor, *, victim_id: str, by_request_id: str, system: str, now: datetime
) -> str:
    """Take back an employee's allocation for the board. Returns the victim code."""
    from api_core.workflow.service import _append_request_audit

    cursor.execute(
        """
        SELECT code, status, current_revision_id::text FROM eas.request
        WHERE id = %s FOR UPDATE
        """,
        [victim_id],
    )
    row = cursor.fetchone()
    if not row or row[1] not in PREEMPTABLE_STATUSES:
        raise ResourceUnavailable(victim_id)
    code, previous_status, revision_id = row
    released = client.post(
        system, "allocations/cancel", {"source_request_id": victim_id}
    ).get("released", [])
    _close_workflow(cursor, victim_id, revision_id, now)
    cursor.execute("SELECT set_config('eas.preempt_request_id', %s, true)", [victim_id])
    cursor.execute(
        """
        UPDATE eas.request SET status = 'REJECTED', lock_version = lock_version + 1,
          completed_at = NULL, updated_at = greatest(%s, updated_at)
        WHERE id = %s
        """,
        [now, victim_id],
    )
    cursor.execute("SELECT set_config('eas.preempt_request_id', '', true)")
    details = {
        "previous_status": previous_status,
        "preempted_by_request_id": by_request_id,
        "released": released,
        "reason": "Ban Giám đốc cần sử dụng tài nguyên trong cùng thời gian.",
    }
    _append_request_audit(
        cursor,
        request_id=victim_id,
        actor_id=None,
        actor_kind="SYSTEM",
        action="RESOURCE_PREEMPTED",
        target_type="request",
        target_id=victim_id,
        details=details,
        correlation_id=str(uuid4()),
        occurred_at=now,
    )
    cursor.execute(
        """
        INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
        VALUES (%s,'RESOURCE_PREEMPTED',%s,%s)
        """,
        [
            victim_id,
            Jsonb({"request_id": victim_id, **details}),
            f"request:{victim_id}:preempted:{by_request_id}",
        ],
    )
    return code


def _victims(cursor, need: Need, holders: list[dict]) -> list[str]:
    """Employee requests the board may take the resource back from (newest first).

    A room / vehicle is indivisible: if any holder may not be preempted
    (another board member, a request awaiting acceptance, an unknown source),
    nothing is taken back.
    """
    rows = _holder_requests(
        cursor, [h["source_request_id"] for h in holders if h["source_request_id"]]
    )
    allowed = [r[0] for r in rows if not r[2] and r[1] in PREEMPTABLE_STATUSES]
    if need.kind == "FACILITY" and len(allowed) != len(holders):
        raise ResourceUnavailable(need.code)
    return allowed


def allocate(
    cursor, *, request_id: str, requester_id: str, need: Need, now: datetime
) -> dict[str, Any]:
    """Book the resource in the external system for an approved request."""
    cursor.execute("SELECT email FROM eas.app_user WHERE id = %s", [requester_id])
    email = cursor.fetchone()[0]
    priority = is_priority(cursor, requester_id)
    data = need.availability()
    preempted: list[str] = []

    def take_back(victim: str) -> None:
        preempted.append(
            preempt(
                cursor,
                victim_id=victim,
                by_request_id=request_id,
                system=need.system,
                now=now,
            )
        )

    if need.kind == "FACILITY":
        if data["status"] in {"MAINTENANCE", "INACTIVE"}:
            raise ResourceUnavailable(need.code)
        if data["holders"]:
            if not priority:
                raise ResourceUnavailable(need.code)
            for victim in _victims(cursor, need, data["holders"]):
                take_back(victim)
        path = "facilities/reservations"
        body = {
            "resource_code": need.code,
            "starts_at": need.starts_at.isoformat(),
            "ends_at": need.ends_at.isoformat(),
            "requester_email": email,
            "purpose": need.purpose,
        }
    else:
        if data["free"] < need.quantity and priority:
            for victim in _victims(cursor, need, data["holders"]):
                take_back(victim)
                if need.availability()["free"] >= need.quantity:
                    break
        path = "assets/loans"
        body = {
            "category_code": need.code,
            "quantity": need.quantity,
            "starts_at": need.starts_at.isoformat(),
            "due_at": need.ends_at.isoformat(),
            "borrower_email": email,
        }
    try:
        result = client.post(
            need.system, path, {**body, "source_request_id": request_id}
        )
    except IntegrationError as exc:
        if exc.code in {"RESOURCE_UNAVAILABLE", "RESOURCE_OUT_OF_SERVICE"}:
            raise ResourceUnavailable(need.code) from None
        raise
    return {
        "kind": need.kind,
        "code": need.code,
        "items": result.get("items", []),
        "starts_at": need.starts_at.isoformat(),
        "ends_at": need.ends_at.isoformat(),
        **({"preempted_requests": preempted} if preempted else {}),
    }


def need_for_request(cursor, request_id: str) -> Need | None:
    cursor.execute(
        """
        SELECT rt.code, v.payload FROM eas.request r
        JOIN eas.request_type rt ON rt.id = r.type_id
        JOIN eas.request_revision v ON v.id = r.current_revision_id
        WHERE r.id = %s
        """,
        [request_id],
    )
    row = cursor.fetchone()
    if not row or not isinstance(row[1], dict):
        return None
    return need_for(row[0], row[1])


# --------------------------------------------------------------------------
# Worker: end of the borrowing period, orphan reconciliation
# --------------------------------------------------------------------------
def release_expired(cursor, *, now: datetime) -> list[tuple[str, list[str]]]:
    """Return everything whose period ended; cancel orphan allocations."""
    from api_core.workflow.service import _append_request_audit

    returned = []
    ended = client.get(
        "allocations", "allocations", state="ended", before=now.isoformat()
    )["items"]
    for request_id in ended:
        codes = client.post(
            "allocations", "allocations/return", {"source_request_id": request_id}
        ).get("released", [])
        if not codes:
            continue
        cursor.execute("SELECT 1 FROM eas.request WHERE id = %s", [request_id])
        if cursor.fetchone():
            _append_request_audit(
                cursor,
                request_id=request_id,
                actor_id=None,
                actor_kind="SYSTEM",
                action="RESOURCE_RETURNED",
                target_type="request",
                target_id=request_id,
                details={"released": codes},
                correlation_id=str(uuid4()),
                occurred_at=now,
            )
        returned.append((request_id, codes))

    active = client.get(
        "allocations",
        "allocations",
        state="active",
        before=(now - ORPHAN_GRACE).isoformat(),
    )["items"]
    if active:
        cursor.execute(
            "SELECT id::text FROM eas.request WHERE id = ANY(%s::uuid[]) AND status = ANY(%s)",
            [active, list(HOLDING_STATUSES)],
        )
        keep = {row[0] for row in cursor.fetchall()}
        for request_id in set(active) - keep:
            client.post(
                "allocations", "allocations/cancel", {"source_request_id": request_id}
            )
    return returned
