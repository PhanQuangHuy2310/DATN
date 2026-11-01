from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from api_core.authn.service import load_actor_from_session
from api_core.http import JsonBodyError, api_error, parse_json_object

from .maintenance import (
    ADMIN_ROLES,
    get_maintenance_metadata,
    is_maintenance_active,
    set_maintenance_mode,
)

logger = logging.getLogger(__name__)

POLICIES_STORAGE_DIR = os.path.join(settings.BASE_DIR, "ai_service", "data")


def _trigger_ai_retraining(policy_payload: dict[str, Any], operator: str):
    """
    Tiến trình chạy nền huấn luyện lại mô hình AI dựa trên quy chế mới nạp.
    Sau khi huấn luyện thành công -> Tự động tắt Maintenance Mode.
    """

    def _run():
        try:
            logger.info(
                "Bắt đầu huấn luyện lại mô hình AI với quy chế mới từ %s...", operator
            )
            # Lưu file quy chế mới vào ai_service/data/
            os.makedirs(POLICIES_STORAGE_DIR, exist_ok=True)
            policy_file = os.path.join(
                POLICIES_STORAGE_DIR, "active_enterprise_policy.json"
            )
            with open(policy_file, "w", encoding="utf-8") as f:
                json.dump(policy_payload, f, ensure_ascii=False, indent=2)

            # Thực thi pipeline AI Retraining
            pipeline_script = os.path.join(
                settings.BASE_DIR,
                "ai_service",
                "training",
                "enterprise_policy_ai_pipeline.py",
            )
            result = subprocess.run(
                [sys.executable, pipeline_script],
                cwd=os.path.join(settings.BASE_DIR, "ai_service"),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                logger.info(
                    "Huấn luyện AI thành công! Output:\n%s", result.stdout[-500:]
                )
            else:
                logger.error("Lỗi khi huấn luyện AI:\n%s", result.stderr[-500:])
        except Exception:
            logger.exception("Ngoại lệ khi chạy AI Retraining")
        finally:
            # Tự động gỡ bảo trì để hệ thống mở lại cho mọi người dùng
            set_maintenance_mode(
                active=False,
                reason="Đã hoàn tất nạp quy chế và cập nhật mô hình AI",
                operator="AI_TRAINER",
            )
            logger.info("Chế độ bảo trì đã được tắt tự động.")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


@require_GET
def maintenance_status(request: HttpRequest) -> JsonResponse:
    """Xem trạng thái bảo trì hệ thống và tiến độ nạp quy chế."""
    meta = get_maintenance_metadata()
    return JsonResponse(
        {
            "status": "ok",
            "maintenance_active": is_maintenance_active(),
            "metadata": meta,
        }
    )


@csrf_exempt
@require_POST
def toggle_maintenance(request: HttpRequest) -> JsonResponse:
    """Admin bật/tắt thủ công chế độ bảo trì."""
    actor = load_actor_from_session(request)
    if not actor or (
        actor.email.split("@", 1)[0] not in {"admin", "director", "policy_admin"}
        and not actor.roles.intersection(ADMIN_ROLES)
    ):
        return api_error(request, "FORBIDDEN", status=403)

    try:
        body = parse_json_object(request)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)

    active = bool(body.get("active", False))
    reason = str(body.get("reason", "Thao tác quản trị hệ thống"))
    duration = int(body.get("estimated_duration_seconds", 120))

    meta = set_maintenance_mode(
        active=active, reason=reason, operator=actor.email, duration_seconds=duration
    )
    return JsonResponse({"status": "ok", "metadata": meta})


