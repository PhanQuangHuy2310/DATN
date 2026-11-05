from __future__ import annotations

import hmac
from datetime import datetime
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone as django_timezone
from django.utils.http import content_disposition_header
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from api_core.authn.service import require_actor
from api_core.catalog.plan_catalog import resolve_five_level_metadata
from api_core.http import JsonBodyError, api_error, correlation_id, parse_json_object
from api_core.workflow.attachments import (
    download_attachment,
    get_attachment_metadata,
    register_attachment,
    register_execution_evidence,
)
from api_core.workflow.config_service import (
    create_or_clone_release,
    get_config_release,
    list_config_releases,
    list_policy_type_status,
    policy_actor_options,
    publish_config_release,
    update_draft_release,
    validate_release_candidate,
)
from api_core.workflow.constants import ERR_REQUEST_NOT_FOUND
from api_core.workflow.insights import (
    build_request_progress,
    list_ai_assessments,
    org_chart,
    preview_route,
    run_ai_assessment,
    team_report,
)
from api_core.workflow.ops_service import (
    list_ops_metadata,
    reassign_actor,
    replay_dead_outbox,
)
from api_core.workflow.reporting import (
    get_request_audit_events,
    get_request_audit_verify,
    get_request_metrics_report,
    list_admin_events,
    list_notifications,
    mark_notification_read,
)
from api_core.workflow.service import (
    CommandError,
    cancel_request,
    create_draft,
    decide_acceptance,
    decide_approval,
    list_assignable_executors,
    report_execution_issue,
    start_execution,
    submit_execution,
    submit_request,
    update_draft,
)


def _key(request: HttpRequest) -> str | None:
    value = request.headers.get("Idempotency-Key")
    return value.strip() if value else None


def _command_response(
    request: HttpRequest, operation: Any, **kwargs: Any
) -> JsonResponse:
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


