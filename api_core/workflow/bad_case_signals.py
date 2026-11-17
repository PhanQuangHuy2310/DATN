"""Tín hiệu ngữ cảnh cho suy luận tình huống xấu (ai_service/bad_cases.py).

Mỗi tín hiệu là một truy vấn tham số hóa trên lịch sử thật của người gửi; chỉ số đếm và tổng tiền
được gửi sang dịch vụ AI, không gửi nội dung hồ sơ hay dữ liệu cá nhân.
"""

from __future__ import annotations

from typing import Any

from django.db import connection

FINANCE_TYPES = (
    "ADVANCE_SMALL",
    "ADVANCE_MEDIUM",
    "ADVANCE_LARGE",
    "EXPENSE_CLAIM",
    "REIMBURSEMENT",
    "SALARY_ADVANCE",
    "REFUND_COMPENSATION",
)
EXCLUDED_STATUSES = ("DRAFT", "CANCELLED", "REJECTED")

SQL_SIGNALS = """
    WITH me AS (
      SELECT r.id, r.requester_id, v.payload, v.submitted_at
      FROM eas.request r
      JOIN eas.request_revision v ON v.id = r.current_revision_id
      WHERE r.id = %(request_id)s
    )
    SELECT
      -- việc đang giữ (bước duyệt hoặc lượt thực hiện còn mở) có hạn SLA trong 24 giờ tới
      (SELECT count(DISTINCT st.id)
         FROM eas.sla_stage st
         LEFT JOIN eas.approval_step s ON s.id = st.approval_step_id
         LEFT JOIN eas.execution_attempt a ON a.id = st.attempt_id
        WHERE st.closed_at IS NULL
          AND st.request_id <> me.id
          AND st.due_at <= coalesce(me.submitted_at, now()) + interval '24 hours'
          AND ((s.assignee_id = me.requester_id AND s.state = 'ACTIVE')
               OR (a.executor_id = me.requester_id AND a.closed_at IS NULL))),
      nullif(me.payload->>'handover_user_id', '') IS NOT NULL,
      -- hồ sơ tài chính đã gửi trong 7 ngày (gồm hồ sơ này)
      (SELECT coalesce(sum(v2.amount_vnd), 0)
         FROM eas.request r2
         JOIN eas.request_type t2 ON t2.id = r2.type_id
         JOIN eas.request_revision v2 ON v2.id = r2.current_revision_id
        WHERE r2.requester_id = me.requester_id
          AND t2.code = ANY(%(finance)s)
          AND r2.status <> ALL(%(excluded)s)
          AND v2.submitted_at > coalesce(me.submitted_at, now()) - interval '7 days'
          AND v2.submitted_at <= coalesce(me.submitted_at, now())),
      (SELECT count(*)
         FROM eas.request r2
         JOIN eas.request_type t2 ON t2.id = r2.type_id
         JOIN eas.request_revision v2 ON v2.id = r2.current_revision_id
        WHERE r2.requester_id = me.requester_id
          AND t2.code = ANY(%(finance)s)
          AND r2.status <> ALL(%(excluded)s)
          AND v2.submitted_at > coalesce(me.submitted_at, now()) - interval '7 days'
          AND v2.submitted_at <= coalesce(me.submitted_at, now())),
      -- điều chỉnh chấm công trong 30 ngày (gồm hồ sơ này)
      (SELECT count(*)
         FROM eas.request r2
         JOIN eas.request_type t2 ON t2.id = r2.type_id
         JOIN eas.request_revision v2 ON v2.id = r2.current_revision_id
        WHERE r2.requester_id = me.requester_id
          AND t2.code = 'ATTENDANCE_ADJUSTMENT'
          AND r2.status <> ALL(%(excluded)s)
          AND v2.submitted_at > coalesce(me.submitted_at, now()) - interval '30 days'
          AND v2.submitted_at <= coalesce(me.submitted_at, now()))
    FROM me
"""

EMPTY: dict[str, Any] = {
    "active_tasks_due_24h": 0,
    "handover_assigned": None,
    "requester_amount_7d": 0.0,
    "requester_finance_count_7d": 0,
    "attendance_count_30d": 0,
}


def load_signals(request_id: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            SQL_SIGNALS,
            {
                "request_id": request_id,
                "finance": list(FINANCE_TYPES),
                "excluded": list(EXCLUDED_STATUSES),
            },
        )
        row = cursor.fetchone()
    if not row:
        return dict(EMPTY)
    return {
        "active_tasks_due_24h": int(row[0] or 0),
        "handover_assigned": bool(row[1]),
        "requester_amount_7d": float(row[2] or 0),
        "requester_finance_count_7d": int(row[3] or 0),
        "attendance_count_30d": int(row[4] or 0),
    }


def safe_load_signals(request_id: str) -> dict[str, Any]:
    """Như load_signals nhưng không bao giờ làm hỏng luồng duyệt: lỗi truy vấn thì trả tín hiệu rỗng."""
    import logging

    try:
        return load_signals(request_id)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning("bad-case signals unavailable: request=%s", request_id, exc_info=True)
        return dict(EMPTY)
