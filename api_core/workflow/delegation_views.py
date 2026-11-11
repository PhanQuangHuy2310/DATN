from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from api_core.authn.service import require_actor
from api_core.http import api_error, correlation_id
from api_core.workflow.delegation_service import (
    create_delegation,
    delegate_candidates,
    list_delegations,
    revoke_delegation,
)
from api_core.workflow.service import CommandError
from api_core.workflow.views import _command_response


def _read(request: HttpRequest, operation, **kwargs) -> JsonResponse:
    try:
        body = operation(request.actor, request.GET.dict(), **kwargs)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    body["correlation_id"] = correlation_id(request)
    return JsonResponse(body)


def _list_or_create(request: HttpRequest, *, ops: bool) -> JsonResponse:
    if request.method == "GET":
        return _read(request, list_delegations, ops=ops)
    if request.method == "POST":
        return _command_response(request, create_delegation, ops=ops)
    return api_error(request, "METHOD_NOT_ALLOWED", status=405)


# Approvers manage their own delegations (client portal).
@require_actor("APPROVER")
def delegations_view(request: HttpRequest) -> JsonResponse:
    return _list_or_create(request, ops=False)


@require_POST
@require_actor("APPROVER")
def delegation_revoke_view(request: HttpRequest, delegation_id) -> JsonResponse:
    return _command_response(
        request, revoke_delegation, delegation_id=str(delegation_id), ops=False
    )


@require_GET
@require_actor("APPROVER", "OPS_ADMIN")
def delegation_candidates_view(request: HttpRequest) -> JsonResponse:
    return _read(request, delegate_candidates)


# Ops Admin acts for an absent approver (thesis SD-22), admin portal.
@require_actor("OPS_ADMIN")
def ops_delegations_view(request: HttpRequest) -> JsonResponse:
    return _list_or_create(request, ops=True)


@require_POST
@require_actor("OPS_ADMIN")
def ops_delegation_revoke_view(request: HttpRequest, delegation_id) -> JsonResponse:
    return _command_response(
        request, revoke_delegation, delegation_id=str(delegation_id), ops=True
    )


@require_POST
@require_actor("REQUESTER", "APPROVER")
def attachment_ocr_view(request: HttpRequest, attachment_id) -> JsonResponse:
    """OCR an attachment the actor may read (C4); result is advisory."""
    from api_core.workflow.ocr_service import run_attachment_ocr

    try:
        body = run_attachment_ocr(
            request.actor, str(attachment_id), correlation_id(request)
        )
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    body["correlation_id"] = correlation_id(request)
    return JsonResponse(body)
