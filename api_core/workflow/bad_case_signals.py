"""Tín hiệu ngữ cảnh cho suy luận tình huống xấu và luật quy định có điều kiện.

Mỗi tín hiệu là một truy vấn tham số hóa trên lịch sử thật của người gửi trong CSDL. Chỉ số
đếm, tổng tiền và số giờ còn lại tới hạn được gửi sang dịch vụ AI, không gửi nội dung hồ sơ hay
dữ liệu cá nhân.

Tín hiệu (mốc thời gian = lúc hồ sơ được gửi):
  handover_assigned       có người nhận bàn giao VÀ người đó đủ vai trò làm thay mọi việc đến hạn
                          (72 giờ tới hoặc trong thời gian vắng); uncovered_work: số việc không ai làm thay
  open_work_due_hours     số giờ còn lại tới hạn của từng việc người gửi đang giữ (bước duyệt
                          đang chờ, lượt thực hiện chưa xong, nghiệm thu đang chờ); hạn = sớm hơn
                          giữa hạn SLA và hạn nghiệp vụ trong biểu mẫu (due_date/end_date)
  work_due_in_absence     số việc trên có hạn rơi vào khoảng vắng mặt của chính đơn (start..end)
  active_tasks_due_24h    số việc đến hạn trong 24 giờ (giữ cho tương thích)
  same_type_count_*       số hồ sơ cùng loại của người gửi trong 7/30 ngày và trong tháng dương lịch
  requester_amount_7d     tổng tiền hồ sơ tài chính 7 ngày; requester_finance_count_7d: số hồ sơ
  attendance_count_30d    số lần điều chỉnh chấm công 30 ngày (giữ cho tương thích)
  team_absence_ratio      tỉ lệ thành viên khác cùng phòng đã vắng (nghỉ/công tác đã duyệt) trùng ngày
  requester_rejected_30d  số hồ sơ của người gửi bị từ chối trong 30 ngày
  ai_revoked_90d          số lần quyết định tự duyệt của AI trên hồ sơ của người gửi bị thu hồi (90 ngày)
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import connection

logger = logging.getLogger(__name__)

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
MAX_WORK_ITEMS = 50
LOCAL_TZ = "Asia/Ho_Chi_Minh"

# Một ngày trong biểu mẫu (YYYY-MM-DD) hết hạn lúc 17:30 giờ Việt Nam.
_PAYLOAD_DUE = """
  CASE WHEN coalesce(v.payload->>'due_date', v.payload->>'end_date') ~ '^\\d{4}-\\d{2}-\\d{2}'
       THEN (left(coalesce(v.payload->>'due_date', v.payload->>'end_date'), 10)::date
             + time '17:30') AT TIME ZONE %(tz)s END
