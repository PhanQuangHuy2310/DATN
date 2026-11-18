"""AI auto-approval of low-risk approval steps (risk weight <= 2).

The worker calls ``try_auto_approve`` after an APPROVAL_REQUESTED event. The
AI service is consulted outside any transaction; when it answers
``auto_approve`` the active step is handed to the non-login AI system account
and approved through ``decide_approval``, so every guard, SoD trigger and
audit rule of a human decision still applies.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from psycopg.types.json import Jsonb

from api_core.authn.models import Actor
from api_core.workflow.service import (
    SQL_INSERT_OUTBOX_EVENT,
    SQL_LOCK_SECURITY,
    CommandError,
    _append_request_audit,
    _canonical_uuid,
    _create_submission_workflow,
    _execute_idempotent,
    _is_actor_valid_for_role,
    _substitute_approver,
    decide_approval,
)

logger = logging.getLogger(__name__)

SQL_AUTO_APPROVE_CONTEXT = """
    SELECT r.status, r.lock_version, v.risk_weight, rt.code, i.lifecycle,
           u.display_name, d.code, s.id::text, s.assignee_id::text, v.amount_vnd,
           NOT EXISTS (
             SELECT 1 FROM eas.audit_event e
             WHERE e.request_id = r.id AND e.action = 'AI_AUTO_APPROVE_REVOKED'
           ),
           u.email, v.payload->>'room_code',
           v.payload->>'start_date', v.payload->>'end_date', r.requester_id::text
    FROM eas.request r
    JOIN eas.request_type rt ON rt.id = r.type_id
    JOIN eas.request_revision v ON v.id = r.current_revision_id
    JOIN eas.workflow_instance i ON i.revision_id = v.id AND i.state = 'ACTIVE'
    JOIN eas.approval_step s ON s.instance_id = i.id AND s.state = 'ACTIVE'
    JOIN eas.app_user u ON u.id = r.requester_id
    JOIN eas.department d ON d.id = u.department_id
    WHERE r.id = %s
