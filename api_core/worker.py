from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NamedTuple
from uuid import uuid4

from django.db import connection, transaction
from django.utils import timezone
from psycopg.types.json import Jsonb

from api_core.workflow.service import _append_admin_audit, _append_request_audit


@dataclass(frozen=True)
class OutboxItem:
    id: str
    request_id: str | None
    event_type: str
    payload: dict[str, object]
    attempts: int
    lease_token: str


# Thesis §2.3 outbox: back off 10s, 30s, 1m, 5m, then stay at 5m.
RETRY_SCHEDULE_SECONDS = (10, 30, 60, 300)
# Thesis: five retries after the first attempt (six in total). The live limit is
# whatever the outbox_dead constraint allows: 4 before migration
# report_migrations/09_outbox_six_attempts_DBA_REVIEW_ONLY.sql, 6 after it.
LEGACY_MAX_ATTEMPTS = 4
THESIS_MAX_ATTEMPTS = 6
_max_attempts_cache: int | None = None


def retry_delay(attempts: int) -> timedelta:
    if attempts < 1:
        raise ValueError("attempts must be positive")
    index = min(attempts, len(RETRY_SCHEDULE_SECONDS)) - 1
    return timedelta(seconds=RETRY_SCHEDULE_SECONDS[index])


def outbox_max_attempts(cursor) -> int:
    """Attempt limit the database accepts for DEAD events (cached per process)."""
    global _max_attempts_cache
    if _max_attempts_cache is None:
        cursor.execute(
            """
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conname='outbox_dead' AND conrelid='eas.outbox_event'::regclass
            """
        )
        row = cursor.fetchone()
        definition = row[0] if row else ""
        _max_attempts_cache = (
            THESIS_MAX_ATTEMPTS
            if f"attempts <= {THESIS_MAX_ATTEMPTS}" in definition
            else LEGACY_MAX_ATTEMPTS
        )
    return _max_attempts_cache


SQL_LOCK_SECURITY = "SELECT eas.lock_security(false)"


def safe_error_code(value: object) -> str:
    code = re.sub(r"[^A-Z0-9_]+", "_", type(value).__name__.upper()).strip("_")
    return (code or "UNKNOWN_ERROR")[:80]


# Stored releases pin reminder_fraction to 0.5 (guard_release); the thesis
# (Table 2.9) asks for 0.8. The worker follows each release's value so a
# reviewed migration plus new releases can switch without a code change.
DEFAULT_REMINDER_FRACTION = 0.5
# Thesis Table 2.9: > 150% of the SLA window is escalation level L2.
SLA_L2_FRACTION = 1.5


def sla_escalation_levels_enabled() -> bool:
    """Thesis L1/L2 escalation (B3). Off until migration
    report_migrations/07_sla_thesis_policy_DBA_REVIEW_ONLY.sql is approved and
    applied: the live sla_alert CHECK rejects kind 'ESCALATE'."""
    return os.environ.get("EAS_SLA_ESCALATION_LEVELS", "").strip() == "1"


def reminder_fraction(value: object) -> float:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 < float(value) < 1
    ):
        return float(value)
    return DEFAULT_REMINDER_FRACTION


def classify_sla_alert(
    *,
    started_at: datetime,
    due_at: datetime,
    breached_at: datetime | None,
    now: datetime,
    fraction: float = DEFAULT_REMINDER_FRACTION,
    escalation_levels: bool = False,
    escalated: bool = False,
) -> str | None:
    window = due_at - started_at
    if breached_at is not None:
        # L1 is the breach itself; L2 fires once past 150% of the window.
        if (
            escalation_levels
            and not escalated
            and now >= started_at + window * SLA_L2_FRACTION
        ):
            return "ESCALATE"
        return None
    if now >= due_at:
        return "BREACH"
    if now >= started_at + window * fraction:
        return "REMINDER"
    return None


