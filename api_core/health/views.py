from __future__ import annotations

import logging
import socket

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from api_core.db_diagnostics import failure_category, sqlstate
from api_core.health.request_type_readiness import (
    assess_request_types,
    catalog_readiness_summary,
)
from api_core.health.schema_contract import has_required_eas_tables
from api_core.http import correlation_id

log = logging.getLogger("eas.database")
from redis.exceptions import RedisError

from api_core.integrations import client
from api_core.workflow.errors import CommandError

MOCK_SCHEMAS = (
    "mock_hr",
    "mock_assets",
    "mock_facilities",
    "mock_crm",
    "mock_procurement",
    "mock_it",
    "mock_finance",
    "mock_travel",
)
REQUIRED_MOCK_MIGRATIONS = {"001", "002", "003", "005"}


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


def assess_mock_sources(
    reachable: bool, versions: set[str], eas_reads_mock: bool
) -> dict[str, bool]:
    """External systems answer over their API; EAS itself cannot read their tables."""
    return {
        "mock_systems_api_reachable": reachable,
        "mock_source_migrations_current": REQUIRED_MOCK_MIGRATIONS.issubset(versions),
        "eas_role_has_no_mock_table_access": not eas_reads_mock,
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
    except OSError:
        pass
    return {
        "attachment_storage_requirement_satisfied": configured,
        "malware_scanner_requirement_satisfied": scanner_reachable,
    }


def database_readiness() -> tuple[bool, dict[str, object], dict[str, object]]:
    checks: dict[str, object] = {}
    catalog: dict[str, object] = {}
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

        # Allow additive catalog tables (eas.lifecycle, eas.role, future tables).
        # Count-only validation could conceal a missing mandatory table.
        cursor.execute(
            """
            SELECT c.relname
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'eas' AND c.relkind IN ('r', 'p')
            """
        )
        checks["schema_has_required_tables"] = has_required_eas_tables(
            {row[0] for row in cursor.fetchall()}
        )

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
        type_assessment = assess_request_types(
            rows, require_active_releases=settings.EAS_REQUIRE_ACTIVE_RELEASES
        )
        # Core readiness needs P0 availability, not publication of every draft
        # request type seeded by newer plans. Missing optional releases remain
        # visible as catalog diagnostics and impossible to submit via workflow API.
        checks["request_types_match_p0"] = type_assessment["request_types_match_p0"]
        checks["p0_active_types_configured"] = type_assessment[
            "p0_active_types_configured"
        ]
        catalog = catalog_readiness_summary(rows)
        if getattr(settings, "EAS_REQUIRE_FULL_CATALOG_READY", False):
            # Opt-in hard gating for deployments which need every active type live.
            checks["all_active_types_configured"] = type_assessment[
                "all_active_types_configured"
            ]

        if settings.EAS_REQUIRE_MOCK_SOURCES:
            cursor.execute(
                """
                SELECT bool_or(has_schema_privilege(current_user, n.oid, 'USAGE'))
                FROM pg_namespace n WHERE n.nspname = ANY(%s)
                """,
                [list(MOCK_SCHEMAS)],
            )
            eas_reads_mock = bool(cursor.fetchone()[0])
            try:
                versions = set(client.get("health", "health")["schema_versions"])
                reachable = True
            except CommandError:
                versions, reachable = set(), False
            checks.update(assess_mock_sources(reachable, versions, eas_reads_mock))

    return all(bool(value) for value in checks.values()), checks, catalog


@require_GET
def live(request):
    return JsonResponse(
        {"status": "ok", "service": "eas-api", "release": settings.EAS_RELEASE}
    )


@require_GET
def ready(request):
    env = getattr(settings, "ENVIRONMENT", "development")
    cache_ttl = (
        0 if env == "test" else int(getattr(settings, "EAS_HEALTH_CACHE_SECONDS", 5))
    )
    payload_cache_key = "eas:health:ready_payload"
    if cache_ttl > 0:
        try:
            cached = cache.get(payload_cache_key)
            if cached and isinstance(cached, dict):
                return JsonResponse(cached["body"], status=cached["status"])
        except (RedisError, OSError, TypeError, ValueError) as exc:
            log.debug("Health cache read failed: %s", exc)
    try:
        is_ready, checks, catalog = database_readiness()
    except DatabaseError as exc:
        request_id = correlation_id(request)
        log.error(
            "Readiness database failure: category=%s exception_type=%s "
            "SQLSTATE=%s correlation_id=%s",
            failure_category(exc),
            type(exc).__name__,
            sqlstate(exc),
            request_id,
            extra={"correlation_id": request_id},
        )
        return JsonResponse(
            {
                "status": "not_ready",
                "service": "eas-api",
                "checks": {"database": False},
            },
            status=503,
        )
    try:
        probe_cache_key = "eas:health:ready"
        cache.set(probe_cache_key, "ok", timeout=5)
        checks["shared_security_cache"] = cache.get(probe_cache_key) == "ok"
    except (RedisError, OSError):
        checks["shared_security_cache"] = False
    checks.update(storage_readiness())
    is_ready = is_ready and all(bool(value) for value in checks.values())
    status_code = 200 if is_ready else 503
    body = {
        "status": "ready" if is_ready else "not_ready",
        "service": "eas-api",
        "checks": checks,
        "catalog": catalog,
    }
    if cache_ttl > 0 and is_ready:
        try:
            cache.set(
                payload_cache_key,
                {"body": body, "status": status_code},
                timeout=cache_ttl,
            )
        except (RedisError, OSError, TypeError, ValueError) as exc:
            log.debug("Health cache write failed: %s", exc)
    return JsonResponse(body, status=status_code)