@require_actor()
def request_list(request: HttpRequest) -> JsonResponse:
    try:
        limit = int(request.GET.get("limit", "20"))
        offset = int(request.GET.get("offset", "0"))
    except ValueError:
        return api_error(request, "INVALID_PAGINATION", status=400)
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        return api_error(request, "INVALID_PAGINATION", status=400)

    tab = (request.GET.get("tab") or "").strip() or None
    status_filter = (request.GET.get("status") or "").strip() or None
    search_filter = (request.GET.get("q") or "").strip()[:100] or None
    type_code_filter = (request.GET.get("type_code") or "").strip() or None
    dept_raw = (request.GET.get("department_id") or "").strip() or None
    requester_raw = (request.GET.get("requester_id") or "").strip() or None
    from_raw = (request.GET.get("created_from") or "").strip() or None
    to_raw = (request.GET.get("created_to") or "").strip() or None

    dept_filter = None
    if dept_raw:
        try:
            dept_filter = str(UUID(dept_raw))
        except (ValueError, TypeError):
            return api_error(request, "INVALID_DEPARTMENT_ID", status=400)

    requester_filter = None
    if requester_raw:
        try:
            requester_filter = str(UUID(requester_raw))
        except (ValueError, TypeError):
            return api_error(request, "INVALID_REQUESTER_ID", status=400)

    from_filter = None
    if from_raw:
        try:
            from_filter = datetime.fromisoformat(from_raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return api_error(request, "INVALID_DATE_FILTER", status=400)

    to_filter = None
    if to_raw:
        try:
            to_filter = datetime.fromisoformat(to_raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return api_error(request, "INVALID_DATE_FILTER", status=400)

    sql = """
        SELECT r.id::text, r.code, rt.code, r.status, r.lock_version,
               r.updated_at, r.created_at,
               COALESCE(v.risk_weight, rt.risk_weight),
               COALESCE(v.approval_level, rt.approval_level),
               u.display_name,
               (SELECT au.display_name FROM eas.approval_step ast2
                  JOIN eas.workflow_instance wi2 ON wi2.id = ast2.instance_id
                  JOIN eas.app_user au ON au.id = ast2.assignee_id
                 WHERE ast2.request_id = r.id AND ast2.state = 'ACTIVE'
                   AND wi2.revision_id = r.current_revision_id
                   AND r.status = 'PENDING_APPROVAL'
                 LIMIT 1),
               (SELECT eu.display_name FROM eas.workflow_instance wi3
                  JOIN eas.app_user eu ON eu.id = CASE
                    WHEN r.status = 'WAITING_FOR_ACCEPTANCE' THEN wi3.acceptor_id
                    ELSE COALESCE((SELECT ea3.executor_id FROM eas.execution_attempt ea3
                                    WHERE ea3.instance_id = wi3.id
                                      AND ea3.state IN ('READY','RUNNING','SUBMITTED')
                                    ORDER BY ea3.attempt_no DESC LIMIT 1),
                                  wi3.planned_executor_id) END
                 WHERE wi3.revision_id = r.current_revision_id
                   AND r.status IN ('READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE')
                 LIMIT 1),
               (SELECT st.due_at FROM eas.sla_stage st
                 WHERE st.request_id = r.id AND st.closed_at IS NULL
                 ORDER BY st.started_at DESC LIMIT 1),
               rt.name,
               COALESCE(
                 NULLIF(TRIM(v.payload->>'title'), ''),
                 NULLIF(TRIM(r.draft_payload->>'title'), ''),
                 rt.name
               ),
               COALESCE(v.department_id, u.department_id)::text,
               d.name,
               COALESCE(v.amount_vnd, r.draft_amount_vnd),
               r.requester_id::text
        FROM eas.request r
        JOIN eas.request_type rt ON rt.id = r.type_id
        LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
        LEFT JOIN eas.app_user u ON u.id = r.requester_id
        LEFT JOIN eas.department d ON d.id = COALESCE(v.department_id, u.department_id)
        WHERE (%s::text IS NULL OR r.status = %s)
          AND (%s::uuid IS NULL OR r.requester_id = %s::uuid)
          AND (%s::text IS NULL OR (STRPOS(LOWER(r.code), LOWER(%s::text)) > 0
               OR STRPOS(LOWER(COALESCE(v.payload->>'title', r.draft_payload->>'title', '')),
                         LOWER(%s::text)) > 0
               OR STRPOS(LOWER(COALESCE(u.display_name, '')), LOWER(%s::text)) > 0))
          AND (%s::text IS NULL OR rt.code = %s)
          AND (%s::uuid IS NULL OR COALESCE(v.department_id, u.department_id) = %s::uuid)
          AND (%s::timestamptz IS NULL OR r.created_at >= %s::timestamptz)
          AND (%s::timestamptz IS NULL OR r.created_at <= %s::timestamptz)
          AND (
            (%s::text = 'mine' AND r.requester_id = %s)
            OR (%s::text = 'approval' AND EXISTS (
              SELECT 1 FROM eas.approval_step ast
              JOIN eas.workflow_instance wi ON wi.id = ast.instance_id
              WHERE ast.request_id = r.id AND ast.state = 'ACTIVE'
                AND ast.assignee_id = %s
                AND wi.state = 'ACTIVE' AND wi.revision_id = r.current_revision_id
                AND r.status = 'PENDING_APPROVAL'
                AND EXISTS (
                  SELECT 1 FROM eas.role_membership grant_approver
                  WHERE grant_approver.user_id = %s AND grant_approver.role = 'APPROVER'
                    AND grant_approver.revoked_at IS NULL
                    AND grant_approver.valid_from <= statement_timestamp()
                    AND (grant_approver.valid_to IS NULL OR grant_approver.valid_to > statement_timestamp())
                    AND (grant_approver.scope_kind = 'GLOBAL' OR
                         (grant_approver.scope_kind = 'DEPARTMENT' AND grant_approver.department_id = v.department_id))
                    AND (grant_approver.type_scope = 'ALL' OR
                         (grant_approver.type_scope = 'ONE' AND grant_approver.type_id = r.type_id))
                )
            ))
            OR (%s::text = 'execution' AND EXISTS (
              SELECT 1 FROM eas.workflow_instance wi
              JOIN eas.execution_attempt ea ON ea.instance_id = wi.id
              WHERE wi.request_id = r.id AND wi.state = 'ACTIVE'
                AND wi.revision_id = r.current_revision_id AND ea.executor_id = %s
                AND ((r.status = 'READY_FOR_EXECUTION' AND ea.state = 'READY')
                     OR (r.status = 'IN_PROGRESS' AND ea.state = 'RUNNING'))
                AND EXISTS (
                  SELECT 1 FROM eas.role_membership grant_executor
                  WHERE grant_executor.user_id = %s AND grant_executor.role = 'EXECUTOR'
                    AND grant_executor.revoked_at IS NULL
                    AND grant_executor.valid_from <= statement_timestamp()
                    AND (grant_executor.valid_to IS NULL OR grant_executor.valid_to > statement_timestamp())
                    AND (grant_executor.scope_kind = 'GLOBAL' OR
                         (grant_executor.scope_kind = 'DEPARTMENT' AND grant_executor.department_id = v.department_id))
                    AND (grant_executor.type_scope = 'ALL' OR
                         (grant_executor.type_scope = 'ONE' AND grant_executor.type_id = r.type_id))
                )
            ))
            OR (%s::text = 'acceptance' AND EXISTS (
              SELECT 1 FROM eas.workflow_instance wi
              JOIN eas.execution_attempt ea ON ea.instance_id = wi.id
              WHERE wi.request_id = r.id AND wi.state = 'ACTIVE' AND wi.lifecycle = 'C'
                AND wi.revision_id = r.current_revision_id
                AND r.status = 'WAITING_FOR_ACCEPTANCE'
                AND wi.acceptor_id = %s AND ea.state = 'SUBMITTED'
                AND EXISTS (
                  SELECT 1 FROM eas.role_membership grant_acceptor
                  WHERE grant_acceptor.user_id = %s AND grant_acceptor.role = 'ACCEPTOR'
                    AND grant_acceptor.revoked_at IS NULL
                    AND grant_acceptor.valid_from <= statement_timestamp()
                    AND (grant_acceptor.valid_to IS NULL OR grant_acceptor.valid_to > statement_timestamp())
                    AND (grant_acceptor.scope_kind = 'GLOBAL' OR
                         (grant_acceptor.scope_kind = 'DEPARTMENT' AND grant_acceptor.department_id = v.department_id))
                    AND (grant_acceptor.type_scope = 'ALL' OR
                         (grant_acceptor.type_scope = 'ONE' AND grant_acceptor.type_id = r.type_id))
                )
            ))
            OR (%s::text IS NULL AND (
                r.requester_id = %s
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.request_participant p
                    WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                  )
                )
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.role_membership rm
                    WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
                      AND rm.revoked_at IS NULL
                      AND rm.valid_from <= statement_timestamp()
                      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                      AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
                      AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
                  )
                )
            ))
          )
          AND (
            r.requester_id = %s
            OR (r.status != 'DRAFT' AND EXISTS (
              SELECT 1 FROM eas.request_participant rp
              WHERE rp.request_id = r.id AND rp.user_id = %s AND rp.read_revoked_at IS NULL
            ))
            OR (r.status != 'DRAFT' AND EXISTS (
              SELECT 1 FROM eas.role_membership aud
              WHERE aud.user_id = %s AND aud.role = 'AUDITOR'
                AND aud.revoked_at IS NULL
                AND aud.valid_from <= statement_timestamp()
                AND (aud.valid_to IS NULL OR aud.valid_to > statement_timestamp())
                AND (aud.scope_kind = 'GLOBAL' OR aud.department_id = COALESCE(v.department_id, u.department_id))
                AND (aud.type_scope = 'ALL' OR aud.type_id = r.type_id)
            ))
          )
        ORDER BY r.updated_at DESC, r.id DESC
        LIMIT %s OFFSET %s
    """
    valid_tab = tab if tab in ("mine", "approval", "execution", "acceptance") else None
    tab_roles = {
        "approval": "APPROVER",
        "execution": "EXECUTOR",
        "acceptance": "ACCEPTOR",
    }
    required_role = tab_roles.get(valid_tab)
    if required_role and required_role not in request.actor.roles:
        return JsonResponse(
            {
                "items": [],
                "next_offset": None,
                "correlation_id": correlation_id(request),
            }
        )
    params = [
        status_filter,
        status_filter,
        requester_filter,
        requester_filter,
        search_filter,
        search_filter,
        search_filter,
        search_filter,
        type_code_filter,
        type_code_filter,
        dept_filter,
        dept_filter,
        from_filter,
        from_filter,
        to_filter,
        to_filter,
        valid_tab,
        request.actor.id,
        valid_tab,
        request.actor.id,  # approval step actor
        request.actor.id,  # approval grant
        valid_tab,
        request.actor.id,  # execution attempt actor
        request.actor.id,  # execution grant
        valid_tab,
        request.actor.id,  # acceptor actor
        request.actor.id,  # acceptance grant
        valid_tab,
        request.actor.id,
        request.actor.id,
        request.actor.id,
        request.actor.id,
        request.actor.id,
        request.actor.id,
        limit + 1,
        offset,
    ]

    with connection.cursor() as cursor:
        cursor.execute(  # NOSONAR python:S2077 - query parameterized with psycopg placeholders
            sql, params
        )
        rows = cursor.fetchall()

    items = []
    now = django_timezone.now()
    for row in rows[:limit]:
        risk_w, app_lvl = resolve_five_level_metadata(
            row[2],
            row[7] if len(row) > 7 else None,
            row[8] if len(row) > 8 else None,
        )
        items.append(
            {
                "id": row[0],
                "code": row[1],
                "type_code": row[2],
                "status": row[3],
                "lock_version": row[4],
                "updated_at": row[5].isoformat(),
                "created_at": row[6].isoformat(),
                "risk_weight": risk_w,
                "approval_level": app_lvl,
                "requester_name": row[9] if len(row) > 9 else None,
                "current_assignee_name": (
                    (row[10] or row[11]) if len(row) > 11 else None
                ),
                "due_at": row[12].isoformat() if len(row) > 12 and row[12] else None,
                # Server clock decides overdue so clients never disagree.
                "overdue": bool(len(row) > 12 and row[12] and row[12] < now),
                "type_name": row[13] if len(row) > 13 else None,
                "title": row[14] if len(row) > 14 else None,
                "department_id": row[15] if len(row) > 15 else None,
                "department_name": row[16] if len(row) > 16 else None,
                "amount_vnd": row[17] if len(row) > 17 else None,
                "requester_id": row[18] if len(row) > 18 else None,
            }
        )
    return JsonResponse(
        {
            "items": items,
            "next_offset": offset + limit if len(rows) > limit else None,
            "correlation_id": correlation_id(request),
        }
    )


@require_actor()
def request_list_or_create(request: HttpRequest) -> JsonResponse:
    if request.method == "POST":
        return draft(request)
    elif request.method == "GET":
        return request_list(request)
    return api_error(request, "METHOD_NOT_ALLOWED", status=405)


@csrf_exempt  # NOSONAR python:S4502 - machine-to-machine call with HMAC token
@require_POST
def internal_auto_approve_view(request: HttpRequest, request_id: str) -> JsonResponse:
    from api_core.workflow.auto_approval import try_auto_approve

    supplied = request.headers.get("X-Internal-Secret") or ""
    expected = settings.EAS_WORKER_INTERNAL_SECRET
    if not expected or not hmac.compare_digest(supplied, expected):
        return api_error(request, "UNAUTHORIZED", status=401)
    result = try_auto_approve(str(request_id), correlation_id(request))
    return JsonResponse(
        {
            "approved": result is not None,
            "result": result,
            "correlation_id": correlation_id(request),
        }
    )


@require_actor("APPROVER")
def assignable_executors_view(request: HttpRequest, request_id: str) -> JsonResponse:
    try:
        result = list_assignable_executors(
            actor=request.actor, request_id=str(request_id)
        )
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    result["correlation_id"] = correlation_id(request)
    return JsonResponse(result)


@require_actor()
def request_detail(request: HttpRequest, request_id: str) -> JsonResponse:
    try:
        req_uuid = str(UUID(request_id))
    except (ValueError, TypeError, AttributeError):
        return api_error(request, ERR_REQUEST_NOT_FOUND, status=404)

    # Steps and the active workflow are fetched as JSON in the same statement:
    # each round trip to the Supabase pooler costs far more than the query.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id::text, r.code, rt.code, r.status, r.lock_version,
                   r.requester_id::text, r.draft_payload, v.payload, v.revision_no,
                   r.created_at, r.updated_at,
                   COALESCE(v.risk_weight, rt.risk_weight),
                   COALESCE(v.approval_level, rt.approval_level),
                   (SELECT COALESCE(json_agg(json_build_object(
                        'step_no', s.step_no, 'assignee_id', s.assignee_id,
                        'state', s.state, 'activated_at', s.activated_at,
                        'closed_at', s.closed_at,
                        'tier_level', COALESCE(s.tier_level, s.step_no),
                        'resolver_code', s.resolver_code,
                        'assignee_name', su.display_name) ORDER BY s.step_no), '[]'::json)
                      FROM eas.approval_step s
                      JOIN eas.workflow_instance si ON si.id = s.instance_id
                      LEFT JOIN eas.app_user su ON su.id = s.assignee_id
                     WHERE s.request_id = r.id AND si.revision_id = r.current_revision_id),
                   (SELECT json_build_object(
                        'lifecycle', wi.lifecycle,
                        'planned_executor_id', wi.planned_executor_id,
                        'acceptor_id', wi.acceptor_id,
                        'attempt', (SELECT json_build_object(
                            'id', a.id, 'attempt_no', a.attempt_no,
                            'executor_id', a.executor_id, 'state', a.state,
                            'result_note', a.result_note,
                            'external_reference', a.external_reference)
                          FROM eas.execution_attempt a
                         WHERE a.instance_id = wi.id
                           AND a.state IN ('READY', 'RUNNING', 'SUBMITTED')
                         ORDER BY a.attempt_no DESC LIMIT 1))
                      FROM eas.workflow_instance wi
                     WHERE wi.request_id = r.id AND wi.revision_id = r.current_revision_id
                     LIMIT 1),
                   u.display_name,
                   COALESCE(v.department_id, u.department_id)::text,
                   d.name,
                   COALESCE(v.amount_vnd, r.draft_amount_vnd),
                   rt.name
            FROM eas.request r
            JOIN eas.request_type rt ON rt.id = r.type_id
            LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
            LEFT JOIN eas.app_user u ON u.id = r.requester_id
            LEFT JOIN eas.department d ON d.id = COALESCE(v.department_id, u.department_id)
            WHERE r.id = %s
              AND (
                r.requester_id = %s
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.request_participant p
                    WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                  )
                )
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.role_membership rm
                    WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
                      AND rm.revoked_at IS NULL
                      AND rm.valid_from <= statement_timestamp()
                      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                      AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
                      AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
                  )
                )
              )
            """,
            [req_uuid, request.actor.id, request.actor.id, request.actor.id],
        )
        row = cursor.fetchone()
        if not row:
            return api_error(request, ERR_REQUEST_NOT_FOUND, status=404)

        step_items = list(row[13] or []) if len(row) > 13 else []
        workflow_payload = row[14] if len(row) > 14 else None
        progress = build_request_progress(
            cursor,
            request_id=req_uuid,
            status=row[3],
            steps=step_items,
            workflow=workflow_payload,
            requester_id=row[5],
        )

    status = row[3]
    requester_id = row[5]
    draft_payload = row[6]
    revision_payload = row[7]

    if status == "NEEDS_INFO":
        if request.actor.id == requester_id:
            effective_payload = (
                draft_payload if draft_payload is not None else revision_payload
            )
        else:
            effective_payload = revision_payload
    elif status == "DRAFT":
        effective_payload = draft_payload
    else:
        effective_payload = (
            revision_payload if revision_payload is not None else draft_payload
        )

    raw_risk = row[11] if len(row) > 11 else None
    if step_items:
        raw_app_level = len(step_items)
    elif len(row) > 12:
        raw_app_level = row[12]
    else:
        raw_app_level = None
    risk_w, app_lvl = resolve_five_level_metadata(row[2], raw_risk, raw_app_level)
    resolved_users: dict[str, str] = {}
    if isinstance(effective_payload, dict):
        candidate_uuids: list[str] = []
        for val in effective_payload.values():
            if isinstance(val, str) and len(val) == 36:
                try:
                    candidate_uuids.append(str(UUID(val)))
                except (ValueError, TypeError):
                    continue
        if candidate_uuids:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id::text, display_name FROM eas.app_user WHERE id = ANY(%s::uuid[])",
                        [candidate_uuids],
                    )
                    resolved_users = {
                        urow[0]: urow[1]
                        for urow in (cursor.fetchall() or [])
                        if urow and len(urow) >= 2 and urow[1]
                    }
            except (DatabaseError, AttributeError, TypeError):
                resolved_users = {}

    ai_approval = None
    if row[3] == "COMPLETED":
        from api_core.workflow.auto_approval import ai_approval_info

        with connection.cursor() as cursor:
            ai_approval = ai_approval_info(cursor, row[0], row[3])
    return JsonResponse(
        {
            "request": {
                "ai_auto_approval": ai_approval,
                "id": row[0],
                "code": row[1],
                "type_code": row[2],
                "type_name": row[19] if len(row) > 19 else None,
                "status": row[3],
                "lock_version": row[4],
                "requester_id": row[5],
                "requester_name": row[15] if len(row) > 15 else None,
                "department_id": row[16] if len(row) > 16 else None,
                "department_name": row[17] if len(row) > 17 else None,
                "amount_vnd": row[18] if len(row) > 18 else None,
                "payload": effective_payload,
                "resolved_users": resolved_users,
                "revision_no": row[8],
                "created_at": row[9].isoformat(),
                "updated_at": row[10].isoformat(),
                "risk_weight": risk_w,
                "approval_level": app_lvl,
                "approval_steps": step_items,
                "workflow": workflow_payload,
                "progress": progress,
            },
            "correlation_id": correlation_id(request),
        }
    )


def request_detail_or_patch(request: HttpRequest, request_id: str) -> JsonResponse:
    if request.method == "PATCH":
        return update_draft_view(request, request_id=str(request_id))
    elif request.method == "GET":
        return request_detail(request, request_id=str(request_id))
    return api_error(request, "METHOD_NOT_ALLOWED", status=405)


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


@require_actor("REQUESTER")
def update_draft_view(request: HttpRequest, request_id: str) -> JsonResponse:
    if request.method != "PATCH":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    return _command_response(request, update_draft, request_id=str(request_id))


@require_POST
@require_actor("REQUESTER")
def submit(request: HttpRequest, request_id: str | None = None) -> JsonResponse:
    key = _key(request)
    if not key:
        return api_error(request, "IDEMPOTENCY_KEY_REQUIRED", status=400)
    try:
        body = parse_json_object(request)
        if request_id is not None:
            body["request_id"] = str(request_id)
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


@require_actor("APPROVER")
def delegations_view(request: HttpRequest) -> JsonResponse:
    from api_core.http import JsonBodyError as _BodyError
    from api_core.workflow import delegation

    try:
        if request.method == "GET":
            result = delegation.list_delegations(actor=request.actor)
            status = 200
        elif request.method == "POST":
            result = delegation.create_delegation(
                actor=request.actor,
                body=parse_json_object(request),
                correlation_id=correlation_id(request),
            )
            status = 201
        else:
            return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    except _BodyError as exc:
        return api_error(request, str(exc), status=400)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    return JsonResponse(
        {**result, "correlation_id": correlation_id(request)}, status=status
    )


@require_GET
@require_actor("APPROVER")
def delegation_candidates_view(request: HttpRequest) -> JsonResponse:
    from api_core.workflow import delegation

    return JsonResponse(
        {
            **delegation.delegate_candidates(actor=request.actor),
            "correlation_id": correlation_id(request),
        }
    )


@require_POST
@require_actor("APPROVER")
def delegation_revoke_view(request: HttpRequest, delegation_id) -> JsonResponse:
    from api_core.workflow import delegation

    try:
        result = delegation.revoke_delegation(
            actor=request.actor,
            delegation_id=str(delegation_id),
            correlation_id=correlation_id(request),
        )
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)
    return JsonResponse({**result, "correlation_id": correlation_id(request)})


@require_POST
@require_actor("APPROVER")
def revoke_ai_approval_view(request: HttpRequest, request_id: str) -> JsonResponse:
    from api_core.workflow.auto_approval import revoke_ai_auto_approval

    return _command_response(
        request, revoke_ai_auto_approval, request_id=str(request_id)
    )


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
            request_id=str(request_id),
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


@require_POST
@require_actor("EXECUTOR")
def report_issue_view(request: HttpRequest, request_id: str) -> JsonResponse:
    return _command_response(
        request, report_execution_issue, request_id=str(request_id)
    )


@require_GET
@require_actor()
def revisions_list(request: HttpRequest, request_id: str) -> JsonResponse:
    try:
        req_uuid = str(UUID(request_id))
    except (ValueError, TypeError, AttributeError):
        return api_error(request, ERR_REQUEST_NOT_FOUND, status=404)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM eas.request r
            LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
            LEFT JOIN eas.app_user u ON u.id = r.requester_id
            WHERE r.id = %s
              AND (
                r.requester_id = %s
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.request_participant p
                    WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                  )
                )
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.role_membership rm
                    WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
                      AND rm.revoked_at IS NULL
                      AND rm.valid_from <= statement_timestamp()
                      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                      AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
                      AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
                  )
                )
              )
            """,
            [req_uuid, request.actor.id, request.actor.id, request.actor.id],
        )
        if not cursor.fetchone():
            return api_error(request, ERR_REQUEST_NOT_FOUND, status=404)

        cursor.execute(
            """
            SELECT v.id::text, v.revision_no, v.department_id::text, v.payload,
                   v.amount_vnd, v.submitted_at
            FROM eas.request_revision v
            WHERE v.request_id = %s
            ORDER BY v.revision_no DESC
            """,
            [req_uuid],
        )
        rev_rows = cursor.fetchall()
        revisions = []
        for r_row in rev_rows:
            rev_id = r_row[0]
            cursor.execute(
                """
                SELECT a.id::text, a.original_name, a.mime, a.size_bytes, a.scan_state
                FROM eas.revision_attachment ra
                JOIN eas.attachment a ON a.id = ra.attachment_id
                WHERE ra.revision_id = %s AND a.deleted_at IS NULL
                ORDER BY a.created_at ASC
                """,
                [rev_id],
            )
            att_rows = cursor.fetchall()
            attachments = [
                {
                    "id": a[0],
                    "original_name": a[1],
                    "mime": a[2],
                    "size_bytes": a[3],
                    "scan_state": a[4],
                }
                for a in att_rows
            ]
            revisions.append(
                {
                    "id": rev_id,
                    "revision_no": r_row[1],
                    "department_id": r_row[2],
                    "payload": r_row[3],
                    "amount_vnd": r_row[4],
                    "submitted_at": r_row[5].isoformat() if r_row[5] else None,
                    "attachments": attachments,
                }
            )

    return JsonResponse(
        {
            "revisions": revisions,
            "correlation_id": correlation_id(request),
        }
    )