def claim_outbox(*, batch_size: int = 20, lease_seconds: int = 60) -> list[OutboxItem]:
    if not 1 <= batch_size <= 100 or not 10 <= lease_seconds <= 300:
        raise ValueError("Unsafe worker claim parameters")
    token = str(uuid4())
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(SQL_LOCK_SECURITY)
        limit = outbox_max_attempts(cursor)
        cursor.execute(
            """
            UPDATE eas.outbox_event
            SET state='DEAD',lease_token=NULL,lease_until=NULL,last_error_code='LEASE_EXHAUSTED'
            WHERE state='PROCESSING' AND lease_until <= statement_timestamp()
              AND attempts=%s
            """,
            [limit],
        )
        cursor.execute(
            """
            WITH candidates AS (
              SELECT id FROM eas.outbox_event
              WHERE attempts < %s AND (
                (state='PENDING' AND available_at <= statement_timestamp()) OR
                (state='PROCESSING' AND lease_until <= statement_timestamp())
              )
              ORDER BY available_at,id
              FOR UPDATE SKIP LOCKED
              LIMIT %s
            )
            UPDATE eas.outbox_event e
            SET state='PROCESSING',attempts=e.attempts+1,lease_token=%s,
                lease_until=statement_timestamp()+make_interval(secs => %s),
                last_error_code=NULL
            FROM candidates c WHERE e.id=c.id
            RETURNING e.id::text,e.request_id::text,e.event_type,e.payload,
                      e.attempts,e.lease_token::text
            """,
            [limit, batch_size, token, lease_seconds],
        )
        return [OutboxItem(*row) for row in cursor.fetchall()]


class Recipient(NamedTuple):
    user_id: str
    label: str
    # Metadata-only recipients (SLA escalation heads, Director, Ops Admin) get
    # the request code and SLA level only; this never grants read access.
    metadata_only: bool = False


def _request_code(cursor, request_id: str | None) -> str:
    cursor.execute("SELECT code FROM eas.request WHERE id=%s", [request_id])
    row = cursor.fetchone()
    return row[0] if row else "?"


DELEGATION_LABELS = {
    "DELEGATION_CREATED": (
        "Bạn đã ủy quyền phê duyệt tạm thời cho {other}",
        "Bạn được ủy quyền phê duyệt tạm thời thay {other}",
    ),
    "DELEGATION_REVOKED": (
        "Ủy quyền phê duyệt cho {other} đã bị thu hồi",
        "Ủy quyền phê duyệt từ {other} đã bị thu hồi",
    ),
}


