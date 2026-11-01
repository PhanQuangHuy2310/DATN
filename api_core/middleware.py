"""Safe JSON reporting of unexpected API database failures and security hardening.

Logs only a redacted SQLSTATE, exception class and correlation ID. These
are sufficient for diagnosis without exposing credentials or SQL payloads.
"""

from __future__ import annotations

import logging
import time
from hashlib import sha256

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError

from api_core.db_diagnostics import api_db_failure, failure_category, sqlstate
from api_core.http import api_error, correlation_id

log = logging.getLogger("eas.database")


class ApiSecurityHeadersMiddleware:
    """Enterprise HTTP defense-in-depth headers (ISO/IEC 27001 & SOC 2)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response["Cross-Origin-Opener-Policy"] = "same-origin"

        if not response.has_header("Content-Security-Policy"):
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "connect-src 'self' http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:*; "
                "frame-ancestors 'none'; "
                "form-action 'self';"
            )
        return response


def client_ip(request) -> str:
    """Resolve the caller address without trusting spoofable headers.

    Behind our own reverse proxy every request shares the proxy's socket
    address, so counting by REMOTE_ADDR would throttle the whole company as one
    client. When the deployment declares a trusted proxy (SECURE_PROXY_SSL_HEADER
    is configured, i.e. EAS_TRUST_PROXY_HEADERS=true) the *last* X-Forwarded-For
    entry is used: it is the one appended by our proxy, whereas earlier entries
    are client-controlled and therefore ignored.
    """
    remote = request.META.get("REMOTE_ADDR", "127.0.0.1")
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip() or remote
    return remote


class ApiRateLimitMiddleware:
    """Sliding-window IP rate limiting for API endpoints (ISO 27001 A.12.1.3 & DoS Protection)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        env = getattr(settings, "ENVIRONMENT", "development")
        if (
            env == "test"
            or not request.path.startswith("/api/v1/")
            or request.path.startswith("/health/")
        ):
            return self.get_response(request)

        ip_hash = sha256(client_ip(request).encode("utf-8")).hexdigest()[:16]
        cache_key = f"eas:ratelimit:api:{ip_hash}"
        limit = int(getattr(settings, "EAS_API_RATE_LIMIT_PER_MINUTE", 300))

        try:
            current = cache.get(cache_key)
            if current is not None and int(current) >= limit:
                return api_error(
                    request,
                    "RATE_LIMIT_EXCEEDED",
                    status=429,
                    headers={"Retry-After": "60"},
                )

            if not cache.add(cache_key, 1, timeout=60):
                try:
                    cache.incr(cache_key)
                except ValueError:
                    cache.set(cache_key, 1, timeout=60)
        except Exception:  # noqa: BLE001
            # Availability first: a cache outage must never take the API down.
            log.warning("Rate limiter cache unavailable; request allowed (fail-open)")

        return self.get_response(request)


class ApiDatabaseErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        if request.path.startswith("/api/v1/"):
            response["Server-Timing"] = f"app;dur={duration_ms}"
            if duration_ms >= 1200:
                log.warning(
                    "Slow API request: path=%s duration_ms=%s status=%s",
                    request.path,
                    duration_ms,
                    response.status_code,
                )
        return response

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/v1/"):
            return None
        request_id = correlation_id(request)
        if isinstance(exception, DatabaseError):
            state = sqlstate(exception)
            category = failure_category(exception)
            code, status = api_db_failure(exception)
            log.error(
                "API database failure: path=%s category=%s exception_type=%s "
                "SQLSTATE=%s correlation_id=%s",
                request.path,
                category,
                type(exception).__name__,
                state,
                request_id,
                extra={"correlation_id": request_id},
            )
            # No raw driver message, SQL, credentials, host or user info in response.
            headers = {"Retry-After": "3"} if status == 503 else None
            return api_error(request, code, status=status, headers=headers)

        log.exception(
            "Unhandled API failure: path=%s exception_type=%s correlation_id=%s",
            request.path,
            type(exception).__name__,
            request_id,
            extra={"correlation_id": request_id},
        )
        return api_error(request, "INTERNAL_SERVER_ERROR", status=500)
