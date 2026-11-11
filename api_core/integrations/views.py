"""Picker values for request forms, fetched from the external systems by EAS.

Browsers never call the external systems directly.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from api_core.authn.service import require_actor
from api_core.http import api_error
from api_core.workflow.errors import CommandError

from .requests import PICKER_TYPES, options


@require_GET
@require_actor("REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR")
def form_options(request):
    type_code = request.GET.get("type_code", "")
    if type_code not in PICKER_TYPES:
        return JsonResponse({"fields": {}})
    try:
        fields = options(type_code)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status)
    response = JsonResponse({"fields": fields})
    response["Cache-Control"] = "private, max-age=30"
    return response
