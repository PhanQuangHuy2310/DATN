"""Time-limited approval delegation: create, revoke, list (thesis §2.3.4, SD-22).

Routing applies an active delegation when a request is submitted
(``api_core.domain.delegation.apply_delegations``). This module owns the
records: who delegates to whom, for which scope and period, and revocation.

Rules (owner decision C3):
- delegator and delegate are active, non-administrative users with a valid
  APPROVER grant covering the scope; delegate != delegator;
- no chains: the delegate may not delegate onward during an overlapping
  period, and a current delegate may not delegate their own work onward;
- one delegation per delegator and scope at a time (no overlap);
- the period is bounded (valid_to required) and cannot start in the past;
- every create/revoke is written to the admin audit chain and notifies both
  parties through the outbox.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from django.db import connection
from psycopg.types.json import Jsonb

from api_core.authn.models import Actor
from api_core.workflow.ops_service import _clean_reason, _uuid_str
from api_core.workflow.service import (
    SQL_LOCK_SECURITY,
    SQL_NOT_ADMINISTRATIVE,
    CommandError,
    CommandResult,
    _append_admin_audit,
    _execute_idempotent,
    approval_delegation_enabled,
)

# Clock skew allowance for "starts now" from the browser.
START_GRACE = timedelta(minutes=5)

STATUS_SQL = """
    CASE WHEN d.revoked_at IS NOT NULL THEN 'REVOKED'
         WHEN d.valid_to <= statement_timestamp() THEN 'EXPIRED'
         WHEN d.valid_from > statement_timestamp() THEN 'SCHEDULED'
         ELSE 'ACTIVE' END
"""

# Approver grant covering a scope for the whole period. %s order:
# user, department(nullable), department, type(nullable), type, from, to.
SQL_APPROVER_COVERS = f"""
    SELECT EXISTS (
      SELECT 1 FROM eas.app_user u
      JOIN eas.role_membership rm ON rm.user_id = u.id
      WHERE u.id = %s AND u.is_active
        AND rm.role = 'APPROVER' AND rm.revoked_at IS NULL
        AND (%s::uuid IS NULL OR rm.scope_kind = 'GLOBAL' OR rm.department_id = %s::uuid)
        AND (%s::uuid IS NULL OR rm.type_scope = 'ALL' OR rm.type_id = %s::uuid)
        AND rm.valid_from <= %s
        AND (rm.valid_to IS NULL OR rm.valid_to >= %s)
        {SQL_NOT_ADMINISTRATIVE}
    )
"""


def _require_enabled() -> None:
    if not approval_delegation_enabled():
        raise CommandError("DELEGATION_NOT_ENABLED", status=409)


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise CommandError(
            "VALIDATION_FAILED", status=422, fields={field: ["required"]}
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CommandError(
            "VALIDATION_FAILED", status=422, fields={field: ["invalid_datetime"]}
        ) from None
    if parsed.tzinfo is None:
        raise CommandError(
            "VALIDATION_FAILED", status=422, fields={field: ["timezone_required"]}
        )
    return parsed.astimezone(timezone.utc)


def _optional_uuid(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _uuid_str(value, field)


def validate_period(valid_from: datetime, valid_to: datetime, now: datetime) -> None:
    if valid_from < now - START_GRACE:
        raise CommandError("DELEGATION_START_IN_PAST", status=422)
    if valid_to <= valid_from:
        raise CommandError("DELEGATION_PERIOD_INVALID", status=422)


def _row(row) -> dict[str, Any]:
    keys = (
        "id",
        "delegator_id",
        "delegator_name",
        "delegate_id",
        "delegate_name",
        "department_id",
        "department_name",
        "type_id",
        "type_name",
        "valid_from",
        "valid_to",
        "reason",
        "status",
        "created_by",
        "created_at",
        "revoked_at",
        "revoked_by",
    )
    item = dict(zip(keys, row, strict=True))
    for key in ("valid_from", "valid_to", "created_at", "revoked_at"):
        if item[key] is not None:
            item[key] = item[key].isoformat()
    return item


SQL_SELECT = f"""
    SELECT d.id::text, d.delegator_id::text, a.display_name,
           d.delegate_id::text, b.display_name,
           d.department_id::text, dep.name, d.type_id::text, rt.name,
           d.valid_from, d.valid_to, d.reason, {STATUS_SQL},
           d.created_by::text, d.created_at, d.revoked_at, d.revoked_by::text
    FROM eas.approval_delegation d
    JOIN eas.app_user a ON a.id = d.delegator_id
    JOIN eas.app_user b ON b.id = d.delegate_id
    LEFT JOIN eas.department dep ON dep.id = d.department_id
    LEFT JOIN eas.request_type rt ON rt.id = d.type_id
