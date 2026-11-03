from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from api_core.http import JsonBodyError, api_error, parse_json_object

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
@require_http_methods(["GET", "POST"])
def publish_ai_policy_rules(request: HttpRequest) -> JsonResponse:
    """POLICY_ADMIN: GET lists versions; POST stores (and activates) a version."""
    from api_core.authn.service import require_actor
    from api_core.http import correlation_id
    from api_core.workflow.service import CommandError

    from . import ai_policy

    @require_actor("POLICY_ADMIN")
    def _handle(req: HttpRequest) -> JsonResponse:
        if req.method == "GET":
            return JsonResponse(
                {**ai_policy.list_versions(), "correlation_id": correlation_id(req)}
            )
        if req.method != "POST":
            return api_error(req, "METHOD_NOT_ALLOWED", status=405)
        try:
            body = parse_json_object(req)
            stored = ai_policy.publish_version(
                actor=req.actor, body=body, correlation_id=correlation_id(req)
            )
        except JsonBodyError as exc:
            return api_error(req, str(exc), status=400)
        except CommandError as exc:
            return api_error(req, exc.code, status=exc.status)
        applied = (
            ai_policy.push_to_ai(stored, correlation_id(req))
            if stored["activated"]
            else None
        )
        return JsonResponse(
            {
                "policy": stored,
                "ai_cache_refreshed": applied is not None,
                "correlation_id": correlation_id(req),
            },
            status=201,
        )

    return _handle(request)


@require_POST
def activate_ai_policy_version(request: HttpRequest, version_id) -> JsonResponse:
    """POLICY_ADMIN activates (or restores) a stored version."""
    from api_core.authn.service import require_actor
    from api_core.http import correlation_id
    from api_core.workflow.service import CommandError

    from . import ai_policy

    @require_actor("POLICY_ADMIN")
    def _handle(req: HttpRequest) -> JsonResponse:
        try:
            document = ai_policy.activate_version(
                actor=req.actor,
                version_id=str(version_id),
                correlation_id=correlation_id(req),
            )
        except CommandError as exc:
            return api_error(req, exc.code, status=exc.status)
        applied = ai_policy.push_to_ai(document, correlation_id(req))
        return JsonResponse(
            {
                "policy": document,
                "ai_cache_refreshed": applied is not None,
                "correlation_id": correlation_id(req),
            }
        )

    return _handle(request)


# called by the AI service over the Docker network
@require_GET
def internal_active_ai_policy(request: HttpRequest) -> JsonResponse:
    """AI service pulls the active version when its cache is empty."""
    import hmac

    from . import ai_policy

    supplied = request.headers.get("X-Internal-Secret") or ""
    expected = settings.EAS_AI_INTERNAL_SECRET
    if not expected or not hmac.compare_digest(supplied, expected):
        return api_error(request, "UNAUTHORIZED", status=401)
    document = ai_policy.active_document()
    if document is None:
        return api_error(request, "NO_ACTIVE_POLICY", status=404)
    return JsonResponse(document)
