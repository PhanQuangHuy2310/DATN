"""Safe JSON reporting of unexpected API database failures.

Logs only a redacted SQLSTATE, exception class and correlation ID. These
are sufficient for diagnosis without exposing credentials or SQL payloads.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import DatabaseError, connection

from api_core.db_diagnostics import api_db_failure, failure_category, sqlstate
from api_core.http import api_error, correlation_id
from api_core.query_timing import QueryTiming

log = logging.getLogger("eas.database")


class ApiDatabaseErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Strictly opt-in: no query text, SQL arguments, credentials or cookies
        # are recorded. Use this only to find slow endpoints before tuning SQL.
        if not getattr(settings, "EAS_DB_TRACE_ENABLED", False):
            return self.get_response(request)
        counter = QueryTiming()
        with connection.execute_wrapper(counter):
            response = self.get_response(request)
        if counter.count:
            log.info(
                "DB metrics path=%s queries=%s total_ms=%.1f max_ms=%.1f",
                request.path, counter.count, counter.duration_ms, counter.max_ms,
            )
        return response

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/v1/") or not isinstance(exception, DatabaseError):
            return None
        request_id = correlation_id(request)
        state = sqlstate(exception)
        category = failure_category(exception)
        code, status = api_db_failure(exception)
        log.error(
            "API database failure: path=%s category=%s exception_type=%s "
            "SQLSTATE=%s correlation_id=%s",
            request.path, category, type(exception).__name__, state, request_id,
            extra={"correlation_id": request_id},
        )
        # No raw driver message, SQL, credentials, host or user info in response.
        headers = {"Retry-After": "3"} if status == 503 else None
        return api_error(request, code, status=status, headers=headers)
