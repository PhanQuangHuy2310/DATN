"""AI auto-approval of low-risk approval steps (risk weight <= 2).

The worker calls ``try_auto_approve`` after an APPROVAL_REQUESTED event. The
AI service is consulted outside any transaction; when it answers
``auto_approve`` the active step is handed to the non-login AI system account
and approved through ``decide_approval``, so every guard, SoD trigger and
audit rule of a human decision still applies.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import connection, transaction

from api_core.authn.models import Actor
from api_core.workflow.service import (
    CommandError,
    _append_request_audit,
    decide_approval,
)

logger = logging.getLogger(__name__)

SQL_AUTO_APPROVE_CONTEXT = """
    SELECT r.status, r.lock_version, r.risk_weight, rt.code, i.lifecycle,
           u.display_name, d.code, s.id::text, s.assignee_id::text, v.amount_vnd
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
    )
    return dict(zip(keys, row, strict=True))


def try_auto_approve(request_id: str, correlation_id: str) -> dict[str, Any] | None:
    """Approve the active step when the AI allows it; return the result or None."""
    if not settings.EAS_AI_AUTO_APPROVE_ENABLED:
        return None
    context = _load_context(request_id)
    if (
        context is None
        or context["risk_weight"] is None
        or context["risk_weight"] > settings.EAS_AI_AUTO_APPROVE_MAX_WEIGHT
        or context["assignee_id"] == settings.EAS_AI_SYSTEM_USER_ID
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
                idempotency_key=f"ai-auto-approve:{context['step_id']}",
                correlation_id=correlation_id,
            )
    except CommandError as exc:
        # Version/state races roll the takeover back; a human still decides.
        logger.info("AI auto-approve skipped: request=%s code=%s", request_id, exc.code)
        return None
    return result.body
