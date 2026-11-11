"""Admin analytics dashboard from the live request data (no sample numbers).

Drafts are not counted: a request enters the statistics once submitted.
Durations run from creation to completion; on-time means within the SLA of the
type's active config release (approval + execution + acceptance hours).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.db import connection
from django.http import JsonResponse

from api_core.authn.module_access import ADMIN_ROLES
from api_core.authn.service import require_actor
from api_core.http import api_error

from .workflows import LIFECYCLES

VN_TZ = timezone(timedelta(hours=7))
SPEED_LABELS = {
    "A": "Siêu tốc (Tự động)",
    "B": "Nhanh (Phòng ban)",
    "C": "Tiêu chuẩn (Đa cấp)",
}
WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
# One row per submitted request in the window.
REQUESTS_SQL = """
    SELECT r.created_at, r.status, rt.lifecycle, rt.name,
           COALESCE(d.name, 'Chưa gán phòng ban'), u.display_name, u.email,
           EXTRACT(EPOCH FROM (r.completed_at - r.created_at)) / 60,
           COALESCE((cr.sla_profile->>'approval_hours')::numeric, 0)
             + COALESCE((cr.sla_profile->>'execution_hours')::numeric, 0)
             + COALESCE((cr.sla_profile->>'acceptance_hours')::numeric, 0)
    FROM eas.request r
    JOIN eas.request_type rt ON rt.id = r.type_id
    LEFT JOIN eas.request_revision rv ON rv.id = r.current_revision_id
    LEFT JOIN eas.app_user u ON u.id = r.requester_id
    LEFT JOIN eas.department d ON d.id = COALESCE(rv.department_id, u.department_id)
    LEFT JOIN eas.config_release cr ON cr.id = rt.active_release_id
    WHERE r.status <> 'DRAFT' AND r.created_at >= %s AND r.created_at <= %s
