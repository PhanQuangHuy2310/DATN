"""Safe JSON reporting of unexpected API database failures.

Logs only a redacted SQLSTATE, exception class and correlation ID. These
are sufficient for diagnosis without exposing credentials or SQL payloads.
"""

from __future__ import annotations

import logging
import time

from django.db import DatabaseError

from api_core.db_diagnostics import api_db_failure, failure_category, sqlstate
from api_core.http import api_error, correlation_id

log = logging.getLogger("eas.database")


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
        if not request.path.startswith("/api/v1/") or not isinstance(
            exception, DatabaseError
        ):
            return None
        request_id = correlation_id(request)
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
