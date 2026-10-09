from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.audit import canonical_sha256
from api_core.authn.models import Actor
from api_core.domain import PayloadValidationError, resolve_route, validate_payload


class CommandError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        status: int = 400,
        fields: dict[str, list[str]] | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.status = status
        self.fields = fields


@dataclass(frozen=True)
class CommandResult:
    body: dict[str, Any]
    status: int
    replayed: bool = False


def _canonical_uuid(value: object, code: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise CommandError(code) from None


def _utc_text(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _authorize(
    cursor,
    *,
    actor_id: str,
    role: str,
    department_id: str,
    type_id: str,
) -> None:
    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM eas.role_membership
          WHERE user_id = %s AND role = %s AND revoked_at IS NULL
            AND valid_from <= statement_timestamp()
            AND (valid_to IS NULL OR valid_to > statement_timestamp())
            AND (scope_kind = 'GLOBAL' OR department_id = %s)
            AND (type_scope = 'ALL' OR type_id = %s)
        )
        """,
        [actor_id, role, department_id, type_id],
    )
    if not cursor.fetchone()[0]:
        raise CommandError("FORBIDDEN", status=403)


def _append_request_audit(
    cursor,
    *,
    request_id: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any],
    correlation_id: str,
    occurred_at: datetime,
) -> None:
    scope_key = f"REQ:{request_id}"
    cursor.execute("SELECT seq,last_hash FROM eas.lock_audit_head(%s)", [scope_key])
    head = cursor.fetchone()
    if not head:
        raise CommandError("AUDIT_HEAD_MISSING", status=500)
    sequence = head[0] + 1
    previous_hash = head[1]
    event_id = str(uuid4())
    event = {
        "action": action,
        "actor_id": actor_id,
        "actor_kind": "HUMAN",
        "correlation_id": correlation_id,
        "details": details,
        "hash_version": 1,
        "id": event_id,
        "occurred_at": _utc_text(occurred_at),
        "prev_hash": previous_hash,
        "request_id": request_id,
        "scope_key": scope_key,
        "seq": str(sequence),
        "target_id": target_id,
        "target_type": target_type,
    }
    digest = canonical_sha256(event)
    cursor.execute(
        """
        INSERT INTO eas.audit_event(
          id,request_id,seq,actor_id,actor_kind,action,target_type,target_id,
          details,correlation_id,occurred_at,hash_version,prev_hash,hash
        ) VALUES (%s,%s,%s,%s,'HUMAN',%s,%s,%s,%s,%s,%s,1,%s,%s)
        """,
        [
            event_id,
            request_id,
            sequence,
            actor_id,
            action,
            target_type,
            target_id,
            Jsonb(details),
            correlation_id,
            occurred_at,
            previous_hash,
            digest,
        ],
    )


def _execute_idempotent(
    *,
    actor_id: str,
    scope: str,
    key: str,
    command_body: dict[str, Any],
    operation: Callable[[Any], tuple[dict[str, Any], int, str | None]],
) -> CommandResult:
    key = _canonical_uuid(key, "INVALID_IDEMPOTENCY_KEY")
    request_hash = canonical_sha256(command_body)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"{actor_id}:{scope}:{key}"],
        )
        cursor.execute(
            """
            SELECT request_hash,http_status,response_body,expires_at > statement_timestamp()
            FROM eas.idempotency_record
            WHERE actor_id=%s AND command_scope=%s AND key=%s
            FOR UPDATE
            """,
            [actor_id, scope, key],
        )
        existing = cursor.fetchone()
        if existing:
            if existing[0] != request_hash:
                raise CommandError("IDEMPOTENCY_KEY_REUSED", status=409)
            if not existing[3] or existing[2] is None:
                raise CommandError("IDEMPOTENCY_RESULT_EXPIRED", status=410)
            return CommandResult(existing[2], existing[1], replayed=True)

        body, status, request_id = operation(cursor)
        cursor.execute(
            """
            INSERT INTO eas.idempotency_record(
              actor_id,command_scope,key,request_hash,http_status,response_body,request_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            [actor_id, scope, key, request_hash, status, Jsonb(body), request_id],
        )
        return CommandResult(body, status)


def create_draft(
    *,
    actor: Actor,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    if set(body) != {"type_code"} or not isinstance(body.get("type_code"), str):
        raise CommandError("INVALID_DRAFT_REQUEST")
    type_code = body["type_code"]

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT rt.id::text,cr.id::text
            FROM eas.request_type rt
            JOIN eas.config_release cr ON cr.id=rt.active_release_id
            WHERE rt.code=%s AND rt.is_active AND cr.state='PUBLISHED'
              AND cr.type_id=rt.id AND cr.lifecycle=rt.lifecycle
            FOR SHARE OF rt,cr
            """,
            [type_code],
        )
        configured = cursor.fetchone()
        if not configured:
            raise CommandError("REQUEST_TYPE_NOT_CONFIGURED", status=409)
        type_id, release_id = configured
        _authorize(
            cursor,
            actor_id=actor.id,
            role="REQUESTER",
            department_id=actor.department_id,
            type_id=type_id,
        )
        request_id = str(uuid4())
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO eas.request(id,requester_id,type_id,draft_release_id)
            VALUES (%s,%s,%s,%s) RETURNING code
            """,
            [request_id, actor.id, type_id, release_id],
        )
        code = cursor.fetchone()[0]
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="DRAFT_CREATED",
            target_type="request",
            target_id=request_id,
            details={"type_code": type_code, "release_id": release_id},
            correlation_id=correlation_id,
            occurred_at=now,
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "code": code,
                    "status": "DRAFT",
                    "lock_version": 0,
                }
            },
            201,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope="request:draft:create",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def submit_request(
    *,
    actor: Actor,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    if set(body) - {
        "type_code",
        "payload",
        "attachment_ids",
        "request_id",
        "expected_version",
    }:
        raise CommandError("UNKNOWN_FIELD")
    type_code = body.get("type_code")
    payload = body.get("payload")
    attachment_ids = body.get("attachment_ids", [])
    existing_request_id = body.get("request_id")
    expected_version = body.get("expected_version", 0)
    if not isinstance(type_code, str) or not isinstance(payload, dict):
        raise CommandError("INVALID_SUBMISSION")
    if (
        not isinstance(attachment_ids, list)
        or len(attachment_ids) > 5
        or len(set(map(str, attachment_ids))) != len(attachment_ids)
    ):
        raise CommandError("INVALID_ATTACHMENTS")
    attachment_ids = [
        _canonical_uuid(item, "INVALID_ATTACHMENT_ID") for item in attachment_ids
    ]
    if existing_request_id is not None:
        existing_request_id = _canonical_uuid(existing_request_id, "INVALID_REQUEST_ID")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT rt.id::text,rt.lifecycle,cr.id::text,cr.form_schema,
                   cr.route_rules,cr.actor_bindings,cr.sla_profile
            FROM eas.request_type rt
            JOIN eas.config_release cr ON cr.id=rt.active_release_id
            WHERE rt.code=%s AND rt.is_active AND cr.state='PUBLISHED'
              AND cr.type_id=rt.id AND cr.lifecycle=rt.lifecycle
            FOR SHARE OF rt,cr
            """,
            [type_code],
        )
        config = cursor.fetchone()
        if not config:
            raise CommandError("REQUEST_TYPE_NOT_CONFIGURED", status=409)
        type_id, lifecycle, release_id, form, rules, bindings, sla = config
        cursor.execute(
            """
            SELECT manager_id::text FROM eas.app_user
            WHERE id=%s AND is_active AND department_id=%s
            FOR SHARE
            """,
            [actor.id, actor.department_id],
        )
        user = cursor.fetchone()
        if not user:
            raise CommandError("ACTOR_NOT_ACTIVE", status=403)
        _authorize(
            cursor,
            actor_id=actor.id,
            role="REQUESTER",
            department_id=actor.department_id,
            type_id=type_id,
        )
        try:
            normalized = validate_payload(
                type_code=type_code,
                payload=payload,
                form_schema=form,
                requester_id=actor.id,
            )
        except PayloadValidationError as exc:
            raise CommandError("VALIDATION_FAILED", fields=exc.errors) from exc
        amount = normalized.get("amount_vnd")
        decision = resolve_route(
            route_rules=rules,
            actor_bindings=bindings,
            department_id=actor.department_id,
            requester_id=actor.id,
            manager_id=user[0],
            amount_vnd=amount,
        )
        routed_actors = set(decision.approver_ids)
        if decision.executor_id:
            routed_actors.add(decision.executor_id)
        if decision.acceptor_id:
            routed_actors.add(decision.acceptor_id)
        cursor.execute(
            "SELECT count(*) FROM eas.app_user WHERE is_active AND id=ANY(%s::uuid[])",
            [list(routed_actors)],
        )
        if cursor.fetchone()[0] != len(routed_actors):
            raise CommandError("ROUTE_ACTOR_INACTIVE", status=409)
        for approver_id in decision.approver_ids:
            _authorize(
                cursor,
                actor_id=approver_id,
                role="APPROVER",
                department_id=actor.department_id,
                type_id=type_id,
            )
        if decision.executor_id:
            _authorize(
                cursor,
                actor_id=decision.executor_id,
                role="EXECUTOR",
                department_id=actor.department_id,
                type_id=type_id,
            )
        if decision.acceptor_id:
            _authorize(
                cursor,
                actor_id=decision.acceptor_id,
                role="ACCEPTOR",
                department_id=actor.department_id,
                type_id=type_id,
            )
        if lifecycle == "C" and not attachment_ids:
            raise CommandError("EQUIPMENT_QUOTE_REQUIRED")

        now = datetime.now(timezone.utc)
        request_id = existing_request_id or str(uuid4())
        revision_id = str(uuid4())
        instance_id = str(uuid4())
        if existing_request_id:
            cursor.execute(
                """
                SELECT code,status,lock_version,type_id::text
                FROM eas.request WHERE id=%s AND requester_id=%s FOR UPDATE
                """,
                [request_id, actor.id],
            )
            draft = cursor.fetchone()
            if not draft:
                raise CommandError("REQUEST_NOT_FOUND", status=404)
            request_code, draft_status, draft_version, draft_type_id = draft
            if draft_status not in {"DRAFT", "NEEDS_INFO"}:
                raise CommandError("REQUEST_STATE_CONFLICT", status=409)
            if draft_version != expected_version:
                raise CommandError("VERSION_CONFLICT", status=409)
            if draft_type_id != type_id:
                raise CommandError("REQUEST_TYPE_CONFLICT", status=409)
        else:
            if expected_version != 0:
                raise CommandError("VERSION_CONFLICT", status=409)
            cursor.execute(
                """
                INSERT INTO eas.request(
                  id,requester_id,type_id,draft_payload,draft_amount_vnd,draft_release_id
                ) VALUES (%s,%s,%s,%s,%s,%s) RETURNING code
                """,
                [request_id, actor.id, type_id, Jsonb(normalized), amount, release_id],
            )
            request_code = cursor.fetchone()[0]
            draft_version = 0
        cursor.execute(
            "SELECT coalesce(max(revision_no),0)+1 FROM eas.request_revision WHERE request_id=%s",
            [request_id],
        )
        revision_no = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO eas.request_revision(
              id,request_id,revision_no,release_id,department_id,payload,
              amount_vnd,submitted_by,payload_sha256,submitted_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            [
                revision_id,
                request_id,
                revision_no,
                release_id,
                actor.department_id,
                Jsonb(normalized),
                amount,
                actor.id,
                canonical_sha256(normalized),
                now,
            ],
        )
        for attachment_id in attachment_ids:
            cursor.execute(
                """
                INSERT INTO eas.revision_attachment(revision_id,attachment_id,request_id)
                SELECT %s,a.id,%s FROM eas.attachment a
                WHERE a.id=%s AND a.request_id=%s AND a.uploader_id=%s
                  AND a.scan_state='CLEAN' AND a.deleted_at IS NULL
                """,
                [revision_id, request_id, attachment_id, request_id, actor.id],
            )
            if cursor.rowcount != 1:
                raise CommandError("ATTACHMENT_NOT_READY", status=409)
            cursor.execute(
                "DELETE FROM eas.draft_attachment WHERE request_id=%s AND attachment_id=%s",
                [request_id, attachment_id],
            )
        cursor.execute(
            """
            INSERT INTO eas.workflow_instance(
              id,request_id,revision_id,matched_rule_id,resolved_route,lifecycle,
              planned_executor_id,acceptor_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            [
                instance_id,
                request_id,
                revision_id,
                decision.matched_rule_id,
                Jsonb(decision.resolved_route),
                lifecycle,
                decision.executor_id,
                decision.acceptor_id,
            ],
        )
        participants = [(actor.id, "REQUESTER")]
        participants.extend((item, "APPROVER") for item in decision.approver_ids)
        if decision.executor_id:
            participants.append((decision.executor_id, "EXECUTOR"))
        for user_id, joined_as in dict(participants).items():
            cursor.execute(
                """
                INSERT INTO eas.request_participant(request_id,user_id,joined_as)
                VALUES (%s,%s,%s)
                """,
                [request_id, user_id, joined_as],
            )
        first_step_id = None
        for index, assignee_id in enumerate(decision.approver_ids, start=1):
            step_id = str(uuid4())
            if index == 1:
                first_step_id = step_id
            cursor.execute(
                """
                INSERT INTO eas.approval_step(
                  id,request_id,instance_id,step_no,assignee_id,state,activated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                [
                    step_id,
                    request_id,
                    instance_id,
                    index,
                    assignee_id,
                    "ACTIVE" if index == 1 else "WAITING",
                    now if index == 1 else None,
                ],
            )
        approval_hours = sla.get("approval_hours")
        if (
            isinstance(approval_hours, bool)
            or not isinstance(approval_hours, int)
            or approval_hours <= 0
        ):
            raise CommandError("INVALID_SLA_CONFIGURATION", status=409)
        cursor.execute(
            """
            INSERT INTO eas.sla_stage(
              request_id,kind,approval_step_id,started_at,due_at
            ) VALUES (%s,'APPROVAL',%s,%s,%s + make_interval(hours => %s))
            """,
            [request_id, first_step_id, now, now, approval_hours],
        )
        cursor.execute(
            """
            UPDATE eas.request SET status='PENDING_APPROVAL',current_revision_id=%s,
              draft_payload=%s,draft_amount_vnd=%s,draft_release_id=%s,
              lock_version=lock_version+1,updated_at=%s
            WHERE id=%s
            """,
            [revision_id, Jsonb(normalized), amount, release_id, now, request_id],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="REQUEST_SUBMITTED",
            target_type="request",
            target_id=request_id,
            details={
                "revision_id": revision_id,
                "release_id": release_id,
                "matched_rule_id": decision.matched_rule_id,
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )
        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
            VALUES (%s,'APPROVAL_REQUESTED',%s,%s)
            """,
            [
                request_id,
                Jsonb({"request_id": request_id, "step_id": first_step_id}),
                f"request:{request_id}:revision:{revision_no}:approval:1",
            ],
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "code": request_code,
                    "status": "PENDING_APPROVAL",
                    "lock_version": draft_version + 1,
                }
            },
            201,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope="request:submit",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def decide_approval(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    if set(body) != {"outcome", "reason", "expected_version"}:
        raise CommandError("INVALID_DECISION")
    outcome = body.get("outcome")
    reason = body.get("reason")
    expected_version = body.get("expected_version")
    if outcome not in {"APPROVE", "REJECT", "NEEDS_INFO"}:
        raise CommandError("INVALID_DECISION")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")
    if outcome != "APPROVE" and (
        not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
    ):
        raise CommandError("DECISION_REASON_REQUIRED")
    if outcome == "APPROVE":
        reason = None

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT r.status,r.lock_version,r.type_id::text,v.department_id::text,
                   i.id::text,i.lifecycle,i.planned_executor_id::text,
                   cr.sla_profile
            FROM eas.request r
            JOIN eas.request_revision v ON v.id=r.current_revision_id
            JOIN eas.workflow_instance i ON i.revision_id=v.id AND i.state='ACTIVE'
            JOIN eas.config_release cr ON cr.id=v.release_id
            WHERE r.id=%s
            FOR UPDATE OF r,i
            """,
            [request_id],
        )
        current = cursor.fetchone()
        if not current:
            raise CommandError("REQUEST_NOT_FOUND", status=404)
        (
            status,
            lock_version,
            type_id,
            department_id,
            instance_id,
            lifecycle,
            executor_id,
            sla,
        ) = current
        if status != "PENDING_APPROVAL":
            raise CommandError("REQUEST_STATE_CONFLICT", status=409)
        if lock_version != expected_version:
            raise CommandError("VERSION_CONFLICT", status=409)
        cursor.execute(
            """
            SELECT id::text,step_no,assignee_id::text
            FROM eas.approval_step
            WHERE instance_id=%s AND state='ACTIVE'
            FOR UPDATE
            """,
            [instance_id],
        )
        step = cursor.fetchone()
        if not step:
            raise CommandError("ACTIVE_STEP_NOT_FOUND", status=409)
        step_id, step_no, assignee_id = step
        if assignee_id != actor.id:
            raise CommandError("FORBIDDEN", status=403)
        _authorize(
            cursor,
            actor_id=actor.id,
            role="APPROVER",
            department_id=department_id,
            type_id=type_id,
        )
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO eas.approval_decision(request_id,step_id,actor_id,outcome,reason,decided_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            [request_id, step_id, actor.id, outcome, reason, now],
        )
        cursor.execute(
            """
            UPDATE eas.approval_step SET state=%s,closed_at=%s WHERE id=%s
            """,
            [
                {
                    "APPROVE": "APPROVED",
                    "REJECT": "REJECTED",
                    "NEEDS_INFO": "NEEDS_INFO",
                }[outcome],
                now,
                step_id,
            ],
        )
        cursor.execute(
            "UPDATE eas.sla_stage SET closed_at=%s WHERE request_id=%s AND closed_at IS NULL",
            [now, request_id],
        )

        next_status = status
        approved_at = None
        completed_at = None
        next_step_id = None
        if outcome == "APPROVE":
            cursor.execute(
                """
                SELECT id::text FROM eas.approval_step
                WHERE instance_id=%s AND state='WAITING'
                ORDER BY step_no LIMIT 1 FOR UPDATE
                """,
                [instance_id],
            )
            next_step = cursor.fetchone()
            if next_step:
                next_step_id = next_step[0]
                cursor.execute(
                    "UPDATE eas.approval_step SET state='ACTIVE',activated_at=%s WHERE id=%s",
                    [now, next_step_id],
                )
                cursor.execute(
                    """
                    INSERT INTO eas.sla_stage(request_id,kind,approval_step_id,started_at,due_at)
                    VALUES (%s,'APPROVAL',%s,%s,%s + make_interval(hours => %s))
                    """,
                    [request_id, next_step_id, now, now, sla["approval_hours"]],
                )
            else:
                approved_at = now
                if lifecycle == "A":
                    cursor.execute(
                        "UPDATE eas.workflow_instance SET state='COMPLETED',closed_at=%s WHERE id=%s",
                        [now, instance_id],
                    )
                    next_status = "COMPLETED"
                    completed_at = now
                else:
                    next_status = "READY_FOR_EXECUTION"
                    attempt_id = str(uuid4())
                    cursor.execute(
                        """
                        INSERT INTO eas.execution_attempt(
                          id,request_id,instance_id,attempt_no,executor_id
                        ) VALUES (%s,%s,%s,1,%s)
                        """,
                        [attempt_id, request_id, instance_id, executor_id],
                    )
                    execution_hours = sla.get("execution_hours")
                    if (
                        isinstance(execution_hours, bool)
                        or not isinstance(execution_hours, int)
                        or execution_hours <= 0
                    ):
                        raise CommandError("INVALID_SLA_CONFIGURATION", status=409)
                    cursor.execute(
                        """
                        INSERT INTO eas.sla_stage(
                          request_id,kind,attempt_id,started_at,due_at
                        ) VALUES (%s,'EXECUTION',%s,%s,%s + make_interval(hours => %s))
                        """,
                        [request_id, attempt_id, now, now, execution_hours],
                    )
        else:
            next_status = "REJECTED" if outcome == "REJECT" else "NEEDS_INFO"
            instance_state = "REJECTED" if outcome == "REJECT" else "SUPERSEDED"
            cursor.execute(
                "UPDATE eas.workflow_instance SET state=%s,closed_at=%s WHERE id=%s",
                [instance_state, now, instance_id],
            )
            cursor.execute(
                """
                UPDATE eas.approval_step SET state='SKIPPED',closed_at=%s
                WHERE instance_id=%s AND state='WAITING'
                """,
                [now, instance_id],
            )
        cursor.execute(
            """
            UPDATE eas.request SET status=%s,lock_version=lock_version+1,
              updated_at=%s,approved_at=COALESCE(%s,approved_at),completed_at=%s
            WHERE id=%s
            """,
            [next_status, now, approved_at, completed_at, request_id],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action=f"APPROVAL_{outcome}",
            target_type="approval_step",
            target_id=step_id,
            details={
                "outcome": outcome,
                "step_no": step_no,
                "next_status": next_status,
                **({"reason": reason} if reason else {}),
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )
        if next_step_id:
            event_type = "APPROVAL_REQUESTED"
        elif outcome == "APPROVE" and lifecycle in {"B", "C"}:
            event_type = "EXECUTION_READY"
        else:
            event_type = f"APPROVAL_{outcome}"
        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
            VALUES (%s,%s,%s,%s)
            """,
            [
                request_id,
                event_type,
                Jsonb({"request_id": request_id, "step_id": next_step_id or step_id}),
                f"request:{request_id}:step:{step_id}:decision:{outcome.lower()}",
            ],
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "status": next_status,
                    "lock_version": lock_version + 1,
                }
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:approval",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def start_execution(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    if set(body) != {"expected_version"}:
        raise CommandError("INVALID_EXECUTION_START")
    expected_version = body.get("expected_version")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT r.status,r.lock_version,r.type_id::text,v.department_id::text,
                   i.id::text,a.id::text,a.executor_id::text,a.state
            FROM eas.request r
            JOIN eas.request_revision v ON v.id=r.current_revision_id
            JOIN eas.workflow_instance i ON i.revision_id=v.id AND i.state='ACTIVE'
            JOIN eas.execution_attempt a ON a.instance_id=i.id
              AND a.state IN ('READY','RUNNING','SUBMITTED')
            WHERE r.id=%s FOR UPDATE OF r,i,a
            """,
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)
        (
            status,
            lock_version,
            type_id,
            department_id,
            instance_id,
            attempt_id,
            executor_id,
            attempt_state,
        ) = row
        if status != "READY_FOR_EXECUTION" or attempt_state != "READY":
            raise CommandError("REQUEST_STATE_CONFLICT", status=409)
        if lock_version != expected_version:
            raise CommandError("VERSION_CONFLICT", status=409)
        if executor_id != actor.id:
            raise CommandError("FORBIDDEN", status=403)
        _authorize(
            cursor,
            actor_id=actor.id,
            role="EXECUTOR",
            department_id=department_id,
            type_id=type_id,
        )
        now = datetime.now(timezone.utc)
        cursor.execute(
            "UPDATE eas.execution_attempt SET state='RUNNING',started_at=%s WHERE id=%s",
            [now, attempt_id],
        )
        cursor.execute(
            """
            UPDATE eas.request SET status='IN_PROGRESS',lock_version=lock_version+1,
              updated_at=%s WHERE id=%s
            """,
            [now, request_id],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="EXECUTION_STARTED",
            target_type="execution_attempt",
            target_id=attempt_id,
            details={"instance_id": instance_id},
            correlation_id=correlation_id,
            occurred_at=now,
        )
        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
            VALUES (%s,'EXECUTION_STARTED',%s,%s)
            """,
            [
                request_id,
                Jsonb({"request_id": request_id, "attempt_id": attempt_id}),
                f"attempt:{attempt_id}:started",
            ],
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "status": "IN_PROGRESS",
                    "lock_version": lock_version + 1,
                    "attempt_id": attempt_id,
                }
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:execution:start",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def submit_execution(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    if set(body) != {"expected_version", "result_note", "external_reference"}:
        raise CommandError("INVALID_EXECUTION_RESULT")
    expected_version = body.get("expected_version")
    result_note = body.get("result_note")
    external_reference = body.get("external_reference")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")
    if not isinstance(result_note, str) or not 10 <= len(result_note.strip()) <= 4000:
        raise CommandError("RESULT_NOTE_INVALID")
    if (
        not isinstance(external_reference, str)
        or not 1 <= len(external_reference.strip()) <= 200
    ):
        raise CommandError("EXTERNAL_REFERENCE_INVALID")
    result_note = result_note.strip()
    external_reference = external_reference.strip()

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT r.status,r.lock_version,r.type_id::text,v.department_id::text,
                   i.id::text,i.lifecycle,a.id::text,a.executor_id::text,a.state,
                   cr.sla_profile
            FROM eas.request r
            JOIN eas.request_revision v ON v.id=r.current_revision_id
            JOIN eas.config_release cr ON cr.id=v.release_id
            JOIN eas.workflow_instance i ON i.revision_id=v.id AND i.state='ACTIVE'
            JOIN eas.execution_attempt a ON a.instance_id=i.id
              AND a.state IN ('READY','RUNNING','SUBMITTED')
            WHERE r.id=%s FOR UPDATE OF r,i,a
            """,
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)
        (
            status,
            lock_version,
            type_id,
            department_id,
            instance_id,
            lifecycle,
            attempt_id,
            executor_id,
            attempt_state,
            sla,
        ) = row
        if status != "IN_PROGRESS" or attempt_state != "RUNNING":
            raise CommandError("REQUEST_STATE_CONFLICT", status=409)
        if lock_version != expected_version:
            raise CommandError("VERSION_CONFLICT", status=409)
        if executor_id != actor.id:
            raise CommandError("FORBIDDEN", status=403)
        _authorize(
            cursor,
            actor_id=actor.id,
            role="EXECUTOR",
            department_id=department_id,
            type_id=type_id,
        )
        cursor.execute(
            "SELECT count(*) FROM eas.execution_attachment WHERE attempt_id=%s",
            [attempt_id],
        )
        if not 1 <= cursor.fetchone()[0] <= 5:
            raise CommandError("EXECUTION_EVIDENCE_REQUIRED", status=409)
        now = datetime.now(timezone.utc)
        if lifecycle == "B":
            cursor.execute(
                """
                UPDATE eas.execution_attempt SET state='FINISHED',closure_kind='SUCCESS',
                  result_note=%s,external_reference=%s,submitted_at=%s,closed_at=%s
                WHERE id=%s
                """,
                [result_note, external_reference, now, now, attempt_id],
            )
            cursor.execute(
                "UPDATE eas.workflow_instance SET state='COMPLETED',closed_at=%s WHERE id=%s",
                [now, instance_id],
            )
            next_status = "COMPLETED"
            completed_at = now
        elif lifecycle == "C":
            cursor.execute(
                """
                UPDATE eas.execution_attempt SET state='SUBMITTED',result_note=%s,
                  external_reference=%s,submitted_at=%s WHERE id=%s
                """,
                [result_note, external_reference, now, attempt_id],
            )
            next_status = "WAITING_FOR_ACCEPTANCE"
            completed_at = None
        else:
            raise CommandError("LIFECYCLE_CONFLICT", status=409)
        cursor.execute(
            "UPDATE eas.sla_stage SET closed_at=%s WHERE request_id=%s AND closed_at IS NULL",
            [now, request_id],
        )
        if lifecycle == "C":
            acceptance_hours = sla.get("acceptance_hours")
            if (
                isinstance(acceptance_hours, bool)
                or not isinstance(acceptance_hours, int)
                or acceptance_hours <= 0
            ):
                raise CommandError("INVALID_SLA_CONFIGURATION", status=409)
            cursor.execute(
                """
                INSERT INTO eas.sla_stage(request_id,kind,attempt_id,started_at,due_at)
                VALUES (%s,'ACCEPTANCE',%s,%s,%s + make_interval(hours => %s))
                """,
                [request_id, attempt_id, now, now, acceptance_hours],
            )
        cursor.execute(
            """
            UPDATE eas.request SET status=%s,lock_version=lock_version+1,
              updated_at=%s,completed_at=%s WHERE id=%s
            """,
            [next_status, now, completed_at, request_id],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="EXECUTION_RESULT_SUBMITTED",
            target_type="execution_attempt",
            target_id=attempt_id,
            details={"lifecycle": lifecycle, "external_reference": external_reference},
            correlation_id=correlation_id,
            occurred_at=now,
        )
        event_type = "ACCEPTANCE_REQUESTED" if lifecycle == "C" else "REQUEST_COMPLETED"
        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
            VALUES (%s,%s,%s,%s)
            """,
            [
                request_id,
                event_type,
                Jsonb({"request_id": request_id, "attempt_id": attempt_id}),
                f"attempt:{attempt_id}:result-submitted",
            ],
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "status": next_status,
                    "lock_version": lock_version + 1,
                }
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:execution:submit",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def decide_acceptance(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    if set(body) != {"outcome", "reason", "expected_version"}:
        raise CommandError("INVALID_ACCEPTANCE")
    outcome = body.get("outcome")
    reason = body.get("reason")
    expected_version = body.get("expected_version")
    if outcome not in {"ACCEPT", "REWORK"}:
        raise CommandError("INVALID_ACCEPTANCE")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")
    if outcome == "REWORK" and (
        not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
    ):
        raise CommandError("ACCEPTANCE_REASON_REQUIRED")
    if outcome == "ACCEPT":
        reason = None

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT r.status,r.lock_version,r.type_id::text,v.department_id::text,
                   i.id::text,i.acceptor_id::text,a.id::text,a.executor_id::text,
                   a.attempt_no,cr.sla_profile
            FROM eas.request r
            JOIN eas.request_revision v ON v.id=r.current_revision_id
            JOIN eas.config_release cr ON cr.id=v.release_id
            JOIN eas.workflow_instance i ON i.revision_id=v.id AND i.state='ACTIVE'
            JOIN eas.execution_attempt a ON a.instance_id=i.id AND a.state='SUBMITTED'
            WHERE r.id=%s AND i.lifecycle='C' FOR UPDATE OF r,i,a
            """,
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)
        (
            status,
            lock_version,
            type_id,
            department_id,
            instance_id,
            acceptor_id,
            attempt_id,
            executor_id,
            attempt_no,
            sla,
        ) = row
        if status != "WAITING_FOR_ACCEPTANCE":
            raise CommandError("REQUEST_STATE_CONFLICT", status=409)
        if lock_version != expected_version:
            raise CommandError("VERSION_CONFLICT", status=409)
        if acceptor_id != actor.id or executor_id == actor.id:
            raise CommandError("FORBIDDEN", status=403)
        _authorize(
            cursor,
            actor_id=actor.id,
            role="ACCEPTOR",
            department_id=department_id,
            type_id=type_id,
        )
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO eas.acceptance_decision(request_id,attempt_id,actor_id,outcome,reason,decided_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            [request_id, attempt_id, actor.id, outcome, reason, now],
        )
        cursor.execute(
            """
            UPDATE eas.execution_attempt SET state='FINISHED',closure_kind=%s,closed_at=%s
            WHERE id=%s
            """,
            ["ACCEPTED" if outcome == "ACCEPT" else "REWORK", now, attempt_id],
        )
        cursor.execute(
            "UPDATE eas.sla_stage SET closed_at=%s WHERE request_id=%s AND closed_at IS NULL",
            [now, request_id],
        )
        if outcome == "ACCEPT":
            next_status = "COMPLETED"
            completed_at = now
            cursor.execute(
                "UPDATE eas.workflow_instance SET state='COMPLETED',closed_at=%s WHERE id=%s",
                [now, instance_id],
            )
            next_attempt_id = None
        else:
            next_status = "READY_FOR_EXECUTION"
            completed_at = None
            next_attempt_id = str(uuid4())
            cursor.execute(
                """
                INSERT INTO eas.execution_attempt(
                  id,request_id,instance_id,attempt_no,executor_id
                ) VALUES (%s,%s,%s,%s,%s)
                """,
                [next_attempt_id, request_id, instance_id, attempt_no + 1, executor_id],
            )
            execution_hours = sla.get("execution_hours")
            if (
                isinstance(execution_hours, bool)
                or not isinstance(execution_hours, int)
                or execution_hours <= 0
            ):
                raise CommandError("INVALID_SLA_CONFIGURATION", status=409)
            cursor.execute(
                """
                INSERT INTO eas.sla_stage(request_id,kind,attempt_id,started_at,due_at)
                VALUES (%s,'EXECUTION',%s,%s,%s + make_interval(hours => %s))
                """,
                [request_id, next_attempt_id, now, now, execution_hours],
            )
        cursor.execute(
            """
            UPDATE eas.request SET status=%s,lock_version=lock_version+1,
              updated_at=%s,completed_at=%s WHERE id=%s
            """,
            [next_status, now, completed_at, request_id],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action=f"ACCEPTANCE_{outcome}",
            target_type="execution_attempt",
            target_id=attempt_id,
            details={"outcome": outcome, **({"reason": reason} if reason else {})},
            correlation_id=correlation_id,
            occurred_at=now,
        )
        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
            VALUES (%s,%s,%s,%s)
            """,
            [
                request_id,
                "REQUEST_COMPLETED" if outcome == "ACCEPT" else "EXECUTION_REWORK",
                Jsonb(
                    {
                        "request_id": request_id,
                        "attempt_id": next_attempt_id or attempt_id,
                    }
                ),
                f"attempt:{attempt_id}:acceptance:{outcome.lower()}",
            ],
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "status": next_status,
                    "lock_version": lock_version + 1,
                    **({"attempt_id": next_attempt_id} if next_attempt_id else {}),
                }
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:acceptance",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def cancel_request(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    if set(body) != {"expected_version", "reason"}:
        raise CommandError("INVALID_CANCELLATION")
    expected_version = body.get("expected_version")
    reason = body.get("reason")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
        raise CommandError("CANCELLATION_REASON_REQUIRED")
    reason = reason.strip()

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT status,lock_version,requester_id::text,current_revision_id::text
            FROM eas.request WHERE id=%s FOR UPDATE
            """,
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)
        status, lock_version, requester_id, revision_id = row
        if requester_id != actor.id:
            raise CommandError("FORBIDDEN", status=403)
        if status not in {"DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"}:
            raise CommandError("REQUEST_STATE_CONFLICT", status=409)
        if lock_version != expected_version:
            raise CommandError("VERSION_CONFLICT", status=409)
        now = datetime.now(timezone.utc)
        if revision_id:
            cursor.execute(
                """
                UPDATE eas.workflow_instance SET state='CANCELLED',closed_at=%s
                WHERE revision_id=%s AND state='ACTIVE'
                """,
                [now, revision_id],
            )
            cursor.execute(
                """
                UPDATE eas.approval_step SET state='SKIPPED',closed_at=%s
                WHERE request_id=%s AND state IN ('WAITING','ACTIVE')
                """,
                [now, request_id],
            )
            cursor.execute(
                "UPDATE eas.sla_stage SET closed_at=%s WHERE request_id=%s AND closed_at IS NULL",
                [now, request_id],
            )
        cursor.execute(
            """
            UPDATE eas.request SET status='CANCELLED',lock_version=lock_version+1,
              updated_at=%s WHERE id=%s
            """,
            [now, request_id],
        )
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="REQUEST_CANCELLED",
            target_type="request",
            target_id=request_id,
            details={"previous_status": status, "reason": reason},
            correlation_id=correlation_id,
            occurred_at=now,
        )
        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
            VALUES (%s,'REQUEST_CANCELLED',%s,%s)
            """,
            [
                request_id,
                Jsonb({"request_id": request_id, "previous_status": status}),
                f"request:{request_id}:cancelled:version:{lock_version + 1}",
            ],
        )
        return (
            {
                "request": {
                    "id": request_id,
                    "status": "CANCELLED",
                    "lock_version": lock_version + 1,
                }
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:cancel",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )
