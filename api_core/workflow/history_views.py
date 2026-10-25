"""Read-only history and removal of draft attachment links (not stored objects)."""

from django.db import connection, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from api_core.authn.service import require_actor
from api_core.http import api_error

from .service import (
    CommandError,
    _append_request_audit,
    _authorize,
    _execute_idempotent,
)
from .views import _command_response, request_detail


def rows(cursor):
    names = [col[0] for col in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


@require_GET
@require_actor()
def history(request, request_id):
    with transaction.atomic(), connection.cursor() as c:
        c.execute("SELECT eas.lock_security(false)")
        response = request_detail(request, request_id)
        if response.status_code != 200:
            return response
        # Authorization is checked by the same detail endpoint, under the security lock.
        c.execute(
            "SELECT requester_id::text,status FROM eas.request WHERE id=%s",
            [str(request_id)],
        )
        owner, status = c.fetchone()
        draft = []
        if owner == request.actor.id and status in ("DRAFT", "NEEDS_INFO"):
            c.execute(
                """SELECT a.id::text,a.original_name,a.mime,a.size_bytes,a.scan_state
                FROM eas.draft_attachment da JOIN eas.attachment a ON a.id=da.attachment_id
                WHERE da.request_id=%s AND a.deleted_at IS NULL ORDER BY a.created_at""",
                [str(request_id)],
            )
            draft = rows(c)
        c.execute(
            """SELECT a.id::text,a.attempt_no,a.executor_id::text,u.display_name AS executor_name,
            a.state,a.closure_kind,a.result_note,a.external_reference,a.started_at,a.submitted_at,a.closed_at
            FROM eas.execution_attempt a JOIN eas.app_user u ON u.id=a.executor_id
            WHERE a.request_id=%s ORDER BY a.started_at NULLS LAST,a.attempt_no,a.id""",
            [str(request_id)],
        )
        attempts = rows(c)
        for attempt in attempts:
            c.execute(
                """SELECT f.id::text,f.original_name,f.scan_state FROM eas.execution_attachment e
                JOIN eas.attachment f ON f.id=e.attachment_id WHERE e.attempt_id=%s AND f.deleted_at IS NULL""",
                [attempt["id"]],
            )
            attempt["attachments"] = rows(c)
            c.execute(
                """SELECT d.outcome,d.reason,d.decided_at,u.display_name AS actor_name
                FROM eas.acceptance_decision d JOIN eas.app_user u ON u.id=d.actor_id
                WHERE d.attempt_id=%s ORDER BY d.decided_at""",
                [attempt["id"]],
            )
            attempt["decisions"] = rows(c)
        c.execute(
            """SELECT d.outcome,d.reason,d.decided_at,s.step_no,u.display_name AS actor_name
            FROM eas.approval_decision d JOIN eas.approval_step s ON s.id=d.step_id
            JOIN eas.app_user u ON u.id=d.actor_id WHERE d.request_id=%s ORDER BY d.decided_at""",
            [str(request_id)],
        )
        decisions = rows(c)
    return JsonResponse(
        {"draft_attachments": draft, "attempts": attempts, "decisions": decisions}
    )


def unlink_attachment(
    *, actor, request_id, attachment_id, body, idempotency_key, correlation_id
):
    if set(body) != {"expected_version"} or type(body["expected_version"]) is not int:
        raise CommandError("EXPECTED_VERSION_REQUIRED", status=422)

    def operation(c):
        c.execute(
            """SELECT r.requester_id::text,r.status,r.lock_version,r.type_id::text,u.department_id::text
            FROM eas.request r JOIN eas.app_user u ON u.id=r.requester_id WHERE r.id=%s FOR UPDATE OF r""",
            [request_id],
        )
        row = c.fetchone()
        if not row:
            raise CommandError("REQUEST_NOT_FOUND", status=404)
        if row[0] != actor.id:
            raise CommandError("FORBIDDEN", status=403)
        _authorize(
            c, actor_id=actor.id, role="REQUESTER", department_id=row[4], type_id=row[3]
        )
        if row[1] not in ("DRAFT", "NEEDS_INFO"):
            raise CommandError("REQUEST_STATE_CONFLICT", status=409)
        if row[2] != body["expected_version"]:
            raise CommandError("VERSION_CONFLICT", status=409)
        c.execute(
            "DELETE FROM eas.draft_attachment WHERE request_id=%s AND attachment_id=%s RETURNING attachment_id",
            [request_id, attachment_id],
        )
        if not c.fetchone():
            raise CommandError("ATTACHMENT_NOT_FOUND", status=404)
        c.execute(
            "UPDATE eas.request SET lock_version=lock_version+1,updated_at=statement_timestamp() WHERE id=%s",
            [request_id],
        )
        _append_request_audit(
            c,
            request_id=request_id,
            actor_id=actor.id,
            action="DRAFT_ATTACHMENT_REMOVED",
            target_type="attachment",
            target_id=attachment_id,
            details={},
            correlation_id=correlation_id,
        )
        return {"removed": True, "lock_version": row[2] + 1}, 200, request_id

    return _execute_idempotent(
        actor_id=actor.id,
        scope="draft:unlink:" + request_id + ":" + attachment_id,
        key=idempotency_key,
        command_body=body,
        operation=operation,
    )


@require_actor("REQUESTER")
def remove_draft_attachment(request, request_id, attachment_id):
    if request.method != "DELETE":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    return _command_response(
        request,
        unlink_attachment,
        request_id=str(request_id),
        attachment_id=str(attachment_id),
    )
