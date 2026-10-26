"""Safe JSON error handling for unexpected API database failures.

Retains HTTP 500, logs a SQLSTATE and correlation ID without SQL text, values,
or credentials, and avoids exposing Django debug HTML to the React client.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import DatabaseError

from api_core.http import api_error, correlation_id

log = logging.getLogger("eas.database")


def _sqlstate(exc: BaseException) -> str:
    visited: set[int] = set()
    current = exc
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        state = getattr(current, "sqlstate", None)
        if isinstance(state, str) and len(state) == 5 and state.isalnum():
            return state
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return "unknown"


class ApiDatabaseErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/v1/") or not isinstance(exception, DatabaseError):
            return None
        request_id = correlation_id(request)
        state = _sqlstate(exception)
        log.error(
            "API database exception: path=%s, SQLSTATE=%s, correlation_id=%s",
            request.path, state, request_id,
            extra={"correlation_id": request_id},
        )
        headers = {"X-EAS-SQLSTATE": state} if settings.DEBUG else None
        return api_error(
            request,
            "DATABASE_QUERY_FAILED",
            status=500,
            headers=headers,
        )
