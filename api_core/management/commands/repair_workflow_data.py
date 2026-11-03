"""Detect (and, only with explicit approval, repair) inconsistent workflow data.

Dry-run is the default and runs in a READ ONLY transaction. --apply needs:
  --operator <email>    active OPS_ADMIN who is recorded as the audit actor;
  --confirm <token>     the plan token printed by the dry-run (the plan must
                        not have changed since it was reviewed);
  --grant-ids a,b       for grant revocation, the exact grants whose holders'
                        organizational role the owner has confirmed.

Each item is repaired in its own transaction under the exclusive security
lock, its preconditions are re-checked with row locks, and the affected audit
chains are verified before commit. Already-repaired items are no longer
detected, so re-running is idempotent.

Repairs mirror normal service behaviour:
  * admin grant on a business manager -> revoke grant (revoked_at), bump the
    user's auth_version and the security epoch, admin audit event;
  * orphaned approval (previous steps approved, next step left WAITING with
    its SLA stage already open) -> activate that step at the stage start,
    request audit event, APPROVAL_REQUESTED notification;
  * terminal request with live steps / open SLA stages -> SKIPPED / closed at
    the request's terminal time, request audit event (like cancellation).

The database guards make step/SLA repairs one-way (SKIPPED and closed SLA
history are immutable, ACTIVE cannot return to WAITING). Rollback therefore
means compensating actions (Ops reassign/cancel; re-grant a role with a new
membership), which is why --apply must be rehearsed on staging first.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timezone
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.workflow.reporting import verify_audit_chain
from api_core.workflow.service import (
    SQL_NOT_ADMINISTRATIVE,
    _append_admin_audit,
    _append_request_audit,
)

ADMIN_ROLES = ("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")

SQL_ADMIN_GRANTS_ON_MANAGERS = """
    SELECT rm.id::text, rm.role, u.id::text, u.email, u.display_name,
      (SELECT count(*) FROM eas.app_user x WHERE x.manager_id = u.id AND x.is_active),
      (SELECT count(DISTINCT rt.code) FROM eas.request_type rt
         JOIN eas.config_release cr ON cr.id = rt.active_release_id
         CROSS JOIN LATERAL jsonb_each(cr.actor_bindings->'departments') dep(k, v)
         CROSS JOIN LATERAL jsonb_each_text(dep.v) slot(s, uid)
        WHERE slot.uid = u.id::text),
      (SELECT count(*) FROM eas.approval_step st
         JOIN eas.workflow_instance wi ON wi.id = st.instance_id
        WHERE st.assignee_id = u.id AND st.state IN ('ACTIVE','WAITING')
          AND wi.state = 'ACTIVE'),
      (SELECT count(*) FROM eas.execution_attempt ea
        WHERE ea.executor_id = u.id AND ea.state IN ('READY','RUNNING','SUBMITTED')),
      (SELECT count(*) FROM eas.role_membership o JOIN eas.app_user ou ON ou.id = o.user_id
        WHERE o.role = rm.role AND o.user_id <> u.id AND ou.is_active
          AND o.revoked_at IS NULL AND o.valid_from <= statement_timestamp()
          AND (o.valid_to IS NULL OR o.valid_to > statement_timestamp()))
    FROM eas.role_membership rm JOIN eas.app_user u ON u.id = rm.user_id
    WHERE rm.role IN ('OPS_ADMIN','POLICY_ADMIN','AUDITOR') AND u.is_active
      AND rm.revoked_at IS NULL AND rm.valid_from <= statement_timestamp()
      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
    ORDER BY u.email, rm.role