"""


def list_delegations(actor: Actor, params: dict[str, str], *, ops: bool) -> dict:
    _require_enabled()
    status = params.get("status") or None
    if status not in (None, "ACTIVE", "SCHEDULED", "EXPIRED", "REVOKED"):
        raise CommandError("INVALID_STATUS", status=422)
    where = ["TRUE"]
    args: list[Any] = []
    if not ops:
        # Approvers see delegations they gave or received.
        where.append("(d.delegator_id = %s OR d.delegate_id = %s)")
        args += [actor.id, actor.id]
    if status:
        where.append(f"({STATUS_SQL}) = %s")
        args.append(status)
    with connection.cursor() as cursor:
        cursor.execute(
            f"{SQL_SELECT} WHERE {' AND '.join(where)} "
            "ORDER BY d.valid_from DESC, d.id LIMIT 200",
            args,
        )
        return {"items": [_row(r) for r in cursor.fetchall()]}


def delegate_candidates(actor: Actor, params: dict[str, str]) -> dict:
    """Active, non-administrative users with an APPROVER grant (names only)."""
    _require_enabled()
    q = (params.get("q") or "").strip()[:80]
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT u.id::text, u.display_name, d.name
            FROM eas.app_user u
            LEFT JOIN eas.department d ON d.id = u.department_id
            WHERE u.is_active AND u.id <> %s
              AND EXISTS (
                SELECT 1 FROM eas.role_membership rm
                WHERE rm.user_id = u.id AND rm.role = 'APPROVER'
                  AND rm.revoked_at IS NULL
                  AND rm.valid_from <= statement_timestamp()
                  AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
              )
              AND (%s = '' OR u.display_name ILIKE '%%' || %s || '%%')
              {SQL_NOT_ADMINISTRATIVE}
            ORDER BY u.display_name LIMIT 50
            """,
            [actor.id, q, q],
        )
        return {
            "items": [
                {"id": r[0], "display_name": r[1], "department_name": r[2]}
                for r in cursor.fetchall()
            ]
        }


def _covers(cursor, user_id, department_id, type_id, valid_from, valid_to) -> bool:
    cursor.execute(
        SQL_APPROVER_COVERS,
        [
            user_id,
            department_id,
            department_id,
            type_id,
            type_id,
            valid_from,
            valid_to,
        ],
    )
    return bool(cursor.fetchone()[0])


def create_delegation(
    *,
    actor: Actor,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
    ops: bool = False,
) -> CommandResult:
    _require_enabled()
    # Approvers delegate their own work; Ops Admins may act for an absent
    # approver (thesis SD-22) but never become a party themselves.
    delegator_id = (
        _uuid_str(body.get("delegator_id"), "delegator_id") if ops else actor.id
    )
    delegate_id = _uuid_str(body.get("delegate_id"), "delegate_id")
    department_id = _optional_uuid(body.get("department_id"), "department_id")
    type_code = body.get("type_code") or None
    if type_code is not None and not isinstance(type_code, str):
        raise CommandError("UNKNOWN_TYPE_CODE", status=422)
    valid_from = _parse_time(body.get("valid_from"), "valid_from")
    valid_to = _parse_time(body.get("valid_to"), "valid_to")
    reason = _clean_reason(body.get("reason"))
    if len(reason) > 500:
        raise CommandError("REASON_INVALID", status=422)
    if delegate_id == delegator_id:
        raise CommandError("DELEGATION_SELF", status=422)
    if ops and actor.id in (delegator_id, delegate_id):
        raise CommandError("DELEGATION_ADMIN_PARTY", status=422)
    validate_period(valid_from, valid_to, datetime.now(timezone.utc))

    def operation(cursor) -> tuple[dict[str, Any], int, None]:
        cursor.execute(SQL_LOCK_SECURITY)
        # Serialize concurrent delegations touching either person.
        cursor.execute(
            "SELECT id FROM eas.app_user WHERE id = ANY(%s::uuid[]) ORDER BY id FOR UPDATE",
            [[delegator_id, delegate_id]],
        )
        if len(cursor.fetchall()) != 2:
            raise CommandError("USER_NOT_FOUND", status=404)
        type_id = None
        if type_code:
            cursor.execute(
                "SELECT id::text FROM eas.request_type WHERE code = %s", [type_code]
            )
            found = cursor.fetchone()
            if not found:
                raise CommandError("UNKNOWN_TYPE_CODE", status=422)
            type_id = found[0]
        if not _covers(
            cursor, delegator_id, department_id, type_id, valid_from, valid_to
        ):
            raise CommandError("DELEGATOR_NOT_APPROVER", status=422)
        if not _covers(
            cursor, delegate_id, department_id, type_id, valid_from, valid_to
        ):
            raise CommandError("DELEGATE_NOT_ELIGIBLE", status=422)
        cursor.execute(
            """
            SELECT
              EXISTS (SELECT 1 FROM eas.approval_delegation d
                      WHERE d.delegator_id = %s AND d.revoked_at IS NULL
                        AND d.valid_from < %s AND d.valid_to > %s
                        AND d.department_id IS NOT DISTINCT FROM %s::uuid
                        AND d.type_id IS NOT DISTINCT FROM %s::uuid),
              EXISTS (SELECT 1 FROM eas.approval_delegation d
                      WHERE d.revoked_at IS NULL AND d.valid_from < %s AND d.valid_to > %s
                        AND (d.delegator_id = %s OR d.delegate_id = %s))
            """,
            [
                delegator_id,
                valid_to,
                valid_from,
                department_id,
                type_id,
                valid_to,
                valid_from,
                delegate_id,
                delegator_id,
            ],
        )
        overlap, chain = cursor.fetchone()
        if overlap:
            raise CommandError("DELEGATION_OVERLAP", status=409)
        if chain:
            raise CommandError("DELEGATION_CHAIN_FORBIDDEN", status=409)
        cursor.execute(
            """
            INSERT INTO eas.approval_delegation(
              delegator_id, delegate_id, department_id, type_id,
              valid_from, valid_to, reason, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id::text
            """,
            [
                delegator_id,
                delegate_id,
                department_id,
                type_id,
                valid_from,
                valid_to,
                reason,
                actor.id,
            ],
        )
        delegation_id = cursor.fetchone()[0]
        details = {
            "delegator_id": delegator_id,
            "delegate_id": delegate_id,
            "type_id": type_id,
            "valid_from": valid_from.isoformat(),
            "valid_to": valid_to.isoformat(),
            "on_behalf": ops,
        }
        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="APPROVAL_DELEGATION_CREATED",
            target_type="approval_delegation",
            target_id=delegation_id,
            department_id=department_id,
            type_id=type_id,
            details=details,
            reason=reason,
            correlation_id=correlation_id,
        )
        _notify(cursor, "DELEGATION_CREATED", delegation_id, delegator_id, delegate_id)
        cursor.execute(f"{SQL_SELECT} WHERE d.id = %s", [delegation_id])
        return {"delegation": _row(cursor.fetchone())}, 201, None

    return _execute_idempotent(
        actor_id=actor.id,
        scope="delegation:create",
        key=idempotency_key,
        command_body={**body, "_ops": ops},
        operation=operation,
    )


def revoke_delegation(
    *,
    actor: Actor,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
    delegation_id: str,
    ops: bool = False,
) -> CommandResult:
    _require_enabled()
    delegation_id = _uuid_str(delegation_id, "delegation_id")
    reason = _clean_reason(body.get("reason"))

    def operation(cursor) -> tuple[dict[str, Any], int, None]:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT delegator_id::text, delegate_id::text, department_id::text,
                   type_id::text, revoked_at IS NOT NULL,
                   valid_to <= statement_timestamp()
            FROM eas.approval_delegation WHERE id = %s FOR UPDATE
            """,
            [delegation_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("DELEGATION_NOT_FOUND", status=404)
        delegator_id, delegate_id, department_id, type_id, revoked, expired = row
        if not ops and actor.id != delegator_id:
            raise CommandError("FORBIDDEN", status=403)
        if revoked or expired:
            raise CommandError("DELEGATION_NOT_ACTIVE", status=409)
        cursor.execute(
            """
            UPDATE eas.approval_delegation
            SET revoked_at = statement_timestamp(), revoked_by = %s
            WHERE id = %s AND revoked_at IS NULL
            """,
            [actor.id, delegation_id],
        )
        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="APPROVAL_DELEGATION_REVOKED",
            target_type="approval_delegation",
            target_id=delegation_id,
            department_id=department_id,
            type_id=type_id,
            details={"delegator_id": delegator_id, "delegate_id": delegate_id},
            reason=reason,
            correlation_id=correlation_id,
        )
        _notify(cursor, "DELEGATION_REVOKED", delegation_id, delegator_id, delegate_id)
        cursor.execute(f"{SQL_SELECT} WHERE d.id = %s", [delegation_id])
        return {"delegation": _row(cursor.fetchone())}, 200, None

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"delegation:revoke:{delegation_id}",
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


def _notify(cursor, event_type, delegation_id, delegator_id, delegate_id) -> None:
    cursor.execute(
        """
        INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
        VALUES (NULL,%s,%s,%s)
        """,
        [
            event_type,
            Jsonb(
                {
                    "delegation_id": delegation_id,
                    "delegator_id": delegator_id,
                    "delegate_id": delegate_id,
                }
            ),
            f"delegation:{delegation_id}:{event_type.lower()}",
        ],
    )
