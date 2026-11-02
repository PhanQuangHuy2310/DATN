"""Read-only dashboard aggregates, limited to OPS_ADMIN's effective scope.

The summary deliberately uses grouped SQL rather than fetching every request into Python.
No new Supabase tables or migrations are required.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from django.db import connection, transaction
from django.http import JsonResponse
from django.utils import timezone as django_timezone

from api_core.authn.service import require_actor
from api_core.http import api_error
from api_core.workflow.service import CommandError

from .service import authorize


def _period(request):
    now = django_timezone.now()
    try:
        raw_start = request.GET.get("created_from")
        raw_end = request.GET.get("created_to")
        start = (
            datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            if raw_start
            else now - timedelta(days=30)
        )
        end = datetime.fromisoformat(raw_end.replace("Z", "+00:00")) if raw_end else now
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or end <= start
            or end - start > timedelta(days=366)
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise CommandError("PERIOD_INVALID", status=422) from None
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


STATUSES = {
    "DRAFT",
    "NEEDS_INFO",
    "PENDING_APPROVAL",
    "READY_FOR_EXECUTION",
    "IN_PROGRESS",
    "WAITING_FOR_ACCEPTANCE",
    "COMPLETED",
    "REJECTED",
    "CANCELLED",
}


def _filters(request):
    department = (request.GET.get("department_id") or "").strip() or None
    if department:
        try:
            department = str(UUID(department))
        except ValueError:
            raise CommandError("INVALID_DEPARTMENT_ID", status=400) from None
    type_code = (request.GET.get("type_code") or "").strip()[:30] or None
    status = (request.GET.get("status") or "").strip() or None
    if status and status not in STATUSES:
        raise CommandError("INVALID_STATUS", status=400)
    return department, type_code, status


@require_actor("OPS_ADMIN")
def system_overview(request):
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        start, end = _period(request)
        department, type_code, status = _filters(request)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(false)")
            authorize(cursor, request.actor)
            # One grouped statement (type x status x department); totals are
            # folded in Python so the dashboard costs a single round trip.
            cursor.execute(
                """
                SELECT rt.code, rt.name, r.status,
                       COALESCE(v.department_id, u.department_id)::text, d.name,
                       COUNT(*)::integer,
                       COUNT(*) FILTER (WHERE EXISTS (
                           SELECT 1 FROM eas.sla_stage s
                           WHERE s.request_id=r.id AND s.closed_at IS NULL
                             AND s.due_at < statement_timestamp()
                       ))::integer,
                       (SELECT COUNT(*) FILTER (WHERE x.is_active)::integer
                          FROM eas.app_user x
                         WHERE %s::uuid IS NULL OR x.department_id=%s::uuid),
                       (SELECT COUNT(*)::integer FROM eas.app_user x
                         WHERE %s::uuid IS NULL OR x.department_id=%s::uuid)
                FROM eas.request r
                JOIN eas.request_type rt ON rt.id=r.type_id
                JOIN eas.app_user u ON u.id=r.requester_id
                LEFT JOIN eas.request_revision v ON v.id=r.current_revision_id
                LEFT JOIN eas.department d
                  ON d.id=COALESCE(v.department_id,u.department_id)
                WHERE r.created_at >= %s AND r.created_at < %s
                  AND (%s::uuid IS NULL
                       OR COALESCE(v.department_id,u.department_id)=%s::uuid)
                  AND (%s::text IS NULL OR rt.code=%s)
                  AND (%s::text IS NULL OR r.status=%s)
                  AND EXISTS (
                      SELECT 1 FROM eas.role_membership rm
                      WHERE rm.user_id=%s AND rm.role='OPS_ADMIN' AND rm.revoked_at IS NULL
                        AND rm.valid_from <= statement_timestamp()
                        AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                        AND (rm.scope_kind='GLOBAL'
                             OR rm.department_id=COALESCE(v.department_id,u.department_id))
                        AND (rm.type_scope='ALL' OR rm.type_id=r.type_id)
                  )
                GROUP BY rt.code, rt.name, r.status,
                         COALESCE(v.department_id, u.department_id), d.name
                """,
                [
                    department,
                    department,
                    department,
                    department,
                    start,
                    end,
                    department,
                    department,
                    type_code,
                    type_code,
                    status,
                    status,
                    request.actor.id,
                ],
            )
            rows = cursor.fetchall()
            if rows:
                active_users, total_users = rows[0][7], rows[0][8]
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*) FILTER (WHERE is_active)::integer, COUNT(*)::integer
                    FROM eas.app_user WHERE %s::uuid IS NULL OR department_id=%s::uuid
                    """,
                    [department, department],
                )
                active_users, total_users = cursor.fetchone()
    except CommandError as error:
        return api_error(request, error.code, status=error.status)

    statuses = {}
    types = {}
    departments = {}
    overdue = 0
    for code, name, state, dept_id, dept_name, count, overdue_count, *_ in rows:
        statuses[state] = statuses.get(state, 0) + count
        item = types.setdefault(code, {"code": code, "name": name, "count": 0})
        item["count"] += count
        bucket = departments.setdefault(
            dept_id,
            {
                "department_id": dept_id,
                "department_name": dept_name,
                "total": 0,
                "completed": 0,
                "pending": 0,
                "overdue": 0,
            },
        )
        bucket["total"] += count
        bucket["overdue"] += overdue_count
        if state == "COMPLETED":
            bucket["completed"] += count
        elif state in ("PENDING_APPROVAL", "NEEDS_INFO"):
            bucket["pending"] += count
        overdue += overdue_count
    return JsonResponse(
        {
            "period": {"from": start.isoformat(), "to": end.isoformat()},
            "scope": "authorized_ops_scope",
            "total": sum(statuses.values()),
            "overdue": overdue,
            "by_status": statuses,
            "top_types": sorted(
                types.values(), key=lambda item: (-item["count"], item["name"])
            )[:10],
            "by_department": sorted(
                departments.values(),
                key=lambda item: (-item["total"], item["department_name"] or ""),
            ),
            "users": {"active": active_users, "total": total_users},
        }
    )