"""

SQL_SIGNALS = f"""
    WITH me AS (
      SELECT r.id, r.requester_id, rt.code AS type_code, r.type_id, v.payload,
             coalesce(v.submitted_at, now()) AS t0, u.department_id,
             CASE WHEN coalesce(v.payload->>'start_date', v.payload->>'date') ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}'
                  THEN left(coalesce(v.payload->>'start_date', v.payload->>'date'), 10)::date END AS d_start,
             CASE WHEN coalesce(v.payload->>'end_date', v.payload->>'start_date', v.payload->>'date')
                       ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}'
                  THEN left(coalesce(v.payload->>'end_date', v.payload->>'start_date',
                                     v.payload->>'date'), 10)::date END AS d_end,
             CASE WHEN coalesce(v.payload->>'visit_date', v.payload->>'booking_date') ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}'
                  THEN left(coalesce(v.payload->>'visit_date', v.payload->>'booking_date'), 10)::date
             END AS d_event,
             CASE WHEN v.payload->>'handover_user_id' ~ '^[0-9a-fA-F-]{{36}}$'
                  THEN (v.payload->>'handover_user_id')::uuid END AS handover_id,
             upper(regexp_replace(coalesce(v.payload->>'invoice_number', ''), '\\s', '', 'g')) AS invoice_no,
             lower(btrim(coalesce(v.payload->>'customer_name', ''))) AS customer
      FROM eas.request r
      JOIN eas.request_type rt ON rt.id = r.type_id
      JOIN eas.request_revision v ON v.id = r.current_revision_id
      JOIN eas.app_user u ON u.id = r.requester_id
      WHERE r.id = %(request_id)s
    ),
    work AS (
      -- việc đang giữ: bước duyệt ACTIVE, lượt thực hiện chưa đóng, nghiệm thu đang chờ
      SELECT st.request_id, st.kind, rq.type_id AS item_type, v.department_id AS item_dept,
             rq.requester_id AS item_requester,
             least(st.due_at, coalesce({_PAYLOAD_DUE}, st.due_at)) AS due_at
      FROM eas.sla_stage st
      JOIN me ON true
      LEFT JOIN eas.approval_step s ON s.id = st.approval_step_id
      LEFT JOIN eas.execution_attempt a ON a.id = st.attempt_id
      LEFT JOIN eas.workflow_instance i ON i.id = coalesce(s.instance_id, a.instance_id)
      JOIN eas.request rq ON rq.id = st.request_id
      JOIN eas.request_revision v ON v.id = rq.current_revision_id
      WHERE st.closed_at IS NULL
        AND st.request_id <> me.id
        AND (
          (st.kind = 'APPROVAL' AND s.state = 'ACTIVE' AND s.assignee_id = me.requester_id)
          OR (st.kind = 'EXECUTION' AND a.closed_at IS NULL AND a.executor_id = me.requester_id)
          OR (st.kind = 'ACCEPTANCE' AND rq.status = 'WAITING_FOR_ACCEPTANCE'
              AND i.acceptor_id = me.requester_id)
        )
    ),
    urgent AS (
      -- việc đến hạn trong 72 giờ hoặc trong thời gian vắng, kèm người nhận bàn giao có làm thay được không
      SELECT w.*, (
        me.handover_id IS NOT NULL AND me.handover_id <> w.item_requester AND EXISTS (
          SELECT 1 FROM eas.role_membership rm
          WHERE rm.user_id = me.handover_id
            AND rm.role = CASE w.kind WHEN 'APPROVAL' THEN 'APPROVER'
                                      WHEN 'EXECUTION' THEN 'EXECUTOR' ELSE 'ACCEPTOR' END
            AND rm.revoked_at IS NULL AND rm.valid_from <= statement_timestamp()
            AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
            AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = w.item_dept)
            AND (rm.type_scope = 'ALL' OR rm.type_id = w.item_type))
      ) AS covered
      FROM work w, me
      WHERE w.due_at <= me.t0 + interval '72 hours'
         OR (me.d_start IS NOT NULL
             AND (w.due_at AT TIME ZONE %(tz)s)::date BETWEEN me.d_start AND me.d_end)
    ),
    hist AS (
      SELECT r2.id, t2.code, r2.status, v2.amount_vnd, v2.submitted_at
      FROM eas.request r2
      JOIN eas.request_type t2 ON t2.id = r2.type_id
      JOIN eas.request_revision v2 ON v2.id = r2.current_revision_id
      JOIN me ON r2.requester_id = me.requester_id
      WHERE v2.submitted_at <= me.t0 AND v2.submitted_at > me.t0 - interval '90 days'
    ),
    absences AS (
      -- vắng mặt: lịch nghỉ/công tác đã duyệt + đơn nghỉ/công tác trong EAS chưa bị từ chối/hủy
      SELECT x.user_id, (x.start_time AT TIME ZONE %(tz)s)::date AS d1,
             (x.end_time AT TIME ZONE %(tz)s)::date AS d2
      FROM eas.user_leave_and_trips x
      WHERE upper(x.approval_status) = 'APPROVED'
      UNION ALL
      SELECT r3.requester_id, left(v3.payload->>'start_date', 10)::date,
             left(CASE WHEN v3.payload->>'end_date' ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}'
                       THEN v3.payload->>'end_date' ELSE v3.payload->>'start_date' END, 10)::date
      FROM eas.request r3
      JOIN eas.request_type t3 ON t3.id = r3.type_id
      JOIN eas.request_revision v3 ON v3.id = r3.current_revision_id
      JOIN me ON r3.id <> me.id
      WHERE t3.code IN ('LEAVE', 'LEAVE_SPECIAL', 'BUSINESS_TRIP')
        AND r3.status <> ALL(%(excluded)s)
        AND v3.payload->>'start_date' ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}'
    ),
    team AS (
      SELECT m.id FROM eas.app_user m JOIN me ON m.department_id = me.department_id
      WHERE m.is_active AND m.id <> me.requester_id AND NOT m.is_system_account
    ),
    handover_work AS (
      SELECT least(st.due_at, coalesce({_PAYLOAD_DUE}, st.due_at)) AS due_at
      FROM eas.sla_stage st
      JOIN me ON me.handover_id IS NOT NULL
      LEFT JOIN eas.approval_step s ON s.id = st.approval_step_id
      LEFT JOIN eas.execution_attempt a ON a.id = st.attempt_id
      JOIN eas.request rq ON rq.id = st.request_id
      JOIN eas.request_revision v ON v.id = rq.current_revision_id
      WHERE st.closed_at IS NULL
        AND ((st.kind = 'APPROVAL' AND s.state = 'ACTIVE' AND s.assignee_id = me.handover_id)
             OR (st.kind = 'EXECUTION' AND a.closed_at IS NULL AND a.executor_id = me.handover_id))
    )
    SELECT
      (SELECT coalesce(array_agg(h ORDER BY h), '{{}}')
         FROM (SELECT round(extract(epoch FROM (w.due_at - me.t0)) / 3600.0, 1)::float8 AS h
                 FROM work w, me ORDER BY w.due_at LIMIT {MAX_WORK_ITEMS}) x),
      (SELECT count(*) FROM work w, me
        WHERE me.d_start IS NOT NULL
          AND (w.due_at AT TIME ZONE %(tz)s)::date BETWEEN me.d_start AND me.d_end),
      (SELECT count(*) FROM work w, me WHERE w.due_at <= me.t0 + interval '24 hours'),
      -- bàn giao hợp lệ: có người nhận VÀ người đó làm thay được mọi việc đến hạn
      (me.handover_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM urgent WHERE NOT covered)),
      (SELECT count(*) FROM hist WHERE hist.code = me.type_code AND hist.status <> ALL(%(excluded)s)
          AND hist.submitted_at > me.t0 - interval '7 days'),
      (SELECT count(*) FROM hist WHERE hist.code = me.type_code AND hist.status <> ALL(%(excluded)s)
          AND hist.submitted_at > me.t0 - interval '30 days'),
      (SELECT count(*) FROM hist WHERE hist.code = me.type_code AND hist.status <> ALL(%(excluded)s)
          AND date_trunc('month', hist.submitted_at AT TIME ZONE %(tz)s)
              = date_trunc('month', me.t0 AT TIME ZONE %(tz)s)),
      (SELECT coalesce(sum(amount_vnd), 0) FROM hist
        WHERE hist.code = ANY(%(finance)s) AND hist.status <> ALL(%(excluded)s)
          AND hist.submitted_at > me.t0 - interval '7 days'),
      (SELECT count(*) FROM hist
        WHERE hist.code = ANY(%(finance)s) AND hist.status <> ALL(%(excluded)s)
          AND hist.submitted_at > me.t0 - interval '7 days'),
      (SELECT count(*) FROM hist WHERE hist.code = 'ATTENDANCE_ADJUSTMENT'
          AND hist.status <> ALL(%(excluded)s) AND hist.submitted_at > me.t0 - interval '30 days'),
      (SELECT CASE WHEN me.d_start IS NULL THEN 0 ELSE
         (SELECT count(DISTINCT a.user_id)::float8 / greatest((SELECT count(*) FROM team), 1)
            FROM absences a JOIN team ON team.id = a.user_id
           WHERE a.d1 <= me.d_end AND a.d2 >= me.d_start)
       END),
      (SELECT count(*) FROM hist WHERE hist.status = 'REJECTED'
          AND hist.submitted_at > me.t0 - interval '30 days'),
      (SELECT count(*) FROM eas.audit_event e
        WHERE e.action = 'AI_AUTO_APPROVE_REVOKED' AND e.request_id IN (SELECT id FROM hist)),
      (SELECT count(*) FROM team),
      (SELECT count(*) FROM handover_work hw
        WHERE me.d_start IS NOT NULL
          AND (hw.due_at AT TIME ZONE %(tz)s)::date BETWEEN me.d_start AND me.d_end),
      (me.handover_id IS NOT NULL AND me.d_start IS NOT NULL AND EXISTS (
         SELECT 1 FROM absences a
         WHERE a.user_id = me.handover_id AND a.d1 <= me.d_end AND a.d2 >= me.d_start)),
      (SELECT count(*) FROM eas.request r4
         JOIN eas.request_type t4 ON t4.id = r4.type_id
         JOIN eas.request_revision v4 ON v4.id = r4.current_revision_id
        WHERE me.invoice_no <> '' AND r4.id <> me.id
          AND t4.code IN ('EXPENSE_CLAIM', 'REIMBURSEMENT')
          AND r4.status <> ALL(%(excluded)s)
          AND v4.submitted_at > me.t0 - interval '180 days'
          AND upper(regexp_replace(coalesce(v4.payload->>'invoice_number', ''), '\\s', '', 'g'))
              = me.invoice_no),
      (SELECT count(*) FROM eas.request r5
         JOIN eas.request_type t5 ON t5.id = r5.type_id
         JOIN eas.request_revision v5 ON v5.id = r5.current_revision_id
        WHERE me.customer <> '' AND r5.id <> me.id AND t5.code = 'SPECIAL_DISCOUNT'
          AND r5.status <> ALL(%(excluded)s)
          AND v5.submitted_at > me.t0 - interval '7 days'
          AND lower(btrim(coalesce(v5.payload->>'customer_name', ''))) = me.customer),
      (me.d_event IS NOT NULL AND EXISTS (
         SELECT 1 FROM absences a
         WHERE a.user_id = me.requester_id AND me.d_event BETWEEN a.d1 AND a.d2)),
      (SELECT count(*) FROM hist
        WHERE hist.submitted_at > me.t0 - interval '7 days'
          AND (extract(isodow FROM hist.submitted_at AT TIME ZONE %(tz)s) IN (6, 7)
               OR (hist.submitted_at AT TIME ZONE %(tz)s)::time NOT BETWEEN '08:00' AND '17:30'
               OR (hist.submitted_at AT TIME ZONE %(tz)s)::date IN
                  (SELECT holiday_date FROM eas.business_holiday))),
      (SELECT count(*) FROM urgent WHERE NOT covered),
      me.handover_id IS NOT NULL
    FROM me
