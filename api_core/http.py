from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from django.http import HttpRequest, JsonResponse


class JsonBodyError(ValueError):
    pass


def correlation_id(request: HttpRequest) -> str:
    existing = getattr(request, "correlation_id", None)
    if existing:
        return existing
    supplied = request.headers.get("X-Correlation-ID", "")
    try:
        value = str(UUID(supplied)) if supplied else str(uuid4())
    except (ValueError, TypeError, AttributeError):
        value = str(uuid4())
    request.correlation_id = value
    return value


def parse_json_object(
    request: HttpRequest, *, max_bytes: int = 64 * 1024
) -> dict[str, Any]:
    if request.content_type != "application/json":
        raise JsonBodyError("CONTENT_TYPE_MUST_BE_JSON")
    if len(request.body) > max_bytes:
        raise JsonBodyError("BODY_TOO_LARGE")
    try:
        value = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise JsonBodyError("MALFORMED_JSON") from None
    if not isinstance(value, dict):
        raise JsonBodyError("OBJECT_REQUIRED")
    return value


def api_error(
    request: HttpRequest,
    code: str,
    *,
    status: int,
    fields: dict[str, list[str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JsonResponse:
    response = JsonResponse(
        {
            "error": {"code": code, **({"fields": fields} if fields else {})},
            "correlation_id": correlation_id(request),
        },
        status=status,
    )
    response["X-Correlation-ID"] = request.correlation_id
    for key, value in (headers or {}).items():
        response[key] = value
    return response