"""


SCOPE_COMPANY = {"kind": "COMPANY", "label": "Toàn công ty"}


def _scope(request) -> tuple[str, list, dict]:
    """Which requests the viewer may aggregate.

    Admin and company-wide approvers: everything; department approvers: their
    departments; everyone else: only their own requests.
    """
    actor = request.actor
    if actor.roles & ADMIN_ROLES:
        return "", [], SCOPE_COMPANY
    with connection.cursor() as cur:
        cur.execute(
            """SELECT m.scope_kind, m.type_scope, m.department_id::text
               FROM eas.role_membership m
               WHERE m.user_id = %s AND m.role = 'APPROVER' AND m.revoked_at IS NULL
                 AND m.valid_from <= statement_timestamp()
                 AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())""",
            [actor.id],
        )
        rows = cur.fetchall()
    if any(kind == "GLOBAL" and types == "ALL" for kind, types, _ in rows):
        return "", [], SCOPE_COMPANY
    departments = sorted(
        {dept for kind, _, dept in rows if kind == "DEPARTMENT" and dept}
    )
    if departments:
        return (
            " AND COALESCE(rv.department_id, u.department_id)::text = ANY(%s)",
            [departments],
            {"kind": "DEPARTMENT", "label": "Phòng ban bạn phụ trách"},
        )
    return (
        " AND r.requester_id = %s",
        [actor.id],
        {"kind": "OWN", "label": "Yêu cầu của bạn"},
    )


def _format_duration(minutes):
    if not minutes or minutes <= 0:
        return "0 phút"
    mins = round(minutes)
    if mins < 60:
        return f"{mins} phút"
    hours, rem = divmod(mins, 60)
    return f"{hours} giờ" if rem == 0 else f"{hours}h {rem}m"


def _pct(part, total):
    return round(part / total * 100, 1) if total else 0


def _period_range(period: str, now: datetime) -> tuple[str, datetime]:
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "day":
        return period, midnight
    if period == "week":
        return period, midnight - timedelta(days=now.weekday())
    if period == "year":
        return period, midnight.replace(month=1, day=1)
    return "month", midnight.replace(day=1)


def _bucket(period: str, created: datetime) -> str:
    local = created.astimezone(VN_TZ)
    if period == "day":
        return f"{local.hour // 3 * 3:02d}:00"
    if period == "week":
        return WEEKDAYS[local.weekday()]
    if period == "year":
        return f"T{local.month}"
    return f"Tuần {min((local.day - 1) // 7 + 1, 5)}"


def _bucket_labels(period: str) -> list[str]:
    if period == "day":
        return [f"{h:02d}:00" for h in range(0, 24, 3)]
    if period == "week":
        return WEEKDAYS
    if period == "year":
        return [f"T{m}" for m in range(1, 13)]
    return [f"Tuần {i}" for i in range(1, 6)]


def _parse_dt(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return default
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=VN_TZ)


def _outcome(status: str) -> str:
    if status == "COMPLETED":
        return "success"
    if status in ("REJECTED", "CANCELLED"):
        return "rejected"
    return "processing"


def _top(counter: dict, limit: int | None = None) -> list[tuple]:
    rows = sorted(counter.items(), key=lambda kv: -kv[1]["total"])
    return rows[:limit] if limit else rows


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR", "ADMIN")
def admin_analytics_view(request):
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)

    now = datetime.now(VN_TZ)
    requested_period = request.GET.get("period", "month").lower().strip()
    period, start = _period_range(requested_period, now)
    start = _parse_dt(request.GET.get("created_from"), start)
    end = _parse_dt(request.GET.get("created_to"), now)

    scope_sql, scope_params, scope = _scope(request)
    with connection.cursor() as cur:
        cur.execute(
            REQUESTS_SQL + scope_sql, [start, end, *scope_params]
        )  # NOSONAR python:S2077 - constant fragments
        rows = cur.fetchall()
        if not rows and not request.GET.get("created_from"):
            cur.execute(  # NOSONAR python:S2077 - constant fragments
                """SELECT MAX(r.created_at) FROM eas.request r
                   LEFT JOIN eas.request_revision rv ON rv.id = r.current_revision_id
                   LEFT JOIN eas.app_user u ON u.id = r.requester_id
                   WHERE r.status <> 'DRAFT'"""
                + scope_sql,
                scope_params,
            )
            max_row = cur.fetchone()
            if max_row and max_row[0]:
                anchor = max_row[0].astimezone(VN_TZ)
                period, start = _period_range(requested_period, anchor)
                end = anchor.replace(hour=23, minute=59, second=59)
                cur.execute(
                    REQUESTS_SQL + scope_sql, [start, end, *scope_params]
                )  # NOSONAR python:S2077
                rows = cur.fetchall()

    # ponytail: aggregated in Python; move to SQL GROUP BY if a period exceeds ~100k requests.
    kpi = {"success": 0, "rejected": 0, "processing": 0}
    status_breakdown: dict[str, int] = {}
    trends = {
        label: {
            "label": label,
            "total": 0,
            "success": 0,
            "rejected": 0,
            "processing": 0,
        }
        for label in _bucket_labels(period)
    }
    lifecycles = {
        code: {"total": 0, "success": 0, "on_time": 0, "durations": [], "sla": []}
        for code in LIFECYCLES
    }
    types, depts, users = {}, {}, {}
    for (
        created,
        status,
        lifecycle,
        type_name,
        dept,
        user_name,
        email,
        minutes,
        sla_hours,
    ) in rows:
        outcome = _outcome(status)
        kpi[outcome] += 1
        status_breakdown[status] = status_breakdown.get(status, 0) + 1
        b_key = _bucket(period, created)
        bucket = trends.get(b_key)
        if not bucket:
            bucket = trends.setdefault(
                b_key,
                {
                    "label": b_key,
                    "total": 0,
                    "success": 0,
                    "rejected": 0,
                    "processing": 0,
                },
            )
        bucket["total"] += 1
        bucket[outcome] += 1
        lc = lifecycles.setdefault(
            lifecycle,
            {"total": 0, "success": 0, "on_time": 0, "durations": [], "sla": []},
        )
        lc["total"] += 1
        if sla_hours:
            lc["sla"].append(float(sla_hours))
        if outcome == "success":
            lc["success"] += 1
        if minutes is not None:
            lc["durations"].append(float(minutes))
            if not sla_hours or float(minutes) <= float(sla_hours) * 60:
                lc["on_time"] += 1
        for counter, key in (
            (types, type_name),
            (depts, dept),
            (users, (user_name or email or "Nhân viên", email or "", dept)),
        ):
            entry = counter.setdefault(key, {"total": 0, "success": 0})
            entry["total"] += 1
            entry["success"] += outcome == "success"

    total = len(rows)
    category_performance = []
    default_slas = {"A": 2, "B": 24, "C": 72}
    for code, lc in lifecycles.items():
        avg = sum(lc["durations"]) / len(lc["durations"]) if lc["durations"] else 0.0
        sla = sorted(lc["sla"])
        sla_val = int(sla[len(sla) // 2]) if sla else default_slas.get(code, 24)
        category_performance.append(
            {
                "category_code": code,
                "name": LIFECYCLES.get(code, (code,))[0],
                "sla_hours": sla_val,
                "total_requests": lc["total"],
                "avg_duration_minutes": round(avg, 1),
                "avg_duration_text": _format_duration(avg),
                "on_time_count": lc["on_time"],
                "on_time_rate": _pct(lc["on_time"], len(lc["durations"]))
                if lc["durations"]
                else 100.0,
                "speed_rating": SPEED_LABELS.get(code, "Tiêu chuẩn"),
            }
        )

    return JsonResponse(
        {
            "period": period,
            "scope": scope,
            "date_range": {"from": start.isoformat(), "to": end.isoformat()},
            "kpis": {
                "total_requests": total,
                "success_count": kpi["success"],
                "success_rate": _pct(kpi["success"], total),
                "rejected_count": kpi["rejected"],
                "rejected_rate": _pct(kpi["rejected"], total),
                "processing_count": kpi["processing"],
                "processing_rate": _pct(kpi["processing"], total),
            },
            "status_breakdown": status_breakdown,
            "trends": list(trends.values()),
            "top_types": [
                {"name": k, "count": v["total"], "percentage": _pct(v["total"], total)}
                for k, v in _top(types)
            ],
            "top_departments": [
                {
                    "department_name": k,
                    "total": v["total"],
                    "success": v["success"],
                    "percentage": _pct(v["total"], total),
                }
                for k, v in _top(depts, 5)
            ],
            "top_users": [
                {
                    "name": k[0],
                    "email": k[1],
                    "department": k[2],
                    "total": v["total"],
                    "success": v["success"],
                }
                for k, v in _top(users, 5)
            ],
            "category_performance": category_performance,
        }
    )
