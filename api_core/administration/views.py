from django.db import IntegrityError, connection, transaction
from django.http import JsonResponse

from api_core.authn.service import require_actor
from api_core.http import JsonBodyError, api_error, correlation_id, parse_json_object
from api_core.workflow.service import CommandError

from .catalog import access_matrix, api_catalog
from .service import TABLES, authorize, list_records, mutate, read_record


@require_actor("OPS_ADMIN")
def records(request, kind, record_id=None):
    if kind not in TABLES:
        return api_error(request, "NOT_FOUND", status=404)
    try:
        if request.method == "GET":
            return JsonResponse(
                read_record(request.actor, kind, str(record_id))
                if record_id is not None
                else list_records(request.actor, kind, request.GET)
            )
        if (request.method == "POST" and record_id is None) or (
            request.method in {"PATCH", "DELETE"} and record_id is not None
        ):
            key = request.headers.get("Idempotency-Key", "").strip()
            if not key or len(key) > 200:
                return api_error(request, "IDEMPOTENCY_KEY_REQUIRED", status=400)
            result = mutate(
                request.actor,
                kind,
                str(record_id) if record_id else None,
                parse_json_object(request),
                request.method,
                key,
                correlation_id(request),
            )
            return JsonResponse(result.body, status=result.status)
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    except IntegrityError:
        return api_error(request, "CONSTRAINT_CONFLICT", status=409)


def _read_admin_reference(request, supplier):
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(false)")
            authorize(cursor, request.actor)
            return JsonResponse(supplier())
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_actor("OPS_ADMIN")
def api_catalog_view(request):
    return _read_admin_reference(request, api_catalog)


@require_actor("OPS_ADMIN")
def access_matrix_view(request):
    return _read_admin_reference(request, access_matrix)