def _recipients(cursor, item: OutboxItem) -> list[Recipient]:
    if item.event_type in DELEGATION_LABELS:
        # Request-independent: both parties of the delegation are told.
        delegator = item.payload.get("delegator_id")
        delegate = item.payload.get("delegate_id")
        cursor.execute(
            "SELECT id::text, display_name FROM eas.app_user WHERE id = ANY(%s::uuid[])",
            [[delegator, delegate]],
        )
        names = dict(cursor.fetchall())
        to_delegator, to_delegate = DELEGATION_LABELS[item.event_type]
        recipients = []
        if delegator:
            recipients.append(
                Recipient(delegator, to_delegator.format(other=names.get(delegate, "")))
            )
        if delegate:
            recipients.append(
                Recipient(delegate, to_delegate.format(other=names.get(delegator, "")))
            )
        return recipients
    if item.event_type in {"SLA_REMINDER", "SLA_BREACH"}:
        # Notify the *current assignee*, not only the original requester.
        # A stage's responsible user may change when OPS reassigns work.
        cursor.execute(
            """
            SELECT CASE WHEN s.kind='APPROVAL' THEN ap.assignee_id::text
                        WHEN s.kind='EXECUTION' THEN ex.executor_id::text
                        ELSE wi.acceptor_id::text END
            FROM eas.sla_stage s
            LEFT JOIN eas.approval_step ap ON ap.id=s.approval_step_id
            LEFT JOIN eas.execution_attempt ex ON ex.id=s.attempt_id
            LEFT JOIN eas.workflow_instance wi ON wi.id=ex.instance_id
            WHERE s.id=%s AND s.request_id=%s
            """,
            [item.payload.get("stage_id"), item.request_id],
        )
        row = cursor.fetchone()
        label = (
            "Công việc được phân công đã quá hạn, vui lòng xử lý"
            if item.event_type == "SLA_BREACH"
            else "Công việc được phân công đang đến hạn xử lý"
        )
        recipients = [Recipient(row[0], label)] if row and row[0] else []
        if (
            item.event_type == "SLA_BREACH"
            and recipients
            and sla_escalation_levels_enabled()
        ):
            # Thesis L1: the assignee plus their head (direct manager).
            cursor.execute(
                "SELECT manager_id::text FROM eas.app_user WHERE id=%s",
                [recipients[0].user_id],
            )
            head = cursor.fetchone()
            if head and head[0] and head[0] != recipients[0].user_id:
                code = _request_code(cursor, item.request_id)
                recipients.append(
                    Recipient(
                        head[0],
                        f"SLA L1: hồ sơ {code} của nhân sự bạn quản lý đã quá hạn",
                        metadata_only=True,
                    )
                )
        return recipients
    if item.event_type == "SLA_ESCALATE":
        # Thesis L2: the department DIRECTOR binding of the request's release
        # plus active global Ops Admins, metadata only.
        cursor.execute(
            """
            SELECT DISTINCT x.id FROM (
              SELECT cr.actor_bindings->'departments'->(v.department_id::text)->>'DIRECTOR' AS id
              FROM eas.request r
              JOIN eas.request_revision v ON v.id=r.current_revision_id
              JOIN eas.config_release cr ON cr.id=v.release_id
              WHERE r.id=%s
              UNION
              SELECT rm.user_id::text FROM eas.role_membership rm
              WHERE rm.role='OPS_ADMIN' AND rm.scope_kind='GLOBAL' AND rm.revoked_at IS NULL
                AND rm.valid_from <= statement_timestamp()
                AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
            ) x WHERE x.id IS NOT NULL ORDER BY 1
            """,
            [item.request_id],
        )
        ids = [row[0] for row in cursor.fetchall()]
        code = _request_code(cursor, item.request_id)
        label = f"SLA L2: hồ sơ {code} quá hạn nghiêm trọng (>150%), cần điều chuyển"
        return [Recipient(user_id, label, metadata_only=True) for user_id in ids]
    if item.event_type == "APPROVAL_REQUESTED":
        cursor.execute(
            "SELECT assignee_id::text FROM eas.approval_step WHERE id=%s",
            [item.payload.get("step_id")],
        )
        label = "Bạn có một yêu cầu cần phê duyệt"
    elif item.event_type == "EXECUTION_READY":
        cursor.execute(
            """
            SELECT i.planned_executor_id::text
            FROM eas.request r JOIN eas.workflow_instance i
              ON i.revision_id=r.current_revision_id AND i.state='ACTIVE'
            WHERE r.id=%s
            """,
            [item.request_id],
        )
        label = "Bạn có một yêu cầu cần thực hiện"
    else:
        cursor.execute(
            "SELECT requester_id::text FROM eas.request WHERE id=%s",
            [item.request_id],
        )
        label = "Yêu cầu của bạn vừa được cập nhật"
    row = cursor.fetchone()
    return [Recipient(row[0], label)] if row and row[0] else []


def acknowledge_outbox(item: OutboxItem) -> None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            """
            SELECT state,lease_token::text,lease_until > statement_timestamp()
            FROM eas.outbox_event WHERE id=%s FOR UPDATE
            """,
            [item.id],
        )
        lease = cursor.fetchone()
        if lease != ("PROCESSING", item.lease_token, True):
            raise RuntimeError("OUTBOX_LEASE_LOST")
        for recipient_id, label, metadata_only in _recipients(cursor, item):
            cursor.execute(
                """
                SELECT u.is_active,
                       CASE
                         WHEN %s::uuid IS NULL THEN TRUE
                         WHEN r.requester_id = u.id THEN TRUE
                         WHEN p.id IS NOT NULL AND p.read_revoked_at IS NULL THEN TRUE
                         ELSE FALSE
                       END AS can_read
                FROM eas.app_user u
                LEFT JOIN eas.request r ON r.id = %s::uuid
                LEFT JOIN eas.request_participant p ON p.request_id = %s::uuid AND p.user_id = u.id
                WHERE u.id = %s
                """,
                [item.request_id, item.request_id, item.request_id, recipient_id],
            )
            recip_status = cursor.fetchone()
            # Metadata-only recipients need an active account, not read access.
            readable = bool(recip_status and recip_status[1]) or metadata_only
            if not recip_status or not recip_status[0] or not readable:
                _append_admin_audit(
                    cursor,
                    actor_id=None,
                    actor_kind="SYSTEM",
                    action="NOTIFICATION_SKIPPED_INACTIVE_OR_REVOKED",
                    target_type="outbox_event",
                    target_id=item.id,
                    reason="Recipient is inactive or read access was revoked.",
                    details={
                        "recipient_id": recipient_id,
                        "request_id": item.request_id,
                    },
                    correlation_id=str(uuid4()),
                )
                continue
            cursor.execute(
                """
                INSERT INTO eas.notification(event_id,recipient_id,request_id,label)
                VALUES (%s,%s,%s,%s) ON CONFLICT (event_id,recipient_id) DO NOTHING
                """,
                [item.id, recipient_id, item.request_id, label],
            )

        cursor.execute(
            """
            UPDATE eas.outbox_event SET state='SENT',sent_at=statement_timestamp(),
              lease_token=NULL,lease_until=NULL,last_error_code=NULL
            WHERE id=%s AND lease_token=%s
            """,
            [item.id, item.lease_token],
        )
        if cursor.rowcount != 1:
            raise RuntimeError("OUTBOX_LEASE_LOST")


def fail_outbox(item: OutboxItem, error: object) -> None:
    available_at = timezone.now() + retry_delay(item.attempts)
    with transaction.atomic(), connection.cursor() as cursor:
        next_state = (
            "DEAD" if item.attempts >= outbox_max_attempts(cursor) else "PENDING"
        )
        cursor.execute(
            """
            UPDATE eas.outbox_event SET state=%s,available_at=%s,
              lease_token=NULL,lease_until=NULL,last_error_code=%s
            WHERE id=%s AND state='PROCESSING' AND lease_token=%s
            """,
            [
                next_state,
                available_at,
                safe_error_code(error),
                item.id,
                item.lease_token,
            ],
        )
        if cursor.rowcount != 1:
            raise RuntimeError("OUTBOX_LEASE_LOST")


def run_outbox_batch(*, batch_size: int = 20) -> int:
    items = claim_outbox(batch_size=batch_size)
    for item in items:
        try:
            acknowledge_outbox(item)
        except Exception as exc:  # noqa: BLE001 - every delivery failure must release the lease
            fail_outbox(item, exc)
    return len(items)


