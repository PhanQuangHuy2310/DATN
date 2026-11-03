"""Read models for request progress, route preview, team reporting, org chart
and persisted AI assessments.

Every query here reuses the documented read predicate (UC05/UC15): a person
sees a request when they own it, participate in it, or hold an AUDITOR grant
matching its department/type snapshot. Nothing in this module widens that
scope, and only the AI assessment command writes (an append-only audit event).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from django.db import connection, transaction

from api_core.authn.models import Actor
from api_core.domain import resolve_route
from api_core.domain.delegation import apply_delegations
from api_core.domain.routing import (
    RoutingError,
    SodEscalationError,
    extract_amount_vnd,
)
from api_core.workflow.constants import ERR_REQUEST_NOT_FOUND
from api_core.workflow.service import (
    SQL_LOCK_SECURITY,
    CommandError,
    _active_delegations,
    _append_request_audit,
    _approver_eligibility,
    _manager_chain,
    approval_delegation_enabled,
    check_resources,
)

# Aliases required by READ_SCOPE_SQL: r=request, v=current revision, u=requester.
READ_SCOPE_SQL = """
    (
      r.requester_id = %s
      OR (r.status != 'DRAFT' AND EXISTS (
        SELECT 1 FROM eas.request_participant rp
        WHERE rp.request_id = r.id AND rp.user_id = %s AND rp.read_revoked_at IS NULL
      ))
      OR (r.status != 'DRAFT' AND EXISTS (
        SELECT 1 FROM eas.role_membership aud
        WHERE aud.user_id = %s AND aud.role = 'AUDITOR' AND aud.revoked_at IS NULL
          AND aud.valid_from <= statement_timestamp()
          AND (aud.valid_to IS NULL OR aud.valid_to > statement_timestamp())
          AND (aud.scope_kind = 'GLOBAL' OR aud.department_id = COALESCE(v.department_id, u.department_id))
          AND (aud.type_scope = 'ALL' OR aud.type_id = r.type_id)
      ))
    )
