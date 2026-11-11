"""
Business logic and endpoints for Mock API Management & System Versions Changelog (Phase 6).
Handles:
1. Circuit Breaker for Mock APIs (HR, Finance, IT, CRM, Assets, Facilities, Procurement, Travel)
2. Linking APIs to request types & providing mock payload previews
3. Real-time API status endpoint for client circuit breaking
4. System Versions Overview & Audit Changelog with Before/After diffs
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.db import DatabaseError, connection, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from api_core.authn.service import require_actor
from api_core.catalog import integrations
from api_core.http import api_error, correlation_id
from api_core.workflow.service import record_system_change

logger = logging.getLogger(__name__)


def _get_active_system_version() -> str:
    """Retrieve current system version string from ai_system_state or fallback."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT active_regulation_version FROM eas.ai_system_state WHERE id = 1"
            )
            row = cur.fetchone()
            if row and row[0]:
                v = str(row[0])
                return f"v{v}" if not v.startswith("v") else v
    except DatabaseError:
        logger.warning("ai_system_state unavailable", exc_info=True)
    return "v2.0"


# ---------------------------------------------------------------------------
# 1. MOCK API MANAGEMENT & CIRCUIT BREAKER
# ---------------------------------------------------------------------------


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def mock_apis_list_view(request: HttpRequest) -> JsonResponse:
    """
    GET /api/v1/admin/mock-apis
    Returns list of all 8 internal APIs, their status, mock payloads, and linked request types.
    """
    with connection.cursor() as cur:
        # 1. Fetch all mock APIs
        cur.execute(
            """
            SELECT id, api_code, api_name, endpoint_path, http_method,
                   source_system, domain_key, data_provided, mock_payload,
                   is_enabled, updated_by, updated_at
            FROM eas.mock_apis
            ORDER BY api_code ASC
            """
        )
        cols = [c[0] for c in cur.description]
        apis = [dict(zip(cols, r)) for r in cur.fetchall()]

        # 2. Fetch all request types to compute linked requests
        cur.execute(
            """
            SELECT code, name, category, lifecycle, is_active
            FROM eas.request_type
            WHERE is_active = true
            ORDER BY name ASC
            """
        )
        req_types = cur.fetchall()

    for item in apis:
        item["id"] = str(item["id"])
        item["updated_at"] = (
            item["updated_at"].isoformat() if item["updated_at"] else None
        )
        d_key = str(item.get("domain_key", "")).lower()

        # Request types closed when this API is switched off.
        linked = [
            {"code": r_code, "name": r_name, "category": r_cat, "lifecycle": r_life}
            for r_code, r_name, r_cat, r_life, _ in req_types
            if integrations.blocks(d_key, r_code, r_cat)
        ]

        item["linked_requests"] = linked
        item["linked_count"] = len(linked)

    total_count = len(apis)
    enabled_count = sum(1 for a in apis if a.get("is_enabled"))

    return JsonResponse(
        {
            "apis": apis,
            "total_count": total_count,
            "enabled_count": enabled_count,
            "circuit_breaker_active": enabled_count < total_count,
        }
    )


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def mock_api_toggle_circuit_breaker(request: HttpRequest, api_id: str) -> JsonResponse:
    """
    PATCH /api/v1/admin/mock-apis/<id>/toggle
    Toggles the Circuit Breaker for an API (ON -> OFF or OFF -> ON),
    and records the action into the hash-chained eas.admin_event.
    """
    if request.method not in ("PATCH", "POST"):
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)

    actor = getattr(request, "actor", None)
    actor_id = str(actor.id) if actor else "admin@eas.com"
    now = datetime.now(timezone.utc)
    current_version = _get_active_system_version()

    with transaction.atomic(), connection.cursor() as cur:
        # Check current API state
        cur.execute(
            """
            SELECT id, api_code, api_name, source_system, domain_key, is_enabled
            FROM eas.mock_apis
            WHERE id = %s
            FOR UPDATE
            """,
            [api_id],
        )
        row = cur.fetchone()
        if not row:
            return api_error(request, "API_NOT_FOUND", status=404)

        api_code, api_name, source_system, old_enabled = (
            row[1],
            row[2],
            row[3],
            bool(row[5]),
        )
        new_enabled = not old_enabled

        # Update mock_apis
        cur.execute(
            """
            UPDATE eas.mock_apis
            SET is_enabled = %s,
                updated_by = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [new_enabled, actor_id, now, api_id],
        )

        action_verb = "BẬT" if new_enabled else "TẮT (Ngắt)"
        record_system_change(
            cur,
            actor_id=actor.id,
            change_type="API_STATUS",
            system_version=current_version,
            title=f"{action_verb} kết nối API: {api_name}",
            description=(
                f"Quản trị viên đã {action_verb.lower()} kết nối đến {source_system} ({api_code}). "
                f"Các mẫu yêu cầu liên quan {'hoạt động bình thường' if new_enabled else 'tự động tạm ngưng và khóa nút gửi'}."
            ),
            old_value={"is_enabled": old_enabled, "api_code": api_code},
            new_value={"is_enabled": new_enabled, "api_code": api_code},
            action="ADMIN_INTEGRATION_" + ("ENABLE" if new_enabled else "DISABLE"),
            target_type="mock_api",
            target_id=str(api_id),
            correlation_id=correlation_id(request),
        )
        transaction.on_commit(integrations.invalidate)

    return JsonResponse(
        {
            "message": f"Đã {'bật kết nối lại' if new_enabled else 'ngắt kết nối (Circuit Breaker)'} API {api_name}.",
            "id": api_id,
            "api_code": api_code,
            "is_enabled": new_enabled,
            "system_version": current_version,
        }
    )


@require_GET
def public_circuit_breaker_status(request: HttpRequest) -> JsonResponse:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT api_code, api_name, source_system, domain_key, is_enabled
            FROM eas.mock_apis
            ORDER BY api_code ASC
            """
        )
        apis = cur.fetchall()

        cur.execute(
            """
            SELECT code, name, category
            FROM eas.request_type
            """
        )
        req_types = cur.fetchall()

    disabled_domains = {}
    disabled_apis = []
    disabled_categories = set()
    disabled_request_types = []
    disabled_type_notices = {}

    for code, name, source, domain, is_en in apis:
        d_key = (domain or "").lower()
        if is_en:
            continue
        disabled_domains[d_key] = False
        mapping = integrations.DOMAIN_MAPPING.get(
            d_key, {"categories": [], "extra_codes": []}
        )
        disabled_categories.update(mapping["categories"])
        notice = integrations.notice_for(source or name)
        disabled_apis.append(
            {
                "api_code": code,
                "api_name": name,
                "source_system": source,
                "domain_key": d_key,
                "unavailable_notice": notice,
            }
        )
        for r_code, _r_name, r_cat in req_types:
            if (
                integrations.blocks(d_key, r_code, r_cat)
                and r_code not in disabled_type_notices
            ):
                disabled_request_types.append(r_code)
                disabled_type_notices[r_code] = notice

    return JsonResponse(
        {
            "is_all_enabled": len(disabled_apis) == 0,
            "disabled_count": len(disabled_apis),
            "disabled_domains": disabled_domains,
            "disabled_categories": list(disabled_categories),
            "disabled_apis": disabled_apis,
            "disabled_request_types": disabled_request_types,
            "disabled_type_notices": disabled_type_notices,
        }
    )