@csrf_exempt
@require_POST
def ingest_policy(request: HttpRequest) -> JsonResponse:
    """
    API tiếp nhận quy định mới từ bên thứ 3 (Third-party HRM, ERP hoặc Ban Giám Đốc):
    - Tự động kích hoạt Maintenance Mode (Bảo trì trả 503 cho non-admin).
    - Lưu trữ nội dung quy chế và học quy tắc mới.
    - Kích hoạt pipeline huấn luyện lại mô hình AI (NLP Classifier & XGBoost Risk Models).
    """
    try:
        body = parse_json_object(request)
    except JsonBodyError as exc:
        return api_error(request, str(exc), status=400)

    policy_title = body.get("title", "Quy chế Doanh nghiệp Mới")
    policy_domain = body.get(
        "domain", "GENERAL"
    )  # IT, HR, FINANCE, PROCUREMENT, GENERAL
    rules = body.get("rules", [])
    author = body.get("author", "THIRD_PARTY_INTEGRATION")

    if not rules and not body.get("raw_text"):
        return api_error(request, "RULES_OR_RAW_TEXT_REQUIRED", status=400)

    # 1. Bật chế độ bảo trì để bảo vệ dữ liệu trong lúc nạp và train
    reason = f"Đang nạp quy chế '{policy_title}' và huấn luyện lại mô hình AI"
    meta = set_maintenance_mode(
        active=True, reason=reason, operator=author, duration_seconds=180
    )

    # 2. Gửi tiến trình huấn luyện AI chạy nền
    _trigger_ai_retraining(body, author)

    return JsonResponse(
        {
            "status": "INGESTION_ACCEPTED",
            "message": "Đã tiếp nhận quy chế mới thành công. Hệ thống tự động chuyển sang chế độ bảo trì để huấn luyện mô hình AI.",
            "policy_title": policy_title,
            "domain": policy_domain,
            "maintenance_mode": meta,
        },
        status=202,
    )


def publish_ai_policy_rules(request: HttpRequest) -> JsonResponse:
    """POLICY_ADMIN: GET lists versions; POST stores (and activates) a version."""
    from api_core.authn.service import require_actor
    from api_core.http import correlation_id
    from api_core.workflow.service import CommandError

    from . import ai_policy

    @require_actor("POLICY_ADMIN")
    def _handle(req: HttpRequest) -> JsonResponse:
        if req.method == "GET":
            return JsonResponse(
                {**ai_policy.list_versions(), "correlation_id": correlation_id(req)}
            )
        if req.method != "POST":
            return api_error(req, "METHOD_NOT_ALLOWED", status=405)
        try:
            body = parse_json_object(req)
            stored = ai_policy.publish_version(
                actor=req.actor, body=body, correlation_id=correlation_id(req)
            )
        except JsonBodyError as exc:
            return api_error(req, str(exc), status=400)
        except CommandError as exc:
            return api_error(req, exc.code, status=exc.status)
        applied = (
            ai_policy.push_to_ai(stored, correlation_id(req))
            if stored["activated"]
            else None
        )
        return JsonResponse(
            {
                "policy": stored,
                "ai_cache_refreshed": applied is not None,
                "correlation_id": correlation_id(req),
            },
            status=201,
        )

    return _handle(request)


@require_POST
def activate_ai_policy_version(request: HttpRequest, version_id) -> JsonResponse:
    """POLICY_ADMIN activates (or restores) a stored version."""
    from api_core.authn.service import require_actor
    from api_core.http import correlation_id
    from api_core.workflow.service import CommandError

    from . import ai_policy

    @require_actor("POLICY_ADMIN")
    def _handle(req: HttpRequest) -> JsonResponse:
        try:
            document = ai_policy.activate_version(
                actor=req.actor,
                version_id=str(version_id),
                correlation_id=correlation_id(req),
            )
        except CommandError as exc:
            return api_error(req, exc.code, status=exc.status)
        applied = ai_policy.push_to_ai(document, correlation_id(req))
        return JsonResponse(
            {
                "policy": document,
                "ai_cache_refreshed": applied is not None,
                "correlation_id": correlation_id(req),
            }
        )

    return _handle(request)


@csrf_exempt  # called by the AI service over the Docker network
@require_GET
def internal_active_ai_policy(request: HttpRequest) -> JsonResponse:
    """AI service pulls the active version when its cache is empty."""
    import hmac

    from . import ai_policy

    supplied = request.headers.get("X-Internal-Secret") or ""
    expected = settings.EAS_AI_INTERNAL_SECRET
    if not expected or not hmac.compare_digest(supplied, expected):
        return api_error(request, "UNAUTHORIZED", status=401)
    document = ai_policy.active_document()
    if document is None:
        return api_error(request, "NO_ACTIVE_POLICY", status=404)
    return JsonResponse(document)