"""

STAGE_BY_STATUS = {
    "DRAFT": "DRAFT",
    "NEEDS_INFO": "REVISION",
    "PENDING_APPROVAL": "APPROVAL",
    "READY_FOR_EXECUTION": "EXECUTION",
    "IN_PROGRESS": "EXECUTION",
    "WAITING_FOR_ACCEPTANCE": "ACCEPTANCE",
    "COMPLETED": "CLOSED",
    "REJECTED": "CLOSED",
    "CANCELLED": "CLOSED",
}
AI_ASSESSMENT_ACTION = "AI_ASSESSMENT_RECORDED"
OPEN_STATUSES = (
    "NEEDS_INFO",
    "PENDING_APPROVAL",
    "READY_FOR_EXECUTION",
    "IN_PROGRESS",
    "WAITING_FOR_ACCEPTANCE",
)


def _uuid(value: Any, code: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise CommandError(code, status=400) from None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _parse_period(params: dict[str, str]) -> tuple[datetime, datetime]:
    try:
        start = datetime.fromisoformat(params["created_from"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(params["created_to"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        raise CommandError("PERIOD_INVALID", status=422) from None
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or end <= start
        or (end - start).total_seconds() > 366 * 86400
    ):
        raise CommandError("PERIOD_INVALID", status=422)
    return start, end


# ---------------------------------------------------------------------------
# Request progress (current/next actor, decisions, SLA deadline)
# ---------------------------------------------------------------------------


def build_request_progress(
    cursor,
    *,
    request_id: str,
    status: str,
    steps: list[dict[str, Any]],
    workflow: dict[str, Any] | None,
    requester_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return display-ready progress for a request the caller may already read."""
    cursor.execute(
        """
        SELECT ru.display_name, rt.name, d.name,
          (SELECT COALESCE(json_agg(json_build_object(
              'kind', 'APPROVAL', 'revision_no', rv.revision_no, 'step_no', s.step_no,
              'resolver_code', s.resolver_code, 'outcome', ad.outcome, 'reason', ad.reason,
              'decided_at', ad.decided_at, 'actor_name', au.display_name)
              ORDER BY ad.decided_at), '[]'::json)
             FROM eas.approval_decision ad
             JOIN eas.approval_step s ON s.id = ad.step_id
             JOIN eas.workflow_instance wi ON wi.id = s.instance_id
             JOIN eas.request_revision rv ON rv.id = wi.revision_id
             JOIN eas.app_user au ON au.id = ad.actor_id
            WHERE ad.request_id = r.id),
          (SELECT COALESCE(json_agg(json_build_object(
              'kind', 'ACCEPTANCE', 'attempt_no', ea.attempt_no, 'outcome', acc.outcome,
              'reason', acc.reason, 'decided_at', acc.decided_at,
              'actor_name', au.display_name) ORDER BY acc.decided_at), '[]'::json)
             FROM eas.acceptance_decision acc
             JOIN eas.execution_attempt ea ON ea.id = acc.attempt_id
             JOIN eas.app_user au ON au.id = acc.actor_id
            WHERE acc.request_id = r.id),
          (SELECT json_build_object('kind', st.kind, 'started_at', st.started_at,
                                    'due_at', st.due_at)
             FROM eas.sla_stage st
            WHERE st.request_id = r.id AND st.closed_at IS NULL
            ORDER BY st.started_at DESC LIMIT 1),
          (SELECT COALESCE(json_object_agg(x.id::text, x.display_name), '{}'::json)
             FROM eas.app_user x
            WHERE x.id IN (
              SELECT wi.planned_executor_id FROM eas.workflow_instance wi
               WHERE wi.revision_id = r.current_revision_id
              UNION SELECT wi.acceptor_id FROM eas.workflow_instance wi
               WHERE wi.revision_id = r.current_revision_id
              UNION SELECT ea.executor_id FROM eas.execution_attempt ea
                JOIN eas.workflow_instance wi ON wi.id = ea.instance_id
               WHERE wi.revision_id = r.current_revision_id))
        FROM eas.request r
        JOIN eas.app_user ru ON ru.id = r.requester_id
        JOIN eas.request_type rt ON rt.id = r.type_id
        LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
        LEFT JOIN eas.department d ON d.id = COALESCE(v.department_id, ru.department_id)
        WHERE r.id = %s
        """,
        [request_id],
    )
    row = cursor.fetchone() or (None, None, None, [], [], None, {})
    requester_name, type_name, department_name = row[0], row[1], row[2]
    decisions = sorted(
        [*(row[3] or []), *(row[4] or [])],
        key=lambda item: str(item.get("decided_at") or ""),
    )
    sla = row[5]

    names: dict[str, str] = dict(row[6] or {}) if len(row) > 6 else {}

    def person(user_id: str | None, role: str, resolver: str | None = None):
        if not user_id:
            return None
        return {
            "id": user_id,
            "name": names.get(user_id),
            "role": role,
            "resolver_code": resolver,
        }

    for step in steps:
        names.setdefault(step["assignee_id"], step.get("assignee_name"))

    stage = STAGE_BY_STATUS.get(status, "CLOSED")
    lifecycle = (workflow or {}).get("lifecycle")
    attempt = (workflow or {}).get("attempt") or {}
    executor_id = attempt.get("executor_id") or (workflow or {}).get(
        "planned_executor_id"
    )
    acceptor = person((workflow or {}).get("acceptor_id"), "ACCEPTOR")
    executor = person(executor_id, "EXECUTOR")
    current = None
    following = None
    if stage == "APPROVAL":
        active = next((s for s in steps if s["state"] == "ACTIVE"), None)
        waiting = [s for s in steps if s["state"] == "WAITING"]
        if active:
            current = person(
                active["assignee_id"], "APPROVER", active.get("resolver_code")
            )
        if waiting:
            nxt = waiting[0]
            following = person(nxt["assignee_id"], "APPROVER", nxt.get("resolver_code"))
        elif lifecycle in ("B", "C"):
            following = executor
    elif stage == "EXECUTION":
        current = executor
        following = acceptor if lifecycle == "C" else None
    elif stage == "ACCEPTANCE":
        current = acceptor
    elif stage in ("REVISION", "DRAFT"):
        current = {
            "id": requester_id,
            "name": requester_name,
            "role": "REQUESTER",
            "resolver_code": None,
        }

    deadline = None
    if sla and stage not in ("CLOSED", "DRAFT"):
        due_at = sla.get("due_at")
        due = datetime.fromisoformat(str(due_at)) if due_at else None
        now = now or datetime.now(timezone.utc)
        remaining = int((due - now).total_seconds()) if due else None
        deadline = {
            "kind": sla.get("kind"),
            "started_at": sla.get("started_at"),
            "due_at": due_at,
            "remaining_seconds": remaining,
            "overdue": remaining is not None and remaining < 0,
        }

    return {
        "stage": stage,
        "requester_name": requester_name,
        "type_name": type_name,
        "department_name": department_name,
        "current_assignee": current,
        "next_assignee": following,
        "executor": executor,
        "acceptor": acceptor,
        "deadline": deadline,
        "decisions": decisions,
    }


