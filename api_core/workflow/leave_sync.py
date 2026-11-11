"""Approved leave / business trip requests become working-status records.

When a request of these types is fully approved, an APPROVED row is written to
eas.user_leave_and_trips so eas.get_user_working_status shows the employee as
"Nghỉ làm" / "Công tác" on both portals for the requested days.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from django.db import DatabaseError, transaction

logger = logging.getLogger(__name__)
VN_TZ = timezone(timedelta(hours=7))
# request type -> leave type stored in eas.user_leave_and_trips
LEAVE_TYPES = {
    "LEAVE": "PAID_LEAVE",
    "LEAVE_SPECIAL": "PAID_LEAVE",
    "BUSINESS_TRIP": "BUSINESS_TRIP",
}
# Attendance adjustments: half-day windows on the work date (08:00-17:30 day).
ATTENDANCE_WINDOWS = {
    "Đi muộn": ("LATE_IN", time(8, 0), time(12, 0)),
    "Về sớm": ("EARLY_OUT", time(13, 30), time(17, 30)),
}


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def leave_record(
    type_code: str, payload: dict
) -> tuple[str, datetime, datetime] | None:
    """(leave_type, start, end) for a request payload, or None if not applicable."""
    if type_code in LEAVE_TYPES:
        start, end = _day(payload.get("start_date")), _day(payload.get("end_date"))
        if not start or not end or end < start:
            return None
        kind = LEAVE_TYPES[type_code]
        if type_code == "LEAVE" and payload.get("leave_kind") == "KHONG_LUONG":
            kind = "UNPAID_LEAVE"  # "Nghỉ không lương" menu entry
        return (
            kind,
            datetime.combine(start, time.min, VN_TZ),
            datetime.combine(end, time(23, 59, 59), VN_TZ),
        )
    if type_code == "ATTENDANCE_ADJUSTMENT":
        window = ATTENDANCE_WINDOWS.get(payload.get("change_type"))
        work_date = _day(payload.get("work_date"))
        if not window or not work_date:
            return None
        kind, start, end = window
        return (
            kind,
            datetime.combine(work_date, start, VN_TZ),
            datetime.combine(work_date, end, VN_TZ),
        )
    return None


def record_approved_leave(cursor, request_id: str, approver_name: str) -> None:
    """Best effort: a status-sync failure never blocks the approval itself."""
    cursor.execute(
        """
        SELECT rt.code, r.requester_id::text, rv.payload
        FROM eas.request r
        JOIN eas.request_type rt ON rt.id = r.type_id
        LEFT JOIN eas.request_revision rv ON rv.id = r.current_revision_id
        WHERE r.id = %s
        """,
        [request_id],
    )
    row = cursor.fetchone()
    if not row or row[0] not in {*LEAVE_TYPES, "ATTENDANCE_ADJUSTMENT"}:
        return
    type_code, requester_id, payload = row
    payload = payload if isinstance(payload, dict) else {}
    record = leave_record(type_code, payload)
    if not record:
        return
    kind, start, end = record
    title = str(payload.get("title") or payload.get("reason") or type_code)[:300]
    try:
        with transaction.atomic():
            cursor.execute(
                """
                INSERT INTO eas.user_leave_and_trips
                    (id, user_id, type, title, start_time, end_time, approval_status, approved_by, created_at)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 'APPROVED', %s, now())
                """,
                [requester_id, kind, title, start, end, approver_name[:150]],
            )
    except DatabaseError:
        logger.warning(
            "leave_status_sync_failed", extra={"request_id": request_id}, exc_info=True
        )
