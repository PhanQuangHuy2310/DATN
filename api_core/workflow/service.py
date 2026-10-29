from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.audit import canonical_sha256
from api_core.authn.models import Actor
from api_core.domain import (
    PayloadValidationError,
    resolve_route,
    validate_draft_payload,
    validate_payload,
)
from api_core.domain.routing import RoutingError
from api_core.workflow.constants import (
    ERR_REQUEST_NOT_FOUND,
    ERR_STATE_CONFLICT,
    ERR_VERSION_CONFLICT,
)

SQL_LOCK_SECURITY = "SELECT eas.lock_security(false)"
SQL_COMPLETE_WORKFLOW = (
    "UPDATE eas.workflow_instance SET state='COMPLETED',closed_at=%s WHERE id=%s"
)
SQL_CLOSE_SLA_STAGE = (
    "UPDATE eas.sla_stage SET closed_at=%s WHERE request_id=%s AND closed_at IS NULL"
)
SQL_INSERT_OUTBOX_EVENT = """
            INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
            VALUES (%s,%s,%s,%s)
            """
HTML_TAG = re.compile(r"<[^>]+>")


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


def _is_actor_valid_for_role(
    cursor,
    *,
    actor_id: str,
    role: str,
    department_id: str,
    type_id: str,
) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM eas.app_user u
          JOIN eas.role_membership rm ON rm.user_id = u.id
          WHERE u.id = %s AND u.is_active
            AND rm.role = %s AND rm.revoked_at IS NULL
            AND rm.valid_from <= statement_timestamp()
            AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
            AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = %s)
            AND (rm.type_scope = 'ALL' OR rm.type_id = %s)
        )
        """,
        [actor_id, role, department_id, type_id],
    )
    return bool(cursor.fetchone()[0])


def _append_request_audit(
    cursor,
    *,
    request_id: str,
    actor_id: str | None,
    actor_kind: str = "HUMAN",
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any],
    correlation_id: str,
    occurred_at: datetime | None = None,
) -> None:
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)
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
        "actor_kind": actor_kind,
        "correlation_id": correlation_id,
        "details": details,
        "hash_version": 1,
        "id": event_id,
        "occurred_at": _utc_text(occurred_at),
        "prev_hash": previous_hash,
        "request_id": request_id,
        "scope_key": scope_key,
        "seq": str(sequence),
        "target_id": str(target_id),
        "target_type": target_type,
    }
    digest = canonical_sha256(event)
    cursor.execute(
        """
        INSERT INTO eas.audit_event(
          id,request_id,seq,actor_id,actor_kind,action,target_type,target_id,
          details,correlation_id,occurred_at,hash_version,prev_hash,hash
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s)
        """,
        [
            event_id,
            request_id,
            sequence,
            actor_id,
            actor_kind,
            action,
            target_type,
            str(target_id),
            Jsonb(details),
            correlation_id,
            occurred_at,
            previous_hash,
            digest,
        ],
    )


def _append_admin_audit(
    cursor,
    *,
    actor_id: str | None,
    actor_kind: str = "HUMAN",
    action: str,
    target_type: str,
    target_id: str,
    department_id: str | None = None,
    type_id: str | None = None,
    details: dict[str, Any],
    reason: str,
    correlation_id: str,
    occurred_at: datetime | None = None,
) -> str:
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)
    scope_key = "ADMIN"
    cursor.execute("SELECT seq, last_hash FROM eas.lock_audit_head(%s)", [scope_key])
    head = cursor.fetchone()
    if not head:
        raise CommandError("AUDIT_HEAD_MISSING", status=500)
    sequence = head[0] + 1
    previous_hash = head[1]
    event_id = str(uuid4())
    event = {
        "action": action,
        "actor_id": actor_id,
        "actor_kind": actor_kind,
        "correlation_id": correlation_id,
        "department_id": department_id,
        "details": details,
        "hash_version": 1,
        "id": event_id,
        "occurred_at": _utc_text(occurred_at),
        "prev_hash": previous_hash,
        "reason": reason,
        "scope_key": scope_key,
        "seq": str(sequence),
        "target_id": str(target_id),
        "target_type": target_type,
        "type_id": type_id,
    }
    digest = canonical_sha256(event)
    cursor.execute(
        """
        INSERT INTO eas.admin_event(
          id, seq, actor_id, actor_kind, action, target_type, target_id,
          department_id, type_id, details, reason, correlation_id, occurred_at,
          hash_version, prev_hash, hash
        ) VALUES (
          %s, %s, %s, %s, %s, %s, %s,
          %s, %s, %s, %s, %s, %s,
          1, %s, %s
        )
        """,
        [
            event_id,
            sequence,
            actor_id,
            actor_kind,
            action,
            target_type,
            str(target_id),
            department_id,
            type_id,
            Jsonb(details),
            reason,
            correlation_id,
            occurred_at,
            previous_hash,
            digest,
        ],
    )
    return event_id


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
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"{actor_id}:{scope}:{key}"],
        )
        cursor.execute(
            """
            SELECT request_hash, http_status, response_body,
                   expires_at > statement_timestamp() AS not_expired,
                   tombstone_until > statement_timestamp() AS in_tombstone,
                   request_id::text
            FROM eas.idempotency_record
            WHERE actor_id = %s AND command_scope = %s AND key = %s
            FOR UPDATE
            """,
            [actor_id, scope, key],
        )
        existing = cursor.fetchone()
        if existing:
            (
                saved_hash,
                http_status,
                response_body,
                not_expired,
                _in_tombstone,
                existing_request_id,
            ) = existing
            if saved_hash != request_hash:
                raise CommandError("IDEMPOTENCY_KEY_REUSED", status=409)
            if not not_expired or response_body is None:
                raise CommandError("IDEMPOTENCY_RESULT_EXPIRED", status=410)
            if existing_request_id is not None:
                cursor.execute(
                    """
                    SELECT r.status, r.requester_id::text,
                           EXISTS (
                             SELECT 1 FROM eas.request_participant p
                             WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                           ),
                           EXISTS (
                             SELECT 1 FROM eas.app_user u WHERE u.id = %s AND u.is_active
                           )
                    FROM eas.request r
                    WHERE r.id = %s
                    """,
                    [actor_id, actor_id, existing_request_id],
                )
                r_row = cursor.fetchone()
                if not r_row:
                    raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
                r_status, r_requester_id, is_active_participant, is_user_active = r_row
                if not is_user_active:
                    raise CommandError("FORBIDDEN", status=403)
                can_read = (r_requester_id == actor_id) or (
                    is_active_participant and r_status != "DRAFT"
                )
                if not can_read:
                    raise CommandError("FORBIDDEN", status=403)
            return CommandResult(response_body, http_status, replayed=True)

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


def _validate_create_draft_input(
    body: dict[str, Any],
) -> tuple[str, str | None, str | None]:
    allowed_fields = {"type_code", "title", "origin_request_id"}
    if set(body) - allowed_fields or not isinstance(body.get("type_code"), str):
        raise CommandError("INVALID_DRAFT_REQUEST")
    type_code = body["type_code"]

    origin_request_id = body.get("origin_request_id")
    if origin_request_id is not None:
        origin_request_id = _canonical_uuid(
            origin_request_id, "ORIGIN_REQUEST_NOT_FOUND"
        )

    title = body.get("title")
    clean_title = None
    if title is not None:
        if not isinstance(title, str):
            raise CommandError("INVALID_DRAFT_REQUEST")
        clean_title = unicodedata.normalize("NFC", title).strip()
        if not (5 <= len(clean_title) <= 150) or HTML_TAG.search(
            html.unescape(clean_title)
        ):
            raise CommandError("INVALID_DRAFT_REQUEST")

    return type_code, origin_request_id, clean_title


def create_draft(
    *,
    actor: Actor,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    type_code, origin_request_id, clean_title = _validate_create_draft_input(body)

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute(SQL_LOCK_SECURITY)
        if origin_request_id:
            cursor.execute(
                "SELECT 1 FROM eas.request WHERE id = %s AND requester_id = %s",
                [origin_request_id, actor.id],
            )
            if not cursor.fetchone():
                raise CommandError("ORIGIN_REQUEST_NOT_FOUND", status=404)

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
        draft_payload = {"title": clean_title} if clean_title else None
        cursor.execute(
            """
            INSERT INTO eas.request(id,requester_id,type_id,draft_release_id,draft_payload,origin_request_id)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING code
            """,
            [
                request_id,
                actor.id,
                type_id,
                release_id,
                Jsonb(draft_payload) if draft_payload else None,
                origin_request_id,
            ],
        )
        code = cursor.fetchone()[0]
        audit_details: dict[str, Any] = {
            "type_code": type_code,
            "release_id": release_id,
        }
        if clean_title:
            audit_details["title"] = clean_title
        if origin_request_id:
            audit_details["origin_request_id"] = origin_request_id
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="DRAFT_CREATED",
            target_type="request",
            target_id=request_id,
            details=audit_details,
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


def _validate_update_draft_input(
    body: dict[str, Any],
) -> tuple[int, dict[str, Any] | None, int | None, str | None, list[str] | None]:
    allowed_fields = {
        "expected_version",
        "payload",
        "amount_vnd",
        "viewed_release_id",
        "attachment_ids",
    }
    forbidden_fields = {"owner_id", "requester_id", "status", "lock_version"}
    if any(k in body for k in forbidden_fields) or (set(body) - allowed_fields):
        raise CommandError("UNKNOWN_FIELD", status=422)

    expected_version = body.get("expected_version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        raise CommandError("EXPECTED_VERSION_REQUIRED")

    payload = body.get("payload")
    if payload is not None:
        if not isinstance(payload, dict):
            raise CommandError("INVALID_PAYLOAD", status=422)
        if any(k in payload for k in forbidden_fields):
            raise CommandError("UNKNOWN_FIELD", status=422)

    amount_vnd = body.get("amount_vnd")
    if amount_vnd is not None and (
        isinstance(amount_vnd, bool)
        or not isinstance(amount_vnd, int)
        or amount_vnd <= 0
    ):
        raise CommandError("INVALID_AMOUNT", status=422)

    viewed_release_id = body.get("viewed_release_id")
    if viewed_release_id is not None:
        viewed_release_id = _canonical_uuid(viewed_release_id, "INVALID_RELEASE_ID")

    attachment_ids = body.get("attachment_ids")
    if attachment_ids is not None:
        if (
            not isinstance(attachment_ids, list)
            or len(attachment_ids) > 5
            or len(set(map(str, attachment_ids))) != len(attachment_ids)
        ):
            raise CommandError("INVALID_ATTACHMENTS", status=422)
        attachment_ids = [
            _canonical_uuid(item, "INVALID_ATTACHMENT_ID") for item in attachment_ids
        ]

    return expected_version, payload, amount_vnd, viewed_release_id, attachment_ids


def _sync_draft_attachments(
    cursor,
    request_id: str,
    actor_id: str,
    attachment_ids: list[str],
) -> None:
    for att_id in attachment_ids:
        cursor.execute(
            """
            SELECT 1 FROM eas.attachment
            WHERE id = %s AND request_id = %s AND uploader_id = %s
              AND scan_state = 'CLEAN' AND deleted_at IS NULL
            """,
            [att_id, request_id, actor_id],
        )
        if not cursor.fetchone():
            raise CommandError("ATTACHMENT_INVALID", status=422)
    cursor.execute(
        "DELETE FROM eas.draft_attachment WHERE request_id = %s",
        [request_id],
    )
    for att_id in attachment_ids:
        cursor.execute(
            """
            INSERT INTO eas.draft_attachment(request_id, attachment_id, added_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (request_id, attachment_id) DO NOTHING
            """,
            [request_id, att_id, actor_id],
        )


def _merge_and_validate_draft_payload(
    existing_draft_payload: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    type_code: str,
    form_schema: dict[str, Any],
    requester_id: str,
    actor_department_id: str | None = None,
) -> dict[str, Any]:
    merged_payload = dict(existing_draft_payload or {})
    if payload is not None:
        try:
            validated_patch = validate_draft_payload(
                type_code=type_code,
                payload=payload,
                form_schema=form_schema,
                requester_id=requester_id,
            )
        except PayloadValidationError as exc:
            raise CommandError(
                "VALIDATION_FAILED", status=422, fields=exc.errors
            ) from exc
        if (
            actor_department_id is not None
            and validated_patch.get("department_id") is not None
            and validated_patch["department_id"] != actor_department_id
        ):
            raise CommandError("DEPARTMENT_SCOPE_VIOLATION", status=403)
        merged_payload.update(validated_patch)
    return merged_payload


def update_draft(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    (
        expected_version,
        payload,
        amount_vnd,
        viewed_release_id,
        attachment_ids,
    ) = _validate_update_draft_input(body)

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT r.status, r.lock_version, r.type_id::text, rt.code,
                   r.draft_payload, r.draft_amount_vnd, r.draft_release_id::text,
                   rt.active_release_id::text, cr.form_schema
            FROM eas.request r
            JOIN eas.request_type rt ON rt.id = r.type_id
            JOIN eas.config_release cr ON cr.id = rt.active_release_id
            WHERE r.id = %s AND r.requester_id = %s
            FOR UPDATE OF r
            """,
            [request_id, actor.id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
        (
            status,
            lock_version,
            type_id,
            type_code,
            existing_draft_payload,
            existing_amount_vnd,
            _draft_release_id,
            active_release_id,
            form_schema,
        ) = row

        if status not in {"DRAFT", "NEEDS_INFO"}:
            raise CommandError(ERR_STATE_CONFLICT, status=409)
        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)

        _authorize(
            cursor,
            actor_id=actor.id,
            role="REQUESTER",
            department_id=actor.department_id,
            type_id=type_id,
        )

        effective_release_id = viewed_release_id or active_release_id
        merged_payload = _merge_and_validate_draft_payload(
            existing_draft_payload,
            payload,
            type_code,
            form_schema,
            actor.id,
            actor.department_id,
        )

        final_amount_vnd = amount_vnd if amount_vnd is not None else existing_amount_vnd
        if type_code in {"LEAVE", "ACCESS"} and final_amount_vnd is not None:
            raise CommandError("AMOUNT_NOT_ALLOWED", status=422)

        if attachment_ids is not None:
            _sync_draft_attachments(cursor, request_id, actor.id, attachment_ids)

        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            UPDATE eas.request
            SET draft_payload = %s, draft_amount_vnd = %s, draft_release_id = %s,
                lock_version = lock_version + 1, updated_at = %s
            WHERE id = %s
            """,
            [
                Jsonb(merged_payload),
                final_amount_vnd,
                effective_release_id,
                now,
                request_id,
            ],
        )

        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action="DRAFT_UPDATED",
            target_type="request",
            target_id=request_id,
            details={"lock_version": lock_version + 1},
            correlation_id=correlation_id,
            occurred_at=now,
        )

        return (
            {
                "request": {
                    "id": request_id,
                    "status": status,
                    "lock_version": lock_version + 1,
                }
            },
            200,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:draft:update",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def _validate_execution_issue_input(
    body: dict[str, Any],
) -> tuple[int, str, str, str | None]:
    allowed_fields = {"expected_version", "kind", "reason", "attempt_id"}
    if set(body) - allowed_fields:
        raise CommandError("UNKNOWN_FIELD", status=422)

    expected_version = body.get("expected_version")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")

    kind = body.get("kind")
    if kind not in {"UNABLE_TO_CLAIM", "BLOCKED"}:
        raise CommandError("INVALID_ISSUE_KIND", status=422)

    reason = body.get("reason")
    if not isinstance(reason, str):
        raise CommandError("ISSUE_REASON_INVALID", status=422)
    clean_reason = unicodedata.normalize("NFC", reason).strip()
    if not (10 <= len(clean_reason) <= 2000) or HTML_TAG.search(
        html.unescape(clean_reason)
    ):
        raise CommandError("ISSUE_REASON_INVALID", status=422)

    attempt_id = body.get("attempt_id")
    if attempt_id is not None:
        attempt_id = _canonical_uuid(attempt_id, "INVALID_ATTEMPT_ID")

    return expected_version, kind, clean_reason, attempt_id


def _validate_execution_issue_state(kind: str, status: str, attempt_state: str) -> None:
    if kind == "UNABLE_TO_CLAIM":
        if status != "READY_FOR_EXECUTION" or attempt_state != "READY":
            raise CommandError(ERR_STATE_CONFLICT, status=409)
    elif kind == "BLOCKED" and (status != "IN_PROGRESS" or attempt_state != "RUNNING"):
        raise CommandError(ERR_STATE_CONFLICT, status=409)


def report_execution_issue(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    (
        expected_version,
        kind,
        clean_reason,
        attempt_id,
    ) = _validate_execution_issue_input(body)

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT r.status, r.lock_version, r.type_id::text, v.department_id::text,
                   i.id::text, a.id::text, a.executor_id::text, a.state
            FROM eas.request r
            JOIN eas.request_revision v ON v.id = r.current_revision_id
            JOIN eas.workflow_instance i ON i.revision_id = v.id AND i.state = 'ACTIVE'
            JOIN eas.execution_attempt a ON a.instance_id = i.id
              AND (%s::uuid IS NULL AND a.state IN ('READY', 'RUNNING') OR a.id = %s::uuid)
            WHERE r.id = %s
            ORDER BY a.attempt_no DESC LIMIT 1
            FOR UPDATE OF r, i, a
            """,
            [attempt_id, attempt_id, request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
        (
            status,
            lock_version,
            type_id,
            department_id,
            _instance_id,
            matched_attempt_id,
            executor_id,
            attempt_state,
        ) = row

        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)

        if executor_id != actor.id:
            raise CommandError("FORBIDDEN", status=403)

        _authorize(
            cursor,
            actor_id=actor.id,
            role="EXECUTOR",
            department_id=department_id,
            type_id=type_id,
        )

        _validate_execution_issue_state(kind, status, attempt_state)

        issue_id = str(uuid4())
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO eas.execution_issue(id, request_id, attempt_id, actor_id, kind, reason, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                issue_id,
                request_id,
                matched_attempt_id,
                actor.id,
                kind,
                clean_reason,
                now,
            ],
        )

        cursor.execute(
            """
            UPDATE eas.request
            SET lock_version = lock_version + 1, updated_at = %s
            WHERE id = %s
            """,
            [now, request_id],
        )

        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action=f"EXECUTION_ISSUE_{kind}",
            target_type="execution_attempt",
            target_id=matched_attempt_id,
            details={"issue_id": issue_id, "kind": kind, "reason": clean_reason},
            correlation_id=correlation_id,
            occurred_at=now,
        )

        cursor.execute(
            """
            INSERT INTO eas.outbox_event(request_id, event_type, payload, dedupe_key)
            VALUES (%s, %s, %s, %s)
            """,
            [
                request_id,
                f"EXECUTION_{kind}",
                Jsonb(
                    {
                        "request_id": request_id,
                        "issue_id": issue_id,
                        "attempt_id": matched_attempt_id,
                    }
                ),
                f"issue:{issue_id}",
            ],
        )

        return (
            {
                "issue": {
                    "id": issue_id,
                    "kind": kind,
                    "attempt_id": matched_attempt_id,
                },
                "request": {
                    "id": request_id,
                    "status": status,
                    "lock_version": lock_version + 1,
                },
            },
            201,
            request_id,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"request:{request_id}:issue:{kind.lower()}",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def _validate_submit_input(
    body: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None, int, str | None, list[str] | None]:
    allowed_fields = {
        "type_code",
        "payload",
        "attachment_ids",
        "request_id",
        "expected_version",
        "viewed_release_id",
    }
    if set(body) - allowed_fields:
        raise CommandError("UNKNOWN_FIELD")
    type_code = body.get("type_code")
    payload = body.get("payload")
    existing_request_id = body.get("request_id")
    expected_version = body.get("expected_version", 0)
    viewed_release_id = body.get("viewed_release_id")
    if not isinstance(type_code, str) or not isinstance(payload, dict):
        raise CommandError("INVALID_SUBMISSION")

    if "attachment_ids" in body:
        attachment_ids_input = body["attachment_ids"]
        if (
            not isinstance(attachment_ids_input, list)
            or len(attachment_ids_input) > 5
            or len(set(map(str, attachment_ids_input))) != len(attachment_ids_input)
        ):
            raise CommandError("INVALID_ATTACHMENTS")
        attachment_ids = [
            _canonical_uuid(item, "INVALID_ATTACHMENT_ID")
            for item in attachment_ids_input
        ]
    else:
        attachment_ids = None

    if viewed_release_id is not None:
        viewed_release_id = _canonical_uuid(viewed_release_id, "INVALID_RELEASE_ID")

    if existing_request_id is not None:
        existing_request_id = _canonical_uuid(existing_request_id, "INVALID_REQUEST_ID")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise CommandError("EXPECTED_VERSION_REQUIRED")

    return (
        type_code,
        payload,
        existing_request_id,
        expected_version,
        viewed_release_id,
        attachment_ids,
    )


def _fetch_submit_config(
    cursor, type_code: str, viewed_release_id: str | None
) -> tuple[
    str, str, str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
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

    if viewed_release_id is not None and viewed_release_id != release_id:
        raise CommandError("CONFIG_CHANGED", status=409)

    return type_id, lifecycle, release_id, form, rules, bindings, sla


def _resolve_and_verify_route_actors(
    cursor,
    rules: dict[str, Any],
    bindings: dict[str, Any],
    actor: Actor,
    manager_id: str | None,
    type_id: str,
    normalized: dict[str, Any],
    amount: int | None,
):
    try:
        decision = resolve_route(
            route_rules=rules,
            actor_bindings=bindings,
            department_id=actor.department_id,
            requester_id=actor.id,
            manager_id=manager_id,
            amount_vnd=amount,
            payload=normalized,
        )
    except RoutingError as exc:
        # Unresolved role bindings are a configuration conflict, not a 500.
        # No draft is submitted or workflow instance created.
        raise CommandError("ROUTE_CONFIGURATION_INVALID", status=409) from exc
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
    return decision


def _resolve_submit_attachments(
    cursor,
    existing_request_id: str | None,
    attachment_ids: list[str] | None,
    type_code: str,
    form: dict[str, Any],
) -> list[str]:
    resolved = attachment_ids
    if resolved is None:
        if existing_request_id:
            cursor.execute(
                """
                SELECT a.id::text FROM eas.draft_attachment da
                JOIN eas.attachment a ON a.id = da.attachment_id AND a.request_id = da.request_id
                WHERE da.request_id = %s AND a.scan_state = 'CLEAN' AND a.deleted_at IS NULL
                ORDER BY a.created_at
                """,
                [existing_request_id],
            )
            resolved = [row[0] for row in cursor.fetchall()]
        else:
            resolved = []

    # A type's evidence requirements are determined by its published form,
    # not by lifecycle C alone (e.g. onboarding can be C without a quote).
    # The P0 EQUIPMENT quotation obligation remains unchanged.
    evidence_fields = [
        name
        for name in form.get("required", [])
        if isinstance(name, str)
        and re.search(
            r"(?:_file|_files|_pdf|_doc|_images|photo_evidence|board_resolution|handover_doc)$",
            name,
        )
    ]
    if type_code == "EQUIPMENT" and not resolved:
        raise CommandError("EQUIPMENT_QUOTE_REQUIRED")
    if evidence_fields and not resolved:
        raise CommandError("ATTACHMENT_REQUIRED", status=422)
    return resolved


def _upsert_submission_request(
    cursor,
    actor: Actor,
    existing_request_id: str | None,
    expected_version: int,
    type_id: str,
    normalized: dict[str, Any],
    amount: int | None,
    release_id: str,
) -> tuple[str, str, int]:
    if existing_request_id:
        request_id = existing_request_id
        cursor.execute(
            """
            SELECT code,status,lock_version,type_id::text
            FROM eas.request WHERE id=%s AND requester_id=%s FOR UPDATE
            """,
            [request_id, actor.id],
        )
        draft = cursor.fetchone()
        if not draft:
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
        request_code, draft_status, draft_version, draft_type_id = draft
        if draft_status not in {"DRAFT", "NEEDS_INFO"}:
            raise CommandError(ERR_STATE_CONFLICT, status=409)
        if draft_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)
        if draft_type_id != type_id:
            raise CommandError("REQUEST_TYPE_CONFLICT", status=409)
        return request_id, request_code, draft_version

    if expected_version != 0:
        raise CommandError(ERR_VERSION_CONFLICT, status=409)
    request_id = str(uuid4())
    cursor.execute(
        """
        INSERT INTO eas.request(
          id,requester_id,type_id,draft_payload,draft_amount_vnd,draft_release_id
        ) VALUES (%s,%s,%s,%s,%s,%s) RETURNING code
        """,
        [request_id, actor.id, type_id, Jsonb(normalized), amount, release_id],
    )
    request_code = cursor.fetchone()[0]
    return request_id, request_code, 0


def _link_revision_attachments(
    cursor,
    revision_id: str,
    request_id: str,
    actor_id: str,
    resolved_attachments: list[str],
) -> None:
    for attachment_id in resolved_attachments:
        cursor.execute(
            """
            INSERT INTO eas.revision_attachment(revision_id,attachment_id,request_id)
            SELECT %s,a.id,%s FROM eas.attachment a
            WHERE a.id=%s AND a.request_id=%s AND a.uploader_id=%s
              AND a.scan_state='CLEAN' AND a.deleted_at IS NULL
            """,
            [revision_id, request_id, attachment_id, request_id, actor_id],
        )
        if cursor.rowcount != 1:
            raise CommandError("ATTACHMENT_NOT_READY", status=409)
        cursor.execute(
            "DELETE FROM eas.draft_attachment WHERE request_id=%s AND attachment_id=%s",
            [request_id, attachment_id],
        )


def _create_submission_workflow(
    cursor,
    request_id: str,
    revision_id: str,
    decision,
    lifecycle: str,
    actor_id: str,
    sla: dict[str, Any],
    now: datetime,
) -> str:
    instance_id = str(uuid4())
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
    participants: list[tuple[str, str]] = [(actor_id, "REQUESTER")]
    participants.extend((item, "APPROVER") for item in decision.approver_ids)
    if decision.executor_id:
        participants.append((decision.executor_id, "EXECUTOR"))
    if decision.acceptor_id:
        participants.append((decision.acceptor_id, "ACCEPTOR"))
    seen_users: set[str] = set()
    unique_participants: list[tuple[str, str]] = []
    for user_id, joined_as in participants:
        if user_id not in seen_users:
            seen_users.add(user_id)
            unique_participants.append((user_id, joined_as))
    for user_id, joined_as in unique_participants:
        cursor.execute(
            """
            INSERT INTO eas.request_participant(request_id,user_id,joined_as)
            VALUES (%s,%s,%s)
            ON CONFLICT (request_id, user_id) DO NOTHING
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
    return first_step_id


def submit_request(
    *,
    actor: Actor,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    (
        type_code,
        payload,
        existing_request_id,
        expected_version,
        viewed_release_id,
        attachment_ids,
    ) = _validate_submit_input(body)

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute(SQL_LOCK_SECURITY)
        (
            type_id,
            lifecycle,
            release_id,
            form,
            rules,
            bindings,
            sla,
        ) = _fetch_submit_config(cursor, type_code, viewed_release_id)

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
        # Department is derived from the current authenticated session.  A forged
        # cross-department field must never influence assignment or reporting.
        if normalized.get("department_id") is not None and normalized["department_id"] != actor.department_id:
            raise CommandError("DEPARTMENT_SCOPE_VIOLATION", status=403)
        amount = normalized.get("amount_vnd")
        decision = _resolve_and_verify_route_actors(
            cursor=cursor,
            rules=rules,
            bindings=bindings,
            actor=actor,
            manager_id=user[0],
            type_id=type_id,
            normalized=normalized,
            amount=amount,
        )

        resolved_attachments = _resolve_submit_attachments(
            cursor, existing_request_id, attachment_ids, type_code, form
        )

        now = datetime.now(timezone.utc)
        request_id, request_code, draft_version = _upsert_submission_request(
            cursor=cursor,
            actor=actor,
            existing_request_id=existing_request_id,
            expected_version=expected_version,
            type_id=type_id,
            normalized=normalized,
            amount=amount,
            release_id=release_id,
        )

        cursor.execute(
            "SELECT coalesce(max(revision_no),0)+1 FROM eas.request_revision WHERE request_id=%s",
            [request_id],
        )
        revision_no = cursor.fetchone()[0]
        revision_id = str(uuid4())
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
        _link_revision_attachments(
            cursor, revision_id, request_id, actor.id, resolved_attachments
        )
        first_step_id = _create_submission_workflow(
            cursor=cursor,
            request_id=request_id,
            revision_id=revision_id,
            decision=decision,
            lifecycle=lifecycle,
            actor_id=actor.id,
            sla=sla,
            now=now,
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


def _validate_approval_decision_input(
    body: dict[str, Any],
) -> tuple[str, str | None, int]:
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
    return outcome, reason, expected_version


def _handle_approval_approved(
    cursor,
    request_id: str,
    instance_id: str,
    department_id: str,
    type_id: str,
    lifecycle: str,
    executor_id: str | None,
    acceptor_id: str | None,
    sla: dict[str, Any],
    now: datetime,
) -> tuple[str, datetime | None, datetime | None, str | None]:
    cursor.execute(
        """
        SELECT id::text, assignee_id::text FROM eas.approval_step
        WHERE instance_id=%s AND state='WAITING'
        ORDER BY step_no LIMIT 1 FOR UPDATE
        """,
        [instance_id],
    )
    next_step = cursor.fetchone()
    if next_step:
        next_step_id, next_assignee_id = next_step
        if not _is_actor_valid_for_role(
            cursor,
            actor_id=next_assignee_id,
            role="APPROVER",
            department_id=department_id,
            type_id=type_id,
        ):
            raise CommandError("ASSIGNEE_UNAVAILABLE", status=409)
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
        return "PENDING_APPROVAL", None, None, next_step_id

    if lifecycle in {"B", "C"}:
        if not _is_actor_valid_for_role(
            cursor,
            actor_id=executor_id,
            role="EXECUTOR",
            department_id=department_id,
            type_id=type_id,
        ):
            raise CommandError("ASSIGNEE_UNAVAILABLE", status=409)
        if lifecycle == "C" and (
            not _is_actor_valid_for_role(
                cursor,
                actor_id=acceptor_id,
                role="ACCEPTOR",
                department_id=department_id,
                type_id=type_id,
            )
            or acceptor_id == executor_id
        ):
            raise CommandError("ASSIGNEE_UNAVAILABLE", status=409)

    approved_at = now
    if lifecycle == "A":
        cursor.execute(
            SQL_COMPLETE_WORKFLOW,
            [now, instance_id],
        )
        return "COMPLETED", approved_at, now, None

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
    return "READY_FOR_EXECUTION", approved_at, None, None


def _handle_approval_rejected_or_needs_info(
    cursor,
    request_id: str,
    instance_id: str,
    outcome: str,
    now: datetime,
) -> str:
    if outcome == "NEEDS_INFO":
        cursor.execute(
            """
            INSERT INTO eas.draft_attachment(request_id, attachment_id, added_by)
            SELECT r.id, ra.attachment_id, r.requester_id
            FROM eas.request r
            JOIN eas.revision_attachment ra ON ra.revision_id = r.current_revision_id AND ra.request_id = r.id
            JOIN eas.attachment a ON a.id = ra.attachment_id AND a.request_id = r.id
            WHERE r.id = %s AND a.scan_state = 'CLEAN' AND a.deleted_at IS NULL
            ON CONFLICT (request_id, attachment_id) DO NOTHING
            """,
            [request_id],
        )
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
    return next_status


def decide_approval(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    outcome, reason, expected_version = _validate_approval_decision_input(body)

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT r.status,r.lock_version,r.type_id::text,v.department_id::text,
                   i.id::text,i.lifecycle,i.planned_executor_id::text,i.acceptor_id::text,
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
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
        (
            status,
            lock_version,
            type_id,
            department_id,
            instance_id,
            lifecycle,
            executor_id,
            acceptor_id,
            sla,
        ) = current
        if status != "PENDING_APPROVAL":
            raise CommandError(ERR_STATE_CONFLICT, status=409)
        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)
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
            SQL_CLOSE_SLA_STAGE,
            [now, request_id],
        )

        if outcome == "APPROVE":
            (
                next_status,
                approved_at,
                completed_at,
                next_step_id,
            ) = _handle_approval_approved(
                cursor=cursor,
                request_id=request_id,
                instance_id=instance_id,
                department_id=department_id,
                type_id=type_id,
                lifecycle=lifecycle,
                executor_id=executor_id,
                acceptor_id=acceptor_id,
                sla=sla,
                now=now,
            )
        else:
            next_status = _handle_approval_rejected_or_needs_info(
                cursor, request_id, instance_id, outcome, now
            )
            approved_at = None
            completed_at = None
            next_step_id = None

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
            SQL_INSERT_OUTBOX_EVENT,
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
        cursor.execute(SQL_LOCK_SECURITY)
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
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
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
            raise CommandError(ERR_STATE_CONFLICT, status=409)
        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)
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


def _validate_execution_submission_input(
    body: dict[str, Any],
) -> tuple[int, str, str]:
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
    return expected_version, result_note.strip(), external_reference.strip()


def _apply_execution_submission(
    cursor,
    lifecycle: str,
    attempt_id: str,
    instance_id: str,
    request_id: str,
    result_note: str,
    external_reference: str,
    sla: dict[str, Any],
    now: datetime,
) -> tuple[str, datetime | None]:
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
            SQL_COMPLETE_WORKFLOW,
            [now, instance_id],
        )
        return "COMPLETED", now
    elif lifecycle == "C":
        cursor.execute(
            """
            UPDATE eas.execution_attempt SET state='SUBMITTED',result_note=%s,
              external_reference=%s,submitted_at=%s WHERE id=%s
            """,
            [result_note, external_reference, now, attempt_id],
        )
        cursor.execute(
            SQL_CLOSE_SLA_STAGE,
            [now, request_id],
        )
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
        return "WAITING_FOR_ACCEPTANCE", None
    else:
        raise CommandError("LIFECYCLE_CONFLICT", status=409)


def submit_execution(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    (
        expected_version,
        result_note,
        external_reference,
    ) = _validate_execution_submission_input(body)

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute(
            """
            SELECT r.status,r.lock_version,r.type_id::text,v.department_id::text,
                   i.id::text,i.lifecycle,a.id::text,a.executor_id::text,a.state,
                   cr.sla_profile,i.acceptor_id::text
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
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
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
            acceptor_id,
        ) = row
        if status != "IN_PROGRESS" or attempt_state != "RUNNING":
            raise CommandError(ERR_STATE_CONFLICT, status=409)
        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)
        if executor_id != actor.id:
            raise CommandError("FORBIDDEN", status=403)
        _authorize(
            cursor,
            actor_id=actor.id,
            role="EXECUTOR",
            department_id=department_id,
            type_id=type_id,
        )
        if lifecycle == "C" and (
            not _is_actor_valid_for_role(
                cursor,
                actor_id=acceptor_id,
                role="ACCEPTOR",
                department_id=department_id,
                type_id=type_id,
            )
            or acceptor_id == actor.id
        ):
            raise CommandError("ASSIGNEE_UNAVAILABLE", status=409)
        cursor.execute(
            "SELECT count(*) FROM eas.execution_attachment WHERE attempt_id=%s",
            [attempt_id],
        )
        if not 1 <= cursor.fetchone()[0] <= 5:
            raise CommandError("EXECUTION_EVIDENCE_REQUIRED", status=409)
        now = datetime.now(timezone.utc)
        next_status, completed_at = _apply_execution_submission(
            cursor=cursor,
            lifecycle=lifecycle,
            attempt_id=attempt_id,
            instance_id=instance_id,
            request_id=request_id,
            result_note=result_note,
            external_reference=external_reference,
            sla=sla,
            now=now,
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
            SQL_INSERT_OUTBOX_EVENT,
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


def _validate_acceptance_input(
    body: dict[str, Any],
) -> tuple[str, str | None, int]:
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
    return outcome, reason, expected_version


def _apply_acceptance_decision(
    cursor,
    outcome: str,
    instance_id: str,
    request_id: str,
    attempt_no: int,
    planned_executor_id: str,
    department_id: str,
    type_id: str,
    sla: dict[str, Any],
    now: datetime,
) -> tuple[str, datetime | None, str | None]:
    if outcome == "ACCEPT":
        cursor.execute(
            SQL_COMPLETE_WORKFLOW,
            [now, instance_id],
        )
        return "COMPLETED", now, None

    if not _is_actor_valid_for_role(
        cursor,
        actor_id=planned_executor_id,
        role="EXECUTOR",
        department_id=department_id,
        type_id=type_id,
    ):
        raise CommandError("ASSIGNEE_UNAVAILABLE", status=409)

    next_attempt_id = str(uuid4())
    cursor.execute(
        """
        INSERT INTO eas.execution_attempt(
          id,request_id,instance_id,attempt_no,executor_id
        ) VALUES (%s,%s,%s,%s,%s)
        """,
        [
            next_attempt_id,
            request_id,
            instance_id,
            attempt_no + 1,
            planned_executor_id,
        ],
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
    return "READY_FOR_EXECUTION", None, next_attempt_id


def decide_acceptance(
    *,
    actor: Actor,
    request_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    request_id = _canonical_uuid(request_id, "INVALID_REQUEST_ID")
    outcome, reason, expected_version = _validate_acceptance_input(body)

    def operation(cursor) -> tuple[dict[str, Any], int, str]:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT r.status,r.lock_version,r.type_id::text,v.department_id::text,
                   i.id::text,i.acceptor_id::text,a.id::text,a.executor_id::text,
                   a.attempt_no,cr.sla_profile,i.planned_executor_id::text
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
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
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
            planned_executor_id,
        ) = row
        if status != "WAITING_FOR_ACCEPTANCE":
            raise CommandError(ERR_STATE_CONFLICT, status=409)
        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)
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
            SQL_CLOSE_SLA_STAGE,
            [now, request_id],
        )
        next_status, completed_at, next_attempt_id = _apply_acceptance_decision(
            cursor=cursor,
            outcome=outcome,
            instance_id=instance_id,
            request_id=request_id,
            attempt_no=attempt_no,
            planned_executor_id=planned_executor_id,
            department_id=department_id,
            type_id=type_id,
            sla=sla,
            now=now,
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
            SQL_INSERT_OUTBOX_EVENT,
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
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT status,lock_version,requester_id::text,current_revision_id::text
            FROM eas.request WHERE id=%s FOR UPDATE
            """,
            [request_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
        status, lock_version, requester_id, revision_id = row
        if requester_id != actor.id:
            raise CommandError("FORBIDDEN", status=403)
        if status not in {"DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"}:
            raise CommandError(ERR_STATE_CONFLICT, status=409)
        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)
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
                SQL_CLOSE_SLA_STAGE,
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