@require_actor("OPS_ADMIN")
def system_diagnostics(request):
    """Worker/outbox, SLA and AI signals for operators. Read-only."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(false)")
            authorize(cursor, request.actor)
            cursor.execute(
                """
                SELECT
                  (SELECT COALESCE(json_object_agg(state, n), '{}'::json) FROM (
                     SELECT state, COUNT(*)::integer AS n FROM eas.outbox_event
                     GROUP BY state) c),
                  (SELECT EXTRACT(EPOCH FROM statement_timestamp() - MIN(available_at))
                     FROM eas.outbox_event
                    WHERE state='PENDING' AND available_at <= statement_timestamp()),
                  (SELECT MAX(sent_at) FROM eas.outbox_event WHERE state='SENT'),
                  (SELECT COALESCE(json_agg(x ORDER BY x.created_at DESC), '[]'::json)
                     FROM (
                       SELECT o.id, o.event_type, o.attempts, o.last_error_code,
                              o.created_at, o.replay_count, r.code AS request_code
                       FROM eas.outbox_event o
                       LEFT JOIN eas.request r ON r.id=o.request_id
                       WHERE o.state='DEAD'
                       ORDER BY o.created_at DESC LIMIT 20) x),
                  (SELECT COUNT(*)::integer FROM eas.sla_stage WHERE closed_at IS NULL),
                  (SELECT COUNT(*)::integer FROM eas.sla_stage
                    WHERE closed_at IS NULL AND due_at < statement_timestamp()),
                  (SELECT COALESCE(json_object_agg(kind, n), '{}'::json) FROM (
                     SELECT kind, COUNT(*)::integer AS n FROM eas.sla_alert
                     WHERE created_at > statement_timestamp() - interval '24 hours'
                     GROUP BY kind) a)
                """
            )
            (
                outbox_counts,
                oldest_pending_seconds,
                last_sent_at,
                dead_events,
                open_stages,
                overdue_stages,
                alerts_24h,
            ) = cursor.fetchone()
    except CommandError as error:
        return api_error(request, error.code, status=error.status)

    from api_core.integrations.ai_service import ai_client

    try:
        ai_ok = asyncio.run(asyncio.wait_for(ai_client.health_check(), timeout=3))
    except (TimeoutError, RuntimeError, OSError):
        ai_ok = False
    lag = None if oldest_pending_seconds is None else int(oldest_pending_seconds)
    return JsonResponse(
        {
            "outbox": {
                "counts": outbox_counts or {},
                "oldest_pending_seconds": lag,
                "last_sent_at": last_sent_at.isoformat() if last_sent_at else None,
                "dead_events": dead_events or [],
            },
            # The worker is the only outbox consumer: a due backlog older than
            # five minutes means it is stopped or failing. An empty backlog does
            # not prove it is running, so report exactly what is known.
            "worker": {"backlog_ok": lag is None or lag < 300},
            "sla": {
                "open_stages": open_stages,
                "overdue_stages": overdue_stages,
                "alerts_24h": alerts_24h or {},
            },
            "ai_service": {"healthy": bool(ai_ok)},
        }
    )
