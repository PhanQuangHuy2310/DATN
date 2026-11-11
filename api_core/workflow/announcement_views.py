"""System update announcements (what changed after an AI regulation update)."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from api_core.authn.service import require_actor
from api_core.http import api_error, correlation_id

from .ai_learning import list_announcements, mark_announcement_read


@require_GET
@require_actor()
def announcements_view(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/announcements?unread=1 — newest first, read state per user."""
    unread_only = request.GET.get("unread") in {"1", "true"}
    items = list_announcements(request.actor, unread_only=unread_only)
    return JsonResponse({"items": items, "correlation_id": correlation_id(request)})


@require_POST
@require_actor()
def announcement_read_view(request: HttpRequest, announcement_id) -> JsonResponse:
    """POST /api/v1/announcements/<id>/read — idempotent acknowledgement."""
    if not mark_announcement_read(request.actor, str(announcement_id)):
        return api_error(request, "NOT_FOUND", status=404)
    return JsonResponse({"read": True, "correlation_id": correlation_id(request)})
