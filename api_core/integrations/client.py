"""The only way EAS talks to the external systems (Mock Systems API).

EAS never reads or writes mock_* tables; it calls this client
(docs/TICH_HOP_HE_THONG_NGOAI.md). The admin circuit breaker
(eas.mock_apis.is_enabled) is honoured before any call.
"""

from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings

from api_core.catalog.integrations import disabled_apis
from api_core.workflow.errors import CommandError


class IntegrationError(CommandError):
    """The external system answered with a business error (e.g. 409)."""


def _check_enabled(system: str) -> None:
    for _code, domain, source in disabled_apis():
        if domain == system:
            raise CommandError(
                "INTEGRATION_DISABLED",
                status=503,
                fields={"integration": [f"Kết nối {source} đang bị tắt."]},
            )


def call(
    system: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call ``/<path>`` of the Mock Systems API; ``system`` is the domain key."""
    _check_enabled(system)
    try:
        response = httpx.request(
            method,
            f"{settings.EAS_MOCK_API_URL}/{path.lstrip('/')}",
            params={k: v for k, v in (params or {}).items() if v is not None},
            json=body,
            headers={"X-Integration-Secret": settings.EAS_MOCK_API_SECRET},
            timeout=settings.EAS_MOCK_API_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        raise CommandError("INTEGRATION_UNAVAILABLE", status=503) from None
    if response.status_code >= 500:
        raise CommandError("INTEGRATION_UNAVAILABLE", status=503)
    try:
        data = response.json()
    except ValueError:
        raise CommandError("INTEGRATION_UNAVAILABLE", status=503) from None
    if response.status_code >= 400:
        code = (data.get("error") or {}).get("code") or "INTEGRATION_REJECTED"
        raise IntegrationError(code, status=response.status_code)
    return data


def get(system: str, path: str, **params: Any) -> dict[str, Any]:
    return call(system, "GET", path, params=params)


def post(system: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    return call(system, "POST", path, body=body)
