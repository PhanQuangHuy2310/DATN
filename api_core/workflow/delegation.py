"""Approval delegation (migration 10): an approver hands their approval steps
to a colleague for a time window. Steps are reassigned when they activate
(see service._substitute_approver)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.authn.models import Actor
from api_core.workflow.service import (
    CommandError,
    _append_admin_audit,
    _canonical_uuid,
    _substitute_approver,
    _table_readable,
)

MAX_WINDOW = timedelta(days=90)
SQL_APPROVER_ACTIVE = """
    EXISTS (
      SELECT 1 FROM eas.role_membership rm
      WHERE rm.user_id = u.id AND rm.role = 'APPROVER' AND rm.revoked_at IS NULL
        AND rm.valid_from <= statement_timestamp()
        AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
    )
"""


def _ensure_ready(cursor) -> None:
    if not _table_readable(cursor, "eas.approval_delegation"):
        raise CommandError("DELEGATION_NOT_INSTALLED", status=503)


def _timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise CommandError(
            "INVALID_DELEGATION_WINDOW", status=422, fields={field: ["INVALID"]}
        ) from None
    if parsed.tzinfo is None:
        raise CommandError(
            "INVALID_DELEGATION_WINDOW",
            status=422,
            fields={field: ["TIMEZONE_REQUIRED"]},
        )
    return parsed


def validate_delegation(actor: Actor, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict) or set(body) != {
        "delegate_id",
        "starts_at",
        "ends_at",
        "reason",
    }:
        raise CommandError("INVALID_DELEGATION", status=422)
    delegate_id = _canonical_uuid(body["delegate_id"], "INVALID_DELEGATE")
    if delegate_id == actor.id:
        raise CommandError("CANNOT_DELEGATE_TO_SELF", status=422)
    starts_at = _timestamp(body["starts_at"], "starts_at")
    ends_at = _timestamp(body["ends_at"], "ends_at")
    if ends_at <= starts_at or ends_at - starts_at > MAX_WINDOW:
        raise CommandError("INVALID_DELEGATION_WINDOW", status=422)
    reason = body["reason"]
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 500:
        raise CommandError("DELEGATION_REASON_REQUIRED", status=422)
    return {
        "delegate_id": delegate_id,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "reason": reason.strip(),
    }


def _serialize(row) -> dict[str, Any]:
    return {
        "id": row[0],
        "delegator_id": row[1],
        "delegator_name": row[2],
        "delegate_id": row[3],
        "delegate_name": row[4],
        "starts_at": row[5].isoformat(),
        "ends_at": row[6].isoformat(),
        "reason": row[7],
        "revoked_at": row[8].isoformat() if row[8] else None,
    }


def list_delegations(*, actor: Actor) -> dict[str, Any]:
    with connection.cursor() as cursor:
        _ensure_ready(cursor)
        cursor.execute(
            """
            SELECT d.id::text, d.delegator_id::text, a.display_name, d.delegate_id::text,
                   b.display_name, d.starts_at, d.ends_at, d.reason, d.revoked_at
            FROM eas.approval_delegation d
            JOIN eas.app_user a ON a.id = d.delegator_id
            JOIN eas.app_user b ON b.id = d.delegate_id
            WHERE d.delegator_id = %s OR d.delegate_id = %s
            ORDER BY d.created_at DESC LIMIT 100
            """,
            [actor.id, actor.id],
        )
        rows = [_serialize(r) for r in cursor.fetchall()]
    return {
        "given": [r for r in rows if r["delegator_id"] == actor.id],
        "received": [r for r in rows if r["delegate_id"] == actor.id],
    }


def delegate_candidates(*, actor: Actor) -> dict[str, Any]:
    """Active approvers of the actor's department plus the actor's manager."""
    with connection.cursor() as cursor:
        cursor.execute(  # NOSONAR python:S2077 - constant SQL fragment
            f"""
            SELECT u.id::text, u.display_name FROM eas.app_user u
            WHERE u.is_active AND u.id <> %s
              AND (u.department_id = %s
                   OR u.id = (SELECT manager_id FROM eas.app_user WHERE id = %s))
              AND {SQL_APPROVER_ACTIVE}
              AND NOT COALESCE((to_jsonb(u)->>'is_system_account')::boolean, false)
            ORDER BY u.display_name
            """,
            [actor.id, actor.department_id, actor.id],
        )
        return {
            "items": [{"id": r[0], "display_name": r[1]} for r in cursor.fetchall()]
        }


def create_delegation(
    *, actor: Actor, body: Any, correlation_id: str
) -> dict[str, Any]:
    data = validate_delegation(actor, body)
    with transaction.atomic(), connection.cursor() as cursor:
        _ensure_ready(cursor)
        cursor.execute(  # NOSONAR python:S2077 - constant SQL fragment
            f"SELECT 1 FROM eas.app_user u WHERE u.id = %s AND u.is_active AND {SQL_APPROVER_ACTIVE}",
            [data["delegate_id"]],
        )
        if not cursor.fetchone():
            raise CommandError("DELEGATE_NOT_APPROVER", status=422)
        cursor.execute(
            """
            SELECT 1 FROM eas.approval_delegation
            WHERE delegator_id = %s AND revoked_at IS NULL
              AND tstzrange(starts_at, ends_at) && tstzrange(%s, %s)
            """,
            [actor.id, data["starts_at"], data["ends_at"]],
        )
        if cursor.fetchone():
            raise CommandError("DELEGATION_OVERLAP", status=409)
        cursor.execute(
            """
            INSERT INTO eas.approval_delegation(delegator_id, delegate_id, starts_at, ends_at, reason)
            VALUES (%s, %s, %s, %s, %s) RETURNING id::text
            """,
            [
                actor.id,
                data["delegate_id"],
                data["starts_at"],
                data["ends_at"],
                data["reason"],
            ],
        )
        delegation_id = cursor.fetchone()[0]
        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="APPROVAL_DELEGATION_CREATED",
            target_type="approval_delegation",
            target_id=delegation_id,
            details={
                "delegate_id": data["delegate_id"],
                "starts_at": data["starts_at"].isoformat(),
                "ends_at": data["ends_at"].isoformat(),
            },
            reason=data["reason"],
            correlation_id=correlation_id,
        )
    # A delegation that is already in force also takes the steps waiting on
    # the delegator now; later ones are picked up by the worker tick.
    moved = reassign_delegated_steps(
        delegator_id=actor.id, correlation_id=correlation_id
    )
    return {
        "id": delegation_id,
        **{k: str(v) for k, v in data.items()},
        "reassigned_steps": moved,
    }


def reassign_delegated_steps(
    *, delegator_id: str | None = None, correlation_id: str | None = None
) -> int:
    """Hand approval steps already waiting on an approver to their delegate.

    Steps are otherwise substituted only when they activate, so work that was
    pending before the delegation started stayed with the absent approver.
    Eligibility (role, scope, SoD) is re-checked by _substitute_approver.
    """
    moved = 0
    with transaction.atomic(), connection.cursor() as cursor:
        if not _table_readable(cursor, "eas.approval_delegation"):
            return 0
        cursor.execute(
            """
            SELECT s.id::text, r.id::text, r.requester_id::text,
                   v.department_id::text, r.type_id::text
            FROM eas.approval_step s
            JOIN eas.request r ON r.id = s.request_id
            JOIN eas.request_revision v ON v.id = r.current_revision_id
            WHERE s.state = 'ACTIVE' AND r.status = 'PENDING_APPROVAL'
              AND (%s::uuid IS NULL OR s.assignee_id = %s::uuid)
              AND EXISTS (
                SELECT 1 FROM eas.approval_delegation d
                WHERE d.delegator_id = s.assignee_id AND d.revoked_at IS NULL
                  AND d.starts_at <= statement_timestamp()
                  AND d.ends_at > statement_timestamp()
              )
            ORDER BY s.activated_at
            LIMIT 200
            FOR UPDATE OF s, r SKIP LOCKED
            """,
            [delegator_id, delegator_id],
        )
        for (
            step_id,
            request_id,
            requester_id,
            department_id,
            type_id,
        ) in cursor.fetchall():
            change = _substitute_approver(
                cursor,
                step_id=step_id,
                request_id=request_id,
                requester_id=requester_id,
                department_id=department_id,
                type_id=type_id,
                correlation_id=correlation_id,
            )
            if not change:
                continue
            moved += 1
            cursor.execute(
                """
                INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
                VALUES (%s,'APPROVAL_REQUESTED',%s,%s)
                ON CONFLICT DO NOTHING
                """,
                [
                    request_id,
                    Jsonb({"request_id": request_id, "step_id": step_id}),
                    f"request:{request_id}:step:{step_id}:to:{change['assignee_id']}",
                ],
            )
    return moved


def revoke_delegation(
    *, actor: Actor, delegation_id: str, correlation_id: str
) -> dict[str, Any]:
    delegation_id = _canonical_uuid(delegation_id, "INVALID_DELEGATION")
    with transaction.atomic(), connection.cursor() as cursor:
        _ensure_ready(cursor)
        cursor.execute(
            """
            UPDATE eas.approval_delegation SET revoked_at = statement_timestamp()
            WHERE id = %s AND delegator_id = %s AND revoked_at IS NULL
            RETURNING id::text
            """,
            [delegation_id, actor.id],
        )
        if not cursor.fetchone():
            raise CommandError("NOT_FOUND", status=404)
        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="APPROVAL_DELEGATION_REVOKED",
            target_type="approval_delegation",
            target_id=delegation_id,
            details={},
            reason="Thu hồi ủy quyền duyệt",
            correlation_id=correlation_id,
        )
    return {"id": delegation_id, "revoked": True}
