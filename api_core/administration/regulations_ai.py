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


def _list_regulations() -> list[dict]:
    with connection.cursor() as cur:
        cur.execute(  # NOSONAR python:S2077 - REGULATION_COLUMNS is a constant
            f"SELECT {REGULATION_COLUMNS} FROM eas.company_regulations "
            "WHERE NOT is_deleted ORDER BY code"
        )
        return [_serialize_regulation(r) for r in cur.fetchall()]


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

    version = _v(regulation["version_string"])
    return JsonResponse(
        {
            "message": f"Đã ban hành quy định {code} (phiên bản {version}). AI đang học quy định mới; cổng nhân viên tạm khoá tới khi áp dụng xong.",
            "regulation": regulation,
            "new_version": version,
            "version_type": "MAJOR",
            "maintenance_active": True,
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

    version = _v(regulation["version_string"])
    return JsonResponse(
        {
            "message": f"Đã cập nhật quy định (phiên bản {version}). AI đang học lại; cổng nhân viên tạm khoá tới khi áp dụng xong.",
            "regulation": regulation,
            "new_version": version,
            "version_type": "MINOR",
            "maintenance_active": True,
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