# ---------------------------------------------------------------------------
# 2. SYSTEM VERSIONS & CHANGELOG VIEW
# ---------------------------------------------------------------------------


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def system_versions_changelog_view(request: HttpRequest) -> JsonResponse:
    """
    GET /api/v1/admin/system-versions/changelog
    Returns overall system specifications, current versions, and full audit changelog.
    """
    change_type_filter = request.GET.get("type", "").strip().upper()
    search_q = request.GET.get("q", "").strip()

    with connection.cursor() as cur:
        # 1. Fetch AI & Regulation system state
        cur.execute(
            """
            SELECT active_regulation_version, provider_name, model_name, global_major_version, global_minor_version
            FROM eas.ai_system_state
            WHERE id = 1
            """
        )
        ai_row = cur.fetchone()
        active_reg_v = str(ai_row[0] or "2.0") if ai_row else "2.0"
        if not active_reg_v.startswith("v"):
            active_reg_v = f"v{active_reg_v}"
        provider_name = (
            ai_row[1] if ai_row else None
        ) or "Google Gemini + Scikit-Learn Hybrid"
        model_name = (
            ai_row[2] if ai_row else None
        ) or "gemini-2.5-flash & nlp_risk_pipeline_v2"

        # 2. Fetch API stats
        cur.execute(
            "SELECT COUNT(*)::int, COUNT(*) FILTER (WHERE is_enabled = true)::int FROM eas.mock_apis"
        )
        api_row = cur.fetchone()
        total_apis = api_row[0] or 8
        enabled_apis = api_row[1] or 8

        # 3. Fetch Regulations count
        cur.execute(
            "SELECT COUNT(*)::int FROM eas.company_regulations WHERE is_deleted = false"
        )
        total_regs = cur.fetchone()[0] or 0

        # 4. Changelog = admin_event rows carrying details.change_type (schema v2).
        query = """
            SELECT e.id::text AS id,
                   e.details->>'system_version' AS system_version,
                   e.details->>'change_type' AS change_type,
                   e.details->>'change_scope' AS change_scope,
                   e.details->>'title' AS title,
                   e.details->>'description' AS description,
                   e.details->'old_value' AS old_value,
                   e.details->'new_value' AS new_value,
                   COALESCE(e.details->>'changed_by', u.email, e.actor_kind) AS changed_by,
                   COALESCE((e.details->>'original_created_at')::timestamptz, e.occurred_at)
                     AS created_at
            FROM eas.admin_event e
            LEFT JOIN eas.app_user u ON u.id = e.actor_id
            WHERE e.details ? 'change_type'
        """
        params = []
        if change_type_filter and change_type_filter != "ALL":
            query += " AND e.details->>'change_type' = %s"
            params.append(change_type_filter)
        if search_q:
            query += (
                " AND (STRPOS(LOWER(COALESCE(e.details->>'title', '')), LOWER(%s)) > 0"
                " OR STRPOS(LOWER(COALESCE(e.details->>'description', '')), LOWER(%s)) > 0"
                " OR STRPOS(LOWER(COALESCE(u.email, '')), LOWER(%s)) > 0)"
            )
            params.extend([search_q, search_q, search_q])

        query += " ORDER BY created_at DESC LIMIT 100"
        cur.execute(query, params)
        cols = [c[0] for c in cur.description]
        changelog = []
        for r in cur.fetchall():
            item = dict(zip(cols, r))
            item["created_at"] = (
                item["created_at"].isoformat() if item["created_at"] else None
            )
            changelog.append(item)

    sys_summary = {
        "system_version": active_reg_v,
        "regulation_version": active_reg_v,
        "ai_provider": provider_name,
        "ai_model": model_name,
        "api_status": f"{enabled_apis}/{total_apis} Kết nối hoạt động",
        "is_all_apis_enabled": enabled_apis == total_apis,
        "apis_enabled_count": enabled_apis,
        "apis_total_count": total_apis,
        "circuit_breaker_active": enabled_apis < total_apis,
        "total_regulations_count": total_regs,
        "regulations_count": total_regs,
        "total_changelog_entries": len(changelog),
    }
    return JsonResponse(
        {
            "system_info": sys_summary,
            "current_system": sys_summary,
            "changelog": changelog,
        }
    )
