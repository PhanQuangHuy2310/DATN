from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from django.db import connection
from psycopg.types.json import Jsonb

from api_core.authn.service import Actor
from api_core.workflow.service import (
    CommandError,
    CommandResult,
    _append_admin_audit,
    _append_request_audit,
    _authorize,
    _execute_idempotent,
    _is_actor_valid_for_role,
)

_HTML_RE = re.compile(r"<[^>]+>")
_SQL_LOCK_SECURITY = "SELECT eas.lock_security(false)"
_UPDATE_PLANNED_EXECUTOR_SQL = (
    "UPDATE eas.workflow_instance SET planned_executor_id = %s WHERE id = %s"
)


def _clean_reason(value: Any) -> str:
    if not isinstance(value, str):
        raise CommandError("REASON_INVALID", status=422)
    cleaned = value.strip()
    if len(cleaned) < 10 or len(cleaned) > 2000 or _HTML_RE.search(cleaned):
        raise CommandError("REASON_INVALID", status=422)
    return cleaned


def _uuid_str(val: Any, field_name: str) -> str:
    if not isinstance(val, str):
        raise CommandError(f"INVALID_{field_name.upper()}", status=422)
    try:
        return str(UUID(val))
    except (ValueError, TypeError):
        raise CommandError(f"INVALID_{field_name.upper()}", status=422)


def list_ops_metadata(
    actor: Actor,
    query_params: dict[str, str],
) -> dict[str, Any]:
    try:
        limit = int(query_params.get("limit", "20"))
        offset = int(query_params.get("offset", "0"))
    except ValueError:
        raise CommandError("INVALID_PAGINATION", status=400)
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        raise CommandError("INVALID_PAGINATION", status=400)

    status_filter = query_params.get("status")
    type_code_filter = query_params.get("type_code")
    dept_filter = query_params.get("department_id")

    dept_uuid = None
    if dept_filter:
        try:
            dept_uuid = str(UUID(dept_filter))
        except (ValueError, TypeError):
            raise CommandError("INVALID_DEPARTMENT_ID", status=400)

    sql = """
        SELECT r.id::text, r.code, rt.code, r.status, r.lock_version,
               COALESCE(v.department_id, u.department_id)::text AS department_id,
               s.id::text AS active_step_id, s.step_no, s.assignee_id::text,
               a.id::text AS attempt_id, a.attempt_no, a.executor_id::text, a.state,
               i.acceptor_id::text, i.planned_executor_id::text,
               sla.id::text, sla.kind, sla.started_at, sla.due_at, sla.breached_at,
               r.updated_at
        FROM eas.request r
        JOIN eas.request_type rt ON rt.id = r.type_id
        JOIN eas.app_user u ON u.id = r.requester_id
        LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
        LEFT JOIN eas.workflow_instance i ON i.revision_id = r.current_revision_id AND i.state = 'ACTIVE'
        LEFT JOIN eas.approval_step s ON s.instance_id = i.id AND s.state = 'ACTIVE'
        LEFT JOIN eas.execution_attempt a ON a.instance_id = i.id AND a.state IN ('READY', 'RUNNING', 'SUBMITTED')
        LEFT JOIN eas.sla_stage sla ON sla.request_id = r.id AND sla.closed_at IS NULL
        WHERE (%s IS NULL OR r.status = %s)
          AND (%s IS NULL OR rt.code = %s)
          AND (%s IS NULL OR COALESCE(v.department_id, u.department_id) = %s)
          AND EXISTS (
            SELECT 1 FROM eas.role_membership rm
            WHERE rm.user_id = %s AND rm.role = 'OPS_ADMIN' AND rm.revoked_at IS NULL
              AND rm.valid_from <= statement_timestamp()
              AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
          )
        ORDER BY r.updated_at DESC, r.id DESC
        LIMIT %s OFFSET %s
    """
    params = [
        status_filter,
        status_filter,
        type_code_filter,
        type_code_filter,
        dept_uuid,
        dept_uuid,
        actor.id,
        limit + 1,
        offset,
    ]

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    items = [
        {
            "id": row[0],
            "code": row[1],
            "type_code": row[2],
            "status": row[3],
            "lock_version": row[4],
            "department_id": row[5],
            "active_step": (
                {"id": row[6], "step_no": row[7], "assignee_id": row[8]}
                if row[6]
                else None
            ),
            "current_attempt": (
                {
                    "id": row[9],
                    "attempt_no": row[10],
                    "executor_id": row[11],
                    "state": row[12],
                }
                if row[9]
                else None
            ),
            "acceptor_id": row[13],
            "planned_executor_id": row[14],
            "sla": (
                {
                    "id": row[15],
                    "kind": row[16],
                    "started_at": row[17].isoformat() if row[17] else None,
                    "due_at": row[18].isoformat() if row[18] else None,
                    "breached_at": row[19].isoformat() if row[19] else None,
                }
                if row[15]
                else None
            ),
            "updated_at": row[20].isoformat(),
        }
        for row in rows[:limit]
    ]

    return {
        "items": items,
        "next_offset": offset + limit if len(rows) > limit else None,
    }


