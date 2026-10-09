import logging

from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from api_core.authn.service import require_actor
from api_core.http import api_error, correlation_id

from .service import RESOURCE_ROLES, QueryValidationError, list_resource

logger = logging.getLogger(__name__)


@require_GET
@require_actor(
    "REQUESTER",
    "APPROVER",
    "EXECUTOR",
    "ACCEPTOR",
    "POLICY_ADMIN",
    "OPS_ADMIN",
    "AUDITOR",
)
def resource_list(request, resource: str):
    request_id = correlation_id(request)
    try:
        data = list_resource(resource, request.GET, roles=request.actor.roles)
    except QueryValidationError as exc:
        code = str(exc)
        return api_error(
            request,
            code,
            status=(
                404
                if code == "RESOURCE_NOT_FOUND"
                else 403
                if code == "RESOURCE_FORBIDDEN"
                else 400
            ),
        )
    except DatabaseError:
        logger.error(
            "mock_source_unavailable",
            extra={"correlation_id": request_id, "resource": resource},
        )
        return api_error(request, "SOURCE_UNAVAILABLE", status=503)
    response = JsonResponse({"data": data, "correlation_id": request_id})
    response["X-Correlation-ID"] = request_id
    response["Cache-Control"] = (
        "no-store" if resource in RESOURCE_ROLES else "private, max-age=30"
    )
    return response
