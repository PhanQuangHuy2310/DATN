"""Hướng xử lý gốc rễ sau khi hồ sơ dính tình huống xấu: AI đề xuất, quản lý xác nhận, hệ thống thực hiện.

Ví dụ đặc tả (18/11/2026): ông 1 còn giữ việc mai đến hạn nhưng xin nghỉ; hồ sơ được AI chuyển sang luồng
B; cấp trên vẫn cho nghỉ. AI đề xuất cho TỪNG việc ông 1 đang giữ:
  - DELEGATE_APPROVALS (bước duyệt) / REASSIGN_WORK (lượt thực hiện): giao cho người phù hợp nhất
    (ràng buộc cứng bằng SQL + mô hình xếp hạng ở ai_service/remediation_ranker.py);
  - POSTPONE_DEADLINE: lùi hạn SLA tới sau ngày đi làm lại (migration 23 cho phép lùi có cờ + audit);
  - RESCHEDULE_REQUEST: đề nghị đổi ngày nghỉ (chỉ là hướng dẫn, không đổi dữ liệu).

Ai bấm và chịu trách nhiệm: QUẢN LÝ đã/đang duyệt hồ sơ dính tình huống xấu (hoặc OPS_ADMIN). Thao tác ghi
audit trên cả hồ sơ gốc và hồ sơ của việc được chuyển, với ``proposed_by: AI`` và ``confirmed_by``;
người nhận việc mới và người gửi việc đó được thông báo. AI không tự thực hiện thao tác nào.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import connection
from psycopg.types.json import Jsonb

from api_core.authn.models import Actor
from api_core.workflow import ai_feedback
from api_core.workflow.ops_service import _reassign_approval_step, _reassign_executor
from api_core.workflow.service import (
    SQL_INSERT_OUTBOX_EVENT,
    SQL_LOCK_SECURITY,
    CommandError,
    _append_request_audit,
    _canonical_uuid,
    _execute_idempotent,
)

logger = logging.getLogger(__name__)
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
HORIZON_HOURS = 72
ACTIONS = ("DELEGATE_APPROVALS", "REASSIGN_WORK", "POSTPONE_DEADLINE")

_ITEM_SQL = """
    SELECT st.id::text, st.kind, st.due_at, rq.id::text, rq.code, t.code, t.name, rq.type_id::text,
           v.department_id::text, rq.requester_id::text, rq.status, s.id::text, a.id::text,
           coalesce(s.instance_id, a.instance_id, ai.id)::text, i.planned_executor_id::text, i.acceptor_id::text,
           coalesce(v.payload->>'title', '')
    FROM eas.sla_stage st
    JOIN eas.request rq ON rq.id = st.request_id
    JOIN eas.request_type t ON t.id = rq.type_id
    JOIN eas.request_revision v ON v.id = rq.current_revision_id
    LEFT JOIN eas.approval_step s ON s.id = st.approval_step_id
    LEFT JOIN eas.execution_attempt a ON a.id = st.attempt_id
    LEFT JOIN eas.workflow_instance ai ON ai.revision_id = rq.current_revision_id AND ai.state = 'ACTIVE'
    LEFT JOIN eas.workflow_instance i ON i.id = coalesce(s.instance_id, a.instance_id, ai.id)
    WHERE st.closed_at IS NULL AND st.request_id <> %(request_id)s
      AND ((st.kind = 'APPROVAL' AND s.state = 'ACTIVE' AND s.assignee_id = %(holder)s)
        OR (st.kind = 'EXECUTION' AND a.closed_at IS NULL AND a.executor_id = %(holder)s)
        OR (st.kind = 'ACCEPTANCE' AND rq.status = 'WAITING_FOR_ACCEPTANCE' AND i.acceptor_id = %(holder)s))
      AND (st.due_at <= %(now)s + make_interval(hours => %(horizon)s)
           OR st.due_at < %(window_end)s)
    ORDER BY st.due_at
    LIMIT 30