"""

EMPTY: dict[str, Any] = {
    "open_work_due_hours": [],
    "work_due_in_absence": 0,
    "active_tasks_due_24h": 0,
    "handover_assigned": None,
    "same_type_count_7d": 0,
    "same_type_count_30d": 0,
    "same_type_count_month": 0,
    "requester_amount_7d": 0.0,
    "requester_finance_count_7d": 0,
    "attendance_count_30d": 0,
    "team_absence_ratio": 0.0,
    "requester_rejected_30d": 0,
    "ai_revoked_90d": 0,
    "team_size": 0,
    "handover_open_work_in_absence": 0,
    "handover_absent": False,
    "duplicate_invoice_count": 0,
    "same_customer_count_7d": 0,
    "requester_absent_on_event": False,
    "off_hours_count_7d": 0,
    "uncovered_work": 0,
    "handover_named": False,
}


def load_signals(request_id: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            SQL_SIGNALS,
            {
                "request_id": request_id,
                "finance": list(FINANCE_TYPES),
                "excluded": list(EXCLUDED_STATUSES),
                "tz": LOCAL_TZ,
            },
        )
        row = cursor.fetchone()
    if not row:
        return dict(EMPTY)
    return {
        "open_work_due_hours": [float(h) for h in (row[0] or [])],
        "work_due_in_absence": int(row[1] or 0),
        "active_tasks_due_24h": int(row[2] or 0),
        "handover_assigned": bool(row[3]),
        "same_type_count_7d": int(row[4] or 0),
        "same_type_count_30d": int(row[5] or 0),
        "same_type_count_month": int(row[6] or 0),
        "requester_amount_7d": float(row[7] or 0),
        "requester_finance_count_7d": int(row[8] or 0),
        "attendance_count_30d": int(row[9] or 0),
        "team_absence_ratio": round(min(float(row[10] or 0), 1.0), 3),
        "requester_rejected_30d": int(row[11] or 0),
        "ai_revoked_90d": int(row[12] or 0),
        "team_size": int(row[13] or 0),
        "handover_open_work_in_absence": int(row[14] or 0),
        "handover_absent": bool(row[15]),
        "duplicate_invoice_count": int(row[16] or 0),
        "same_customer_count_7d": int(row[17] or 0),
        "requester_absent_on_event": bool(row[18]),
        "off_hours_count_7d": int(row[19] or 0),
        "uncovered_work": int(row[20] or 0),
        "handover_named": bool(row[21]),
    }


def safe_load_signals(request_id: str) -> dict[str, Any]:
    """Như load_signals nhưng không bao giờ làm hỏng luồng duyệt: lỗi truy vấn thì trả tín hiệu rỗng."""
    try:
        return load_signals(request_id)
    except Exception:
        logger.warning(
            "bad-case signals unavailable: request=%s", request_id, exc_info=True
        )
        return dict(EMPTY)
