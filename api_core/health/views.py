from __future__ import annotations

import socket

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from redis.exceptions import RedisError

EXPECTED_TYPES = {("ACCESS", "B"), ("EQUIPMENT", "C"), ("LEAVE", "A")}
EXPECTED_MOCK_RELATIONS = {
    "mock_hr.department",
    "mock_hr.employee_directory",
    "mock_hr.leave_balance",
    "mock_assets.asset_catalog",
    "mock_assets.asset_loan",
    "mock_facilities.resource_catalog",
    "mock_crm.customer_directory",
    "mock_crm.contract",
    "mock_procurement.supplier_directory",
    "mock_procurement.catalog_item",
    "mock_it.application_catalog",
    "mock_it.access_role",
    "mock_it.service_catalog",
    "mock_finance.cost_center_budget",
    "mock_finance.expense_category",
    "mock_travel.travel_policy",
    "mock_travel.travel_option",
}


def assess_runtime_role(
    role_row: tuple[bool, bool, bool, bool, bool, bool, bool, bool] | None,
) -> dict[str, bool]:
    """Assess capabilities, not a brittle list of privileged role names."""

    if role_row is None:
        return {
            "runtime_role_exists": False,
            "runtime_role_is_non_admin": False,
            "runtime_role_is_api_only": False,
        }
    (
        is_superuser,
        bypasses_rls,
        can_create_role,
        can_create_db,
        is_api_member,
        is_worker_member,
        is_migration_member,
        is_privacy_member,
    ) = role_row
    has_admin_capability = any(
        (is_superuser, bypasses_rls, can_create_role, can_create_db)
    )
    has_conflicting_membership = any(
        (is_worker_member, is_migration_member, is_privacy_member)
    )
    return {
        "runtime_role_exists": True,
        "runtime_role_is_non_admin": not has_admin_capability,
        "runtime_role_is_api_only": is_api_member and not has_conflicting_membership,
    }


def assess_request_types(
    rows: list[tuple[str, str, bool]], *, require_active_releases: bool
) -> dict[str, bool]:
    return {
        "request_types_match_p0": {(code, lifecycle) for code, lifecycle, _ in rows}
        == EXPECTED_TYPES,
        "all_active_types_configured": (not require_active_releases)
        or (len(rows) == 3 and all(valid for _, _, valid in rows)),
    }


def assess_mock_sources(
    rows: list[tuple[str, bool]], versions: set[str]
) -> dict[str, bool]:
    available = {name for name, can_read in rows if can_read}
    return {
        "mock_source_contract_complete": available == EXPECTED_MOCK_RELATIONS,
        "mock_source_migrations_current": {"001", "002", "003"}.issubset(versions),
    }


def storage_readiness() -> dict[str, bool]:
    if not settings.EAS_REQUIRE_STORAGE:
        return {
            "attachment_storage_requirement_satisfied": True,
            "malware_scanner_requirement_satisfied": True,
        }
    configured = bool(settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY)
    scanner_reachable = False
    try:
        with socket.create_connection(
            (settings.EAS_CLAMAV_HOST, settings.EAS_CLAMAV_PORT), timeout=2
        ):
            scanner_reachable = True
    except (OSError, TimeoutError):
        pass
    return {
        "attachment_storage_requirement_satisfied": configured,
        "malware_scanner_requirement_satisfied": scanner_reachable,
    }


def database_readiness() -> tuple[bool, dict[str, object]]:
    checks: dict[str, object] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.rolsuper,
                   r.rolbypassrls,
                   r.rolcreaterole,
                   r.rolcreatedb,
                   pg_has_role(current_user, 'eas_api', 'member'),
                   pg_has_role(current_user, 'eas_worker', 'member'),
                   pg_has_role(current_user, 'eas_migration', 'member'),
                   pg_has_role(current_user, 'eas_privacy', 'member')
            FROM pg_roles r
            WHERE r.rolname = current_user
            """
        )
        role_checks = assess_runtime_role(cursor.fetchone())
        if settings.EAS_ALLOW_ADMIN_DB:
            role_checks["runtime_role_is_non_admin"] = True
            role_checks["runtime_role_is_api_only"] = True
        checks.update(role_checks)

        cursor.execute(
            """
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_schema = 'eas' AND table_type = 'BASE TABLE'
            """
        )
        checks["schema_has_30_tables"] = cursor.fetchone()[0] == 30

        cursor.execute(
            """
            SELECT rt.code,
                   rt.lifecycle,
                   cr.id IS NOT NULL
                     AND cr.state = 'PUBLISHED'
                     AND cr.type_id = rt.id
                     AND cr.lifecycle = rt.lifecycle AS active_release_valid
            FROM eas.request_type rt
            LEFT JOIN eas.config_release cr ON cr.id = rt.active_release_id
            WHERE rt.is_active
            ORDER BY rt.code
            """
        )
        rows = cursor.fetchall()
        checks.update(
            assess_request_types(
                rows,
                require_active_releases=settings.EAS_REQUIRE_ACTIVE_RELEASES,
            )
        )

        if settings.EAS_REQUIRE_MOCK_SOURCES:
            cursor.execute(
                """
                SELECT relation_name,
                       to_regclass(relation_name) IS NOT NULL
                       AND has_table_privilege(current_user,relation_name,'SELECT')
                FROM unnest(%s::text[]) AS relation_name
                ORDER BY relation_name
                """,
                [sorted(EXPECTED_MOCK_RELATIONS)],
            )
            mock_rows = cursor.fetchall()
            cursor.execute("SELECT version FROM mock_hr.schema_migration")
            checks.update(
                assess_mock_sources(mock_rows, {row[0] for row in cursor.fetchall()})
            )

    return all(bool(value) for value in checks.values()), checks


@require_GET
def live(request):
    return JsonResponse(
        {"status": "ok", "service": "eas-api", "release": settings.EAS_RELEASE}
    )


@require_GET
def ready(request):
    try:
        is_ready, checks = database_readiness()
    except DatabaseError:
        return JsonResponse(
            {
                "status": "not_ready",
                "service": "eas-api",
                "checks": {"database": False},
            },
            status=503,
        )
    try:
        cache_key = "eas:health:ready"
        cache.set(cache_key, "ok", timeout=5)
        checks["shared_security_cache"] = cache.get(cache_key) == "ok"
    except (RedisError, OSError, TimeoutError):
        checks["shared_security_cache"] = False
    checks.update(storage_readiness())
    is_ready = is_ready and all(bool(value) for value in checks.values())
    return JsonResponse(
        {
            "status": "ready" if is_ready else "not_ready",
            "service": "eas-api",
            "checks": checks,
        },
        status=200 if is_ready else 503,
    )