def reassign_actor(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    normalized_request_id = _uuid_str(request_id, "request_id")
    target_kind = body.get("target_kind")
    if target_kind not in ("APPROVAL_STEP", "EXECUTOR", "ACCEPTOR", "PLANNED_EXECUTOR"):
        raise CommandError("UNKNOWN_TARGET_KIND", status=422)

    target_id = _uuid_str(body.get("target_id"), "target_id")
    new_user_id = _uuid_str(body.get("new_user_id"), "new_user_id")
    reason = _clean_reason(body.get("reason"))

    expected_version = body.get("expected_version")
    if not isinstance(expected_version, int) or expected_version < 0:
        raise CommandError("INVALID_EXPECTED_VERSION", status=422)

    def _op(cursor) -> tuple[dict[str, Any], int, str | None]:
        cursor.execute(_SQL_LOCK_SECURITY)

        cursor.execute(
            """
            SELECT r.id::text, r.status, r.lock_version, r.type_id::text, r.requester_id::text,
                   COALESCE(v.department_id, u.department_id)::text AS department_id,
                   i.id::text AS instance_id, i.lifecycle, i.planned_executor_id::text, i.acceptor_id::text
            FROM eas.request r
            JOIN eas.app_user u ON u.id = r.requester_id
            LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
            LEFT JOIN eas.workflow_instance i ON i.revision_id = r.current_revision_id AND i.state = 'ACTIVE'
            WHERE r.id = %s
            FOR UPDATE OF r
            """,
            [normalized_request_id],
        )
        req_row = cursor.fetchone()
        if not req_row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)

        (
            _r_id,
            r_status,
            r_lock_version,
            type_id,
            requester_id,
            department_id,
            instance_id,
            lifecycle,
            planned_executor_id,
            acceptor_id,
        ) = req_row

        _authorize(
            cursor,
            actor_id=actor.id,
            role="OPS_ADMIN",
            department_id=department_id,
            type_id=type_id,
        )

        if r_lock_version != expected_version:
            raise CommandError("VERSION_CONFLICT", status=409)

        cursor.execute(
            "SELECT is_active FROM eas.app_user WHERE id = %s",
            [new_user_id],
        )
        user_row = cursor.fetchone()
        if not user_row or not user_row[0]:
            raise CommandError("ASSIGNEE_INVALID", status=422)

        next_status = r_status
        old_user_id: str | None = None
        role_joined_as = "PARTICIPANT"

        if target_kind == "APPROVAL_STEP":
            role_joined_as = "APPROVER"
            if not instance_id:
                raise CommandError("TARGET_IMMUTABLE", status=409)

            cursor.execute(
                """
                SELECT id::text, assignee_id::text, state
                FROM eas.approval_step
                WHERE id = %s AND instance_id = %s
                FOR UPDATE
                """,
                [target_id, instance_id],
            )
            step_row = cursor.fetchone()
            if not step_row:
                raise CommandError("TARGET_IMMUTABLE", status=409)

            step_id, current_assignee, step_state = step_row
            if step_state not in ("ACTIVE", "WAITING"):
                raise CommandError("TARGET_IMMUTABLE", status=409)

            cursor.execute(
                "SELECT 1 FROM eas.approval_decision WHERE step_id = %s",
                [step_id],
            )
            if cursor.fetchone():
                raise CommandError("TARGET_IMMUTABLE", status=409)

            if not _is_actor_valid_for_role(
                cursor,
                actor_id=new_user_id,
                role="APPROVER",
                department_id=department_id,
                type_id=type_id,
            ):
                raise CommandError("ASSIGNEE_INVALID", status=422)

            # SoD checks
            if new_user_id == requester_id:
                raise CommandError("ASSIGNEE_INVALID", status=422)
            if planned_executor_id and new_user_id == planned_executor_id:
                raise CommandError("ASSIGNEE_INVALID", status=422)

            cursor.execute(
                """
                SELECT 1 FROM eas.approval_step
                WHERE instance_id = %s AND id <> %s AND assignee_id = %s
                """,
                [instance_id, step_id, new_user_id],
            )
            if cursor.fetchone():
                raise CommandError("ASSIGNEE_INVALID", status=422)

            cursor.execute(
                """
                SELECT 1 FROM eas.execution_attempt
                WHERE instance_id = %s AND executor_id = %s
                """,
                [instance_id, new_user_id],
            )
            if cursor.fetchone():
                raise CommandError("ASSIGNEE_INVALID", status=422)

            old_user_id = current_assignee
            cursor.execute(
                "UPDATE eas.approval_step SET assignee_id = %s WHERE id = %s",
                [new_user_id, step_id],
            )

        elif target_kind == "EXECUTOR":
            role_joined_as = "EXECUTOR"
            if not instance_id:
                raise CommandError("TARGET_IMMUTABLE", status=409)

            cursor.execute(
                """
                SELECT id::text, attempt_no, executor_id::text, state
                FROM eas.execution_attempt
                WHERE id = %s AND instance_id = %s
                FOR UPDATE
                """,
                [target_id, instance_id],
            )
            attempt_row = cursor.fetchone()
            if not attempt_row:
                raise CommandError("TARGET_IMMUTABLE", status=409)

            attempt_id, attempt_no, current_exec, attempt_state = attempt_row
            if attempt_state not in ("READY", "RUNNING") or r_status not in (
                "READY_FOR_EXECUTION",
                "IN_PROGRESS",
            ):
                raise CommandError("TARGET_IMMUTABLE", status=409)

            if not _is_actor_valid_for_role(
                cursor,
                actor_id=new_user_id,
                role="EXECUTOR",
                department_id=department_id,
                type_id=type_id,
            ):
                raise CommandError("ASSIGNEE_INVALID", status=422)

            # SoD checks
            if new_user_id == requester_id:
                raise CommandError("ASSIGNEE_INVALID", status=422)
            if acceptor_id and new_user_id == acceptor_id:
                raise CommandError("ASSIGNEE_INVALID", status=422)

            cursor.execute(
                "SELECT 1 FROM eas.approval_step WHERE instance_id = %s AND assignee_id = %s",
                [instance_id, new_user_id],
            )
            if cursor.fetchone():
                raise CommandError("ASSIGNEE_INVALID", status=422)

            old_user_id = current_exec

            if attempt_state == "READY":
                cursor.execute(
                    "UPDATE eas.execution_attempt SET executor_id = %s WHERE id = %s",
                    [new_user_id, attempt_id],
                )
                cursor.execute(
                    _UPDATE_PLANNED_EXECUTOR_SQL,
                    [new_user_id, instance_id],
                )
                next_status = r_status
            else:  # RUNNING
                cursor.execute(
                    """
                    UPDATE eas.execution_attempt
                    SET state = 'FINISHED', closure_kind = 'REASSIGNED', closed_at = statement_timestamp()
                    WHERE id = %s
                    """,
                    [attempt_id],
                )
                new_attempt_id = str(uuid4())
                cursor.execute(
                    """
                    INSERT INTO eas.execution_attempt(id, request_id, instance_id, attempt_no, executor_id, state)
                    VALUES (%s, %s, %s, %s, %s, 'READY')
                    """,
                    [
                        new_attempt_id,
                        normalized_request_id,
                        instance_id,
                        attempt_no + 1,
                        new_user_id,
                    ],
                )
                cursor.execute(
                    _UPDATE_PLANNED_EXECUTOR_SQL,
                    [new_user_id, instance_id],
                )
                cursor.execute(
                    """
                    UPDATE eas.sla_stage
                    SET attempt_id = %s
                    WHERE request_id = %s AND closed_at IS NULL
                    """,
                    [new_attempt_id, normalized_request_id],
                )
                next_status = "READY_FOR_EXECUTION"

        elif target_kind == "ACCEPTOR":
            role_joined_as = "ACCEPTOR"
            if not instance_id or lifecycle != "C":
                raise CommandError("TARGET_IMMUTABLE", status=409)
            if r_status not in (
                "PENDING_APPROVAL",
                "READY_FOR_EXECUTION",
                "IN_PROGRESS",
                "WAITING_FOR_ACCEPTANCE",
            ):
                raise CommandError("TARGET_IMMUTABLE", status=409)

            cursor.execute(
                """
                SELECT 1 FROM eas.acceptance_decision ad
                JOIN eas.execution_attempt a ON a.id = ad.attempt_id
                WHERE a.instance_id = %s AND a.state IN ('READY', 'RUNNING', 'SUBMITTED')
                """,
                [instance_id],
            )
            if cursor.fetchone():
                raise CommandError("TARGET_IMMUTABLE", status=409)

            if not _is_actor_valid_for_role(
                cursor,
                actor_id=new_user_id,
                role="ACCEPTOR",
                department_id=department_id,
                type_id=type_id,
            ):
                raise CommandError("ASSIGNEE_INVALID", status=422)

            cursor.execute(
                """
                SELECT executor_id::text FROM eas.execution_attempt
                WHERE instance_id = %s AND state IN ('READY', 'RUNNING', 'SUBMITTED')
                """,
                [instance_id],
            )
            current_exec_rows = cursor.fetchall()
            if new_user_id == planned_executor_id or any(
                new_user_id == row[0] for row in current_exec_rows
            ):
                raise CommandError("ASSIGNEE_INVALID", status=422)

            old_user_id = acceptor_id
            cursor.execute(
                "UPDATE eas.workflow_instance SET acceptor_id = %s WHERE id = %s",
                [new_user_id, instance_id],
            )

        elif target_kind == "PLANNED_EXECUTOR":
            role_joined_as = "EXECUTOR"
            if not instance_id or r_status != "WAITING_FOR_ACCEPTANCE":
                raise CommandError("TARGET_IMMUTABLE", status=409)

            if not _is_actor_valid_for_role(
                cursor,
                actor_id=new_user_id,
                role="EXECUTOR",
                department_id=department_id,
                type_id=type_id,
            ):
                raise CommandError("ASSIGNEE_INVALID", status=422)

            if new_user_id == requester_id or (
                acceptor_id and new_user_id == acceptor_id
            ):
                raise CommandError("ASSIGNEE_INVALID", status=422)

            cursor.execute(
                "SELECT 1 FROM eas.approval_step WHERE instance_id = %s AND assignee_id = %s",
                [instance_id, new_user_id],
            )
            if cursor.fetchone():
                raise CommandError("ASSIGNEE_INVALID", status=422)

            old_user_id = planned_executor_id
            cursor.execute(
                _UPDATE_PLANNED_EXECUTOR_SQL,
                [new_user_id, instance_id],
            )

        cursor.execute(
            """
            INSERT INTO eas.request_participant(request_id, user_id, joined_as)
            VALUES (%s, %s, %s)
            ON CONFLICT (request_id, user_id) DO NOTHING
            """,
            [normalized_request_id, new_user_id, role_joined_as],
        )

        cursor.execute(
            """
            UPDATE eas.request
            SET status = %s, lock_version = lock_version + 1, updated_at = statement_timestamp()
            WHERE id = %s
            RETURNING lock_version, updated_at
            """,
            [next_status, normalized_request_id],
        )
        update_row = cursor.fetchone()
        new_lock_version = update_row[0]
        updated_at = update_row[1]

        _append_request_audit(
            cursor,
            request_id=normalized_request_id,
            actor_id=actor.id,
            action="ACTOR_REASSIGNED",
            target_type=target_kind.lower(),
            target_id=target_id,
            details={
                "target_kind": target_kind,
                "old_user_id": old_user_id,
                "new_user_id": new_user_id,
                "reason": reason,
            },
            correlation_id=correlation_id,
            occurred_at=updated_at,
        )

        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="ACTOR_REASSIGNED",
            target_type=target_kind.lower(),
            target_id=target_id,
            department_id=department_id,
            type_id=type_id,
            details={
                "request_id": normalized_request_id,
                "target_kind": target_kind,
                "old_user_id": old_user_id,
                "new_user_id": new_user_id,
            },
            reason=reason,
            correlation_id=correlation_id,
            occurred_at=updated_at,
        )

        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id, event_type, payload, dedupe_key)
            VALUES (%s, 'ACTOR_REASSIGNED', %s, %s)
            """,
            [
                normalized_request_id,
                Jsonb(
                    {
                        "target_kind": target_kind,
                        "target_id": target_id,
                        "old_user_id": old_user_id,
                        "new_user_id": new_user_id,
                    }
                ),
                f"reassign:{normalized_request_id}:{new_lock_version}",
            ],
        )

        return (
            {
                "request": {
                    "id": normalized_request_id,
                    "status": next_status,
                    "lock_version": new_lock_version,
                },
                "reassigned": {
                    "target_kind": target_kind,
                    "old_user_id": old_user_id,
                    "new_user_id": new_user_id,
                },
            },
            200,
            normalized_request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"OPS_REASSIGN:{normalized_request_id}",
        key=idempotency_key,
        command_body=body,
        operation=_op,
    )


def replay_dead_outbox(
    *,
    actor: Actor,
    event_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    normalized_event_id = _uuid_str(event_id, "event_id")
    reason = _clean_reason(body.get("reason"))

    def _op(cursor) -> tuple[dict[str, Any], int, str | None]:
        cursor.execute(_SQL_LOCK_SECURITY)

        cursor.execute(
            """
            SELECT id::text, state, replay_count
            FROM eas.outbox_event
            WHERE id = %s
            FOR UPDATE
            """,
            [normalized_event_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("NOT_FOUND", status=404)

        _ev_id, state, _current_replay_count = row
        if state != "DEAD":
            raise CommandError("EVENT_NOT_DEAD", status=409)

        cursor.execute(
            """
            UPDATE eas.outbox_event
            SET state = 'PENDING',
                attempts = 0,
                replay_count = replay_count + 1,
                available_at = statement_timestamp(),
                lease_token = NULL,
                lease_until = NULL,
                last_error_code = NULL
            WHERE id = %s
            RETURNING replay_count
            """,
            [normalized_event_id],
        )
        new_replay_count = cursor.fetchone()[0]

        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="OUTBOX_REPLAYED",
            target_type="outbox_event",
            target_id=normalized_event_id,
            details={"replay_count": new_replay_count},
            reason=reason,
            correlation_id=correlation_id,
        )

        return (
            {
                "outbox_event": {
                    "id": normalized_event_id,
                    "state": "PENDING",
                    "replay_count": new_replay_count,
                }
            },
            200,
            None,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"OPS_OUTBOX:{normalized_event_id}",
        key=idempotency_key,
        command_body=body,
        operation=_op,
    )
