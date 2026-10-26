from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import connection, transaction

from api_core.audit import canonical_sha256
from api_core.authn.service import Actor
from api_core.workflow.service import CommandError, _utc_text


def _uuid_str(val: Any, field_name: str) -> str:
    if not isinstance(val, str):
        raise CommandError(f"INVALID_{field_name.upper()}", status=422)
    try:
        return str(UUID(val))
    except (ValueError, TypeError):
        raise CommandError(f"INVALID_{field_name.upper()}", status=422)


def list_notifications(actor: Actor, query_params: dict[str, str]) -> dict[str, Any]:
    try:
        limit = int(query_params.get("limit", "20"))
        offset = int(query_params.get("offset", "0"))
    except ValueError:
        raise CommandError("INVALID_PAGINATION", status=400)
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        raise CommandError("INVALID_PAGINATION", status=400)

    unread_only = query_params.get("unread") in ("true", "1")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM eas.notification WHERE recipient_id = %s AND read_at IS NULL",
            [actor.id],
        )
        unread_count = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT id::text, event_id::text, request_id::text, label, read_at, created_at
            FROM eas.notification
            WHERE recipient_id = %s
              AND (%s::boolean IS FALSE OR read_at IS NULL)
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            [actor.id, unread_only, limit + 1, offset],
        )
        rows = cursor.fetchall()

    items = [
        {
            "id": row[0],
            "event_id": row[1],
            "request_id": row[2],
            "label": row[3],
            "read_at": row[4].isoformat() if row[4] else None,
            "created_at": row[5].isoformat(),
        }
        for row in rows[:limit]
    ]

    return {
        "items": items,
        "unread_count": unread_count,
        "next_offset": offset + limit if len(rows) > limit else None,
    }


