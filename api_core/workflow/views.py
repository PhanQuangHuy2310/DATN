from __future__ import annotations

from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from api_core.authn.service import require_actor
from api_core.http import JsonBodyError, api_error, correlation_id, parse_json_object

from .attachments import register_attachment, register_execution_evidence
from .service import (
    CommandError,
    cancel_request,
    create_draft,
    decide_acceptance,
    decide_approval,
    start_execution,
    submit_execution,
    submit_request,
)


def _key(request: HttpRequest) -> str | None:
    value = request.headers.get("Idempotency-Key")
    return value.strip() if value else None


@require_GET
@require_actor()
def request_list(request: HttpRequest) -> JsonResponse:
    try:
        limit = int(request.GET.get("limit", "20"))
        offset = int(request.GET.get("offset", "0"))
    except ValueError:
        return api_error(request, "INVALID_PAGINATION", status=400)
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        return api_error(request, "INVALID_PAGINATION", status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT r.id::text,r.code,rt.code,r.status,r.lock_version,r.updated_at
            FROM eas.request r
            JOIN eas.request_type rt ON rt.id=r.type_id
            LEFT JOIN eas.request_participant p
              ON p.request_id=r.id AND p.user_id=%s AND p.read_revoked_at IS NULL
            WHERE r.requester_id=%s OR p.id IS NOT NULL
            ORDER BY r.updated_at DESC,r.id DESC LIMIT %s OFFSET %s
            """,
            [request.actor.id, request.actor.id, limit + 1, offset],
        )
        rows = cursor.fetchall()
    items = [
        {
            "id": row[0],
            "code": row[1],
            "type_code": row[2],
            "status": row[3],
            "lock_version": row[4],
            "updated_at": row[5].isoformat(),
        }
        for row in rows[:limit]
    ]
    return JsonResponse(
        {
            "items": items,
            "next_offset": offset + limit if len(rows) > limit else None,
            "correlation_id": correlation_id(request),
        }
    )


@require_GET
@require_actor()
def request_detail(request: HttpRequest, request_id: str) -> JsonResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id::text,r.code,rt.code,r.status,r.lock_version,
                   r.requester_id::text,r.draft_payload,v.payload,v.revision_no,
                   r.created_at,r.updated_at
            FROM eas.request r
            JOIN eas.request_type rt ON rt.id=r.type_id
            LEFT JOIN eas.request_revision v ON v.id=r.current_revision_id
            LEFT JOIN eas.request_participant p
              ON p.request_id=r.id AND p.user_id=%s AND p.read_revoked_at IS NULL
            WHERE r.id=%s AND (r.requester_id=%s OR p.id IS NOT NULL)
            """,
            [request.actor.id, request_id, request.actor.id],
        )
        row = cursor.fetchone()
        if not row:
            return api_error(request, "REQUEST_NOT_FOUND", status=404)
        cursor.execute(
            """
            SELECT step_no,assignee_id::text,state,activated_at,closed_at
            FROM eas.approval_step WHERE request_id=%s ORDER BY step_no
            """,
            [request_id],
        )
        steps = cursor.fetchall()
        cursor.execute(
            """
            SELECT i.lifecycle,i.planned_executor_id::text,i.acceptor_id::text,
                   a.id::text,a.attempt_no,a.executor_id::text,a.state,
                   a.result_note,a.external_reference
            FROM eas.workflow_instance i
            LEFT JOIN eas.execution_attempt a ON a.instance_id=i.id
              AND a.state IN ('READY','RUNNING','SUBMITTED')
            WHERE i.request_id=%s AND i.revision_id=(
              SELECT current_revision_id FROM eas.request WHERE id=%s
            )
            ORDER BY a.attempt_no DESC NULLS LAST LIMIT 1
            """,
            [request_id, request_id],
        )
        workflow = cursor.fetchone()
    return JsonResponse(
        {
            "request": {
                "id": row[0],
                "code": row[1],
                "type_code": row[2],
                "status": row[3],
                "lock_version": row[4],
                "requester_id": row[5],
                "payload": row[7] if row[7] is not None else row[6],
                "revision_no": row[8],
                "created_at": row[9].isoformat(),
                "updated_at": row[10].isoformat(),
                "approval_steps": [
                    {
                        "step_no": step[0],
                        "assignee_id": step[1],
                        "state": step[2],
                        "activated_at": step[3].isoformat() if step[3] else None,
                        "closed_at": step[4].isoformat() if step[4] else None,
                    }
                    for step in steps
                ],
                "workflow": (
                    {
                        "lifecycle": workflow[0],
                        "planned_executor_id": workflow[1],
                        "acceptor_id": workflow[2],
                        "attempt": (
                            {
                                "id": workflow[3],
                                "attempt_no": workflow[4],
                                "executor_id": workflow[5],
                                "state": workflow[6],
                                "result_note": workflow[7],
                                "external_reference": workflow[8],
                            }
                            if workflow[3]
                            else None
                        ),
                    }
                    if workflow
                    else None
                ),
            },
            "correlation_id": correlation_id(request),
        }
    )