"""


def _ai_actor() -> Actor:
    return Actor(
        id=settings.EAS_AI_SYSTEM_USER_ID,
        email="ai.system@eas.com",
        display_name="EAS AI",
        department_id="",
        auth_version=0,
        roles=frozenset({"APPROVER"}),
        must_change_password=False,
    )


def auto_approve_key(step_id: str) -> str:
    """Deterministic UUID idempotency key: one AI decision per approval step."""
    return str(uuid5(NAMESPACE_URL, f"eas:ai-auto-approve:{step_id}"))


def _load_context(request_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(SQL_AUTO_APPROVE_CONTEXT, [request_id])
        row = cursor.fetchone()
    if not row or row[0] != "PENDING_APPROVAL":
        return None
    keys = (
        "status",
        "lock_version",
        "risk_weight",
        "type_code",
        "lifecycle",
        "requester_name",
        "department_code",
        "step_id",
        "assignee_id",
        "amount_vnd",
        "ai_allowed",
        "requester_email",
        "room_code",
        "start_date",
        "end_date",
        "requester_id",
    )
    return dict(zip(keys, row, strict=True))


def _requested_days(context: dict[str, Any]) -> int:
    """Inclusive day span of start_date..end_date, 0 when not a date range."""
    try:
        begin = date.fromisoformat(str(context.get("start_date"))[:10])
        end = date.fromisoformat(str(context.get("end_date"))[:10])
    except ValueError:
        return 0
    return max((end - begin).days + 1, 0)


def try_auto_approve(request_id: str, correlation_id: str) -> dict[str, Any] | None:
    """Escalate a type-A request hit by a bad case, else approve the step when the AI allows it.

    Escalation (A -> B/C, ``api_core.workflow.escalation``) is a control, not an automation: it
    runs for every pending type-A request whatever its risk weight, and even when automatic
    approval is switched off. Automatic approval still needs weight <= the configured maximum.
    """
    escalation_on = getattr(settings, "EAS_AI_ESCALATION_ENABLED", True)
    if not (settings.EAS_AI_AUTO_APPROVE_ENABLED or escalation_on):
        return None
    context = _load_context(request_id)
    if (
        context is None
        or context["risk_weight"] is None
        or context["assignee_id"] == settings.EAS_AI_SYSTEM_USER_ID
    ):
        return None
    may_auto = (
        settings.EAS_AI_AUTO_APPROVE_ENABLED
        and context["risk_weight"] <= settings.EAS_AI_AUTO_APPROVE_MAX_WEIGHT
        and context["ai_allowed"]  # a human revoked an earlier AI approval
    )
    may_escalate = escalation_on and context["lifecycle"] == "A"
    if not (may_auto or may_escalate):
        return None

    from api_core.integrations.ai_service import ai_client_sync
    from api_core.workflow.bad_case_learning import safe_detector_config
    from api_core.workflow.bad_case_signals import safe_load_signals

    signals = safe_load_signals(request_id)
    verdict = ai_client_sync.evaluate_auto_approve(
        request_id=request_id,
        request_type=context["type_code"],
        lifecycle_template=context["lifecycle"],
        risk_score=context["risk_weight"],
        requester_name=context["requester_name"],
        requester_dept=context["department_code"],
        requester_email=context.get("requester_email"),
        room_code=context.get("room_code"),
        amount=float(context["amount_vnd"] or 0),
        # Leave rules (balance, < 3 days) need the requested span.
        days_requested=_requested_days(context),
        correlation_id=correlation_id,
        signals=signals,
        bad_case_config=safe_detector_config(),
    )
    if verdict.get("bad_cases"):
        _record_bad_cases(
            request_id, context["step_id"], verdict, signals, correlation_id
        )
    verdict = _apply_feedback_memory(request_id, context, verdict, correlation_id)
    if may_escalate and verdict.get("escalate_to") in ("B", "C"):
        from api_core.workflow.escalation import escalate_request

        escalated = escalate_request(
            request_id=request_id,
            step_id=context["step_id"],
            target=verdict["escalate_to"],
            verdict=verdict,
            signals=signals,
            correlation_id=correlation_id,
        )
        if escalated is not None:
            return {**escalated, "approved": False}
        return None
    if not may_auto or verdict.get("decision") != "auto_approve":
        return None

    ai_user_id = settings.EAS_AI_SYSTEM_USER_ID
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE eas.approval_step SET assignee_id=%s
                WHERE id=%s AND state='ACTIVE' AND assignee_id=%s
                RETURNING id
                """,
                [ai_user_id, context["step_id"], context["assignee_id"]],
            )
            if not cursor.fetchone():
                return None  # a human decided or OPS reassigned meanwhile
            _append_request_audit(
                cursor,
                request_id=request_id,
                actor_id=None,
                actor_kind="SYSTEM",
                action="AI_AUTO_APPROVE_TAKEOVER",
                target_type="approval_step",
                target_id=context["step_id"],
                details={
                    "original_assignee_id": context["assignee_id"],
                    "ai_user_id": ai_user_id,
                    "risk_weight": context["risk_weight"],
                    "ai_reason": verdict.get("reason"),
                },
                correlation_id=correlation_id,
            )
            result = decide_approval(
                actor=_ai_actor(),
                request_id=request_id,
                body={
                    "outcome": "APPROVE",
                    "reason": None,
                    "expected_version": context["lock_version"],
                },
                idempotency_key=auto_approve_key(context["step_id"]),
                correlation_id=correlation_id,
            )
    except CommandError as exc:
        # Version/state races roll the takeover back; a human still decides.
        logger.info("AI auto-approve skipped: request=%s code=%s", request_id, exc.code)
        return None
    except IntegrityError:
        # Databases without migration 14 keep UNIQUE(instance_id, assignee_id),
        # so the AI account cannot take a second step of one instance. Roll back
        # and leave the step to its human approver instead of failing with 500.
        logger.info(
            "AI auto-approve skipped: request=%s code=STEP_TAKEOVER_CONFLICT",
            request_id,
        )
        return None
    return result.body


def _apply_feedback_memory(
    request_id, context, verdict, correlation_id
) -> dict[str, Any]:
    """Bộ nhớ ca (migration 24): không lặp lại quyết định con người đã sửa cho cùng người, cùng loại."""
    from api_core.workflow import ai_feedback

    try:
        with connection.cursor() as cursor:
            adjusted = ai_feedback.apply_to_verdict(
                cursor,
                verdict=verdict,
                type_code=context["type_code"],
                requester_id=context.get("requester_id"),
                lifecycle=context["lifecycle"],
            )
    except Exception:
        logger.warning(
            "AI feedback memory unavailable: request=%s", request_id, exc_info=True
        )
        return verdict
    if not adjusted.get("learned"):
        return adjusted
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            _append_request_audit(
                cursor,
                request_id=request_id,
                actor_id=None,
                actor_kind="SYSTEM",
                action="AI_LEARNED_FROM_FEEDBACK",
                target_type="approval_step",
                target_id=context["step_id"],
                details={"applied": adjusted["learned"][:5]},
                correlation_id=correlation_id,
            )
    except Exception:
        logger.warning(
            "AI learned audit skipped: request=%s", request_id, exc_info=True
        )
    return adjusted


