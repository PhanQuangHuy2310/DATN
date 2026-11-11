"""Repair workflow rows that bypassed the service layer (seed / manual SQL).

Two inconsistencies were found on live (docs/KIEM_TOAN_CODE_DATA_2026-11-04.md D1, D2):

* STUCK  PENDING_APPROVAL request whose ACTIVE instance has no ACTIVE step but a
         WAITING one: nobody can act. The lowest WAITING step is activated
         (absent approver handed over exactly like a normal activation) and an
         approval SLA stage is ensured for it.
* ORPHAN terminal request (COMPLETED/REJECTED/CANCELLED) that still has an open
         SLA stage, ACTIVE/WAITING steps or an ACTIVE instance: they are closed.

Every change is written through the same hash-chained audit as the service
(action DATA_REPAIR_*, actor_kind SYSTEM). Dry-run is the default.

    python manage.py repair_workflow_consistency            # report only
    python manage.py repair_workflow_consistency --apply    # repair
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api_core.workflow.service import (
    SQL_LOCK_SECURITY,
    _append_request_audit,
    _substitute_approver,
)

TERMINAL_INSTANCE_STATE = {
    "COMPLETED": "COMPLETED",
    "REJECTED": "REJECTED",
    "CANCELLED": "CANCELLED",
}

SQL_STUCK = """
    SELECT r.id::text, r.code, i.id::text, r.type_id::text, r.requester_id::text,
           v.department_id::text, cr.sla_profile
    FROM eas.request r
    JOIN eas.request_revision v ON v.id = r.current_revision_id
    JOIN eas.config_release cr ON cr.id = v.release_id
    JOIN eas.workflow_instance i ON i.revision_id = v.id AND i.state = 'ACTIVE'
    WHERE r.status = 'PENDING_APPROVAL'
      AND NOT EXISTS (SELECT 1 FROM eas.approval_step s
                      WHERE s.instance_id = i.id AND s.state = 'ACTIVE')
      AND EXISTS (SELECT 1 FROM eas.approval_step s
                  WHERE s.instance_id = i.id AND s.state = 'WAITING')
    ORDER BY r.code
"""

SQL_ORPHANS = """
    SELECT r.id::text, r.code, r.status
    FROM eas.request r
    WHERE r.status IN ('COMPLETED','REJECTED','CANCELLED') AND (
      EXISTS (SELECT 1 FROM eas.sla_stage s WHERE s.request_id = r.id AND s.closed_at IS NULL)
      OR EXISTS (SELECT 1 FROM eas.approval_step s WHERE s.request_id = r.id
                 AND s.state IN ('ACTIVE','WAITING'))
      OR EXISTS (SELECT 1 FROM eas.workflow_instance i WHERE i.request_id = r.id
                 AND i.state = 'ACTIVE'))
    ORDER BY r.code
"""


def find_problems(cursor) -> tuple[list[tuple], list[tuple]]:
    cursor.execute(SQL_STUCK)
    stuck = cursor.fetchall()
    cursor.execute(SQL_ORPHANS)
    orphans = cursor.fetchall()
    return stuck, orphans


def repair_stuck(cursor, row: tuple, now: datetime) -> dict:
    request_id, code, instance_id, type_id, requester_id, department_id, sla = row
    cursor.execute(
        """
        SELECT id::text, step_no FROM eas.approval_step
        WHERE instance_id = %s AND state = 'WAITING'
        ORDER BY step_no LIMIT 1 FOR UPDATE
        """,
        [instance_id],
    )
    step_id, step_no = cursor.fetchone()
    cursor.execute(
        "UPDATE eas.approval_step SET state='ACTIVE', activated_at=%s WHERE id=%s",
        [now, step_id],
    )
    _substitute_approver(
        cursor,
        step_id=step_id,
        request_id=request_id,
        requester_id=requester_id,
        department_id=department_id,
        type_id=type_id,
        correlation_id=str(uuid.uuid4()),
    )
    # The step only becomes actionable now, so its SLA clock starts now: close
    # the stale stage (its breach stays recorded) and open a fresh one.
    cursor.execute(
        "UPDATE eas.sla_stage SET closed_at=%s WHERE request_id=%s AND closed_at IS NULL",
        [now, request_id],
    )
    hours = int((sla or {}).get("approval_hours") or 24)
    cursor.execute(
        """
        INSERT INTO eas.sla_stage(request_id,kind,approval_step_id,started_at,due_at)
        VALUES (%s,'APPROVAL',%s,%s,%s + make_interval(hours => %s))
        """,
        [request_id, step_id, now, now, hours],
    )
    _append_request_audit(
        cursor,
        request_id=request_id,
        actor_id=None,
        actor_kind="SYSTEM",
        action="DATA_REPAIR_STEP_ACTIVATED",
        target_type="approval_step",
        target_id=step_id,
        details={"step_no": step_no, "reason": "no ACTIVE step on PENDING_APPROVAL"},
        correlation_id=str(uuid.uuid4()),
        occurred_at=now,
    )
    return {"code": code, "action": "STEP_ACTIVATED", "step_no": step_no}


def repair_orphan(cursor, row: tuple, now: datetime) -> dict:
    request_id, code, status = row
    cursor.execute(
        "UPDATE eas.approval_step SET state='SKIPPED', closed_at=%s "
        "WHERE request_id=%s AND state IN ('ACTIVE','WAITING')",
        [now, request_id],
    )
    steps = cursor.rowcount
    cursor.execute(
        "UPDATE eas.workflow_instance SET state=%s, closed_at=%s "
        "WHERE request_id=%s AND state='ACTIVE'",
        [TERMINAL_INSTANCE_STATE[status], now, request_id],
    )
    instances = cursor.rowcount
    cursor.execute(
        "UPDATE eas.sla_stage SET closed_at=%s WHERE request_id=%s AND closed_at IS NULL",
        [now, request_id],
    )
    stages = cursor.rowcount
    _append_request_audit(
        cursor,
        request_id=request_id,
        actor_id=None,
        actor_kind="SYSTEM",
        action="DATA_REPAIR_TERMINAL_CLOSED",
        target_type="request",
        target_id=request_id,
        details={
            "status": status,
            "steps": steps,
            "instances": instances,
            "sla_stages": stages,
        },
        correlation_id=str(uuid.uuid4()),
        occurred_at=now,
    )
    return {
        "code": code,
        "action": "TERMINAL_CLOSED",
        "steps": steps,
        "sla_stages": stages,
    }


class Command(BaseCommand):
    help = (
        "Find (and with --apply repair) workflow rows that bypassed the service layer."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the repairs.")

    def handle(self, *args, **options):
        apply = options["apply"]
        now = datetime.now(timezone.utc)
        results: list[dict] = []
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(SQL_LOCK_SECURITY)
            stuck, orphans = find_problems(cursor)
            for row in stuck:
                self.stdout.write(f"STUCK   {row[1]}")
            for row in orphans:
                self.stdout.write(f"ORPHAN  {row[1]} ({row[2]})")
            if not apply:
                self.stdout.write(
                    f"dry-run: {len(stuck)} stuck, {len(orphans)} orphan. Re-run with --apply."
                )
                return
            results += [repair_stuck(cursor, row, now) for row in stuck]
            results += [repair_orphan(cursor, row, now) for row in orphans]
        for item in results:
            self.stdout.write(f"REPAIRED {item}")
        self.stdout.write(f"done: {len(results)} request(s) repaired.")
