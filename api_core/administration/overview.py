"""Read-only dashboard aggregates, limited to OPS_ADMIN's effective scope.

The summary deliberately uses grouped SQL rather than fetching every request into Python.
No new Supabase tables or migrations are required.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
        start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")) if raw_start else now - timedelta(days=30)
        end = datetime.fromisoformat(raw_end.replace("Z", "+00:00")) if raw_end else now
        if start.tzinfo is None or end.tzinfo is None or end <= start or end - start > timedelta(days=366):
            raise ValueError
    except (TypeError, ValueError):
        raise CommandError("PERIOD_INVALID", status=422) from None
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


@require_actor("OPS_ADMIN")
def system_overview(request):
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        start, end = _period(request)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(false)")
            authorize(cursor, request.actor)
            cursor.execute(
                """
                SELECT rt.code, rt.name, r.status, COUNT(*)::integer,
                       COUNT(*) FILTER (WHERE EXISTS (
                           SELECT 1 FROM eas.sla_stage s
                           WHERE s.request_id=r.id AND s.closed_at IS NULL
                             AND s.due_at < statement_timestamp()
                       ))::integer
                FROM eas.request r
                JOIN eas.request_type rt ON rt.id=r.type_id
                JOIN eas.app_user u ON u.id=r.requester_id
                LEFT JOIN eas.request_revision v ON v.id=r.current_revision_id
                WHERE r.created_at >= %s AND r.created_at < %s
                  AND EXISTS (
                      SELECT 1 FROM eas.role_membership rm
                      WHERE rm.user_id=%s AND rm.role='OPS_ADMIN' AND rm.revoked_at IS NULL
                        AND rm.valid_from <= statement_timestamp()
                        AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                        AND (rm.scope_kind='GLOBAL'
                             OR rm.department_id=COALESCE(v.department_id,u.department_id))
                        AND (rm.type_scope='ALL' OR rm.type_id=r.type_id)
                  )
                GROUP BY rt.code, rt.name, r.status
                """,
                [start, end, request.actor.id],
            )
            rows = cursor.fetchall()
    except CommandError as error:
        return api_error(request, error.code, status=error.status)

    statuses = {}
    types = {}
    overdue = 0
    for code, name, status, count, overdue_count in rows:
        statuses[status] = statuses.get(status, 0) + count
        item = types.setdefault(code, {"code": code, "name": name, "count": 0})
        item["count"] += count
        overdue += overdue_count
    return JsonResponse({
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "scope": "authorized_ops_scope",
        "total": sum(statuses.values()),
        "overdue": overdue,
        "by_status": statuses,
        "top_types": sorted(types.values(), key=lambda item: (-item["count"], item["name"]))[:10],
    })
