"""Nâng luồng CHÍNH hồ sơ A -> B/C khi AI phát hiện tình huống xấu hoặc luật quy định yêu cầu.

Đặc tả nhóm (18/11/2026): chỉ luồng A có AI tự duyệt. Hồ sơ A dính tình huống xấu không được tự
duyệt mà phải chuyển sang luồng có người kiểm duyệt thủ công: B (quản lý duyệt -> bộ phận chuyên môn
xử lý) hoặc C (+ nghiệm thu độc lập). Loại yêu cầu vẫn là A cho mọi hồ sơ khác.

Cơ chế (cần migration 23):
  - Mỗi loại A có bản cấu hình nâng cấp B và C (config_release.escalation).
  - Phiên duyệt A đang chờ bị đóng (SUPERSEDED, bước chờ SKIPPED), hồ sơ nhận revision mới cùng nội
    dung nhưng gắn bản nâng cấp, tuyến duyệt/người xử lý/người nghiệm thu được tính lại theo người gửi.
  - Mọi bảo vệ của luồng thường vẫn áp dụng (SoD, trigger CSDL, audit chuỗi băm).
  - Ghi audit AI_ESCALATED kèm nguyên nhân, thông báo người gửi và người duyệt mới, lưu đề xuất xử lý
    gốc rễ (eas.ai_remediation) để quản lý chọn sau khi duyệt.

Không nâng được (chưa chạy migration, tuyến không giải được, người duyệt đã quyết định) thì hồ sơ giữ
luồng A với người duyệt thủ công như trước và ghi audit lý do.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.workflow.service import (
    SQL_INSERT_OUTBOX_EVENT,
    SQL_LOCK_SECURITY,
    CommandError,
    _append_request_audit,
    _create_submission_workflow,
    _resolve_and_verify_route_actors,
    _substitute_approver,
)

logger = logging.getLogger(__name__)

ORDER = {"A": 0, "B": 1, "C": 2}
MODEL_VERSION = "bad-case-catalog-1"


def _escalation_release(cursor, type_id: str, lifecycle: str) -> tuple | None:
    cursor.execute("SELECT to_regclass('eas.ai_remediation') IS NOT NULL")
    if not cursor.fetchone()[0]:
        return None  # migration 23 chưa chạy
    cursor.execute(
        """
        SELECT cr.id::text, cr.route_rules, cr.actor_bindings, cr.sla_profile
        FROM eas.config_release cr
        WHERE cr.type_id = %s AND cr.lifecycle = %s AND cr.state = 'PUBLISHED'
          AND coalesce((to_jsonb(cr)->>'escalation')::boolean, false)
        ORDER BY cr.version DESC LIMIT 1
        """,
        [type_id, lifecycle],
    )
    return cursor.fetchone()


def _skip(
    request_id: str, step_id: str, reason: str, target: str, correlation_id: str
) -> None:
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM eas.audit_event WHERE request_id=%s AND action='AI_ESCALATION_SKIPPED' "
                "AND target_id=%s LIMIT 1",
                [request_id, step_id],
            )
            if cursor.fetchone():
                return
            _append_request_audit(
                cursor,
                request_id=request_id,
                actor_id=None,
                actor_kind="SYSTEM",
                action="AI_ESCALATION_SKIPPED",
                target_type="approval_step",
                target_id=step_id,
                details={"reason": reason, "target_lifecycle": target},
                correlation_id=correlation_id,
            )
    except Exception:
        logger.warning(
            "escalation skip audit failed: request=%s", request_id, exc_info=True
        )


def escalate_request(
    *,
    request_id: str,
    step_id: str,
    target: str,
    verdict: dict[str, Any],
    signals: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any] | None:
    """Chuyển hồ sơ đang chờ duyệt ở luồng A sang luồng ``target`` (B/C). Trả về kết quả hoặc None."""
    if target not in ("B", "C"):
        return None
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            return _escalate(
                cursor, request_id, step_id, target, verdict, signals, correlation_id
            )
    except _Skip as skip:
        _skip(request_id, step_id, skip.reason, target, correlation_id)
        return None
    except CommandError as exc:
        _skip(request_id, step_id, exc.code, target, correlation_id)
        return None


class _Skip(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _escalate(cursor, request_id, step_id, target, verdict, signals, correlation_id):
    cursor.execute(SQL_LOCK_SECURITY)
    cursor.execute(
        """
        SELECT r.status, r.lock_version, r.requester_id::text, r.type_id::text,
               v.id::text, v.revision_no, v.department_id::text, v.payload, v.amount_vnd,
               v.payload_sha256, v.risk_weight, i.id::text, i.lifecycle,
               (SELECT manager_id::text FROM eas.app_user WHERE id = r.requester_id),
               EXISTS (SELECT 1 FROM eas.approval_decision d
                       JOIN eas.approval_step s ON s.id = d.step_id
                       WHERE s.instance_id = i.id)
        FROM eas.request r
        JOIN eas.request_revision v ON v.id = r.current_revision_id
        JOIN eas.workflow_instance i ON i.revision_id = v.id AND i.state = 'ACTIVE'
        WHERE r.id = %s
        FOR UPDATE OF r
        """,
        [request_id],
    )
    row = cursor.fetchone()
    if not row:
        raise _Skip("NO_ACTIVE_INSTANCE")
    (
        status,
        lock_version,
        requester_id,
        type_id,
        revision_id,
        revision_no,
        department_id,
        payload,
        amount,
        payload_sha,
        risk_weight,
        old_instance_id,
        lifecycle,
        manager_id,
        decided,
    ) = row
    if status != "PENDING_APPROVAL":
        raise _Skip("NOT_PENDING")
    if decided:
        raise _Skip(
            "ALREADY_DECIDED"
        )  # người duyệt đã quyết định một bước: không đổi luồng giữa chừng
    if ORDER.get(lifecycle, 0) >= ORDER[target]:
        raise _Skip("ALREADY_AT_OR_ABOVE_TARGET")
    release = _escalation_release(cursor, type_id, target)
    if release is None:
        raise _Skip("ESCALATION_RELEASE_MISSING")
    release_id, rules, bindings, sla = release

    requester = SimpleNamespace(id=requester_id, department_id=department_id)
    decision = _resolve_and_verify_route_actors(
        cursor=cursor,
        rules=rules,
        bindings=bindings,
        actor=requester,
        manager_id=manager_id,
        type_id=type_id,
        normalized=payload,
        amount=amount,
    )

    now = datetime.now(timezone.utc)
    # 1. Đóng phiên duyệt A đang chờ.
    cursor.execute(
        """
        UPDATE eas.sla_stage SET closed_at=%s
        WHERE request_id=%s AND closed_at IS NULL AND approval_step_id IN
          (SELECT id FROM eas.approval_step WHERE instance_id=%s)
        """,
        [now, request_id, old_instance_id],
    )
    cursor.execute(
        """
        UPDATE eas.approval_step SET state='SKIPPED', closed_at=%s
        WHERE instance_id=%s AND state IN ('ACTIVE','WAITING')
        """,
        [now, old_instance_id],
    )
    cursor.execute(
        "UPDATE eas.workflow_instance SET state='SUPERSEDED', closed_at=%s WHERE id=%s",
        [now, old_instance_id],
    )
    cursor.execute(
        """
        UPDATE eas.request SET status='NEEDS_INFO', lock_version=lock_version+1, updated_at=%s
        WHERE id=%s
        """,
        [now, request_id],
    )
    # 2. Revision mới: cùng nội dung, gắn bản cấu hình nâng cấp.
    new_risk = max(int(risk_weight or 1), int(verdict.get("effective_risk") or 0), 3)
    new_revision_id = str(uuid4())
    cursor.execute(
        """
        INSERT INTO eas.request_revision(
          id,request_id,revision_no,release_id,department_id,payload,
          amount_vnd,submitted_by,payload_sha256,submitted_at,risk_weight,approval_level
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        [
            new_revision_id,
            request_id,
            revision_no + 1,
            release_id,
            department_id,
            Jsonb(payload),
            amount,
            requester_id,
            payload_sha,
            now,
            min(new_risk, 5),
            max(1, min(5, len(decision.approver_ids))),
        ],
    )
    cursor.execute(
        """
        INSERT INTO eas.revision_attachment(revision_id, attachment_id, request_id)
        SELECT %s, attachment_id, request_id FROM eas.revision_attachment WHERE revision_id = %s
        """,
        [new_revision_id, revision_id],
    )
    first_step_id = _create_submission_workflow(
        cursor=cursor,
        request_id=request_id,
        revision_id=new_revision_id,
        decision=decision,
        lifecycle=target,
        actor_id=requester_id,
        sla=sla,
        now=now,
    )
    _substitute_approver(
        cursor,
        step_id=first_step_id,
        request_id=request_id,
        requester_id=requester_id,
        department_id=department_id,
        type_id=type_id,
        correlation_id=correlation_id,
    )
    cursor.execute(
        """
        UPDATE eas.request SET current_revision_id=%s, status='PENDING_APPROVAL',
          lock_version=lock_version+1, updated_at=%s
        WHERE id=%s
        """,
        [new_revision_id, now, request_id],
    )
    causes = [
        {
            "source": str(c.get("source") or ""),
            "code": str(c.get("code") or ""),
            "escalate_to": c.get("escalate_to"),
            "text": str(c.get("text") or "")[:400],
            # Vì sao đó là bad case (tác hại, cột eas.bad_case.rationale) và nguồn: danh mục có sẵn / học được.
            "why": str(c.get("why") or "")[:600] or None,
            "origin": c.get("origin"),
        }
        for c in verdict.get("escalation_causes") or []
    ][:8]
    _append_request_audit(
        cursor,
        request_id=request_id,
        actor_id=None,
        actor_kind="SYSTEM",
        action="AI_ESCALATED",
        target_type="request_revision",
        target_id=new_revision_id,
        details={
            "from_lifecycle": lifecycle,
            "to_lifecycle": target,
            "release_id": release_id,
            "previous_revision_id": revision_id,
            "previous_instance_id": old_instance_id,
            "causes": causes,
            "effective_risk": verdict.get("effective_risk"),
            "executor_id": decision.executor_id,
            "acceptor_id": decision.acceptor_id,
        },
        correlation_id=correlation_id,
        occurred_at=now,
    )
    cursor.execute(
        SQL_INSERT_OUTBOX_EVENT,
        [
            request_id,
            "APPROVAL_REQUESTED",
            Jsonb({"request_id": request_id, "step_id": first_step_id}),
            f"request:{request_id}:escalated:{new_revision_id}",
        ],
    )
    cursor.execute(
        SQL_INSERT_OUTBOX_EVENT,
        [
            request_id,
            "REQUEST_ESCALATED",
            Jsonb({"request_id": request_id, "to_lifecycle": target}),
            f"request:{request_id}:escalated-notice:{new_revision_id}",
        ],
    )
    _store_proposals(cursor, request_id, verdict)
    return {
        "request": {
            "id": request_id,
            "status": "PENDING_APPROVAL",
            "lock_version": lock_version + 2,
        },
        "escalated_to": target,
        "revision_id": new_revision_id,
        "first_step_id": first_step_id,
    }


def _store_proposals(cursor, request_id: str, verdict: dict[str, Any]) -> None:
    """Một đề xuất xử lý (PROPOSED) cho mỗi tình huống xấu có hướng xử lý."""
    for case in verdict.get("bad_cases") or []:
        options = case.get("remediation") or []
        if not options:
            continue
        cursor.execute(
            """
            INSERT INTO eas.ai_remediation(request_id, case_code, proposal, model_version)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (request_id, case_code) WHERE state = 'PROPOSED' DO NOTHING
            """,
            [
                request_id,
                str(case.get("code")),
                Jsonb(
                    {
                        "title": case.get("title"),
                        "message": str(case.get("message") or "")[:500],
                        "evidence": case.get("evidence") or {},
                        "options": options[:6],
                    }
                ),
                str(case.get("catalog_version") or MODEL_VERSION),
            ],
        )