"""

_CANDIDATE_SQL = """
    WITH holder AS (SELECT id, manager_id FROM eas.app_user WHERE id = %(holder)s)
    SELECT u.id::text, u.display_name,
           (u.department_id = %(item_dept)s::uuid)::int,
           (u.manager_id IS NOT NULL AND u.manager_id = holder.manager_id)::int,
           (SELECT count(*) FROM eas.sla_stage st
              LEFT JOIN eas.approval_step s ON s.id = st.approval_step_id
              LEFT JOIN eas.execution_attempt a ON a.id = st.attempt_id
             WHERE st.closed_at IS NULL
               AND ((s.state = 'ACTIVE' AND s.assignee_id = u.id) OR (a.closed_at IS NULL AND a.executor_id = u.id))),
           (SELECT count(*) FROM eas.sla_stage st
              LEFT JOIN eas.approval_step s ON s.id = st.approval_step_id
              LEFT JOIN eas.execution_attempt a ON a.id = st.attempt_id
             WHERE st.closed_at IS NULL AND st.due_at >= %(window_start)s AND st.due_at < %(window_end)s
               AND ((s.state = 'ACTIVE' AND s.assignee_id = u.id) OR (a.closed_at IS NULL AND a.executor_id = u.id))),
           (SELECT count(*) FROM eas.approval_decision d JOIN eas.request r2 ON r2.id = d.request_id
             WHERE d.actor_id = u.id AND r2.type_id = %(item_type)s::uuid
               AND d.decided_at > now() - interval '180 days')
           + (SELECT count(*) FROM eas.execution_attempt x JOIN eas.request r3 ON r3.id = x.request_id
             WHERE x.executor_id = u.id AND r3.type_id = %(item_type)s::uuid AND x.closed_at IS NOT NULL
               AND x.closed_at > now() - interval '180 days'),
           (u.id = holder.manager_id)::int
    FROM eas.app_user u, holder
    WHERE u.is_active AND NOT u.is_system_account
      AND u.id <> holder.id AND u.id <> %(item_requester)s::uuid
      AND EXISTS (
        SELECT 1 FROM eas.role_membership rm
        WHERE rm.user_id = u.id AND rm.role = %(role)s AND rm.revoked_at IS NULL
          AND rm.valid_from <= statement_timestamp()
          AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
          AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = %(item_dept)s::uuid)
          AND (rm.type_scope = 'ALL' OR rm.type_id = %(item_type)s::uuid))
      AND NOT EXISTS (
        SELECT 1 FROM eas.role_membership adm
        WHERE adm.user_id = u.id AND adm.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR')
          AND adm.revoked_at IS NULL)
      AND NOT EXISTS (
        SELECT 1 FROM eas.user_leave_and_trips x
        WHERE x.user_id = u.id AND upper(x.approval_status) = 'APPROVED'
          AND x.start_time < %(window_end)s AND x.end_time > %(window_start)s)
      AND NOT EXISTS (
        SELECT 1 FROM eas.approval_step s2
        WHERE s2.instance_id = %(instance)s::uuid AND s2.assignee_id = u.id)
      AND NOT EXISTS (
        SELECT 1 FROM eas.execution_attempt x2
        WHERE x2.instance_id = %(instance)s::uuid AND x2.executor_id = u.id)
    ORDER BY u.display_name
    LIMIT 40
"""


def _window(payload: dict[str, Any]) -> tuple[datetime, datetime]:
    """Khoảng vắng mặt của đơn (ngày đầu 00:00 .. ngày cuối +1 00:00, giờ VN); đơn không có ngày: hôm nay."""

    def _d(key: str) -> date | None:
        try:
            return date.fromisoformat(str(payload.get(key) or "")[:10])
        except ValueError:
            return None

    start = _d("start_date") or _d("date") or _d("work_date") or datetime.now(TZ).date()
    end = _d("end_date") or start
    return (
        datetime.combine(start, time(0), TZ),
        datetime.combine(end + timedelta(days=1), time(0), TZ),
    )


def can_mark_escalation_unnecessary(cursor, actor_id: str, request_id: str) -> bool:
    """Chỉ người kiểm duyệt được gán ở phiên quy trình hiện tại (chưa bị thay thế) mới đánh dấu chuyển nhầm được; người gửi yêu cầu luôn bị chặn."""
    if not actor_id:
        return False
    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM eas.approval_step s
          JOIN eas.workflow_instance i ON i.id = s.instance_id
          JOIN eas.request r ON r.current_revision_id = i.revision_id
          WHERE r.id = %s
            AND i.state <> 'SUPERSEDED'
            AND r.requester_id <> %s
            AND s.assignee_id = %s
        )
        """,
        [request_id, actor_id, actor_id],
    )
    return bool(cursor.fetchone()[0])