@require_POST
@require_actor("REQUESTER")
def draft(request: HttpRequest) -> JsonResponse:
    key = _key(request)
    if not key:
        return api_error(request, "IDEMPOTENCY_KEY_REQUIRED", status=400)
    try:
        body = parse_json_object(request)
        result = create_draft(
            actor=request.actor,
            body=body,
            idempotency_key=key,
            correlation_id=correlation_id(request),
        )
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    response = JsonResponse(result.body, status=result.status)
    response["X-Idempotent-Replay"] = "true" if result.replayed else "false"
    response["X-Correlation-ID"] = correlation_id(request)
    return response


@require_POST
@require_actor("REQUESTER")
def submit(request: HttpRequest) -> JsonResponse:
    key = _key(request)
    if not key:
        return api_error(request, "IDEMPOTENCY_KEY_REQUIRED", status=400)
    try:
        body = parse_json_object(request)
        result = submit_request(
            actor=request.actor,
            body=body,
            idempotency_key=key,
            correlation_id=correlation_id(request),
        )
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    response = JsonResponse(result.body, status=result.status)
    response["X-Idempotent-Replay"] = "true" if result.replayed else "false"
    response["X-Correlation-ID"] = correlation_id(request)
    return response


@require_POST
@require_actor("APPROVER")
def approval_decision(request: HttpRequest, request_id: str) -> JsonResponse:
    key = _key(request)
    if not key:
        return api_error(request, "IDEMPOTENCY_KEY_REQUIRED", status=400)
    try:
        body = parse_json_object(request)
        result = decide_approval(
            actor=request.actor,
            request_id=request_id,
            body=body,
            idempotency_key=key,
            correlation_id=correlation_id(request),
        )
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    response = JsonResponse(result.body, status=result.status)
    response["X-Idempotent-Replay"] = "true" if result.replayed else "false"
    response["X-Correlation-ID"] = correlation_id(request)
    return response


@require_POST
@require_actor("REQUESTER")
def attachment(request: HttpRequest, request_id: str) -> JsonResponse:
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return api_error(request, "FILE_REQUIRED", status=400)
    try:
        body = register_attachment(
            actor=request.actor,
            request_id=str(request_id),
            original_name=uploaded.name,
            data=uploaded.read(10 * 1024 * 1024 + 1),
            correlation_id=correlation_id(request),
        )
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    response = JsonResponse(body, status=201)
    response["X-Correlation-ID"] = correlation_id(request)
    return response


def _command_response(request: HttpRequest, operation, **kwargs) -> JsonResponse:
    key = _key(request)
    if not key:
        return api_error(request, "IDEMPOTENCY_KEY_REQUIRED", status=400)
    try:
        body = parse_json_object(request)
        result = operation(
            actor=request.actor,
            body=body,
            idempotency_key=key,
            correlation_id=correlation_id(request),
            **kwargs,
        )
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    response = JsonResponse(result.body, status=result.status)
    response["X-Idempotent-Replay"] = "true" if result.replayed else "false"
    response["X-Correlation-ID"] = correlation_id(request)
    return response


@require_POST
@require_actor("EXECUTOR")
def execution_start(request: HttpRequest, request_id: str) -> JsonResponse:
    return _command_response(request, start_execution, request_id=str(request_id))


@require_POST
@require_actor("EXECUTOR")
def execution_submit(request: HttpRequest, request_id: str) -> JsonResponse:
    return _command_response(request, submit_execution, request_id=str(request_id))


@require_POST
@require_actor("ACCEPTOR")
def acceptance_decision(request: HttpRequest, request_id: str) -> JsonResponse:
    return _command_response(request, decide_acceptance, request_id=str(request_id))


@require_POST
@require_actor("EXECUTOR")
def execution_attachment(request: HttpRequest, request_id: str) -> JsonResponse:
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return api_error(request, "FILE_REQUIRED", status=400)
    try:
        body = register_execution_evidence(
            actor=request.actor,
            request_id=str(request_id),
            original_name=uploaded.name,
            data=uploaded.read(10 * 1024 * 1024 + 1),
            correlation_id=correlation_id(request),
        )
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    response = JsonResponse(body, status=201)
    response["X-Correlation-ID"] = correlation_id(request)
    return response


@require_POST
@require_actor("REQUESTER")
def cancellation(request: HttpRequest, request_id: str) -> JsonResponse:
    return _command_response(request, cancel_request, request_id=str(request_id))