# The reminder point comes from the request's own release (sla_profile);
# the L2 branch is inert unless escalation levels are enabled.
SQL_DUE_SLA_STAGES = """
    SELECT s.id::text,s.request_id::text,s.started_at,s.due_at,s.breached_at,
           f.fraction,
           EXISTS (SELECT 1 FROM eas.sla_alert al
                   WHERE al.stage_id=s.id AND al.kind='ESCALATE')
    FROM eas.sla_stage s
    JOIN eas.request r ON r.id=s.request_id
    LEFT JOIN eas.request_revision v ON v.id=r.current_revision_id
    LEFT JOIN eas.config_release cr ON cr.id=v.release_id
    CROSS JOIN LATERAL (
      SELECT CASE WHEN jsonb_typeof(cr.sla_profile->'reminder_fraction')='number'
                       AND (cr.sla_profile->>'reminder_fraction')::float8 > 0
                       AND (cr.sla_profile->>'reminder_fraction')::float8 < 1
                  THEN (cr.sla_profile->>'reminder_fraction')::float8
                  ELSE %s END AS fraction
    ) f
    WHERE s.closed_at IS NULL AND (
      (s.breached_at IS NULL AND (
        (s.due_at <= %s AND NOT EXISTS (
            SELECT 1 FROM eas.sla_alert al WHERE al.stage_id=s.id AND al.kind='BREACH'
        )) OR
        (%s >= s.started_at + (s.due_at-s.started_at)*f.fraction AND NOT EXISTS (
            SELECT 1 FROM eas.sla_alert al WHERE al.stage_id=s.id AND al.kind='REMINDER'
        ))
      )) OR (%s AND s.breached_at IS NOT NULL
        AND %s >= s.started_at + (s.due_at-s.started_at)*%s
        AND NOT EXISTS (
            SELECT 1 FROM eas.sla_alert al WHERE al.stage_id=s.id AND al.kind='ESCALATE'
        ))
    )
    ORDER BY s.due_at,s.id
    FOR UPDATE OF s SKIP LOCKED LIMIT %s
"""


def sla_stage_params(now: datetime, levels: bool, batch_size: int) -> list[object]:
    return [
        DEFAULT_REMINDER_FRACTION,
        now,
        now,
        levels,
        now,
        SLA_L2_FRACTION,
        batch_size,
    ]


def process_sla_batch(*, batch_size: int = 100) -> int:
    if not 1 <= batch_size <= 500:
        raise ValueError("Unsafe SLA batch size")
    created = 0
    now = timezone.now()
    levels = sla_escalation_levels_enabled()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(SQL_DUE_SLA_STAGES, sla_stage_params(now, levels, batch_size))
        stages = cursor.fetchall()
        for (
            stage_id,
            request_id,
            started_at,
            due_at,
            breached_at,
            fraction,
            escalated,
        ) in stages:
            kind = classify_sla_alert(
                started_at=started_at,
                due_at=due_at,
                breached_at=breached_at,
                now=now,
                fraction=reminder_fraction(fraction),
                escalation_levels=levels,
                escalated=bool(escalated),
            )
            if kind is None:
                continue
            cursor.execute(
                """
                INSERT INTO eas.sla_alert(request_id,stage_id,kind)
                VALUES (%s,%s,%s) ON CONFLICT (stage_id,kind) DO NOTHING
                RETURNING id::text
                """,
                [request_id, stage_id, kind],
            )
            alert = cursor.fetchone()
            if not alert:
                continue
            if kind == "BREACH":
                cursor.execute(
                    "UPDATE eas.sla_stage SET breached_at=due_at WHERE id=%s AND breached_at IS NULL",
                    [stage_id],
                )
            cursor.execute(
                """
                INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)
                VALUES (%s,%s,%s,%s)
                """,
                [
                    request_id,
                    f"SLA_{kind}",
                    Jsonb({"request_id": request_id, "stage_id": stage_id}),
                    f"sla:{stage_id}:{kind.lower()}",
                ],
            )
            _append_request_audit(
                cursor,
                request_id=request_id,
                actor_id=None,
                actor_kind="SYSTEM",
                action=f"SLA_{kind}",
                target_type="sla_stage",
                target_id=stage_id,
                details={"kind": kind, "stage_id": stage_id},
                correlation_id=str(uuid4()),
                occurred_at=now,
            )
            created += 1

    return created