def _authorize_escalation_reviewer(cursor, actor: Actor, request_id: str) -> None:
    if not can_mark_escalation_unnecessary(cursor, actor.id, request_id):
        raise CommandError("FORBIDDEN", status=403)


def _authorize_manager(cursor, actor: Actor, request_id: str) -> None:
    """Quản lý được giao duyệt hồ sơ này (phiên hiện tại chưa bị thay thế) hoặc OPS_ADMIN (không phải người gửi)."""
    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM eas.request r
          WHERE r.id = %s
            AND r.requester_id <> %s
            AND (
              EXISTS (
                SELECT 1
                FROM eas.approval_step s
                JOIN eas.workflow_instance i ON i.id = s.instance_id
                WHERE i.revision_id = r.current_revision_id
                  AND i.state <> 'SUPERSEDED'
                  AND s.assignee_id = %s
              )
              OR EXISTS (
                SELECT 1
                FROM eas.role_membership rm
                WHERE rm.user_id = %s
                  AND rm.role = 'OPS_ADMIN'
                  AND rm.scope_kind = 'GLOBAL'
                  AND rm.revoked_at IS NULL
              )
            )
        )
        """,
        [request_id, actor.id, actor.id, actor.id],
    )
    if not cursor.fetchone()[0]:
        raise CommandError("FORBIDDEN", status=403)


def _load_request(cursor, request_id: str) -> tuple:
    cursor.execute(
        """
        SELECT r.requester_id::text, v.payload, r.code, r.status
        FROM eas.request r JOIN eas.request_revision v ON v.id = r.current_revision_id
        WHERE r.id = %s
        """,
        [request_id],
    )
    row = cursor.fetchone()
    if not row:
        raise CommandError("REQUEST_NOT_FOUND", status=404)
    return row


def _items(
    cursor, request_id: str, holder: str, now: datetime, window_end: datetime
) -> list[dict[str, Any]]:
    cursor.execute(
        _ITEM_SQL,
        {
            "request_id": request_id,
            "holder": holder,
            "now": now,
            "horizon": HORIZON_HOURS,
            "window_end": window_end,
        },
    )
    keys = (
        "stage_id",
        "kind",
        "due_at",
        "item_request_id",
        "item_code",
        "type_code",
        "type_name",
        "type_id",
        "item_dept",
        "item_requester",
        "item_status",
        "step_id",
        "attempt_id",
        "instance_id",
        "planned_executor_id",
        "acceptor_id",
        "title",
    )
    return [dict(zip(keys, row, strict=True)) for row in cursor.fetchall()]


def _candidates(
    cursor, item: dict[str, Any], holder: str, window: tuple[datetime, datetime]
) -> list[dict]:
    role = {"APPROVAL": "APPROVER", "EXECUTION": "EXECUTOR"}.get(
        item["kind"], "ACCEPTOR"
    )
    cursor.execute(
        _CANDIDATE_SQL,
        {
            "holder": holder,
            "item_dept": item["item_dept"],
            "item_type": item["type_id"],
            "item_requester": item["item_requester"],
            "role": role,
            "instance": item["instance_id"],
            "window_start": window[0],
            "window_end": window[1],
        },
    )
    keys = (
        "user_id",
        "display_name",
        "same_department",
        "same_team",
        "open_items",
        "due_in_window",
        "type_experience",
        "is_superior",
    )
    return [dict(zip(keys, row, strict=True)) for row in cursor.fetchall()]


def _rank(absence_hours: float, items: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "absence_hours": absence_hours,
        "items": [
            {
                "item_id": it["stage_id"],
                "kind": it["kind"],
                "hours_to_due": it["hours_to_due"],
                "candidates": it["candidates"],
            }
            for it in items
        ],
    }
    try:
        import httpx

        with httpx.Client(
            base_url=settings.EAS_AI_SERVICE_URL,
            timeout=httpx.Timeout(8.0, connect=3.0),
            headers={"X-Internal-Secret": settings.EAS_AI_INTERNAL_SECRET},
        ) as client:
            resp = client.post("/ai/remediation/rank", json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        logger.warning("remediation ranking unavailable", exc_info=True)
        out = []
        for it in payload["items"]:
            ranked = sorted(
                it["candidates"], key=lambda c: c["open_items"] + 3 * c["due_in_window"]
            )
            best = ranked[0] if ranked else None
            if best is not None:
                action = (
                    "DELEGATE_APPROVALS"
                    if it["kind"] == "APPROVAL"
                    else "REASSIGN_WORK"
                )
            else:
                action = "POSTPONE_DEADLINE"
            out.append(
                {
                    "item_id": it["item_id"],
                    "kind": it["kind"],
                    "engine": "api-fallback-least-loaded",
                    "suggestion": {
                        "action": action,
                        "why": "AI không phản hồi; xếp theo người ít việc nhất",
                    },
                    "candidates": ranked[:5],
                }
            )
        return {"model_version": "api-fallback", "items": out}


def build_plan(*, actor: Actor, request_id: str) -> dict[str, Any]:
    """Kế hoạch xử lý cho người quản lý: các đề xuất của AI + việc đang giữ + ứng viên đã xếp hạng."""
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    with connection.cursor() as cursor:
        _authorize_manager(cursor, actor, request_id)
        holder, payload, code, status = _load_request(cursor, request_id)
        cursor.execute("SELECT to_regclass('eas.ai_remediation') IS NOT NULL")
        proposals = []
        if cursor.fetchone()[0]:
            cursor.execute(
                """
                SELECT id::text, case_code, state, proposal, model_version, chosen, result,
                       proposed_at, decided_at
                FROM eas.ai_remediation WHERE request_id = %s ORDER BY proposed_at
                """,
                [request_id],
            )
            proposals = [
                {
                    "id": r[0],
                    "case_code": r[1],
                    "state": r[2],
                    "proposal": r[3],
                    "model_version": r[4],
                    "chosen": r[5],
                    "result": r[6],
                    "proposed_at": r[7].isoformat(),
                    "decided_at": r[8].isoformat() if r[8] else None,
                }
                for r in cursor.fetchall()
            ]
        now = datetime.now(timezone.utc)
        window = _window(payload or {})
        items = _items(cursor, request_id, holder, now, window[1])
        for it in items:
            it["hours_to_due"] = round((it["due_at"] - now).total_seconds() / 3600, 1)
            it["candidates"] = _candidates(cursor, it, holder, window)
            it["preferences"] = ai_feedback.ranking_preferences(
                cursor, holder_id=holder, item_type_code=it["type_code"]
            )
    absence_hours = max((window[1] - now).total_seconds() / 3600, 0)
    ranked = (
        {r["item_id"]: r for r in _rank(absence_hours, items).get("items", [])}
        if items
        else {}
    )
    postpone_to = datetime.combine(window[1].date(), time(17, 30), TZ)
    out_items = []
    for it in items:
        r = _apply_preferences(ranked.get(it["stage_id"], {}), it)
        out_items.append(
            {
                "stage_id": it["stage_id"],
                "kind": it["kind"],
                "item_request_id": it["item_request_id"],
                "item_code": it["item_code"],
                "type_name": it["type_name"],
                "title": it["title"],
                "due_at": it["due_at"].isoformat(),
                "hours_to_due": it["hours_to_due"],
                "suggestion": r.get("suggestion"),
                "engine": r.get("engine"),
                "candidates": r.get("candidates") or [],
                "postpone_to": postpone_to.isoformat()
                if it["due_at"] < postpone_to
                else None,
            }
        )
    return {
        "request": {"id": request_id, "code": code, "status": status},
        "absence": {"start": window[0].isoformat(), "end": window[1].isoformat()},
        "proposals": proposals,
        "items": out_items,
    }


def _apply_preferences(ranked: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Bộ nhớ ca cho xếp hạng: người quản lý đã chọn cho việc cùng loại của cùng người xin nghỉ lên đầu."""
    if not item.get("preferences"):
        return ranked
    out = dict(ranked)
    candidates = list(out.get("candidates") or [])
    raw = {c["user_id"]: c for c in item.get("candidates") or []}
    for pref in item["preferences"]:
        pid = pref["candidate_id"]
        if pid not in raw:
            continue  # không còn hợp lệ (vắng, đổi vai trò): bỏ qua ca này
        chosen = next((c for c in candidates if c["user_id"] == pid), None) or {
            **raw[pid],
            "score": None,
            "why": [],
        }
        candidates = [c for c in candidates if c["user_id"] != pid]
        chosen = {
            **chosen,
            "learned": True,
            "why": [
                f"quản lý đã chọn người này cho việc cùng loại ({pref['text']})",
                *chosen.get("why", []),
            ],
        }
        out["candidates"] = [chosen, *candidates][:5]
        action = "DELEGATE_APPROVALS" if item["kind"] == "APPROVAL" else "REASSIGN_WORK"
        out["suggestion"] = {
            "action": action,
            "why": f"giao cho {chosen.get('display_name')} theo lựa chọn trước đây của quản lý",
        }
        out["engine"] = f"{out.get('engine') or 'ranker'}+feedback-memory"
        break
    return out