# ---------------------------------------------------------------------------
# Approval route preview (read-only; same resolver as submit)
# ---------------------------------------------------------------------------


def preview_route(actor: Actor, body: dict[str, Any]) -> dict[str, Any]:
    type_code = body.get("type_code")
    if not isinstance(type_code, str) or not type_code.strip():
        raise CommandError("TYPE_CODE_REQUIRED", status=400)
    payload = body.get("payload") or {}
    if not isinstance(payload, dict):
        raise CommandError("INVALID_PAYLOAD", status=400)
    try:
        amount = extract_amount_vnd(payload, body.get("amount_vnd"), allow_zero=True)
    except (TypeError, ValueError):
        amount = None

    # Read-only by construction: only SELECTs, no lock_security, no audit.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT rt.id::text, rt.lifecycle, cr.id::text, cr.route_rules,
                   cr.actor_bindings, cr.sla_profile, u.manager_id::text
            FROM eas.request_type rt
            JOIN eas.config_release cr ON cr.id = rt.active_release_id
            JOIN eas.app_user u ON u.id = %s
            WHERE rt.code = %s AND rt.is_active AND cr.state = 'PUBLISHED'
              AND cr.type_id = rt.id AND cr.lifecycle = rt.lifecycle
            """,
            [actor.id, type_code.strip()],
        )
        config = cursor.fetchone()
        if not config:
            raise CommandError("REQUEST_TYPE_NOT_CONFIGURED", status=409)
        type_id, lifecycle, release_id, rules, bindings, sla, manager_id = config
        try:
            decision = resolve_route(
                route_rules=rules,
                actor_bindings=bindings,
                department_id=actor.department_id,
                requester_id=actor.id,
                manager_id=manager_id,
                amount_vnd=amount,
                payload=payload,
                manager_chain=_manager_chain(cursor, actor.id),
                is_eligible=_approver_eligibility(
                    cursor, department_id=actor.department_id, type_id=type_id
                ),
            )
        except RoutingError as exc:
            # Same outcome submit would report; nothing is persisted.
            return {
                "type_code": type_code,
                "release_id": release_id,
                "lifecycle": lifecycle,
                "resolvable": False,
                "problem": "ROUTE_SOD_ESCALATION_UNRESOLVED"
                if isinstance(exc, SodEscalationError)
                else "ROUTE_CONFIGURATION_INVALID",
                "steps": [],
            }

        if approval_delegation_enabled():
            decision = apply_delegations(
                decision,
                requester_id=actor.id,
                delegations=_active_delegations(
                    cursor,
                    decision.approver_ids,
                    department_id=actor.department_id,
                    type_id=type_id,
                ),
                is_eligible=_approver_eligibility(
                    cursor, department_id=actor.department_id, type_id=type_id
                ),
            )
        ids = {*decision.approver_ids}
        ids.update(i for i in (decision.executor_id, decision.acceptor_id) if i)
        # Same grant predicate as submit's _authorize, batched in one round trip.
        cursor.execute(
            """
            SELECT u.id::text, u.display_name, u.is_active,
                   COALESCE(array_agg(DISTINCT rm.role)
                            FILTER (WHERE rm.role IS NOT NULL), '{}'),
                   EXISTS (
                     SELECT 1 FROM eas.role_membership adm
                     WHERE adm.user_id = u.id
                       AND adm.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR')
                       AND adm.revoked_at IS NULL
                       AND adm.valid_from <= statement_timestamp()
                       AND (adm.valid_to IS NULL OR adm.valid_to > statement_timestamp())
                   )
            FROM eas.app_user u
            LEFT JOIN eas.role_membership rm
              ON rm.user_id = u.id
             AND rm.role IN ('APPROVER', 'EXECUTOR', 'ACCEPTOR')
             AND rm.revoked_at IS NULL
             AND rm.valid_from <= statement_timestamp()
             AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
             AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = %s)
             AND (rm.type_scope = 'ALL' OR rm.type_id = %s)
            WHERE u.id = ANY(%s::uuid[])
            GROUP BY u.id, u.display_name, u.is_active
            """,
            [actor.department_id, type_id, sorted(ids)],
        )
        users = {
            row[0]: (
                row[1],
                row[2],
                set(row[3]),
                bool(row[4]) if len(row) > 4 else False,
            )
            for row in cursor.fetchall()
        }

        def entry(user_id: str, role: str, slot: str | None, level: int | None):
            name, active, roles, administrative = users.get(
                user_id, (None, False, set(), False)
            )
            # Mirrors submit: administrative identities cannot hold business work.
            authorized = bool(active) and role in roles and not administrative
            return {
                "level": level,
                "role": role,
                "resolver_code": slot,
                "assignee_id": user_id,
                "assignee_name": name,
                "authorized": authorized,
            }

        escalated = {e["step_no"] for e in decision.escalations}
        delegated = {d["step_no"] for d in decision.delegations}
        steps = [
            {
                **entry(user_id, "APPROVER", slot, index),
                "sod_escalated": index in escalated,
                "delegated": index in delegated,
            }
            for index, (user_id, slot) in enumerate(
                zip(decision.approver_ids, decision.approver_slots, strict=True), 1
            )
        ]
        if decision.executor_id:
            steps.append(
                entry(decision.executor_id, "EXECUTOR", rules.get("executor"), None)
            )
        if decision.acceptor_id:
            steps.append(
                entry(decision.acceptor_id, "ACCEPTOR", rules.get("acceptor"), None)
            )

        resource_checks = [
            c.as_dict()
            for c in check_resources(
                cursor,
                actor_id=actor.id,
                department_id=actor.department_id,
                type_code=type_code.strip(),
                payload=payload,
                amount=amount,
            )
        ]

    problem = None if all(s["authorized"] for s in steps) else "ROUTE_ACTOR_INACTIVE"
    return {
        "type_code": type_code,
        "release_id": release_id,
        "lifecycle": lifecycle,
        "matched_rule_id": decision.matched_rule_id,
        "resolvable": problem is None,
        "problem": problem,
        "steps": steps,
        "resource_checks": resource_checks,
        "sla_hours": {
            "approval": sla.get("approval_hours"),
            "execution": sla.get("execution_hours"),
            "acceptance": sla.get("acceptance_hours"),
        },
    }


# ---------------------------------------------------------------------------
# Team / department report (scoped to the documented read predicate)
# ---------------------------------------------------------------------------


def team_report(actor: Actor, params: dict[str, str]) -> dict[str, Any]:
    if not {"APPROVER", "AUDITOR"} & set(actor.roles):
        raise CommandError("FORBIDDEN", status=403)
    start, end = _parse_period(params)
    dept = params.get("department_id") or None
    dept = _uuid(dept, "INVALID_DEPARTMENT_ID") if dept else None

    sql = f"""
        WITH scoped AS (
          SELECT r.id, r.status, r.requester_id, r.created_at, r.approved_at,
                 r.completed_at, COALESCE(v.department_id, u.department_id) AS dept_id,
                 (SELECT min(fr.submitted_at) FROM eas.request_revision fr
                   WHERE fr.request_id = r.id) AS first_submitted,
                 EXISTS (SELECT 1 FROM eas.sla_stage s
                          WHERE s.request_id = r.id AND s.closed_at IS NULL
                            AND s.due_at < statement_timestamp()) AS overdue,
                 EXISTS (SELECT 1 FROM eas.approval_step st
                          JOIN eas.workflow_instance wi ON wi.id = st.instance_id
                          WHERE st.request_id = r.id AND st.state = 'ACTIVE'
                            AND st.assignee_id = %s AND wi.state = 'ACTIVE'
                            AND wi.revision_id = r.current_revision_id) AS awaiting_me
          FROM eas.request r
          JOIN eas.app_user u ON u.id = r.requester_id
          LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
          WHERE r.status != 'DRAFT' AND r.requester_id <> %s
            AND r.created_at >= %s AND r.created_at <= %s
            AND (%s::uuid IS NULL OR COALESCE(v.department_id, u.department_id) = %s::uuid)
            AND {READ_SCOPE_SQL}
        )
        SELECT s.dept_id::text, d.name, s.requester_id::text, ru.display_name,
               COUNT(*)::integer,
               COUNT(*) FILTER (WHERE s.status IN ('PENDING_APPROVAL','NEEDS_INFO'))::integer,
               COUNT(*) FILTER (WHERE s.status IN
                 ('READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE'))::integer,
               COUNT(*) FILTER (WHERE s.status = 'COMPLETED')::integer,
               COUNT(*) FILTER (WHERE s.status = 'REJECTED')::integer,
               COUNT(*) FILTER (WHERE s.status = 'CANCELLED')::integer,
               COUNT(*) FILTER (WHERE s.overdue)::integer,
               COUNT(*) FILTER (WHERE s.awaiting_me)::integer,
               AVG(EXTRACT(EPOCH FROM (s.completed_at - s.first_submitted)))
                 FILTER (WHERE s.status = 'COMPLETED'),
               AVG(EXTRACT(EPOCH FROM (s.approved_at - s.first_submitted)))
                 FILTER (WHERE s.approved_at IS NOT NULL)
        FROM scoped s
        JOIN eas.department d ON d.id = s.dept_id
        JOIN eas.app_user ru ON ru.id = s.requester_id
        GROUP BY s.dept_id, d.name, s.requester_id, ru.display_name
        ORDER BY d.name, ru.display_name
        LIMIT 1000
    """
    with connection.cursor() as cursor:
        # NOSONAR python:S2077 - fragments are constants; values are parameters
        cursor.execute(
            sql,
            [actor.id, actor.id, start, end, dept, dept, actor.id, actor.id, actor.id],
        )
        rows = cursor.fetchall()

    def hours(seconds):
        return None if seconds is None else round(float(seconds) / 3600, 1)

    employees = []
    departments: dict[str, dict[str, Any]] = {}
    totals = dict.fromkeys(
        (
            "total",
            "pending",
            "in_progress",
            "completed",
            "rejected",
            "cancelled",
            "overdue",
            "awaiting_me",
        ),
        0,
    )
    for row in rows:
        counts = dict(zip(totals, row[4:12], strict=True))
        employees.append(
            {
                "department_id": row[0],
                "department_name": row[1],
                "requester_id": row[2],
                "requester_name": row[3],
                **counts,
                "avg_completion_hours": hours(row[12]),
                "avg_approval_hours": hours(row[13]),
            }
        )
        bucket = departments.setdefault(
            row[0],
            {
                "department_id": row[0],
                "department_name": row[1],
                "employees": 0,
                **dict.fromkeys(totals, 0),
            },
        )
        bucket["employees"] += 1
        for key, value in counts.items():
            bucket[key] += value
            totals[key] += value

    return {
        "report": {
            "period": {"from": start.isoformat(), "to": end.isoformat()},
            "scope": "participant_or_auditor",
            "totals": totals,
            "departments": sorted(
                departments.values(), key=lambda item: item["department_name"]
            ),
            "employees": employees,
        }
    }


# ---------------------------------------------------------------------------
# Organization chart
# ---------------------------------------------------------------------------


def org_chart(actor: Actor) -> dict[str, Any]:
    """Departments are always listed (names only). People are visible for the
    whole organization to GLOBAL OPS_ADMIN/AUDITOR; everyone else sees their own
    department plus their upward management chain, matching the existing
    department-scoped colleague directory."""
    # One round trip: Supabase latency dominates, so scope check, department
    # list and visible people are resolved together.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE wide AS (
              SELECT EXISTS (
                SELECT 1 FROM eas.role_membership
                WHERE user_id = %s AND role IN ('OPS_ADMIN', 'AUDITOR')
                  AND scope_kind = 'GLOBAL' AND revoked_at IS NULL
                  AND valid_from <= statement_timestamp()
                  AND (valid_to IS NULL OR valid_to > statement_timestamp())
              ) AS ok
            ), chain AS (
              SELECT manager_id FROM eas.app_user WHERE id = %s
              UNION
              SELECT m.manager_id FROM eas.app_user m JOIN chain c ON m.id = c.manager_id
            )
            SELECT (SELECT ok FROM wide),
              (SELECT COALESCE(json_agg(json_build_object(
                  'id', d.id, 'code', d.code, 'name', d.name, 'parent_id', d.parent_id,
                  'member_count', (SELECT COUNT(*) FROM eas.app_user x
                                    WHERE x.department_id = d.id AND x.is_active))
                  ORDER BY d.name), '[]'::json)
                 FROM eas.department d WHERE d.is_active),
              (SELECT COALESCE(json_agg(json_build_object(
                  'id', u.id, 'display_name', u.display_name,
                  'department_id', u.department_id, 'manager_id', u.manager_id)
                  ORDER BY u.display_name, u.id), '[]'::json)
                 FROM eas.app_user u
                WHERE u.is_active
                  AND ((SELECT ok FROM wide) OR u.department_id = %s
                       OR u.id IN (SELECT manager_id FROM chain
                                    WHERE manager_id IS NOT NULL)))
            """,
            [actor.id, actor.id, actor.department_id],
        )
        organization_wide, departments, people = cursor.fetchone()
    organization_wide = bool(organization_wide)
    departments = list(departments or [])
    people = list(people or [])
    visible = {p["id"] for p in people}
    for p in people:
        # Never leak the identity of a manager outside the visible set.
        if p["manager_id"] not in visible:
            p["manager_id"] = None
    return {
        "scope": "organization" if organization_wide else "department",
        "departments": departments,
        "users": people,
    }


