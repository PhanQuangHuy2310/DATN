"""AI auto-approval of low-risk approval steps (risk weight <= 2).

The worker calls ``try_auto_approve`` after an APPROVAL_REQUESTED event. The
AI service is consulted outside any transaction; when it answers
``auto_approve`` the active step is handed to the non-login AI system account
and approved through ``decide_approval``, so every guard, SoD trigger and
audit rule of a human decision still applies.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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
           u.email, v.payload->>'room_code'
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
    )
    return dict(zip(keys, row, strict=True))


def try_auto_approve(request_id: str, correlation_id: str) -> dict[str, Any] | None:
    """Approve the active step when the AI allows it; return the result or None."""
    if not (
        settings.EAS_AI_AUTO_APPROVE_ENABLED
        and settings.EAS_AI_AUTO_APPROVAL_POLICY_APPROVED
    ):
        # Advisory-only is the approved default. Even an old `.env` that
        # enabled auto-approval cannot authorize an AI signature alone.
        return None
    context = _load_context(request_id)
    if (
        context is None
        or context["risk_weight"] is None
        or context["risk_weight"] > settings.EAS_AI_AUTO_APPROVE_MAX_WEIGHT
        or context["assignee_id"] == settings.EAS_AI_SYSTEM_USER_ID
        or not context["ai_allowed"]  # a human revoked an earlier AI approval
    ):
        return None

    from api_core.integrations.ai_service import ai_client_sync

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
        correlation_id=correlation_id,
    )
    if verdict.get("decision") != "auto_approve":
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
        ORDER BY d.decided_at DESC LIMIT 1
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