def _validate_confirm(body: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    if not isinstance(body, dict) or set(body) - {"proposal_id", "actions", "note"}:
        raise CommandError("INVALID_REMEDIATION", status=422)
    proposal_id = _canonical_uuid(body.get("proposal_id"), "INVALID_PROPOSAL_ID")
    actions = body.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 30:
        raise CommandError("INVALID_REMEDIATION", status=422)
    clean = []
    for a in actions:
        if not isinstance(a, dict) or a.get("action") not in ACTIONS:
            raise CommandError("INVALID_REMEDIATION", status=422)
        item = {
            "action": a["action"],
            "stage_id": _canonical_uuid(a.get("stage_id"), "INVALID_STAGE_ID"),
        }
        if a["action"] != "POSTPONE_DEADLINE":
            item["candidate_id"] = _canonical_uuid(
                a.get("candidate_id"), "INVALID_CANDIDATE_ID"
            )
        clean.append(item)
    note = body.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 500):
        raise CommandError("INVALID_REMEDIATION", status=422)
    return proposal_id, clean, (note or "").strip()


def confirm_plan(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
):
    """Quản lý xác nhận đề xuất: thực hiện chuyển việc / lùi hạn dưới quyền của quản lý."""
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    proposal_id, actions, note = _validate_confirm(body)

    def operation(cursor):
        cursor.execute(SQL_LOCK_SECURITY)
        _authorize_manager(cursor, actor, request_id)
        holder, payload, code, _status = _load_request(cursor, request_id)
        cursor.execute(
            "SELECT case_code, state FROM eas.ai_remediation WHERE id = %s AND request_id = %s FOR UPDATE",
            [proposal_id, request_id],
        )
        prop = cursor.fetchone()
        if not prop:
            raise CommandError("PROPOSAL_NOT_FOUND", status=404)
        if prop[1] != "PROPOSED":
            raise CommandError("PROPOSAL_ALREADY_DECIDED", status=409)
        now = datetime.now(timezone.utc)
        window = _window(payload or {})
        items = {
            it["stage_id"]: it
            for it in _items(cursor, request_id, holder, now, window[1])
        }
        results = []
        for a in actions:
            item = items.get(a["stage_id"])
            if item is None:
                raise CommandError("WORK_ITEM_NOT_HELD", status=409)
            if a["action"] == "POSTPONE_DEADLINE":
                results.append(
                    _postpone(cursor, actor, item, window, request_id, correlation_id)
                )
            else:
                cands = _candidates(cursor, item, holder, window)
                if a["candidate_id"] not in {c["user_id"] for c in cands}:
                    raise CommandError("CANDIDATE_NOT_ELIGIBLE", status=422)
                _record_ranking_choice(
                    cursor,
                    actor,
                    request_id,
                    holder,
                    item,
                    cands,
                    a["candidate_id"],
                    now,
                    window,
                )
                results.append(
                    _reassign(
                        cursor,
                        actor,
                        item,
                        a["candidate_id"],
                        request_id,
                        correlation_id,
                    )
                )
        cursor.execute(
            """
            UPDATE eas.ai_remediation SET state='CONFIRMED', chosen=%s, result=%s, decided_by=%s,
              decided_at=statement_timestamp()
            WHERE id=%s AND state='PROPOSED'
            """,
            [
                Jsonb({"actions": actions, "note": note}),
                Jsonb({"applied": results}),
                actor.id,
                proposal_id,
            ],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="AI_REMEDIATION_CONFIRMED",
            target_type="ai_remediation",
            target_id=proposal_id,
            details={
                "case_code": prop[0],
                "proposed_by": "AI",
                "confirmed_by": actor.id,
                "applied": results,
                "note": note[:300],
            },
            correlation_id=correlation_id,
        )
        return (
            {
                "request": {"id": request_id, "code": code},
                "proposal_id": proposal_id,
                "applied": results,
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:ai-remediation",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def dismiss_plan(
    *, actor: Actor, request_id: str, proposal_id: str, reason: str, correlation_id: str
) -> dict:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    proposal_id = _canonical_uuid(proposal_id, "INVALID_PROPOSAL_ID")
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 500:
        raise CommandError("DISMISS_REASON_REQUIRED", status=422)
    from django.db import transaction

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(SQL_LOCK_SECURITY)
        _authorize_manager(cursor, actor, request_id)
        cursor.execute(
            """
            UPDATE eas.ai_remediation SET state='DISMISSED', chosen=%s, decided_by=%s,
              decided_at=statement_timestamp()
            WHERE id=%s AND request_id=%s AND state='PROPOSED' RETURNING case_code
            """,
            [Jsonb({"reason": reason.strip()}), actor.id, proposal_id, request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("PROPOSAL_ALREADY_DECIDED", status=409)
        holder, _payload, _code, _status = _load_request(cursor, request_id)
        ai_feedback.record(
            cursor,
            kind="REMEDIATION_DISMISSED",
            request_id=request_id,
            type_code=_type_code(cursor, request_id),
            subject_id=holder,
            actor_id=actor.id,
            ai_decision={"case_code": row[0], "proposal_id": proposal_id},
            human_decision={"decision": "dismiss"},
            reason=reason.strip(),
            case_codes=[row[0]],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="AI_REMEDIATION_DISMISSED",
            target_type="ai_remediation",
            target_id=proposal_id,
            details={"case_code": row[0], "reason": reason.strip()[:300]},
            correlation_id=correlation_id,
        )
    return {"proposal_id": proposal_id, "state": "DISMISSED"}


def _type_code(cursor, request_id: str) -> str:
    cursor.execute(
        "SELECT t.code FROM eas.request r JOIN eas.request_type t ON t.id = r.type_id WHERE r.id = %s",
        [request_id],
    )
    return cursor.fetchone()[0]


_FEATURES = (
    "same_department",
    "same_team",
    "open_items",
    "due_in_window",
    "type_experience",
    "is_superior",
)


def _record_ranking_choice(
    cursor, actor, request_id, holder, item, cands, chosen_id, now, window
) -> None:
    """Quản lý chọn khác ứng viên ĐÃ HIỂN THỊ ở đầu (mô hình + bộ nhớ ca): lưu cặp ưu tiên thật.

    So với thứ hạng đã hiển thị chứ không phải thứ hạng gốc của mô hình: nếu bộ nhớ đã đưa người cũ lên đầu
    mà quản lý chọn người khác, lựa chọn mới phải được ghi để bộ nhớ không lặp lại gợi ý cũ.
    """
    if len(cands) < 2:
        return
    item = {
        **item,
        "candidates": cands,
        "hours_to_due": round((item["due_at"] - now).total_seconds() / 3600, 1),
        "preferences": ai_feedback.ranking_preferences(
            cursor, holder_id=holder, item_type_code=item["type_code"]
        ),
    }
    absence_hours = max((window[1] - now).total_seconds() / 3600, 0)
    ranked = _apply_preferences(
        (_rank(absence_hours, [item]).get("items") or [{}])[0], item
    )
    top = (ranked.get("candidates") or [{}])[0]
    if not top.get("user_id") or top["user_id"] == chosen_id:
        return
    feats = {c["user_id"]: {k: c.get(k) for k in _FEATURES} for c in cands}
    ai_feedback.record(
        cursor,
        kind="RANKING_OVERRIDDEN",
        request_id=request_id,
        type_code=item["type_code"],
        subject_id=holder,
        actor_id=actor.id,
        ai_decision={
            "candidate_id": top["user_id"],
            "engine": ranked.get("engine"),
            "features": feats.get(top["user_id"]),
        },
        human_decision={"candidate_id": chosen_id, "features": feats.get(chosen_id)},
        reason=f"Việc {item['item_code']} ({item['kind']})",
        # Cả nhóm ứng viên để học dồn: người được chọn được ưu tiên hơn mọi người còn lại.
        signals={
            "group": [
                {**feats[c["user_id"]], "chosen": c["user_id"] == chosen_id}
                for c in cands
            ][:30]
        },
    )


def mark_escalation_unnecessary(
    *, actor: Actor, request_id: str, reason: str, correlation_id: str
) -> dict:
    """Quản lý xác nhận AI chuyển luồng nhầm: lần sau cùng người, cùng loại, cùng tình huống thì không chuyển."""
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 500:
        raise CommandError("FEEDBACK_REASON_REQUIRED", status=422)
    from django.db import transaction

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(SQL_LOCK_SECURITY)
        _authorize_escalation_reviewer(cursor, actor, request_id)
        if not ai_feedback.available(cursor):
            raise CommandError("AI_FEEDBACK_NOT_INSTALLED", status=503)
        cursor.execute(
            "SELECT details FROM eas.audit_event WHERE request_id=%s AND action='AI_ESCALATED' "
            "ORDER BY seq DESC LIMIT 1",
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_ESCALATED", status=409)
        cursor.execute(
            "SELECT 1 FROM eas.ai_feedback WHERE request_id=%s AND kind='ESCALATION_UNNECESSARY'",
            [request_id],
        )
        if cursor.fetchone():
            raise CommandError("FEEDBACK_ALREADY_RECORDED", status=409)
        details = row[0] or {}
        codes = [
            c.get("code")
            for c in details.get("causes") or []
            if c.get("source") == "BAD_CASE"
        ]
        holder, _payload, _code, _status = _load_request(cursor, request_id)
        from api_core.workflow.bad_case_signals import safe_load_signals

        feedback_id = ai_feedback.record(
            cursor,
            kind="ESCALATION_UNNECESSARY",
            request_id=request_id,
            type_code=_type_code(cursor, request_id),
            subject_id=holder,
            actor_id=actor.id,
            ai_decision={
                "escalate_to": details.get("to_lifecycle"),
                "causes": details.get("causes") or [],
            },
            human_decision={"decision": "escalation_unnecessary"},
            reason=reason.strip(),
            case_codes=codes,
            signals=safe_load_signals(request_id),
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="AI_ESCALATION_MARKED_UNNECESSARY",
            target_type="ai_feedback",
            target_id=feedback_id,
            details={"case_codes": codes, "reason": reason.strip()[:300]},
            correlation_id=correlation_id,
        )
    return {"feedback_id": feedback_id, "case_codes": codes}


def _bump(cursor, item_request_id: str, next_status: str | None = None) -> None:
    cursor.execute(
        """
        UPDATE eas.request SET status=coalesce(%s, status), lock_version=lock_version+1,
          updated_at=statement_timestamp()
        WHERE id=%s
        """,
        [next_status, item_request_id],
    )


def _reassign(
    cursor,
    actor: Actor,
    item: dict[str, Any],
    new_user: str,
    source_request: str,
    correlation_id: str,
) -> dict[str, Any]:
    cursor.execute(
        "SELECT 1 FROM eas.request WHERE id=%s FOR UPDATE", [item["item_request_id"]]
    )
    if item["kind"] == "APPROVAL":
        old, joined = _reassign_approval_step(
            cursor,
            instance_id=item["instance_id"],
            target_id=item["step_id"],
            new_user_id=new_user,
            requester_id=item["item_requester"],
            planned_executor_id=item["planned_executor_id"],
            department_id=item["item_dept"],
            type_id=item["type_id"],
        )
        next_status = None
        action = "DELEGATE_APPROVALS"
    elif item["kind"] == "EXECUTION":
        old, joined, next_status = _reassign_executor(
            cursor,
            instance_id=item["instance_id"],
            target_id=item["attempt_id"],
            new_user_id=new_user,
            requester_id=item["item_requester"],
            acceptor_id=item["acceptor_id"],
            r_status=item["item_status"],
            normalized_request_id=item["item_request_id"],
            department_id=item["item_dept"],
            type_id=item["type_id"],
        )
        action = "REASSIGN_WORK"
    else:
        raise CommandError("WORK_ITEM_NOT_REASSIGNABLE", status=409)
    cursor.execute(
        """
        INSERT INTO eas.request_participant(request_id, user_id, joined_as) VALUES (%s, %s, %s)
        ON CONFLICT (request_id, user_id) DO NOTHING
        """,
        [item["item_request_id"], new_user, joined],
    )
    _bump(cursor, item["item_request_id"], next_status)
    details = {
        "old_user_id": old,
        "new_user_id": new_user,
        "proposed_by": "AI",
        "confirmed_by": actor.id,
        "source_request_id": source_request,
        "action": action,
    }
    _append_request_audit(
        cursor,
        request_id=item["item_request_id"],
        actor_id=actor.id,
        action="AI_REMEDIATION_REASSIGNED",
        target_type=item["kind"].lower(),
        target_id=item["step_id"] or item["attempt_id"],
        details=details,
        correlation_id=correlation_id,
    )
    cursor.execute(
        SQL_INSERT_OUTBOX_EVENT,
        [
            item["item_request_id"],
            "WORK_REASSIGNED",
            Jsonb({"recipient_id": new_user, **details}),
            f"remediation:{item['stage_id']}:{new_user}",
        ],
    )
    return {
        "stage_id": item["stage_id"],
        "item_code": item["item_code"],
        "action": action,
        "old_user_id": old,
        "new_user_id": new_user,
    }


def _postpone(
    cursor,
    actor: Actor,
    item: dict[str, Any],
    window,
    source_request: str,
    correlation_id: str,
) -> dict[str, Any]:
    new_due = datetime.combine(window[1].date(), time(17, 30), TZ)
    if item["due_at"] >= new_due:
        raise CommandError("DEADLINE_ALREADY_AFTER_RETURN", status=409)
    cursor.execute(
        "SELECT set_config('eas.sla_extend_stage_id', %s, true)", [item["stage_id"]]
    )
    cursor.execute(
        """
        UPDATE eas.sla_stage SET due_at=%s
        WHERE id=%s AND closed_at IS NULL AND breached_at IS NULL AND due_at < %s
        """,
        [new_due, item["stage_id"], new_due],
    )
    if cursor.rowcount != 1:
        raise CommandError("DEADLINE_NOT_EXTENDABLE", status=409)
    cursor.execute("SELECT set_config('eas.sla_extend_stage_id', '', true)")
    cursor.execute(
        "SELECT 1 FROM eas.request WHERE id=%s FOR UPDATE", [item["item_request_id"]]
    )
    _bump(cursor, item["item_request_id"])
    details = {
        "old_due_at": item["due_at"].isoformat(),
        "new_due_at": new_due.isoformat(),
        "proposed_by": "AI",
        "confirmed_by": actor.id,
        "source_request_id": source_request,
    }
    _append_request_audit(
        cursor,
        request_id=item["item_request_id"],
        actor_id=actor.id,
        action="SLA_DEADLINE_POSTPONED",
        target_type="sla_stage",
        target_id=item["stage_id"],
        details=details,
        correlation_id=correlation_id,
    )
    cursor.execute(
        SQL_INSERT_OUTBOX_EVENT,
        [
            item["item_request_id"],
            "DEADLINE_POSTPONED",
            Jsonb({"recipient_id": item["item_requester"], **details}),
            f"postpone:{item['stage_id']}:{new_due.isoformat()}",
        ],
    )
    return {
        "stage_id": item["stage_id"],
        "item_code": item["item_code"],
        "action": "POSTPONE_DEADLINE",
        "new_due_at": new_due.isoformat(),
    }
