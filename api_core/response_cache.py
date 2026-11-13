"""Per-user Redis cache for GET API responses.

A page switch should not wait on the database. A successful GET on a data
endpoint is stored under (data version, user, auth version, portal, URL) and
served from Redis on the next identical request.

Safety:
- Entries are per user, so one person's data is never shown to another.
- The session is still checked on every request; a revoked session or an
  auth_version change (password reset, account lock) misses the cache.
- Users who must change their password, or non-admins during AI maintenance,
  always reach the view and get its 403/503.
- Every successful API write bumps the shared data version (see
  ApiDatabaseErrorMiddleware), so nobody reads data older than the last write.
  Writes made outside the API (worker SLA/outbox jobs) show up within TTL_SECONDS.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.http import HttpResponse

from api_core import read_cache

log = logging.getLogger(__name__)

TTL_SECONDS = 300
CACHED_PREFIXES = (
    "/api/v1/workspace/",
    "/api/v1/admin/",
    "/api/v1/requests",
    "/api/v1/request-types",
    "/api/v1/meta/",
    "/api/v1/reports/",
    "/api/v1/delegations",
    "/api/v1/ops/",
)
# Live state that must always come from the source.
LIVE_PATHS = (
    "/api/v1/admin/ai-engine/",
    "/api/v1/admin/diagnostics",
    "/api/v1/admin/overview",
    "/api/v1/requests/route-preview",
)


def _cacheable(request) -> bool:
    path = request.path
    return (
        request.method == "GET"
        and path.startswith(CACHED_PREFIXES)
        and not path.startswith(LIVE_PATHS)
        and "/attachments/" not in path
        and "/download" not in path
    )


class ApiResponseCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not _cacheable(request):
            return self.get_response(request)
        from api_core.authn.service import load_actor_from_session
        from api_core.maintenance import is_admin_actor, is_maintenance_active

        try:
            actor = load_actor_from_session(request)
        except Exception:  # noqa: BLE001 - let the view report the failure
            return self.get_response(request)
        if (
            actor is None
            or getattr(actor, "must_change_password", False)
            or (is_maintenance_active() and not is_admin_actor(actor))
        ):
            return self.get_response(request)
        request.actor = actor  # require_actor reuses it: no second lookup
        portal = request.headers.get("X-EAS-Portal", "")
        key = (
            f"eas:resp:{read_cache.version()}:{actor.id}:{getattr(actor, 'auth_version', 0)}:"
            f"{portal}:{request.get_full_path()}"
        )
        try:
            hit = cache.get(key)
        except Exception:  # noqa: BLE001 - cache down: serve from the database
            hit = None
        if hit is not None:
            response = HttpResponse(hit, content_type="application/json")
            response["X-EAS-Cache"] = "hit"
            return response
        response = self.get_response(request)
        if response.status_code == 200 and "application/json" in response.get(
            "Content-Type", ""
        ):
            try:
                cache.set(key, response.content, timeout=TTL_SECONDS)
            except Exception:  # noqa: BLE001
                log.warning("Response cache write failed; served without caching")
        return response
