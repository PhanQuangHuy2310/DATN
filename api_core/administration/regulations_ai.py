"""Company regulations CRUD and AI engine status (admin portal).

Version numbers are assigned by the BEFORE trigger on eas.company_regulations
(create/delete = major, edit = minor) and the AFTER trigger records history.
Every change queues an AI learning job in the same transaction
(api_core.workflow.ai_learning); the employee portal stays locked until the AI
has learned and applied the new rules, then users get an announcement.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from django.core.cache import cache
from django.db import connection, transaction
from django.http import HttpRequest, JsonResponse
from psycopg.types.json import Jsonb

from api_core.authn.module_access import ACTION_BY_METHOD, can
from api_core.authn.service import require_actor
from api_core.http import JsonBodyError, api_error, correlation_id, parse_json_object
from api_core.maintenance import get_ai_maintenance_state
from api_core.read_cache import cached
from api_core.workflow.ai_learning import _ai_http, enqueue_learning, steps_detail
from api_core.workflow.service import _append_admin_audit

MAX_TITLE = 300
MAX_CATEGORY = 120
MAX_CONTENT = 20000
REGULATION_COLUMNS = """
    id::text, code, title, category, content, version_string, major_version,
    minor_version, is_deleted, updated_by, created_at, updated_at
"""


def _iso(value):
    return value.isoformat() if value else None


def _serialize_regulation(row) -> dict[str, Any]:
    keys = (
        "id",
        "code",
        "title",
        "category",
        "content",
        "version_string",
        "major_version",
        "minor_version",
        "is_deleted",
        "updated_by",
        "created_at",
        "updated_at",
    )
    item = dict(zip(keys, row))
    item["created_at"] = _iso(item["created_at"])
    item["updated_at"] = _iso(item["updated_at"])
    return item


def _v(value) -> str | None:
    if not value:
        return None
    value = str(value)
    return value if value.startswith("v") else f"v{value}"


def ai_engine_state() -> dict[str, Any]:
    """AI state for admin screens; the lock comes from the open learning job."""
    import os

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT provider_name, model_name, active_regulation_version,
                   target_regulation_version, global_major_version, global_minor_version,
                   sync_status, current_step_index, current_step_label,
                   progress_percent, steps_detail, updated_at
            FROM eas.ai_system_state WHERE id = 1
            """
        )
        row = cur.fetchone()
    if not row:
        return {"sync_status": "NOT_CONFIGURED", "client_maintenance_lock": False}
    lock = get_ai_maintenance_state()
    step = int(row[7] or 4)
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
    raw_provider = str(row[0] or "").strip()
    if not has_gemini_key and (not raw_provider or "gemini" in raw_provider.lower()):
        provider_name = (
            "Scikit-Learn Local Pipeline (Gemini Fallback: Chưa cấu hình Key)"
        )
        model_name = "nlp_risk_pipeline_v2 (Local Scikit-Learn / XGBoost)"
    else:
        provider_name = raw_provider or "Google Gemini + Scikit-Learn Hybrid"
        model_name = row[1] or "gemini-2.5-flash & nlp_risk_pipeline_v2"
    return {
        "provider_name": provider_name,
        "model_name": model_name,
        "gemini_configured": has_gemini_key,
        "active_regulation_version": _v(row[2]) or "v1.0",
        "target_regulation_version": _v(row[3]) or _v(row[2]) or "v1.0",
        "global_major_version": row[4] or 1,
        "global_minor_version": row[5] or 0,
        "sync_status": row[6] or "COMPLETED",
        "current_step_index": step,
        "current_step_label": row[8] or "",
        "progress_percent": row[9] if row[9] is not None else 100,
        "client_maintenance_lock": lock is not None,
        "steps_detail": row[10] or steps_detail(step),
        "updated_at": _iso(row[11]),
    }


def _parse(request: HttpRequest):
    try:
        return parse_json_object(request), None
    except JsonBodyError as exc:
        return None, api_error(request, str(exc), status=400)


def _validated_fields(
    body: dict, current: dict | None = None
) -> tuple[dict | None, dict]:
    current = current or {}
    fields = {
        "title": str(body.get("title", current.get("title", ""))).strip(),
        "category": str(
            body.get("category", current.get("category") or "Quy định chung")
        ).strip(),
        "content": str(body.get("content", current.get("content", ""))).strip(),
    }
    errors = {}
    if not fields["title"] or len(fields["title"]) > MAX_TITLE:
        errors["title"] = [f"Bắt buộc, tối đa {MAX_TITLE} ký tự"]
    if len(fields["category"]) > MAX_CATEGORY:
        errors["category"] = [f"Tối đa {MAX_CATEGORY} ký tự"]
    if not fields["content"] or len(fields["content"]) > MAX_CONTENT:
        errors["content"] = [f"Bắt buộc, tối đa {MAX_CONTENT} ký tự"]
    return (None if errors else fields), errors


def _audit(cur, request, *, action: str, regulation: dict, reason: str) -> None:
    _append_admin_audit(
        cur,
        actor_id=request.actor.id,
        action=action,
        target_type="company_regulation",
        target_id=regulation["id"],
        details={"code": regulation["code"], "version": regulation["version_string"]},
        # admin_event.reason requires 10..2000 characters.
        reason=reason
        if len(reason.strip()) >= 10
        else f"Quy định {regulation['code']}: {reason}",
        correlation_id=correlation_id(request),
    )


def _forbidden_unless_writer(request: HttpRequest):
    """Admin, or an employee granted the matching right on module `regulations`."""
    action = ACTION_BY_METHOD.get(request.method, "update")
    if not can(request, "regulations", action):
        return api_error(request, "FORBIDDEN", status=403)
    return None