def _record_bad_cases(request_id, step_id, verdict, signals, correlation_id) -> None:
    """Ghi một sự kiện kiểm toán khi AI chặn tự duyệt vì tình huống xấu (một lần cho mỗi bước duyệt)."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM eas.audit_event WHERE request_id=%s AND action='AI_BAD_CASE_FLAGGED' "
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
                action="AI_BAD_CASE_FLAGGED",
                target_type="approval_step",
                target_id=step_id,
                details={
                    "cases": [
                        {
                            "code": str(c.get("code")),
                            "message": str(c.get("message"))[:400],
                        }
                        for c in verdict.get("bad_cases") or []
                    ][:5],
                    "effective_risk": verdict.get("effective_risk"),
                    "signals": {
                        k: (v if not isinstance(v, float) else round(v))
                        for k, v in signals.items()
                    },
                },
                correlation_id=correlation_id,
            )
    except Exception:
        logger.warning(
            "AI bad-case audit skipped: request=%s", request_id, exc_info=True
        )


REVOKE_WINDOW = timedelta(hours=24)


def _latest_ai_decision(cursor, request_id: str) -> datetime | None:
    """decided_at of the AI decision when it is the latest on the current revision."""
    cursor.execute(
        """
        SELECT d.actor_id::text, d.decided_at
        FROM eas.approval_decision d
        JOIN eas.approval_step s ON s.id = d.step_id
        JOIN eas.workflow_instance i ON i.id = s.instance_id
        JOIN eas.request r ON r.id = d.request_id AND r.current_revision_id = i.revision_id
        WHERE d.request_id = %s
        ORDER BY d.decided_at DESC, s.step_no DESC, d.id DESC LIMIT 1
        """,
        [request_id],
    )
    row = cursor.fetchone()
    if not row or row[0] != settings.EAS_AI_SYSTEM_USER_ID:
        return None
    return row[1]


def ai_approval_info(cursor, request_id: str, status: str) -> dict[str, Any] | None:
    """Request-detail block: when the AI decided and until when it can be revoked."""
    decided_at = _latest_ai_decision(cursor, request_id)
    if decided_at is None:
        return None
    until = decided_at + REVOKE_WINDOW
    return {
        "decided_at": decided_at.isoformat(),
        "revocable_until": until.isoformat(),
        "revocable": status == "COMPLETED" and datetime.now(timezone.utc) < until,
    }


def _validate_revoke_input(body: dict[str, Any]) -> tuple[str, int]:
    if set(body) != {"reason", "expected_version"}:
        raise CommandError("INVALID_REVOKE")
    reason = body.get("reason")
    version = body.get("expected_version")
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
        raise CommandError("REVOKE_REASON_REQUIRED")
    if isinstance(version, bool) or not isinstance(version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")
    return reason.strip(), version


def _snapshot_for_learning(request_id: str) -> dict[str, Any]:
    """Tín hiệu + đặc trưng của bản AI đã duyệt, lấy TRƯỚC khi thu hồi tạo bản mới (mốc = lúc gửi bản đó)."""
    from api_core.workflow.bad_case_learning import request_features
    from api_core.workflow.bad_case_signals import safe_load_signals

    signals = safe_load_signals(request_id)
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            signals.update(request_features(cursor, request_id))
    except Exception:
        logger.warning("request features not captured: request=%s", request_id, exc_info=True)
    return signals


def _record_revoke_feedback(
    cursor, request_id, type_id, requester_id, actor_id, decided_at, reason, signals=None
) -> None:
    """Bộ nhớ ca (migration 24) + học bad case từ lý do (migration 25, phân tích sau khi lưu). Lỗi bỏ qua."""
    from api_core.workflow import ai_feedback
    from api_core.workflow.bad_case_signals import safe_load_signals

    try:
        with transaction.atomic():
            cursor.execute("SELECT code FROM eas.request_type WHERE id=%s", [type_id])
            feedback_id = ai_feedback.record(
                cursor,
                kind="AUTO_APPROVE_REVOKED",
                request_id=request_id,
                type_code=cursor.fetchone()[0],
                subject_id=requester_id,
                actor_id=actor_id,
                ai_decision={
                    "decision": "auto_approve",
                    "decided_at": decided_at.isoformat(),
                },
                human_decision={"decision": "manual_review"},
                reason=reason,
                signals=signals if signals is not None else safe_load_signals(request_id),
            )
        if feedback_id:
            from api_core.workflow.bad_case_learning import analyze_in_background

            transaction.on_commit(lambda: analyze_in_background(feedback_id))
    except Exception:
        logger.warning(
            "revoke feedback not recorded: request=%s", request_id, exc_info=True
        )


def revoke_ai_auto_approval(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
):
    """Within 24h an approver sends an AI-approved request back to manual review.

    The approved revision stays as history; its content is re-submitted as a
    new revision whose approval route is the original human snapshot.
    """
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    reason, expected_version = _validate_revoke_input(body)

    def operation(cursor):
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT r.status, r.lock_version, r.requester_id::text, r.type_id::text,
                   v.id::text, v.revision_no, v.release_id::text, v.department_id::text,
                   v.payload, v.amount_vnd, v.payload_sha256, v.risk_weight, v.approval_level,
                   i.id::text, i.lifecycle, i.matched_rule_id, i.resolved_route, cr.sla_profile
            FROM eas.request r
            JOIN eas.request_revision v ON v.id = r.current_revision_id
            JOIN eas.workflow_instance i ON i.revision_id = v.id
            JOIN eas.config_release cr ON cr.id = v.release_id
            WHERE r.id = %s
            FOR UPDATE OF r
            """,
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)
        (
            status,
            lock_version,
            requester_id,
            type_id,
            revision_id,
            revision_no,
            release_id,
            department_id,
            payload,
            amount,
            payload_sha,
            risk_weight,
            approval_level,
            old_instance_id,
            lifecycle,
            matched_rule_id,
            resolved_route,
            sla,
        ) = row
        if lock_version != expected_version:
            raise CommandError("VERSION_CONFLICT", status=409)
        decided_at = _latest_ai_decision(cursor, request_id)
        if (
            status != "COMPLETED"
            or lifecycle != "A"
            or decided_at is None
            or datetime.now(timezone.utc) >= decided_at + REVOKE_WINDOW
        ):
            raise CommandError("AI_APPROVAL_NOT_REVOCABLE", status=409)
        if actor.id == requester_id or not _is_actor_valid_for_role(
            cursor,
            actor_id=actor.id,
            role="APPROVER",
            department_id=department_id,
            type_id=type_id,
        ):
            raise CommandError("FORBIDDEN", status=403)

        learning_snapshot = _snapshot_for_learning(request_id)
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            UPDATE eas.request
            SET status='NEEDS_INFO', lock_version=lock_version+1, updated_at=%s,
                approved_at=NULL, completed_at=NULL
            WHERE id=%s
            """,
            [now, request_id],
        )
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
                risk_weight,
                approval_level,
            ],
        )
        cursor.execute(
            """
            INSERT INTO eas.revision_attachment(revision_id, attachment_id, request_id)
            SELECT %s, attachment_id, request_id FROM eas.revision_attachment
            WHERE revision_id = %s
            """,
            [new_revision_id, revision_id],
        )
        route = sorted(resolved_route, key=lambda step: step["step_no"])
        decision = SimpleNamespace(
            matched_rule_id=matched_rule_id,
            resolved_route=route,
            approver_slots=tuple(step["resolver"] for step in route),
            approver_ids=tuple(step["assignee_id"] for step in route),
            executor_id=None,
            acceptor_id=None,
        )
        first_step_id = _create_submission_workflow(
            cursor=cursor,
            request_id=request_id,
            revision_id=new_revision_id,
            decision=decision,
            lifecycle=lifecycle,
            actor_id=requester_id,
            sla=sla,
            now=now,
            risk_weight=risk_weight or 3,
            approval_level=approval_level or 1,
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
            UPDATE eas.request
            SET current_revision_id=%s, status='PENDING_APPROVAL',
                lock_version=lock_version+1, updated_at=%s
            WHERE id=%s
            """,
            [new_revision_id, now, request_id],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="AI_AUTO_APPROVE_REVOKED",
            target_type="request_revision",
            target_id=new_revision_id,
            details={
                "reason": reason,
                "ai_decided_at": decided_at.isoformat(),
                "previous_revision_id": revision_id,
                "previous_instance_id": old_instance_id,
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
                f"request:{request_id}:ai-revoke:{new_revision_id}",
            ],
        )
        _record_revoke_feedback(
            cursor,
            request_id,
            type_id,
            requester_id,
            actor.id,
            decided_at,
            reason,
            signals=learning_snapshot,
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "status": "PENDING_APPROVAL",
                    "lock_version": lock_version + 2,
                }
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:ai-revoke",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )
