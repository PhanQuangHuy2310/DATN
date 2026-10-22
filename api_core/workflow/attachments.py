from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.authn.models import Actor
from api_core.storage import (
    StorageError,
    delete_private_object,
    get_private_object,
    put_private_object,
    scan_with_clamav,
    sniff_allowed_mime,
)

from .service import CommandError, _append_request_audit, _authorize


def register_attachment(
    *,
    actor: Actor,
    request_id: str,
    original_name: str,
    data: bytes,
    correlation_id: str,
) -> dict[str, object]:
    try:
        request_id = str(UUID(request_id))
    except (ValueError, TypeError, AttributeError):
        raise CommandError("INVALID_REQUEST_ID") from None
    if not data or len(data) > 10 * 1024 * 1024:
        raise CommandError("FILE_SIZE_INVALID")
    if (
        not original_name
        or len(original_name) > 150
        or PurePath(original_name).name != original_name
        or ".." in original_name
        or "/" in original_name
        or "\\" in original_name
    ):
        raise CommandError("FILE_NAME_INVALID")
    try:
        mime = sniff_allowed_mime(data)
        scan_with_clamav(data)
    except StorageError as exc:
        code = str(exc)
        status = 422 if code in {"FILE_TYPE_NOT_ALLOWED", "MALWARE_DETECTED"} else 503
        raise CommandError(code, status=status) from exc

    attachment_id = str(uuid4())
    digest = hashlib.sha256(data).hexdigest()
    extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[
        mime
    ]
    key = f"requests/{request_id}/{attachment_id}.{extension}"
    try:
        stored = put_private_object(key=key, data=data, mime=mime, sha256=digest)
    except StorageError as exc:
        raise CommandError(str(exc), status=503) from exc

    try:
        now = datetime.now(timezone.utc)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(false)")
            cursor.execute(
                """
                SELECT r.type_id::text,u.department_id::text
                FROM eas.request r JOIN eas.app_user u ON u.id=r.requester_id
                WHERE r.id=%s AND r.requester_id=%s
                  AND r.status IN ('DRAFT','NEEDS_INFO')
                FOR UPDATE OF r
                """,
                [request_id, actor.id],
            )
            owner = cursor.fetchone()
            if not owner:
                raise CommandError("REQUEST_NOT_FOUND", status=404)
            _authorize(
                cursor,
                actor_id=actor.id,
                role="REQUESTER",
                department_id=owner[1],
                type_id=owner[0],
            )
            cursor.execute(
                """
                INSERT INTO eas.attachment(
                  id,request_id,uploader_id,storage_key,object_version,original_name,
                  mime,size_bytes,sha256,scan_state,scan_attempts,scanned_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'CLEAN',1,%s)
                """,
                [
                    attachment_id,
                    request_id,
                    actor.id,
                    stored.key,
                    stored.version,
                    original_name,
                    mime,
                    len(data),
                    digest,
                    now,
                ],
            )
            cursor.execute(
                """
                INSERT INTO eas.draft_attachment(request_id,attachment_id,added_by)
                VALUES (%s,%s,%s)
                """,
                [request_id, attachment_id, actor.id],
            )
            _append_request_audit(
                cursor,
                request_id=request_id,
                actor_id=actor.id,
                action="ATTACHMENT_ADDED",
                target_type="attachment",
                target_id=attachment_id,
                details={"mime": mime, "size_bytes": len(data), "sha256": digest},
                correlation_id=correlation_id,
                occurred_at=now,
            )
            cursor.execute(
                """
                INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
                VALUES (%s,'ATTACHMENT_CLEAN',%s,%s)
                """,
                [
                    request_id,
                    Jsonb({"request_id": request_id, "attachment_id": attachment_id}),
                    f"attachment:{attachment_id}:clean",
                ],
            )
    except Exception:
        try:
            delete_private_object(key)
        except StorageError:
            pass
        raise
    return {
        "attachment": {
            "id": attachment_id,
            "original_name": original_name,
            "mime": mime,
            "size_bytes": len(data),
            "scan_state": "CLEAN",
        }
    }


def register_execution_evidence(
    *,
    actor: Actor,
    request_id: str,
    original_name: str,
    data: bytes,
    correlation_id: str,
) -> dict[str, object]:
    try:
        request_id = str(UUID(request_id))
    except (ValueError, TypeError, AttributeError):
        raise CommandError("INVALID_REQUEST_ID") from None
    if not data or len(data) > 10 * 1024 * 1024:
        raise CommandError("FILE_SIZE_INVALID")
    if (
        not original_name
        or len(original_name) > 150
        or PurePath(original_name).name != original_name
        or ".." in original_name
        or "/" in original_name
        or "\\" in original_name
    ):
        raise CommandError("FILE_NAME_INVALID")
    try:
        mime = sniff_allowed_mime(data)
        scan_with_clamav(data)
    except StorageError as exc:
        code = str(exc)
        status = 422 if code in {"FILE_TYPE_NOT_ALLOWED", "MALWARE_DETECTED"} else 503
        raise CommandError(code, status=status) from exc
    attachment_id = str(uuid4())
    digest = hashlib.sha256(data).hexdigest()
    extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[
        mime
    ]
    key = f"requests/{request_id}/execution/{attachment_id}.{extension}"
    try:
        stored = put_private_object(key=key, data=data, mime=mime, sha256=digest)
    except StorageError as exc:
        raise CommandError(str(exc), status=503) from exc
    try:
        now = datetime.now(timezone.utc)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(false)")
            cursor.execute(
                """
                SELECT r.type_id::text,v.department_id::text,a.id::text
                FROM eas.request r
                JOIN eas.request_revision v ON v.id=r.current_revision_id
                JOIN eas.workflow_instance i ON i.revision_id=v.id AND i.state='ACTIVE'
                JOIN eas.execution_attempt a ON a.instance_id=i.id AND a.state='RUNNING'
                WHERE r.id=%s AND r.status='IN_PROGRESS' AND a.executor_id=%s
                FOR UPDATE OF r,a
                """,
                [request_id, actor.id],
            )
            execution = cursor.fetchone()
            if not execution:
                raise CommandError("REQUEST_NOT_FOUND", status=404)
            type_id, department_id, attempt_id = execution
            _authorize(
                cursor,
                actor_id=actor.id,
                role="EXECUTOR",
                department_id=department_id,
                type_id=type_id,
            )
            cursor.execute(
                """
                INSERT INTO eas.attachment(
                  id,request_id,uploader_id,storage_key,object_version,original_name,
                  mime,size_bytes,sha256,scan_state,scan_attempts,scanned_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'CLEAN',1,%s)
                """,
                [
                    attachment_id,
                    request_id,
                    actor.id,
                    stored.key,
                    stored.version,
                    original_name,
                    mime,
                    len(data),
                    digest,
                    now,
                ],
            )
            cursor.execute(
                """
                INSERT INTO eas.execution_attachment(attempt_id,attachment_id,request_id)
                VALUES (%s,%s,%s)
                """,
                [attempt_id, attachment_id, request_id],
            )
            _append_request_audit(
                cursor,
                request_id=request_id,
                actor_id=actor.id,
                action="EXECUTION_EVIDENCE_ADDED",
                target_type="attachment",
                target_id=attachment_id,
                details={
                    "attempt_id": attempt_id,
                    "mime": mime,
                    "size_bytes": len(data),
                    "sha256": digest,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
    except Exception:
        try:
            delete_private_object(key)
        except StorageError:
            pass
        raise
    return {
        "attachment": {
            "id": attachment_id,
            "attempt_id": attempt_id,
            "original_name": original_name,
            "mime": mime,
            "size_bytes": len(data),
            "scan_state": "CLEAN",
        }
    }


def get_attachment_metadata(
    *,
    actor: Actor,
    attachment_id: str,
) -> dict[str, Any]:
    try:
        att_uuid = str(UUID(attachment_id))
    except (ValueError, TypeError, AttributeError):
        raise CommandError("NOT_FOUND", status=404) from None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT a.id::text, a.request_id::text, a.original_name, a.mime,
                   a.size_bytes, a.scan_state, a.created_at, a.scanned_at
            FROM eas.attachment a
            JOIN eas.request r ON r.id = a.request_id
            LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
            LEFT JOIN eas.app_user u ON u.id = r.requester_id
            WHERE a.id = %s AND a.deleted_at IS NULL
              AND (
                r.requester_id = %s
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.request_participant p
                    WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                  )
                )
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.role_membership rm
                    WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
                      AND rm.revoked_at IS NULL
                      AND rm.valid_from <= statement_timestamp()
                      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                      AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
                      AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
                  )
                )
              )
            """,
            [att_uuid, actor.id, actor.id, actor.id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("NOT_FOUND", status=404)

    return {
        "attachment": {
            "id": row[0],
            "request_id": row[1],
            "original_name": row[2],
            "mime": row[3],
            "size_bytes": row[4],
            "scan_state": row[5],
            "created_at": row[6].isoformat(),
            "scanned_at": row[7].isoformat() if row[7] else None,
        }
    }


def download_attachment(
    *,
    actor: Actor,
    attachment_id: str,
    correlation_id: str,
) -> tuple[bytes, str, str]:
    try:
        att_uuid = str(UUID(attachment_id))
    except (ValueError, TypeError, AttributeError):
        raise CommandError("NOT_FOUND", status=404) from None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT a.id::text, a.request_id::text, a.storage_key, a.original_name,
                   a.mime, a.scan_state, r.status, r.requester_id::text,
                   EXISTS (SELECT 1 FROM eas.revision_attachment ra WHERE ra.attachment_id = a.id) AS in_rev,
                   EXISTS (SELECT 1 FROM eas.execution_attachment ea WHERE ea.attachment_id = a.id) AS in_exec,
                   EXISTS (SELECT 1 FROM eas.draft_attachment da WHERE da.attachment_id = a.id) AS in_draft
            FROM eas.attachment a
            JOIN eas.request r ON r.id = a.request_id
            LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
            LEFT JOIN eas.app_user u ON u.id = r.requester_id
            WHERE a.id = %s AND a.deleted_at IS NULL
              AND (
                r.requester_id = %s
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.request_participant p
                    WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                  )
                )
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.role_membership rm
                    WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
                      AND rm.revoked_at IS NULL
                      AND rm.valid_from <= statement_timestamp()
                      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                      AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
                      AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
                  )
                )
              )
            """,
            [att_uuid, actor.id, actor.id, actor.id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("NOT_FOUND", status=404)

        (
            att_id,
            req_id,
            storage_key,
            original_name,
            mime,
            scan_state,
            _req_status,
            requester_id,
            in_rev,
            in_exec,
            in_draft,
        ) = row

        if scan_state != "CLEAN":
            raise CommandError("FILE_NOT_READY", status=409)

        if not in_rev and not in_exec and not in_draft:
            raise CommandError("NOT_FOUND", status=404)

        if not in_rev and not in_exec and in_draft and actor.id != requester_id:
            raise CommandError("NOT_FOUND", status=404)

    try:
        data = get_private_object(storage_key)
    except StorageError as exc:
        raise CommandError("STORAGE_UNAVAILABLE", status=503) from exc

    now = datetime.now(timezone.utc)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(false)")
        _append_request_audit(
            cursor,
            request_id=req_id,
            actor_id=actor.id,
            action="ATTACHMENT_DOWNLOADED",
            target_type="attachment",
            target_id=att_id,
            details={
                "original_name": original_name,
                "mime": mime,
                "size_bytes": len(data),
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )

    return data, original_name, mime