@require_GET
@require_actor()
def revision_detail(
    request: HttpRequest, request_id: str, revision_id: str
) -> JsonResponse:
    try:
        req_uuid = str(UUID(request_id))
        rev_uuid = str(UUID(revision_id))
    except (ValueError, TypeError, AttributeError):
        return api_error(request, "NOT_FOUND", status=404)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM eas.request r
            LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
            LEFT JOIN eas.app_user u ON u.id = r.requester_id
            WHERE r.id = %s
              AND (
                r.requester_id = %s
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.request_participant p
                    WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                  )
                )
                OR (
                  r.status != 'DRAFT'
                  AND EXISTS (
                    SELECT 1 FROM eas.role_membership rm
                    WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
                      AND rm.revoked_at IS NULL
                      AND rm.valid_from <= statement_timestamp()
                      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                      AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
                      AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
                  )
                )
              )
            """,
            [req_uuid, request.actor.id, request.actor.id, request.actor.id],
        )
        if not cursor.fetchone():
            return api_error(request, ERR_REQUEST_NOT_FOUND, status=404)

        cursor.execute(
            """
            SELECT v.id::text, v.revision_no, v.department_id::text, v.payload,
                   v.amount_vnd, v.submitted_at
            FROM eas.request_revision v
            WHERE v.id = %s AND v.request_id = %s
            """,
            [rev_uuid, req_uuid],
        )
        r_row = cursor.fetchone()
        if not r_row:
            return api_error(request, "REVISION_NOT_FOUND", status=404)

        cursor.execute(
            """
            SELECT a.id::text, a.original_name, a.mime, a.size_bytes, a.scan_state
            FROM eas.revision_attachment ra
            JOIN eas.attachment a ON a.id = ra.attachment_id
            WHERE ra.revision_id = %s AND a.deleted_at IS NULL
            ORDER BY a.created_at ASC
            """,
            [rev_uuid],
        )
        att_rows = cursor.fetchall()
        attachments = [
            {
                "id": a[0],
                "original_name": a[1],
                "mime": a[2],
                "size_bytes": a[3],
                "scan_state": a[4],
            }
            for a in att_rows
        ]

    return JsonResponse(
        {
            "revision": {
                "id": r_row[0],
                "revision_no": r_row[1],
                "department_id": r_row[2],
                "payload": r_row[3],
                "amount_vnd": r_row[4],
                "submitted_at": r_row[5].isoformat() if r_row[5] else None,
                "attachments": attachments,
            },
            "correlation_id": correlation_id(request),
        }
    )


@require_GET
@require_actor()
def attachment_metadata(request: HttpRequest, attachment_id: str) -> JsonResponse:
    try:
        data = get_attachment_metadata(actor=request.actor, attachment_id=attachment_id)
        data["correlation_id"] = correlation_id(request)
        return JsonResponse(data)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor()
def attachment_download(request: HttpRequest, attachment_id: str) -> HttpResponse:
    try:
        data, filename, mime = download_attachment(
            actor=request.actor,
            attachment_id=attachment_id,
            correlation_id=correlation_id(request),
        )
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)

    safe_mime = (
        "application/octet-stream"
        if mime in ("text/html", "application/xhtml+xml", "text/xml", "image/svg+xml")
        else mime
    )
    response = HttpResponse(
        data, content_type=safe_mime
    )  # NOSONAR pythonsecurity:S5131
    # RFC 6266 quoting/encoding: Vietnamese names survive and a stored name
    # cannot inject extra header parameters.
    response["Content-Disposition"] = content_disposition_header(True, filename)
    response["Content-Security-Policy"] = "default-src 'none'"
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Correlation-ID"] = correlation_id(request)
    return response


@require_GET
@require_actor("OPS_ADMIN")
def ops_requests_view(request: HttpRequest) -> JsonResponse:
    try:
        result = list_ops_metadata(actor=request.actor, query_params=request.GET.dict())
        result["correlation_id"] = correlation_id(request)
        return JsonResponse(result)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_POST
@require_actor("OPS_ADMIN")
def reassign_view(request: HttpRequest, request_id: str) -> JsonResponse:
    return _command_response(request, reassign_actor, request_id=str(request_id))


@require_POST
@require_actor("OPS_ADMIN")
def outbox_replay_view(request: HttpRequest, event_id: str) -> JsonResponse:
    return _command_response(request, replay_dead_outbox, event_id=str(event_id))


def config_releases_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":

        @require_actor("POLICY_ADMIN")
        def _get(req: HttpRequest) -> JsonResponse:
            try:
                res = list_config_releases(actor=req.actor, query_params=req.GET.dict())
                res["correlation_id"] = correlation_id(req)
                return JsonResponse(res)
            except CommandError as exc:
                return api_error(req, exc.code, status=exc.status, fields=exc.fields)

        return _get(request)
    elif request.method == "POST":

        @require_actor("POLICY_ADMIN")
        def _post(req: HttpRequest) -> JsonResponse:
            return _command_response(req, create_or_clone_release)

        return _post(request)
    return api_error(request, "METHOD_NOT_ALLOWED", status=405)


@require_GET
@require_actor("POLICY_ADMIN")
def policy_actor_options_view(request: HttpRequest) -> JsonResponse:
    try:
        data = policy_actor_options(request.actor, request.GET.get("type_code", ""))
        data["correlation_id"] = correlation_id(request)
        return JsonResponse(data)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor("POLICY_ADMIN")
def policy_type_status_view(request: HttpRequest) -> JsonResponse:
    try:
        data = list_policy_type_status(request.actor)
        data["correlation_id"] = correlation_id(request)
        return JsonResponse(data)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


def config_release_detail_view(request: HttpRequest, release_id: str) -> JsonResponse:
    if request.method == "GET":

        @require_actor("POLICY_ADMIN")
        def _get(req: HttpRequest) -> JsonResponse:
            try:
                res = get_config_release(actor=req.actor, release_id=str(release_id))
                res["correlation_id"] = correlation_id(req)
                return JsonResponse(res)
            except CommandError as exc:
                return api_error(req, exc.code, status=exc.status, fields=exc.fields)

        return _get(request)
    elif request.method == "PATCH":

        @require_actor("POLICY_ADMIN")
        def _patch(req: HttpRequest) -> JsonResponse:
            return _command_response(
                req, update_draft_release, release_id=str(release_id)
            )

        return _patch(request)
    return api_error(request, "METHOD_NOT_ALLOWED", status=405)


@require_POST
@require_actor("POLICY_ADMIN")
def config_release_validate_view(request: HttpRequest, release_id: str) -> JsonResponse:
    try:
        res = validate_release_candidate(
            actor=request.actor, release_id=str(release_id)
        )
        res["correlation_id"] = correlation_id(request)
        return JsonResponse(res)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_POST
@require_actor("POLICY_ADMIN")
def config_release_publish_view(request: HttpRequest, release_id: str) -> JsonResponse:
    return _command_response(
        request, publish_config_release, release_id=str(release_id)
    )


@require_GET
@require_actor()
def notifications_view(request: HttpRequest) -> JsonResponse:
    try:
        res = list_notifications(actor=request.actor, query_params=request.GET.dict())
        res["correlation_id"] = correlation_id(request)
        return JsonResponse(res)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_actor()
def notification_mark_read_view(
    request: HttpRequest, notification_id: str
) -> JsonResponse:
    if request.method not in {"PATCH", "POST"}:
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        res = mark_notification_read(
            actor=request.actor, notification_id=str(notification_id)
        )
        res["correlation_id"] = correlation_id(request)
        return JsonResponse(res)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor()
def reports_requests_view(request: HttpRequest) -> JsonResponse:
    try:
        res = get_request_metrics_report(
            actor=request.actor, query_params=request.GET.dict()
        )
        res["correlation_id"] = correlation_id(request)
        return JsonResponse(res)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor()
def request_audit_view(request: HttpRequest, request_id: str) -> JsonResponse:
    try:
        res = get_request_audit_events(actor=request.actor, request_id=str(request_id))
        res["correlation_id"] = correlation_id(request)
        return JsonResponse(res)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor("AUDITOR")
def request_audit_verify_view(request: HttpRequest, request_id: str) -> JsonResponse:
    try:
        res = get_request_audit_verify(actor=request.actor, request_id=str(request_id))
        res["correlation_id"] = correlation_id(request)
        return JsonResponse(res)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor("AUDITOR", "POLICY_ADMIN", "OPS_ADMIN")
def admin_events_view(request: HttpRequest) -> JsonResponse:
    try:
        res = list_admin_events(actor=request.actor, query_params=request.GET.dict())
        res["correlation_id"] = correlation_id(request)
        return JsonResponse(res)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_POST
@require_actor()
def ai_classify_view(request: HttpRequest) -> JsonResponse:
    try:
        body = parse_json_object(request)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)

    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return api_error(request, "TITLE_REQUIRED", status=400)

    description = body.get("description", "")
    if not isinstance(description, str):
        description = str(description)

    from api_core.integrations.ai_service import ai_client_sync

    cid = correlation_id(request)
    result = ai_client_sync.classify_request(
        title=title.strip(), description=description.strip(), correlation_id=cid
    )
    return JsonResponse({"data": result, "correlation_id": cid}, status=200)


@require_POST
@require_actor()
def ai_risk_score_view(request: HttpRequest) -> JsonResponse:
    try:
        body = parse_json_object(request)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)

    request_type = body.get("request_type")
    if not isinstance(request_type, str) or not request_type.strip():
        return api_error(request, "REQUEST_TYPE_REQUIRED", status=400)

    lifecycle_template = body.get("lifecycle_template", "A")
    risk_weight = body.get("risk_weight", 2)
    try:
        risk_weight = int(risk_weight)
    except (ValueError, TypeError):
        risk_weight = 2

    from api_core.integrations.ai_service import ai_client_sync

    cid = correlation_id(request)
    result = ai_client_sync.score_risk(
        request_type=request_type,
        lifecycle_template=str(lifecycle_template),
        risk_weight=risk_weight,
        correlation_id=cid,
        **{
            k: v
            for k, v in body.items()
            if k
            not in (
                "request_type",
                "lifecycle_template",
                "risk_weight",
                "correlation_id",
            )
        },
    )
    return JsonResponse({"data": result, "correlation_id": cid}, status=200)


@require_POST
@require_actor()
def ai_summarize_view(request: HttpRequest) -> JsonResponse:
    try:
        body = parse_json_object(request)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)

    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return api_error(request, "TITLE_REQUIRED", status=400)

    request_type = body.get("request_type", "general")
    requester_name = body.get("requester_name") or getattr(
        request.actor, "display_name", ""
    )
    description = body.get("description")
    data = body.get("data")
    risk_score = body.get("risk_score")
    amount = body.get("amount")

    from api_core.integrations.ai_service import ai_client_sync

    cid = correlation_id(request)
    result = ai_client_sync.summarize_request(
        title=title.strip(),
        request_type=str(request_type),
        requester_name=str(requester_name),
        description=description,
        data=data if isinstance(data, dict) else None,
        risk_score=risk_score,
        amount=amount,
        correlation_id=cid,
    )
    return JsonResponse({"data": result, "correlation_id": cid}, status=200)


@require_GET
def system_maintenance_view(request: HttpRequest) -> JsonResponse:
    from api_core.maintenance import get_maintenance_info

    cid = correlation_id(request)
    return JsonResponse(
        {"status": "ok", "maintenance": get_maintenance_info(), "correlation_id": cid},
        status=200,
    )


@require_POST
@require_actor("POLICY_ADMIN", "OPS_ADMIN")
def system_maintenance_start_view(request: HttpRequest) -> JsonResponse:
    from api_core.maintenance import start_maintenance

    try:
        body = parse_json_object(request)
    except JsonBodyError:
        body = {}

    message = body.get("message")
    admin_message = body.get("admin_message")
    release_id = body.get("release_id")

    info = start_maintenance(
        actor_id=request.actor.id,
        release_id=release_id,
        message=message,
        admin_message=admin_message,
    )
    cid = correlation_id(request)
    return JsonResponse(
        {"status": "ok", "maintenance": info, "correlation_id": cid},
        status=200,
    )


@require_POST
@require_actor("POLICY_ADMIN", "OPS_ADMIN")
def system_maintenance_complete_view(request: HttpRequest) -> JsonResponse:
    from django.db import transaction

    from api_core.maintenance import complete_maintenance
    from api_core.workflow.service import _append_admin_audit

    try:
        body = parse_json_object(request)
    except JsonBodyError:
        body = {}

    admin_message = body.get("admin_message")
    cid = correlation_id(request)

    with transaction.atomic(), connection.cursor() as cursor:
        _append_admin_audit(
            cursor,
            actor_id=request.actor.id,
            action="MAINTENANCE_COMPLETED",
            target_type="system",
            target_id="00000000-0000-0000-0000-000000000000",
            details={"status": "COMPLETED"},
            reason="Admin confirmed policy update and AI retraining completion.",
            correlation_id=cid,
        )

    info = complete_maintenance(
        actor_id=request.actor.id,
        admin_message=admin_message,
    )

    return JsonResponse(
        {"status": "ok", "maintenance": info, "correlation_id": cid},
        status=200,
    )


@require_POST
@require_actor("REQUESTER")
def route_preview_view(request: HttpRequest) -> JsonResponse:
    try:
        body = parse_json_object(request)
        return JsonResponse(
            {
                "preview": preview_route(request.actor, body),
                "correlation_id": correlation_id(request),
            }
        )
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor()
def team_report_view(request: HttpRequest) -> JsonResponse:
    try:
        return JsonResponse(team_report(request.actor, request.GET.dict()))
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


@require_GET
@require_actor()
def org_chart_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse(org_chart(request.actor))


@require_actor()
def _ai_assessment_history(request: HttpRequest, request_id: str) -> JsonResponse:
    try:
        return JsonResponse(list_ai_assessments(request.actor, request_id))
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


# Running an assessment appends to the request audit chain, so it is limited to
# business participants; auditors and other administrators stay read-only.
@require_actor("REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR")
def _ai_assessment_run(request: HttpRequest, request_id: str) -> JsonResponse:
    try:
        result = run_ai_assessment(request.actor, request_id, correlation_id(request))
        return JsonResponse(result, status=201)
    except CommandError as exc:
        return api_error(request, exc.code, status=exc.status, fields=exc.fields)


def ai_assessment_view(request: HttpRequest, request_id: str) -> JsonResponse:
    if request.method == "GET":
        return _ai_assessment_history(request, request_id)
    if request.method == "POST":
        return _ai_assessment_run(request, request_id)
    return api_error(request, "METHOD_NOT_ALLOWED", status=405)