def _superseded(cur) -> list[dict[str, Any]]:
    """Điều nào của văn bản nào đang bị văn bản mới hơn thay thế (bộ luật AI đã áp dụng)."""
    cur.execute(
        "SELECT coalesce(applied_policy->'superseded', '[]'::jsonb) FROM eas.ai_system_state WHERE id = 1"
    )
    row = cur.fetchone()
    return list(row[0] or []) if row else []


def _attach_superseded(
    items: list[dict], superseded: list[dict[str, Any]]
) -> list[dict]:
    for item in items:
        item["superseded_by"] = [
            e for e in superseded if e.get("old_code") == item["code"]
        ]
        item["supersedes"] = [
            e for e in superseded if e.get("new_code") == item["code"]
        ]
    return items


def _list_regulations() -> list[dict]:
    with connection.cursor() as cur:
        cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
            f"SELECT {REGULATION_COLUMNS} FROM eas.company_regulations "
            "WHERE NOT is_deleted ORDER BY code"
        )
        items = [_serialize_regulation(r) for r in cur.fetchall()]
        return _attach_superseded(items, _superseded(cur))


def _content_check(cur, *, code: str, fields: dict) -> dict[str, Any]:
    """AI đọc văn bản trước khi lưu: lỗi ký tự, mâu thuẫn giữa các điều / với quy định đang hiệu lực."""
    from api_core.workflow.regulation_compiler import RequestTypeName
    from api_core.workflow.regulation_validation import validate

    cur.execute("SELECT code, name, lifecycle FROM eas.request_type WHERE is_active")
    types = [
        RequestTypeName(
            code=r[0], name=r[1] or "", lifecycle=(r[2] or "").strip() or None
        )
        for r in cur.fetchall()
    ]
    cur.execute(
        "SELECT code, title, content FROM eas.company_regulations WHERE NOT is_deleted AND code <> %s",
        [code],
    )
    others = [
        {"code": r[0], "title": r[1], "content": r[2] or ""} for r in cur.fetchall()
    ]
    return validate(
        code=code or "MỚI",
        title=fields["title"],
        content=fields["content"],
        types=types,
        others=others,
    )