def mark_notification_read(actor: Actor, notification_id: str) -> dict[str, Any]:
    norm_id = _uuid_str(notification_id, "notification_id")
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(false)")

        cursor.execute(
            """
            SELECT id::text, read_at
            FROM eas.notification
            WHERE id = %s AND recipient_id = %s
            FOR UPDATE
            """,
            [norm_id, actor.id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("NOT_FOUND", status=404)

        _notif_id, read_at = row
        if read_at is None:
            cursor.execute(
                """
                UPDATE eas.notification
                SET read_at = statement_timestamp()
                WHERE id = %s
                RETURNING read_at
                """,
                [norm_id],
            )
            read_at = cursor.fetchone()[0]

    return {
        "notification": {
            "id": norm_id,
            "read_at": read_at.isoformat(),
        }
    }


def get_request_metrics_report(
    actor: Actor, query_params: dict[str, str]
) -> dict[str, Any]:
    from_str = query_params.get("created_from")
    to_str = query_params.get("created_to")

    if not from_str or not to_str:
        raise CommandError("PERIOD_INVALID", status=422)

    try:
        dt_from = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(to_str.replace("Z", "+00:00"))
    except ValueError:
        raise CommandError("PERIOD_INVALID", status=422)

    if dt_to <= dt_from:
        raise CommandError("PERIOD_INVALID", status=422)

    duration = dt_to - dt_from
    if duration.total_seconds() > 366 * 86400:
        raise CommandError("PERIOD_INVALID", status=422)

    type_code_filter = query_params.get("type_code")
    dept_filter = query_params.get("department_id")

    dept_uuid = None
    if dept_filter:
        try:
            dept_uuid = str(UUID(dept_filter))
        except (ValueError, TypeError):
            raise CommandError("INVALID_DEPARTMENT_ID", status=400)

    sql = """
        SELECT r.id::text, r.status, r.current_revision_id, r.approved_at
        FROM eas.request r
        JOIN eas.request_type rt ON rt.id = r.type_id
        JOIN eas.app_user u ON u.id = r.requester_id
        LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
        WHERE r.status != 'DRAFT'
          AND r.created_at >= %s
          AND r.created_at <= %s
          AND (%s::text IS NULL OR rt.code = %s)
          AND (%s::uuid IS NULL OR COALESCE(v.department_id, u.department_id) = %s::uuid)
          AND (
            (r.requester_id = %s)
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
    """
    params = [
        dt_from,
        dt_to,
        type_code_filter,
        type_code_filter,
        dept_uuid,
        dept_uuid,
        actor.id,
        actor.id,
        actor.id,
    ]

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    submitted = sum(1 for row in rows if row[2] is not None)
    approved = sum(1 for row in rows if row[3] is not None)
    completed = sum(1 for row in rows if row[1] == "COMPLETED")

    by_status: dict[str, int] = {}
    for row in rows:
        st = row[1]
        by_status[st] = by_status.get(st, 0) + 1

    approved_rate = round(approved / submitted, 4) if submitted > 0 else None
    completed_rate = round(completed / submitted, 4) if submitted > 0 else None

    return {
        "report": {
            "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
            "submitted": submitted,
            "approved": approved,
            "completed": completed,
            "approved_rate": approved_rate,
            "completed_rate": completed_rate,
            "by_status": by_status,
        }
    }


def get_request_audit_events(actor: Actor, request_id: str) -> dict[str, Any]:
    norm_id = _uuid_str(request_id, "request_id")
    sql = """
        SELECT r.id::text
        FROM eas.request r
        JOIN eas.app_user u ON u.id = r.requester_id
        LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
        WHERE r.id = %s
          AND (
            (r.requester_id = %s)
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
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [norm_id, actor.id, actor.id, actor.id])
        if not cursor.fetchone():
            raise CommandError("REQUEST_NOT_FOUND", status=404)

        cursor.execute(
            """
            SELECT id::text, request_id::text, seq, actor_id::text, actor_kind,
                   action, target_type, target_id::text, details, correlation_id::text,
                   occurred_at, hash_version, prev_hash, hash
            FROM eas.audit_event
            WHERE request_id = %s
            ORDER BY seq ASC
            """,
            [norm_id],
        )
        rows = cursor.fetchall()

    items = [
        {
            "id": row[0],
            "request_id": row[1],
            "seq": row[2],
            "actor_id": row[3],
            "actor_kind": row[4],
            "action": row[5],
            "target_type": row[6],
            "target_id": row[7],
            "details": row[8],
            "correlation_id": row[9],
            "occurred_at": row[10].isoformat(),
            "hash_version": row[11],
            "prev_hash": row[12],
            "hash": row[13],
        }
        for row in rows
    ]
    return {"items": items}


def list_admin_events(actor: Actor, query_params: dict[str, str]) -> dict[str, Any]:
    try:
        limit = int(query_params.get("limit", "20"))
        offset = int(query_params.get("offset", "0"))
    except ValueError:
        raise CommandError("INVALID_PAGINATION", status=400)
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        raise CommandError("INVALID_PAGINATION", status=400)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM eas.role_membership
              WHERE user_id = %s AND role IN ('AUDITOR', 'POLICY_ADMIN', 'OPS_ADMIN')
                AND revoked_at IS NULL
                AND valid_from <= statement_timestamp()
                AND (valid_to IS NULL OR valid_to > statement_timestamp())
            )
            """,
            [actor.id],
        )
        if not cursor.fetchone()[0]:
            raise CommandError("FORBIDDEN", status=403)

        cursor.execute(
            """
            SELECT e.id::text, e.seq, e.actor_id::text, e.actor_kind, e.action,
                   e.target_type, e.target_id::text, e.department_id::text,
                   e.type_id::text, e.details, e.reason, e.correlation_id::text,
                   e.occurred_at, e.hash_version, e.prev_hash, e.hash
            FROM eas.admin_event e
            ORDER BY e.seq DESC
            LIMIT %s OFFSET %s
            """,
            [limit + 1, offset],
        )
        rows = cursor.fetchall()

    items = [
        {
            "id": row[0],
            "seq": row[1],
            "actor_id": row[2],
            "actor_kind": row[3],
            "action": row[4],
            "target_type": row[5],
            "target_id": row[6],
            "department_id": row[7],
            "type_id": row[8],
            "details": row[9],
            "reason": row[10],
            "correlation_id": row[11],
            "occurred_at": row[12].isoformat(),
            "hash_version": row[13],
            "prev_hash": row[14],
            "hash": row[15],
        }
        for row in rows[:limit]
    ]
    return {
        "items": items,
        "next_offset": offset + limit if len(rows) > limit else None,
    }


def verify_audit_chain(scope_key: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT seq, last_hash FROM eas.audit_head WHERE scope_key = %s",
            [scope_key],
        )
        head = cursor.fetchone()
        if not head:
            return {
                "status": "UNKNOWN",
                "checked_seq": 0,
                "head_hash": None,
                "reason": "Audit head missing",
            }

        head_seq, head_last_hash = head

        if scope_key == "ADMIN":
            cursor.execute(
                """
                SELECT id::text, seq, actor_id::text, actor_kind, action,
                       target_type, target_id::text, department_id::text,
                       type_id::text, details, reason, correlation_id::text,
                       occurred_at, prev_hash, hash
                FROM eas.admin_event
                WHERE scope_key = 'ADMIN'
                ORDER BY seq ASC
                """
            )
            rows = cursor.fetchall()
            events = [
                {
                    "id": r[0],
                    "seq": r[1],
                    "actor_id": r[2],
                    "actor_kind": r[3],
                    "action": r[4],
                    "target_type": r[5],
                    "target_id": r[6],
                    "department_id": r[7],
                    "type_id": r[8],
                    "details": r[9],
                    "reason": r[10],
                    "correlation_id": r[11],
                    "occurred_at": r[12],
                    "prev_hash": r[13],
                    "hash": r[14],
                }
                for r in rows
            ]
        elif scope_key.startswith("REQ:"):
            req_id = scope_key[4:]
            cursor.execute(
                """
                SELECT id::text, seq, actor_id::text, actor_kind, action,
                       target_type, target_id::text, request_id::text,
                       details, correlation_id::text, occurred_at, prev_hash, hash
                FROM eas.audit_event
                WHERE request_id = %s
                ORDER BY seq ASC
                """,
                [req_id],
            )
            rows = cursor.fetchall()
            events = [
                {
                    "id": r[0],
                    "seq": r[1],
                    "actor_id": r[2],
                    "actor_kind": r[3],
                    "action": r[4],
                    "target_type": r[5],
                    "target_id": r[6],
                    "request_id": r[7],
                    "details": r[8],
                    "correlation_id": r[9],
                    "occurred_at": r[10],
                    "prev_hash": r[11],
                    "hash": r[12],
                }
                for r in rows
            ]
        else:
            return {
                "status": "UNKNOWN",
                "checked_seq": 0,
                "head_hash": head_last_hash,
                "reason": "Unsupported scope_key",
            }

    if not events:
        if head_seq == 0 and head_last_hash == "0" * 64:
            return {
                "status": "PASS",
                "checked_seq": 0,
                "head_hash": head_last_hash,
            }
        return {
            "status": "FAIL",
            "checked_seq": 0,
            "head_hash": head_last_hash,
            "reason": "Events empty but head is non-zero",
        }

    expected_prev = "0" * 64
    for idx, ev in enumerate(events, start=1):
        if ev["seq"] != idx:
            return {
                "status": "FAIL",
                "checked_seq": ev["seq"],
                "head_hash": head_last_hash,
                "reason": f"Sequence gap: expected {idx}, got {ev['seq']}",
            }
        if ev["prev_hash"] != expected_prev:
            return {
                "status": "FAIL",
                "checked_seq": ev["seq"],
                "head_hash": head_last_hash,
                "reason": f"Prev hash mismatch at seq {ev['seq']}",
            }

        if scope_key == "ADMIN":
            canonical_doc = {
                "action": ev["action"],
                "actor_id": ev["actor_id"],
                "actor_kind": ev["actor_kind"],
                "correlation_id": ev["correlation_id"],
                "department_id": ev["department_id"],
                "details": ev["details"],
                "hash_version": 1,
                "id": ev["id"],
                "occurred_at": _utc_text(ev["occurred_at"]),
                "prev_hash": ev["prev_hash"],
                "reason": ev["reason"],
                "scope_key": "ADMIN",
                "seq": str(ev["seq"]),
                "target_id": str(ev["target_id"]),
                "target_type": ev["target_type"],
                "type_id": ev["type_id"],
            }
        else:
            canonical_doc = {
                "action": ev["action"],
                "actor_id": ev["actor_id"],
                "actor_kind": ev["actor_kind"],
                "correlation_id": ev["correlation_id"],
                "details": ev["details"],
                "hash_version": 1,
                "id": ev["id"],
                "occurred_at": _utc_text(ev["occurred_at"]),
                "prev_hash": ev["prev_hash"],
                "request_id": ev["request_id"],
                "scope_key": scope_key,
                "seq": str(ev["seq"]),
                "target_id": str(ev["target_id"]),
                "target_type": ev["target_type"],
            }

        computed = canonical_sha256(canonical_doc)
        if computed != ev["hash"]:
            return {
                "status": "FAIL",
                "checked_seq": ev["seq"],
                "head_hash": head_last_hash,
                "reason": f"Content digest mismatch at seq {ev['seq']}",
            }
        expected_prev = ev["hash"]

    last_ev = events[-1]
    if last_ev["seq"] != head_seq or last_ev["hash"] != head_last_hash:
        return {
            "status": "FAIL",
            "checked_seq": last_ev["seq"],
            "head_hash": head_last_hash,
            "reason": "Audit head does not match the final event hash or sequence",
        }

    return {
        "status": "PASS",
        "checked_seq": last_ev["seq"],
        "head_hash": head_last_hash,
    }


def get_request_audit_verify(actor: Actor, request_id: str) -> dict[str, Any]:
    norm_id = _uuid_str(request_id, "request_id")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id::text, COALESCE(v.department_id, u.department_id)::text, r.type_id::text
            FROM eas.request r
            JOIN eas.app_user u ON u.id = r.requester_id
            LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
            WHERE r.id = %s
            """,
            [norm_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)

        _r_id, dept_id, type_id = row
        cursor.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM eas.role_membership
              WHERE user_id = %s AND role = 'AUDITOR' AND revoked_at IS NULL
                AND valid_from <= statement_timestamp()
                AND (valid_to IS NULL OR valid_to > statement_timestamp())
                AND (scope_kind = 'GLOBAL' OR department_id = %s)
                AND (type_scope = 'ALL' OR type_id = %s)
            )
            """,
            [actor.id, dept_id, type_id],
        )
        if not cursor.fetchone()[0]:
            raise CommandError("FORBIDDEN", status=403)

    return verify_audit_chain(f"REQ:{norm_id}")