# ---------------------------------------------------------------------------
# Persisted AI assessment
# ---------------------------------------------------------------------------


def _readable_request(cursor, actor: Actor, request_id: str):
    cursor.execute(
        f"""
        SELECT r.id::text, r.code, r.status, r.requester_id::text, rt.code, rt.name,
               rt.lifecycle, COALESCE(v.risk_weight, r.risk_weight, rt.risk_weight),
               COALESCE(v.payload, r.draft_payload), COALESCE(v.amount_vnd, r.draft_amount_vnd),
               d.name, cr.form_schema,
               (SELECT COUNT(*) FROM eas.revision_attachment ra
                 WHERE ra.revision_id = r.current_revision_id)::integer
        FROM eas.request r
        JOIN eas.request_type rt ON rt.id = r.type_id
        JOIN eas.app_user u ON u.id = r.requester_id
        LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
        LEFT JOIN eas.department d ON d.id = COALESCE(v.department_id, u.department_id)
        LEFT JOIN eas.config_release cr ON cr.id = COALESCE(v.release_id, rt.active_release_id)
        WHERE r.id = %s AND {READ_SCOPE_SQL}
        """,
        [request_id, actor.id, actor.id, actor.id],
    )
    row = cursor.fetchone()
    if not row:
        raise CommandError(ERR_REQUEST_NOT_FOUND, status=404)
    return row


