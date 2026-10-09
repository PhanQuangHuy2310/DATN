from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from django.db import connection, transaction
from django.utils import timezone
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class OutboxItem:
    id: str
    request_id: str | None
    event_type: str
    payload: dict[str, object]
    attempts: int
    lease_token: str


def retry_delay(attempts: int) -> timedelta:
    if attempts < 1:
        raise ValueError("attempts must be positive")
    return timedelta(seconds=min(15 * (2 ** (attempts - 1)), 300))


def safe_error_code(value: object) -> str:
    code = re.sub(r"[^A-Z0-9_]+", "_", type(value).__name__.upper()).strip("_")
    return (code or "UNKNOWN_ERROR")[:80]


def classify_sla_alert(
    *,
    started_at: datetime,
    due_at: datetime,
    breached_at: datetime | None,
    now: datetime,
) -> str | None:
    if breached_at is not None:
        return None
    if breached_at is None and now >= due_at:
        return "BREACH"
    reminder_at = started_at + (due_at - started_at) / 2
    if now >= reminder_at:
        return "REMINDER"
    return None


def claim_outbox(*, batch_size: int = 20, lease_seconds: int = 60) -> list[OutboxItem]:
    if not 1 <= batch_size <= 100 or not 10 <= lease_seconds <= 300:
        raise ValueError("Unsafe worker claim parameters")
    token = str(uuid4())
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            UPDATE eas.outbox_event
            SET state='DEAD',lease_token=NULL,lease_until=NULL,last_error_code='LEASE_EXHAUSTED'
            WHERE state='PROCESSING' AND lease_until <= statement_timestamp()
              AND attempts=4
            """
        )
        cursor.execute(
            """
            WITH candidates AS (
              SELECT id FROM eas.outbox_event
              WHERE attempts < 4 AND (
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
            [batch_size, token, lease_seconds],
        )
        return [OutboxItem(*row) for row in cursor.fetchall()]


def _recipients(cursor, item: OutboxItem) -> list[tuple[str, str]]:
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
    return [(row[0], label)] if row and row[0] else []


def acknowledge_outbox(item: OutboxItem) -> None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(false)")
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
        for recipient_id, label in _recipients(cursor, item):
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
    next_state = "DEAD" if item.attempts >= 4 else "PENDING"
    available_at = timezone.now() + retry_delay(item.attempts)
    with transaction.atomic(), connection.cursor() as cursor:
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


def process_sla_batch(*, batch_size: int = 100) -> int:
    if not 1 <= batch_size <= 500:
        raise ValueError("Unsafe SLA batch size")
    created = 0
    now = timezone.now()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(false)")
        cursor.execute(
            """
            SELECT s.id::text,s.request_id::text,s.started_at,s.due_at,s.breached_at
            FROM eas.sla_stage s
            WHERE s.closed_at IS NULL AND (
              (s.breached_at IS NULL AND s.due_at <= %s) OR
              (%s >= s.started_at + (s.due_at-s.started_at)/2)
            )
            ORDER BY s.due_at,s.id
            FOR UPDATE SKIP LOCKED LIMIT %s
            """,
            [now, now, batch_size],
        )
        stages = cursor.fetchall()
        for stage_id, request_id, started_at, due_at, breached_at in stages:
            kind = classify_sla_alert(
                started_at=started_at,
                due_at=due_at,
                breached_at=breached_at,
                now=now,
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
            created += 1
    return created