"""

SQL_ORPHANED_APPROVALS = f"""
    SELECT r.id::text, r.code, st.id::text, st.step_no, st.assignee_id::text,
           s.id::text, s.started_at,
           NOT EXISTS (SELECT 1 FROM eas.app_user u WHERE u.id = st.assignee_id
                       AND u.is_active {SQL_NOT_ADMINISTRATIVE})
    FROM eas.request r
    JOIN eas.workflow_instance wi
      ON wi.revision_id = r.current_revision_id AND wi.state = 'ACTIVE'
    JOIN LATERAL (
      SELECT * FROM eas.approval_step x
      WHERE x.instance_id = wi.id AND x.state = 'WAITING'
      ORDER BY x.step_no LIMIT 1
    ) st ON TRUE
    LEFT JOIN eas.sla_stage s
      ON s.approval_step_id = st.id AND s.closed_at IS NULL
    WHERE r.status = 'PENDING_APPROVAL'
      AND NOT EXISTS (SELECT 1 FROM eas.approval_step a
                      WHERE a.instance_id = wi.id AND a.state = 'ACTIVE')
      AND NOT EXISTS (
        SELECT 1 FROM eas.approval_step p
        WHERE p.instance_id = wi.id AND p.step_no < st.step_no
          AND (p.state <> 'APPROVED' OR NOT EXISTS (
                SELECT 1 FROM eas.approval_decision d
                WHERE d.step_id = p.id AND d.outcome = 'APPROVE')))
    ORDER BY r.code
"""

SQL_TERMINAL_WITH_LIVE_WORK = """
    SELECT r.id::text, r.code, r.status, r.updated_at,
      COALESCE((SELECT array_agg(st.id::text ORDER BY st.step_no) FROM eas.approval_step st
                WHERE st.request_id = r.id AND st.state IN ('WAITING','ACTIVE')), '{}'),
      COALESCE((SELECT array_agg(s.id::text ORDER BY s.started_at) FROM eas.sla_stage s
                WHERE s.request_id = r.id AND s.closed_at IS NULL), '{}')
    FROM eas.request r
    WHERE r.status IN ('CANCELLED','REJECTED','COMPLETED')
      AND (EXISTS (SELECT 1 FROM eas.approval_step st
                   WHERE st.request_id = r.id AND st.state IN ('WAITING','ACTIVE'))
        OR EXISTS (SELECT 1 FROM eas.sla_stage s
                   WHERE s.request_id = r.id AND s.closed_at IS NULL))
    ORDER BY r.code