def _describe_payload(payload: dict[str, Any]) -> str:
    parts = []
    for key, value in (payload or {}).items():
        if isinstance(value, (str, int, float)) and str(value).strip():
            parts.append(f"{key}: {value}")
    return "; ".join(parts)[:4000]


def run_ai_assessment(actor: Actor, request_id: str, cid: str) -> dict[str, Any]:
    """Analyse a stored request and append the result to its audit chain.

    The AI never decides: the stored recommendation is advisory and the
    approval step remains with the assigned human approver.
    """
    from api_core.integrations.ai_service import ai_client_sync

    request_id = _uuid(request_id, "INVALID_REQUEST_ID")
    with connection.cursor() as cursor:
        row = _readable_request(cursor, actor, request_id)
    (
        _id,
        code,
        status,
        _requester_id,
        type_code,
        type_name,
        lifecycle,
        risk_weight,
        payload,
        amount,
        department_name,
        form_schema,
        attachment_count,
    ) = row
    if status == "DRAFT":
        # Drafts have no submitted revision to assess or audit.
        raise CommandError("STATE_CONFLICT", status=409)
    payload = payload or {}
    started = datetime.now(timezone.utc)
    stages: list[dict[str, Any]] = [{"key": "RECEIVED", "status": "DONE"}]

    required = list((form_schema or {}).get("required") or [])
    missing = [name for name in required if payload.get(name) in (None, "", [], {})]
    stages.append(
        {
            "key": "VALIDATING",
            "status": "DONE" if not missing else "WARNING",
            "missing_fields": missing,
        }
    )
    stages.append(
        {
            "key": "OCR",
            "status": "NOT_APPLICABLE" if not attachment_count else "NOT_RUN",
            "detail": None
            if not attachment_count
            else "Tệp đính kèm chưa được gửi tới OCR trong luồng này.",
        }
    )

    description = _describe_payload(payload)
    classification = ai_client_sync.classify_request(
        title=f"{type_name} {code}", description=description, correlation_id=cid
    )
    stages.append(
        {
            "key": "CLASSIFICATION",
            "status": "FALLBACK" if classification.get("fallback_used") else "DONE",
            "predicted_request_type": classification.get("predicted_request_type"),
            "predicted_department": classification.get("predicted_department"),
            "confidence": classification.get("confidence_request_type"),
            "method": classification.get("method"),
        }
    )

    risk = ai_client_sync.score_risk(
        request_type=type_code,
        lifecycle_template=lifecycle,
        risk_weight=int(risk_weight or 3),
        amount_vnd=float(amount or 0),
        num_attachments=int(attachment_count or 0),
        description_length=len(description),
        correlation_id=cid,
    )
    risk_score = risk.get("risk_score")
    stages.append(
        {
            "key": "RISK_ANALYSIS",
            "status": "FALLBACK" if risk.get("fallback_used") else "DONE",
            "risk_score": risk_score,
            "risk_label": risk.get("risk_label"),
            "confidence": risk.get("confidence"),
        }
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT s.step_no, s.state, s.resolver_code, u.display_name
            FROM eas.approval_step s
            JOIN eas.workflow_instance wi ON wi.id = s.instance_id
            JOIN eas.request r ON r.id = s.request_id
            JOIN eas.app_user u ON u.id = s.assignee_id
            WHERE s.request_id = %s AND wi.revision_id = r.current_revision_id
            ORDER BY s.step_no
            """,
            [request_id],
        )
        route = [
            {"level": r[0], "state": r[1], "resolver_code": r[2], "assignee_name": r[3]}
            for r in cursor.fetchall()
        ]
    stages.append(
        {
            "key": "ROUTING",
            "status": "DONE" if route else "NOT_AVAILABLE",
            "route": route,
        }
    )

    if classification.get("fallback_used") and risk.get("fallback_used"):
        # Service is unreachable: one more timeout would only push the request
        # past the WSGI worker timeout without producing a real recommendation.
        advice = {"decision": None, "fallback_used": True}
    else:
        advice = ai_client_sync.evaluate_auto_approve(
            request_id=request_id,
            request_type=type_code,
            lifecycle_template=lifecycle,
            risk_score=int(risk_score or risk_weight or 3),
            requester_name="",
            requester_dept=department_name or "",
            amount=float(amount or 0),
            correlation_id=cid,
        )
    fallback = bool(advice.get("fallback_used")) or advice.get("decision") is None
    reasons = [advice["reason"]] if advice.get("reason") else []
    reasons += list(advice.get("detail_reasons") or [])
    if missing:
        reasons = [f"Thiếu trường bắt buộc: {', '.join(missing)}", *reasons]
    stages.append(
        {
            "key": "RECOMMENDATION",
            "status": "FALLBACK" if fallback else "DONE",
            # /ai/auto-approve/evaluate applies documented business rules; it is
            # not a trained model, so say so instead of implying ML output.
            "method": "unavailable" if fallback else "rule_based",
            "decision": advice.get("decision") or "escalate_to_human",
            "reasons": [str(item)[:300] for item in reasons][:8],
        }
    )
    stages.append(
        {
            "key": "HUMAN_REVIEW",
            "status": "PENDING" if status == "PENDING_APPROVAL" else "DONE",
        }
    )
    stages.append(
        {
            "key": "DECISION",
            "status": "PENDING" if status in OPEN_STATUSES else "DONE",
            "request_status": status,
        }
    )
    any_fallback = any(stage["status"] == "FALLBACK" for stage in stages)
    details = {
        "stages": stages,
        "fallback_used": any_fallback,
        "model_versions": {
            "classification": classification.get("model_version"),
            "risk": risk.get("model_version"),
        },
        "advisory_only": True,
        "duration_ms": int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        ),
    }
    # The AI calls run outside the transaction so a slow model never holds
    # row/audit locks; only the append happens under the security lock.
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(SQL_LOCK_SECURITY)
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action=AI_ASSESSMENT_ACTION,
            target_type="request",
            target_id=request_id,
            details=details,
            correlation_id=cid,
        )
    return {
        "assessment": {
            **details,
            "requested_by": actor.id,
            "occurred_at": started.isoformat(),
        }
    }


def list_ai_assessments(actor: Actor, request_id: str) -> dict[str, Any]:
    request_id = _uuid(request_id, "INVALID_REQUEST_ID")
    with connection.cursor() as cursor:
        _readable_request(cursor, actor, request_id)
        cursor.execute(
            """
            SELECT a.id::text, a.occurred_at, a.details, u.display_name
            FROM eas.audit_event a
            LEFT JOIN eas.app_user u ON u.id = a.actor_id
            WHERE a.request_id = %s AND a.action = %s
            ORDER BY a.seq DESC LIMIT 20
            """,
            [request_id, AI_ASSESSMENT_ACTION],
        )
        items = [
            {
                "id": r[0],
                "occurred_at": _iso(r[1]),
                "requested_by_name": r[3],
                **(r[2] or {}),
            }
            for r in cursor.fetchall()
        ]
    return {"items": items}