def _invalid_regulation(request: HttpRequest, check: dict[str, Any]) -> JsonResponse:
    """422 kèm danh sách lỗi từng câu để admin sửa; không lưu, không khoá hệ thống."""
    response = JsonResponse(
        {
            "error": {
                "code": "REGULATION_INVALID",
                "message": f"AI phát hiện {len(check['errors'])} lỗi trong văn bản; sửa rồi ban hành lại.",
            },
            "validation": check,
            "correlation_id": correlation_id(request),
        },
        status=422,
    )
    response["X-Correlation-ID"] = request.correlation_id
    return response


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def regulation_validate_view(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/admin/regulations/validate {code?, title, content}: AI kiểm tra văn bản, không lưu."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    body, error = _parse(request)
    if error:
        return error
    fields, errors = _validated_fields(body)
    if errors:
        return api_error(request, "VALIDATION_FAILED", status=422, fields=errors)
    code = str(body.get("code", "")).strip().upper()[:30]
    with connection.cursor() as cur:
        return JsonResponse(
            {"validation": _content_check(cur, code=code, fields=fields)}
        )


def _rejection_row(r) -> dict[str, Any]:
    keys = (
        "id",
        "regulation_code",
        "action",
        "cause",
        "rejected_title",
        "rejected_content",
        "rejected_version",
        "restored_version",
        "errors",
        "warnings",
        "message",
        "state",
        "note",
        "created_at",
        "resolved_at",
    )
    item = dict(zip(keys, r, strict=True))
    item["created_at"] = _iso(item["created_at"])
    item["resolved_at"] = _iso(item["resolved_at"])
    return item


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def regulation_rejections_list(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/admin/regulations/rejections?state=OPEN: quy định bị trả lại + lỗi từng câu (migration 26)."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    state = (request.GET.get("state") or "OPEN").upper()
    if state not in ("OPEN", "RESOLVED", "DISMISSED", "ALL"):
        return api_error(request, "VALIDATION_FAILED", status=422)
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('eas.regulation_rejection') IS NOT NULL")
        if not cur.fetchone()[0]:
            return JsonResponse({"items": [], "installed": False})
        cur.execute(
            """
            SELECT id::text, regulation_code, action, cause, rejected_title, rejected_content, rejected_version,
                   restored_version, errors, warnings, message, state, note, created_at, resolved_at
            FROM eas.regulation_rejection
            WHERE %s = 'ALL' OR state = %s
            ORDER BY created_at DESC LIMIT 100
            """,
            [state, state],
        )
        return JsonResponse(
            {"items": [_rejection_row(r) for r in cur.fetchall()], "installed": True}
        )


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def regulation_rejection_dismiss(request: HttpRequest, rejection_id) -> JsonResponse:
    """POST .../rejections/<id>/dismiss {note}: admin bỏ qua bản bị trả lại (không nạp lại)."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_writer(request):
        return denied
    body, error = _parse(request)
    if error:
        return error
    note = str(body.get("note") or "").strip()
    if len(note) < 5:
        return api_error(
            request,
            "VALIDATION_FAILED",
            status=422,
            fields={"note": ["Cần lý do (≥ 5 ký tự)"]},
        )
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            """
            UPDATE eas.regulation_rejection
            SET state = 'DISMISSED', resolved_by = %s, resolved_at = statement_timestamp(), note = %s
            WHERE id = %s::uuid AND state = 'OPEN' RETURNING regulation_code
            """,
            [request.actor.id, note[:500], str(rejection_id)],
        )
        row = cur.fetchone()
        if not row:
            return api_error(request, "NOT_FOUND", status=404)
        _append_admin_audit(
            cur,
            actor_id=request.actor.id,
            action="REGULATION_REJECTION_DISMISSED",
            target_type="regulation_rejection",
            target_id=str(rejection_id),
            details={"code": row[0]},
            reason=note
            if len(note) >= 10
            else f"Bỏ qua bản bị trả lại {row[0]}: {note}",
            correlation_id=correlation_id(request),
        )
    return JsonResponse({"id": str(rejection_id), "state": "DISMISSED"})


def _resolve_rejections(cur, request: HttpRequest, code: str) -> None:
    from api_core.workflow.regulation_rejection import resolve_open

    resolve_open(
        cur, code=code, actor_id=request.actor.id, note="Admin đã sửa và nạp lại"
    )


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def regulations_list_create(request: HttpRequest) -> JsonResponse:
    """GET list (+ AI state) / POST create (major version, AI relearns)."""
    if request.method == "GET":
        regulations = cached("regulations", _list_regulations)
        return JsonResponse(
            {
                "regulations": regulations,
                "total_count": len(regulations),
                "ai_state": ai_engine_state(),
            }
        )
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_writer(request):
        return denied
    body, error = _parse(request)
    if error:
        return error
    fields, errors = _validated_fields(body)
    if errors:
        return api_error(request, "VALIDATION_FAILED", status=422, fields=errors)
    code = str(body.get("code", "")).strip().upper()[:30]

    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SELECT eas.lock_security(true)")
        if not code:
            cur.execute(
                "SELECT 'REG-' || lpad((COALESCE(max(substring(code FROM '^REG-(\\d+)$')::int), 0) + 1)::text, 3, '0') "
                "FROM eas.company_regulations"
            )
            code = cur.fetchone()[0]
        cur.execute(
            "SELECT 1 FROM eas.company_regulations WHERE code = %s AND NOT is_deleted",
            [code],
        )
        if cur.fetchone():
            return api_error(request, "REGULATION_CODE_EXISTS", status=409)
        check = _content_check(cur, code=code, fields=fields)
        if not check["ok"]:
            return _invalid_regulation(request, check)
        # Mã là UNIQUE kể cả khi đã gỡ (xóa mềm): ban hành lại một mã từng bị gỡ / bị trả lại thì dùng lại dòng đó.
        cur.execute(
            "SELECT id::text FROM eas.company_regulations WHERE code = %s AND is_deleted FOR UPDATE",
            [code],
        )
        retired = cur.fetchone()
        if retired:
            cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
                f"""
                UPDATE eas.company_regulations
                SET is_deleted = false, title = %s, category = %s, content = %s, updated_by = %s
                WHERE id = %s RETURNING {REGULATION_COLUMNS}
                """,
                [
                    fields["title"],
                    fields["category"],
                    fields["content"],
                    request.actor.display_name,
                    retired[0],
                ],
            )
        else:
            cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
                f"""
                INSERT INTO eas.company_regulations (code, title, category, content, is_deleted, updated_by)
                VALUES (%s, %s, %s, %s, false, %s)
                RETURNING {REGULATION_COLUMNS}
                """,
                [
                    code,
                    fields["title"],
                    fields["category"],
                    fields["content"],
                    request.actor.display_name,
                ],
            )
        regulation = _serialize_regulation(cur.fetchone())
        if retired:
            cur.execute(
                """
                UPDATE eas.regulation_versions SET change_summary = %s
                WHERE id = (SELECT id FROM eas.regulation_versions WHERE regulation_id = %s
                            ORDER BY created_at DESC LIMIT 1)
                """,
                [f'Ban hành lại quy định "{fields["title"]}"', retired[0]],
            )
        _audit(
            cur,
            request,
            action="REGULATION_CREATED",
            regulation=regulation,
            reason=f"Ban hành {code}",
        )
        enqueue_learning(
            cur,
            reason=f"Ban hành {code}: {fields['title']}",
            requested_by=request.actor.id,
        )
        _resolve_rejections(cur, request, code)

    version = _v(regulation["version_string"])
    return JsonResponse(
        {
            "message": f"Đã ban hành quy định {code} (phiên bản {version}). AI đang học quy định mới; cổng nhân viên tạm khoá tới khi áp dụng xong.",
            "regulation": regulation,
            "new_version": version,
            "version_type": "MAJOR",
            "maintenance_active": True,
            "warnings": check["warnings"],
        },
        status=201,
    )


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def regulation_detail_update_delete(request: HttpRequest, reg_id: str) -> JsonResponse:
    """GET detail + history / PATCH edit (minor) / DELETE retire (major)."""
    reg_id = str(reg_id)
    if request.method == "GET":
        with connection.cursor() as cur:
            cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
                f"SELECT {REGULATION_COLUMNS} FROM eas.company_regulations WHERE id = %s",
                [reg_id],
            )
            row = cur.fetchone()
            if not row:
                return api_error(request, "REGULATION_NOT_FOUND", status=404)
            item = _serialize_regulation(row)
            cur.execute(
                """
                SELECT id::text, version_string, major_version, minor_version, action_type,
                       change_summary, created_by, created_at
                FROM eas.regulation_versions WHERE regulation_id = %s
                ORDER BY created_at DESC
                """,
                [reg_id],
            )
            keys = (
                "id",
                "version_string",
                "major_version",
                "minor_version",
                "action_type",
                "change_summary",
                "created_by",
                "created_at",
            )
            item["history"] = [
                {**dict(zip(keys, h)), "created_at": _iso(h[7])} for h in cur.fetchall()
            ]
            _attach_superseded([item], _superseded(cur))
        return JsonResponse({"regulation": item})

    if request.method not in ("PATCH", "PUT", "DELETE"):
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_writer(request):
        return denied

    body = {}
    if request.method != "DELETE":
        body, error = _parse(request)
        if error:
            return error

    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SELECT eas.lock_security(true)")
        cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
            f"SELECT {REGULATION_COLUMNS} FROM eas.company_regulations WHERE id = %s AND NOT is_deleted FOR UPDATE",
            [reg_id],
        )
        row = cur.fetchone()
        if not row:
            return api_error(request, "REGULATION_NOT_FOUND", status=404)
        current = _serialize_regulation(row)

        if request.method == "DELETE":
            cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
                f"""
                UPDATE eas.company_regulations SET is_deleted = true, updated_by = %s
                WHERE id = %s RETURNING {REGULATION_COLUMNS}
                """,
                [request.actor.display_name, reg_id],
            )
            regulation = _serialize_regulation(cur.fetchone())
            reason = f"Bãi bỏ {current['code']}: {current['title']}"
            _audit(
                cur,
                request,
                action="REGULATION_RETIRED",
                regulation=regulation,
                reason=reason,
            )
            enqueue_learning(cur, reason=reason, requested_by=request.actor.id)
            version = _v(regulation["version_string"])
            return JsonResponse(
                {
                    "message": f"Đã bãi bỏ quy định (phiên bản {version}). AI đang học lại; cổng nhân viên tạm khoá tới khi áp dụng xong.",
                    "new_version": version,
                    "version_type": "MAJOR",
                    "maintenance_active": True,
                }
            )

        fields, errors = _validated_fields(body, current)
        if errors:
            return api_error(request, "VALIDATION_FAILED", status=422, fields=errors)
        if all(fields[k] == (current[k] or "") for k in fields):
            return JsonResponse(
                {
                    "message": "Không có thay đổi.",
                    "regulation": current,
                    "new_version": _v(current["version_string"]),
                    "maintenance_active": False,
                }
            )
        check = _content_check(cur, code=current["code"], fields=fields)
        if not check["ok"]:
            return _invalid_regulation(request, check)
        cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
            f"""
            UPDATE eas.company_regulations SET title = %s, category = %s, content = %s, updated_by = %s
            WHERE id = %s RETURNING {REGULATION_COLUMNS}
            """,
            [
                fields["title"],
                fields["category"],
                fields["content"],
                request.actor.display_name,
                reg_id,
            ],
        )
        regulation = _serialize_regulation(cur.fetchone())
        summary = (
            str(body.get("change_summary", "")).strip()[:500]
            or f"Cập nhật {current['code']}: {fields['title']}"
        )
        _audit(
            cur,
            request,
            action="REGULATION_UPDATED",
            regulation=regulation,
            reason=summary,
        )
        enqueue_learning(cur, reason=summary, requested_by=request.actor.id)
        _resolve_rejections(cur, request, current["code"])

    version = _v(regulation["version_string"])
    return JsonResponse(
        {
            "message": f"Đã cập nhật quy định (phiên bản {version}). AI đang học lại; cổng nhân viên tạm khoá tới khi áp dụng xong.",
            "regulation": regulation,
            "new_version": version,
            "version_type": "MINOR",
            "maintenance_active": True,
            "warnings": check["warnings"],
        }
    )


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def ai_system_state_view(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/admin/ai-engine/status — AI state plus recent learning jobs."""
    data = ai_engine_state()
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('eas.ai_learning_job') IS NOT NULL")
        if cur.fetchone()[0] is True:
            cur.execute(
                """
                SELECT id::text, status, target_version, reason, step, step_label, progress,
                       attempts, max_attempts, error, created_at, finished_at
                FROM eas.ai_learning_job ORDER BY created_at DESC LIMIT 10
                """
            )
            keys = (
                "id",
                "status",
                "target_version",
                "reason",
                "step",
                "step_label",
                "progress",
                "attempts",
                "max_attempts",
                "error",
                "created_at",
                "finished_at",
            )
            data["jobs"] = [
                {
                    **dict(zip(keys, r)),
                    "created_at": _iso(r[10]),
                    "finished_at": _iso(r[11]),
                }
                for r in cur.fetchall()
            ]
    return JsonResponse(data)


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def ai_retrain_trigger(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/admin/ai-engine/retrain — relearn the current regulations."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    with transaction.atomic(), connection.cursor() as cur:
        job_id = enqueue_learning(
            cur,
            reason="Quản trị viên yêu cầu AI học lại",
            requested_by=request.actor.id,
        )
        _append_admin_audit(
            cur,
            actor_id=request.actor.id,
            action="AI_RELEARN_REQUESTED",
            target_type="ai_learning_job",
            target_id=job_id or "00000000-0000-0000-0000-000000000000",
            details={},
            reason="Yêu cầu AI học lại bộ quy định hiện hành",
            correlation_id=correlation_id(request),
        )
    if job_id is None:
        return api_error(request, "AI_LEARNING_NOT_INSTALLED", status=503)
    state = ai_engine_state()
    return JsonResponse(
        {
            "message": "Đã xếp lịch cho AI học lại bộ quy định hiện hành.",
            "job_id": job_id,
            "target_version": state.get("target_regulation_version"),
            "sync_status": state.get("sync_status"),
            "progress_percent": state.get("progress_percent"),
            "client_maintenance_lock": True,
        }
    )


def public_ai_status_view(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/system/ai-status — unauthenticated lock status for the login page.

    Returns only what the login screen shows; no provider/model internals.
    Cached for 5s to eliminate polling latency and remote DB round-trips.
    """
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    cached_status = cache.get("eas:public:ai_status")
    if cached_status is not None:
        return JsonResponse(cached_status)
    state = ai_engine_state()
    res_data = {
        key: state.get(key)
        for key in (
            "client_maintenance_lock",
            "sync_status",
            "current_step_index",
            "current_step_label",
            "progress_percent",
            "active_regulation_version",
            "target_regulation_version",
            "steps_detail",
        )
    }
    cache.set("eas:public:ai_status", res_data, timeout=5)
    return JsonResponse(res_data)


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def ai_engine_test_view(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/admin/ai-engine/test: ask the live AI engine about a sample request.

    Read-only: nothing is stored; the decision uses the rules the AI applies now.
    """
    import httpx

    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        payload = parse_json_object(request)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    amount, days = payload.get("amount", 0), payload.get("days", 0)
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or not 0 <= amount <= 1_000_000_000_000
        or isinstance(days, bool)
        or not isinstance(days, int)
        or not 0 <= days <= 365
    ):
        return api_error(request, "INVALID_TEST_INPUT", status=422)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT code, name, lifecycle, risk_weight FROM eas.request_type WHERE code = %s",
            [str(payload.get("request_type") or "")],
        )
        row = cur.fetchone()
    if not row:
        return api_error(request, "REQUEST_TYPE_NOT_FOUND", status=404)
    probe = {
        "request_id": str(uuid4()),
        "request_type": row[0],
        "lifecycle_template": row[2],
        "risk_score": row[3] or 3,
        "amount": float(amount),
        "days_requested": days,
        "requester_name": "Kiểm thử quản trị",
        "requester_dept": "ADMIN",
    }
    try:
        with _ai_http() as client:
            response = client.post("/ai/auto-approve/evaluate", json=probe)
    except (httpx.TransportError, httpx.TimeoutException):
        return api_error(request, "AI_SERVICE_UNAVAILABLE", status=503)
    if response.status_code != 200:
        return api_error(request, "AI_SERVICE_ERROR", status=502)
    decision = response.json()
    return JsonResponse(
        {
            "request_type": {
                "code": row[0],
                "name": row[1],
                "lifecycle": row[2],
                "risk_weight": row[3],
            },
            "decision": decision.get("decision"),
            "reason": decision.get("reason"),
            "detail_reasons": decision.get("detail_reasons") or [],
            "policy_version": decision.get("policy_version"),
            "evaluated_at": decision.get("evaluated_at"),
        }
    )


# ---------------------------------------------------------------------------
# Hồ sơ quy trình: học máy nội bộ đề xuất mẫu vòng đời A/B/C, trọng số rủi ro và
# tác động của quy định mới. Chỉ đọc: kết quả là ĐỀ XUẤT để quản trị viên duyệt;
# đổi mẫu vòng đời vẫn phải phát hành cấu hình mới như mọi thay đổi khác.
# ---------------------------------------------------------------------------
PROFILE_TEXT_LIMIT = 5000
ACTIVE_TYPES_SQL = """
    SELECT rt.code, rt.name, rt.category, coalesce(rt.description, ''),
           (SELECT coalesce(array_agg(k ORDER BY k), ARRAY[]::text[])
              FROM jsonb_object_keys(coalesce(cr.form_schema -> 'properties', '{}'::jsonb)) k),
           rt.lifecycle, rt.risk_weight
      FROM eas.request_type rt
      LEFT JOIN eas.config_release cr ON cr.id = rt.active_release_id
     WHERE rt.is_active AND rt.risk_weight BETWEEN 1 AND 5
     ORDER BY rt.code
"""


def _active_type_configs() -> list[dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(ACTIVE_TYPES_SQL)
        rows = cur.fetchall()
    keys = (
        "code",
        "name",
        "category",
        "description",
        "fields",
        "lifecycle",
        "risk_weight",
    )
    return [
        {
            **dict(zip(keys, r)),
            "fields": list(r[4] or [])[:100],
            "description": (r[3] or "")[:2000],
        }
        for r in rows
    ]


def _profile_call(
    request: HttpRequest, path: str, body: dict, timeout: float | None = None
) -> JsonResponse | dict:
    import httpx

    try:
        with _ai_http() as client:
            if timeout:  # phân tích bằng mô hình ngôn ngữ lớn lâu hơn các API AI khác
                client.timeout = httpx.Timeout(timeout, connect=3.0)
            response = client.post(path, json=body)
    except (httpx.TransportError, httpx.TimeoutException):
        return api_error(request, "AI_SERVICE_UNAVAILABLE", status=503)
    if response.status_code != 200:
        return api_error(request, "AI_SERVICE_ERROR", status=502)
    return response.json()


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def regulation_impact_view(request: HttpRequest, reg_id) -> JsonResponse:
    """GET /api/v1/admin/regulations/<id>/impact: loại yêu cầu bị quy định này tác động và đề xuất cấu hình."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT code, title, content FROM eas.company_regulations WHERE id = %s AND NOT is_deleted",
            [str(reg_id)],
        )
        row = cur.fetchone()
    if not row:
        return api_error(request, "REGULATION_NOT_FOUND", status=404)
    text = f"{row[1] or ''}. {row[2] or ''}".strip()[:PROFILE_TEXT_LIMIT]
    if len(text) < 10:
        return api_error(request, "REGULATION_TOO_SHORT", status=422)
    engine = request.GET.get("engine", "llm")
    if engine not in ("llm", "ml"):
        return api_error(request, "INVALID_ENGINE", status=422)
    types = _active_type_configs()
    if engine == "ml":
        result = _profile_call(
            request,
            "/ai/process-profile/regulation-impact",
            {"text": text, "types": types},
        )
    else:
        result = _profile_call(
            request,
            "/ai/regulation-llm/analyze",
            {
                "text": text,
                "types": types,
                "old_regulations": _other_regulations(str(reg_id)),
            },
            timeout=45.0,
        )
    if isinstance(result, JsonResponse):
        return result
    return JsonResponse(
        {
            "regulation": {"id": str(reg_id), "code": row[0], "title": row[1]},
            "engine": result.get("engine") or result.get("version"),
            "model_version": result.get("model") or result.get("version"),
            "fallback_used": bool(result.get("fallback_used")),
            "atomic_rules": result.get("atomic_rules") or [],
            "conflicts": result.get("conflicts") or [],
            "related": result.get("related") or result.get("retrieved_types") or [],
            "proposals": result.get("proposals") or [],
            "rejected": result.get("rejected") or [],
            "requires_admin_approval": True,
        }
    )


def _other_regulations(reg_id: str) -> list[dict[str, Any]]:
    """Các quy định khác đang hiệu lực, để mô hình ngôn ngữ phát hiện xung đột (mô hình chỉ nhận top 3 gần nhất)."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT code, title, content FROM eas.company_regulations "
            "WHERE NOT is_deleted AND id <> %s ORDER BY updated_at DESC LIMIT 200",
            [reg_id],
        )
        rows = cur.fetchall()
    return [
        {
            "code": r[0] or "",
            "title": (r[1] or "")[:300],
            "content": (r[2] or "")[:20000],
        }
        for r in rows
    ]


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def process_profile_assess_view(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/admin/ai-engine/process-profile: đề xuất mẫu A/B/C và trọng số cho một loại yêu cầu (bản nháp)."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        payload = parse_json_object(request)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)
    name = payload.get("name")
    description = payload.get("description", "")
    category = payload.get("category", "")
    fields = payload.get("fields", [])
    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 200
        or not isinstance(description, str)
        or len(description) > 2000
        or not isinstance(category, str)
        or len(category) > 64
        or not isinstance(fields, list)
        or len(fields) > 100
        or not all(isinstance(f, str) and 0 < len(f) <= 64 for f in fields)
    ):
        return api_error(request, "INVALID_PROFILE_INPUT", status=422)
    result = _profile_call(
        request,
        "/ai/process-profile/assess",
        {
            "name": name.strip(),
            "description": description,
            "category": category,
            "fields": fields,
        },
    )
    if isinstance(result, JsonResponse):
        return result
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Hàng chờ câu quy định AI chưa tự hiểu được (migration 24)
# ---------------------------------------------------------------------------


def _clause_row(r) -> dict[str, Any]:
    return {
        "id": r[0],
        "regulation_code": r[1],
        "sentence": r[2],
        "reason": r[3],
        "suggestion": r[4] or {},
        "state": r[5],
        "approved_rules": r[6],
        "decided_at": _iso(r[7]),
        "note": r[8],
        "created_at": _iso(r[9]),
    }


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def clause_reviews_list(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/admin/regulations/clause-reviews?state=PENDING"""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    state = (request.GET.get("state") or "PENDING").upper()
    if state not in ("PENDING", "APPROVED", "REJECTED", "ALL"):
        return api_error(request, "VALIDATION_FAILED", status=422)
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('eas.regulation_clause_review') IS NOT NULL")
        if not cur.fetchone()[0]:
            return JsonResponse({"items": [], "installed": False})
        cur.execute(
            """
            SELECT id::text, regulation_code, sentence, reason, suggestion, state, approved_rules,
                   decided_at, note, created_at
            FROM eas.regulation_clause_review
            WHERE %s = 'ALL' OR state = %s
            ORDER BY created_at DESC LIMIT 200
            """,
            [state, state],
        )
        return JsonResponse(
            {"items": [_clause_row(r) for r in cur.fetchall()], "installed": True}
        )


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def clause_review_approve(request: HttpRequest, review_id) -> JsonResponse:
    return clause_review_decide(request, review_id, "approve")


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def clause_review_reject(request: HttpRequest, review_id) -> JsonResponse:
    return clause_review_decide(request, review_id, "reject")


def clause_review_decide(
    request: HttpRequest, review_id, decision: str
) -> JsonResponse:
    """POST .../clause-reviews/<id>/approve {rules:[...], note?} | .../reject {note}"""
    from api_core.workflow.ai_learning import validate_review_rules

    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if denied := _forbidden_unless_writer(request):
        return denied
    body, error = _parse(request)
    if error:
        return error
    note = str(body.get("note") or "").strip()[:500] or None
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            "SELECT state FROM eas.regulation_clause_review WHERE id = %s::uuid FOR UPDATE",
            [str(review_id)],
        )
        row = cur.fetchone()
        if not row:
            return api_error(request, "NOT_FOUND", status=404)
        if row[0] != "PENDING":
            return api_error(request, "ALREADY_DECIDED", status=409)
        rules = None
        if decision == "approve":
            cur.execute("SELECT code FROM eas.request_type WHERE is_active")
            try:
                rules = validate_review_rules(
                    body.get("rules"), {r[0] for r in cur.fetchall()}
                )
            except ValueError as exc:
                return api_error(
                    request,
                    "VALIDATION_FAILED",
                    status=422,
                    fields={"rules": [str(exc)]},
                )
        elif not note:
            return api_error(
                request,
                "VALIDATION_FAILED",
                status=422,
                fields={"note": ["Cần lý do từ chối"]},
            )
        cur.execute(
            """
            UPDATE eas.regulation_clause_review
            SET state = %s, approved_rules = %s, decided_by = %s, decided_at = statement_timestamp(), note = %s
            WHERE id = %s::uuid
            """,
            [
                "APPROVED" if decision == "approve" else "REJECTED",
                Jsonb(rules) if rules else None,
                request.actor.id,
                note,
                str(review_id),
            ],
        )
        _append_admin_audit(
            cur,
            actor_id=request.actor.id,
            action="REGULATION_CLAUSE_"
            + ("APPROVED" if decision == "approve" else "REJECTED"),
            target_type="regulation_clause_review",
            target_id=str(review_id),
            details={"rules": rules or []},
            reason=note or "Duyệt cách hiểu điều khoản cho AI",
            correlation_id=correlation_id(request),
        )
        job_id = None
        if rules:
            job_id = enqueue_learning(
                cur,
                reason="Admin duyệt cách hiểu điều khoản",
                requested_by=request.actor.id,
            )
    return JsonResponse(
        {
            "id": str(review_id),
            "state": "APPROVED" if rules else "REJECTED",
            "job_id": job_id,
        }
    )


# ---------------------------------------------------------------------------
# Vòng phản hồi của AI (migration 24)
# ---------------------------------------------------------------------------


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def ai_feedback_view(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/admin/ai-engine/feedback: thống kê + 100 phản hồi gần nhất."""
    from api_core.workflow import ai_feedback

    with connection.cursor() as cur:
        summary = ai_feedback.feedback_summary(cur)
        items = []
        if summary.get("installed"):
            cur.execute(
                """
                SELECT f.id::text, f.kind, r.code, f.type_code, f.case_codes, f.reason, u.display_name,
                       f.created_at, f.retired_at, f.used_in_training
                FROM eas.ai_feedback f JOIN eas.request r ON r.id = f.request_id
                LEFT JOIN eas.app_user u ON u.id = f.actor_id
                ORDER BY f.created_at DESC LIMIT 100
                """
            )
            items = [
                {
                    "id": r[0],
                    "kind": r[1],
                    "request_code": r[2],
                    "type_code": r[3],
                    "case_codes": r[4],
                    "reason": r[5],
                    "actor": r[6],
                    "created_at": _iso(r[7]),
                    "retired_at": _iso(r[8]),
                    "used_in_training": r[9],
                }
                for r in cur.fetchall()
            ]
    return JsonResponse(
        {
            "summary": summary,
            "items": items,
            "learning": cache.get(LEARNING_CACHE_KEY) or {"state": "IDLE"},
        }
    )


LEARNING_CACHE_KEY = "eas:ai-feedback-learning"


def _run_feedback_learning(actor_id: str, cid: str) -> None:
    import threading

    from django.db import close_old_connections

    from api_core.workflow import ai_feedback

    def job():
        close_old_connections()
        try:
            result = ai_feedback.learn_from_feedback()
        except Exception as exc:  # noqa: BLE001
            result = {"status": "FAILED", "error": type(exc).__name__}
        cache.set(
            LEARNING_CACHE_KEY, {"state": "DONE", "result": result}, 7 * 24 * 3600
        )
        try:
            with connection.cursor() as cur:
                _append_admin_audit(
                    cur,
                    actor_id=actor_id,
                    action="AI_FEEDBACK_LEARNING_RUN",
                    target_type="ai_feedback",
                    target_id="00000000-0000-0000-0000-000000000000",
                    details={
                        k: result.get(k)
                        for k in ("status", "version", "reasons", "feedback_rows")
                    },
                    reason="Admin chạy học dồn từ phản hồi",
                    correlation_id=cid,
                )
        finally:
            close_old_connections()

    threading.Thread(target=job, name="ai-feedback-learning", daemon=True).start()


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def ai_feedback_learn_view(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/admin/ai-engine/feedback/learn: chạy học dồn ở nền (≈1-2 phút); xem kết quả ở GET feedback."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    current = cache.get(LEARNING_CACHE_KEY) or {}
    if current.get("state") == "RUNNING":
        return JsonResponse({"state": "RUNNING"}, status=202)
    cache.set(LEARNING_CACHE_KEY, {"state": "RUNNING"}, 15 * 60)
    _run_feedback_learning(request.actor.id, correlation_id(request))
    return JsonResponse({"state": "RUNNING"}, status=202)


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def ai_feedback_retire_view(request: HttpRequest, feedback_id) -> JsonResponse:
    """POST .../feedback/<id>/retire {note}: ngưng dùng một ca nhớ (vd. quản lý sửa nhầm)."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    body, error = _parse(request)
    if error:
        return error
    note = str(body.get("note") or "").strip()
    if len(note) < 5:
        return api_error(
            request, "VALIDATION_FAILED", status=422, fields={"note": ["Cần lý do"]}
        )
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(
            "UPDATE eas.ai_feedback SET retired_at = statement_timestamp(), retired_by = %s "
            "WHERE id = %s::uuid AND retired_at IS NULL RETURNING kind",
            [request.actor.id, str(feedback_id)],
        )
        row = cur.fetchone()
        if not row:
            return api_error(request, "NOT_FOUND", status=404)
        _append_admin_audit(
            cur,
            actor_id=request.actor.id,
            action="AI_FEEDBACK_RETIRED",
            target_type="ai_feedback",
            target_id=str(feedback_id),
            details={"kind": row[0]},
            reason=note[:500],
            correlation_id=correlation_id(request),
        )
    return JsonResponse({"id": str(feedback_id), "retired": True})


# ---------------------------------------------------------------------------
# Danh mục bad case trong CSDL (migration 25): bad case có sẵn, bad case AI học được, ứng viên chờ admin
# ---------------------------------------------------------------------------
BAD_CASE_STATES = ("CANDIDATE", "ACTIVE", "REJECTED", "RETIRED", "ALL")
BAD_CASE_DECISIONS = ("approve", "reject", "retire", "enable")


@require_actor("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
def bad_cases_list(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/admin/ai-engine/bad-cases?state=ALL: danh mục + đánh giá của AI + lý do thu hồi gần nhất."""
    from api_core.workflow import bad_case_learning

    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    state = (request.GET.get("state") or "ALL").upper()
    if state not in BAD_CASE_STATES:
        return api_error(request, "VALIDATION_FAILED", status=422)
    with connection.cursor() as cur:
        if not bad_case_learning.available(cur):
            return JsonResponse({"items": [], "installed": False})
        cur.execute(
            """
            SELECT b.id::text, b.code, b.title, b.rationale, b.condition_text, b.request_types, b.detector,
                   b.base_code, b.condition, b.verdict, b.feature, b.risk, b.escalate_to, b.source, b.state,
                   b.evaluation, b.activated_by, b.activated_at, b.note, b.decided_at, b.created_at, b.updated_at,
                   (SELECT count(*) FROM eas.bad_case_evidence e WHERE e.bad_case_id = b.id),
                   (SELECT coalesce(jsonb_agg(x ORDER BY x.created_at DESC), '[]'::jsonb) FROM (
                      SELECT e.reason, e.verdict, e.confidence, e.created_at, r.code AS request_code,
                             u.display_name AS approver, e.analysis->>'explanation' AS explanation,
                             e.analysis->>'why_missed' AS why_missed
                      FROM eas.bad_case_evidence e
                      JOIN eas.request r ON r.id = e.request_id
                      LEFT JOIN eas.app_user u ON u.id = e.approver_id
                      WHERE e.bad_case_id = b.id ORDER BY e.created_at DESC LIMIT 5) x)
            FROM eas.bad_case b
            WHERE %s = 'ALL' OR b.state = %s
            ORDER BY CASE b.state WHEN 'CANDIDATE' THEN 0 WHEN 'ACTIVE' THEN 1 ELSE 2 END,
                     b.detector = 'BUILTIN', b.updated_at DESC
            LIMIT 300
            """,
            [state, state],
        )
        keys = (
            "id",
            "code",
            "title",
            "rationale",
            "condition_text",
            "request_types",
            "detector",
            "base_code",
            "condition",
            "verdict",
            "feature",
            "risk",
            "escalate_to",
            "source",
            "state",
            "evaluation",
            "activated_by",
            "activated_at",
            "note",
            "decided_at",
            "created_at",
            "updated_at",
            "evidence_count",
            "evidence",
        )
        items = []
        for r in cur.fetchall():
            item = dict(zip(keys, r, strict=True))
            for k in ("activated_at", "decided_at", "created_at", "updated_at"):
                item[k] = _iso(item[k])
            items.append(item)
        cur.execute(
            """
            SELECT e.verdict, count(*) FROM eas.bad_case_evidence e
            WHERE e.created_at > now() - interval '90 days' GROUP BY 1
            """
        )
        verdicts = dict(cur.fetchall())
    return JsonResponse(
        {
            "items": items,
            "installed": True,
            "verdicts_90d": verdicts,
            "thresholds": {
                "window_days": bad_case_learning.WINDOW_DAYS,
                "min_evidence": bad_case_learning.MIN_EVIDENCE,
                "min_requesters": bad_case_learning.MIN_REQUESTERS,
                "min_approvers": bad_case_learning.MIN_APPROVERS,
                "max_coverage": bad_case_learning.MAX_COVERAGE,
            },
        }
    )


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def bad_case_decide_view(request: HttpRequest, case_id, decision: str) -> JsonResponse:
    """POST .../bad-cases/<id>/approve {title?, rationale?, condition?, request_types?, risk?, escalate_to?, note?}
    | /reject {note} | /retire {note} | /enable {note?}"""
    from api_core.workflow import bad_case_learning

    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if decision not in BAD_CASE_DECISIONS:
        return api_error(request, "NOT_FOUND", status=404)
    if denied := _forbidden_unless_writer(request):
        return denied
    body, error = _parse(request)
    if error:
        return error
    try:
        with transaction.atomic(), connection.cursor() as cur:
            result = bad_case_learning.admin_decide(
                cur,
                case_id=str(case_id),
                actor_id=request.actor.id,
                decision=decision,
                body=body,
            )
            note = str(body.get("note") or "").strip()
            _append_admin_audit(
                cur,
                actor_id=request.actor.id,
                action=f"BAD_CASE_{decision.upper()}",
                target_type="bad_case",
                target_id=str(case_id),
                details={"code": result["code"], "state": result["state"]},
                reason=note
                if len(note) >= 10
                else f"Admin {decision} bad case {result['code']}",
                correlation_id=correlation_id(request),
            )
    except LookupError:
        return api_error(request, "NOT_FOUND", status=404)
    except PermissionError:
        return api_error(request, "ALREADY_DECIDED", status=409)
    except ValueError as exc:
        field, _, message = str(exc).partition(": ")
        return api_error(
            request,
            "VALIDATION_FAILED",
            status=422,
            fields={field or "body": [message or str(exc)]},
        )
    return JsonResponse(result)