"""


def detect(cursor) -> dict[str, list[dict]]:
    cursor.execute(SQL_ADMIN_GRANTS_ON_MANAGERS)
    grants = []
    for row in cursor.fetchall():
        (
            grant_id,
            role,
            user_id,
            email,
            name,
            reports,
            bound,
            steps,
            attempts,
            cover,
        ) = row
        evidence = {
            "direct_reports": reports,
            "bound_in_request_types": bound,
            "open_approval_steps": steps,
            "open_execution_attempts": attempts,
        }
        if any(evidence.values()):
            grants.append(
                {
                    "grant_id": grant_id,
                    "role": role,
                    "user_id": user_id,
                    "email": email,
                    "display_name": name,
                    "evidence": evidence,
                    "other_active_holders": cover,
                    "repairable": cover > 0,
                }
            )
    cursor.execute(SQL_ORPHANED_APPROVALS)
    orphans = [
        {
            "request_id": r[0],
            "code": r[1],
            "step_id": r[2],
            "step_no": r[3],
            "assignee_id": r[4],
            "stage_id": r[5],
            "activate_at": r[6].isoformat() if r[6] else None,
            "assignee_blocked": bool(r[7]),
            "repairable": r[5] is not None and not r[7],
        }
        for r in cursor.fetchall()
    ]
    cursor.execute(SQL_TERMINAL_WITH_LIVE_WORK)
    terminal = [
        {
            "request_id": r[0],
            "code": r[1],
            "status": r[2],
            "terminal_at": r[3].isoformat(),
            "step_ids": list(r[4]),
            "stage_ids": list(r[5]),
            "repairable": True,
        }
        for r in cursor.fetchall()
    ]
    return {
        "admin_grants": grants,
        "orphaned_approvals": orphans,
        "terminal_live_work": terminal,
    }


def plan_token(plan: dict) -> str:
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class Command(BaseCommand):
    help = "Dry-run (default) or apply approved repairs of inconsistent workflow data."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--operator", help="Email of the OPS_ADMIN performing --apply"
        )
        parser.add_argument("--confirm", help="Plan token printed by the dry-run")
        parser.add_argument(
            "--grant-ids", default="", help="Comma list of confirmed grant ids"
        )
        parser.add_argument(
            "--only",
            choices=["admin_grants", "orphaned_approvals", "terminal_live_work"],
            action="append",
        )

    def handle(self, *args, **options):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            plan = detect(cursor)
        token = plan_token(plan)
        self.stdout.write(
            json.dumps(
                {"plan": plan, "plan_token": token},
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        if not options["apply"]:
            self.stdout.write("DRY-RUN ONLY: no data changed.")
            return
        if options["confirm"] != token:
            raise CommandError(
                "Plan token mismatch: re-run the dry-run and review the new plan."
            )
        operator = self._operator(options["operator"])
        selected = set(options["only"] or plan)
        confirmed_grants = {g for g in options["grant_ids"].split(",") if g}
        results = []
        if "admin_grants" in selected:
            for item in plan["admin_grants"]:
                if item["grant_id"] in confirmed_grants and item["repairable"]:
                    results.append(self._revoke_grant(item, operator))
        if "orphaned_approvals" in selected:
            for item in plan["orphaned_approvals"]:
                if item["repairable"]:
                    results.append(self._activate_step(item, operator))
        if "terminal_live_work" in selected:
            for item in plan["terminal_live_work"]:
                results.append(self._close_terminal(item, operator))
        self.stdout.write(
            json.dumps({"applied": results}, indent=2, ensure_ascii=False)
        )

    def _operator(self, email: str | None) -> str:
        if not email:
            raise CommandError("--operator is required with --apply")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id::text FROM eas.app_user u JOIN eas.role_membership rm ON rm.user_id = u.id
                WHERE lower(u.email) = lower(%s) AND u.is_active AND rm.role = 'OPS_ADMIN'
                  AND rm.scope_kind = 'GLOBAL' AND rm.revoked_at IS NULL
                  AND rm.valid_from <= statement_timestamp()
                  AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                """,
                [email],
            )
            row = cursor.fetchone()
        if not row:
            raise CommandError("Operator must be an active GLOBAL OPS_ADMIN")
        return row[0]

    @staticmethod
    def _verify(scope_key: str) -> None:
        result = verify_audit_chain(scope_key)
        if result.get("status") != "PASS":
            raise CommandError(f"Audit chain check failed for {scope_key}: {result}")

    def _revoke_grant(self, item: dict, operator: str) -> dict:
        correlation = str(uuid4())
        with transaction.atomic(), connection.cursor() as c:
            c.execute("SELECT eas.lock_security(true)")
            c.execute(
                """
                SELECT user_id::text FROM eas.role_membership
                WHERE id = %s AND revoked_at IS NULL FOR UPDATE
                """,
                [item["grant_id"]],
            )
            if not c.fetchone():
                return {"grant_id": item["grant_id"], "result": "ALREADY_REVOKED"}
            if item["user_id"] == operator:
                raise CommandError("Operator cannot revoke their own grant")
            # Coverage is re-checked now: earlier revocations in this run count.
            c.execute(
                """
                SELECT count(*) FROM eas.role_membership o JOIN eas.app_user ou ON ou.id = o.user_id
                WHERE o.role = %s AND o.user_id <> %s AND ou.is_active
                  AND o.revoked_at IS NULL AND o.valid_from <= statement_timestamp()
                  AND (o.valid_to IS NULL OR o.valid_to > statement_timestamp())
                """,
                [item["role"], item["user_id"]],
            )
            if c.fetchone()[0] == 0:
                return {
                    "grant_id": item["grant_id"],
                    "result": "NO_REPLACEMENT_COVERAGE",
                }
            c.execute(
                "UPDATE eas.role_membership SET revoked_at = statement_timestamp() WHERE id = %s",
                [item["grant_id"]],
            )
            c.execute(
                "UPDATE eas.app_user SET auth_version = auth_version + 1 WHERE id = %s",
                [item["user_id"]],
            )
            c.execute(
                "UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1"
            )
            _append_admin_audit(
                c,
                actor_id=operator,
                action="REPAIR_ADMIN_GRANT_REVOKED",
                target_type="role_membership",
                target_id=item["grant_id"],
                details={
                    "role": item["role"],
                    "user_id": item["user_id"],
                    "evidence": item["evidence"],
                },
                reason="Owner-approved repair: administrative grant held by a business manager.",
                correlation_id=correlation,
            )
            self._verify("ADMIN")
        return {"grant_id": item["grant_id"], "result": "REVOKED"}

    def _activate_step(self, item: dict, operator: str) -> dict:
        correlation = str(uuid4())
        with transaction.atomic(), connection.cursor() as c:
            c.execute("SELECT eas.lock_security(false)")
            c.execute(
                "SELECT status FROM eas.request WHERE id = %s FOR UPDATE",
                [item["request_id"]],
            )
            c.execute(
                """
                SELECT st.state, s.started_at FROM eas.approval_step st
                JOIN eas.sla_stage s ON s.approval_step_id = st.id AND s.closed_at IS NULL
                WHERE st.id = %s FOR UPDATE OF st
                """,
                [item["step_id"]],
            )
            row = c.fetchone()
            if not row or row[0] != "WAITING":
                return {"code": item["code"], "result": "NO_LONGER_ORPHANED"}
            activated_at = row[1]
            c.execute(
                "UPDATE eas.approval_step SET state = 'ACTIVE', activated_at = %s WHERE id = %s AND state = 'WAITING'",
                [activated_at, item["step_id"]],
            )
            _append_request_audit(
                c,
                request_id=item["request_id"],
                actor_id=operator,
                action="REPAIR_APPROVAL_STEP_ACTIVATED",
                target_type="approval_step",
                target_id=item["step_id"],
                details={
                    "step_no": item["step_no"],
                    "activated_at": activated_at.isoformat(),
                    "stage_id": item["stage_id"],
                },
                correlation_id=correlation,
            )
            c.execute(
                """
                INSERT INTO eas.outbox_event(request_id, event_type, payload, dedupe_key)
                VALUES (%s, 'APPROVAL_REQUESTED', %s, %s) ON CONFLICT DO NOTHING
                """,
                [
                    item["request_id"],
                    Jsonb(
                        {"request_id": item["request_id"], "step_id": item["step_id"]}
                    ),
                    f"repair:{item['step_id']}:approval-requested",
                ],
            )
            self._verify(f"REQ:{item['request_id']}")
        return {
            "code": item["code"],
            "result": "STEP_ACTIVATED",
            "step_id": item["step_id"],
        }

    def _close_terminal(self, item: dict, operator: str) -> dict:
        correlation = str(uuid4())
        with transaction.atomic(), connection.cursor() as c:
            c.execute("SELECT eas.lock_security(false)")
            c.execute(
                "SELECT status, updated_at FROM eas.request WHERE id = %s FOR UPDATE",
                [item["request_id"]],
            )
            status, terminal_at = c.fetchone()
            if status not in ("CANCELLED", "REJECTED", "COMPLETED"):
                return {"code": item["code"], "result": "NOT_TERMINAL"}
            c.execute(
                """
                UPDATE eas.approval_step
                SET state = 'SKIPPED', closed_at = GREATEST(%s, COALESCE(activated_at, %s))
                WHERE request_id = %s AND state IN ('WAITING','ACTIVE')
                RETURNING id::text
                """,
                [terminal_at, terminal_at, item["request_id"]],
            )
            steps = [r[0] for r in c.fetchall()]
            c.execute(
                """
                UPDATE eas.sla_stage SET closed_at = GREATEST(%s, started_at)
                WHERE request_id = %s AND closed_at IS NULL
                RETURNING id::text
                """,
                [terminal_at, item["request_id"]],
            )
            stages = [r[0] for r in c.fetchall()]
            if not steps and not stages:
                return {"code": item["code"], "result": "ALREADY_CLEAN"}
            _append_request_audit(
                c,
                request_id=item["request_id"],
                actor_id=operator,
                action="REPAIR_TERMINAL_WORK_CLOSED",
                target_type="request",
                target_id=item["request_id"],
                details={
                    "status": status,
                    "skipped_steps": steps,
                    "closed_sla_stages": stages,
                    "closed_at": terminal_at.astimezone(timezone.utc).isoformat(),
                },
                correlation_id=correlation,
            )
            self._verify(f"REQ:{item['request_id']}")
        return {
            "code": item["code"],
            "result": "CLOSED",
            "steps": steps,
            "stages": stages,
        }
