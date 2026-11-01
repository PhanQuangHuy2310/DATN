from __future__ import annotations

import json
from typing import Any

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from api_core.authn.service import load_actor_from_session

MAINTENANCE_CACHE_KEY = "eas:system:maintenance_mode"
MAINTENANCE_METADATA_KEY = "eas:system:maintenance_metadata"

# Các URL ngoại lệ luôn được phép truy cập khi bảo trì (Health check, Login, Maintenance status)
MAINTENANCE_EXEMPT_PATHS = {
    "/health/",
    "/health/liveness",
    "/health/readiness",
    "/api/v1/auth/csrf",
    "/api/v1/auth/login",
    "/api/v1/auth/password-reset/",
    "/api/v1/auth/logout",
    "/api/v1/policies/maintenance-status/",
    "/api/v1/policies/ingest/",
}

ADMIN_ROLES = {"OPS_ADMIN", "POLICY_ADMIN", "AUDITOR"}


def is_maintenance_active() -> bool:
    """Kiểm tra xem hệ thống có đang ở chế độ bảo trì hay không."""
    return bool(cache.get(MAINTENANCE_CACHE_KEY, False))


def get_maintenance_metadata() -> dict[str, Any]:
    """Lấy thông tin chi tiết về đợt bảo trì hiện tại."""
    data = cache.get(MAINTENANCE_METADATA_KEY)
    if not data:
        return {
            "active": False,
            "reason": "Hệ thống hoạt động bình thường",
            "started_at": None,
            "estimated_duration_seconds": 0
        }
    return data if isinstance(data, dict) else json.loads(data)


def set_maintenance_mode(
    active: bool,
    reason: str = "Cập nhật quy chế doanh nghiệp & Tối ưu hóa mô hình AI",
    operator: str = "SYSTEM",
    duration_seconds: int = 120
) -> dict[str, Any]:
    """Bật/tắt chế độ bảo trì hệ thống."""
    import datetime
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    cache.set(MAINTENANCE_CACHE_KEY, active, timeout=None if active else 1)
    
    metadata = {
        "active": active,
        "reason": reason,
        "operator": operator,
        "started_at": now_iso if active else None,
        "estimated_duration_seconds": duration_seconds if active else 0
    }
    cache.set(MAINTENANCE_METADATA_KEY, metadata, timeout=None if active else 1)
    return metadata


class MaintenanceModeMiddleware:
    """
    Middleware kiểm soát bảo trì thông minh:
    - Nếu hệ thống đang bảo trì:
      + Cho phép Admin (OPS_ADMIN, POLICY_ADMIN, email admin@eas.com) truy cập để giám sát và thao tác.
      + Trả về HTTP 503 cho tất cả các role khác (Requester, Approver, Executor, Acceptor) kèm thông báo tiếng Việt rõ ràng.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 1. Bỏ qua nếu đường dẫn thuộc danh sách miễn trừ
        for path in MAINTENANCE_EXEMPT_PATHS:
            if request.path.startswith(path):
                return self.get_response(request)

        # 2. Nếu chế độ bảo trì không bật, tiếp tục luồng bình thường
        if not is_maintenance_active():
            return self.get_response(request)

        # 3. Khi chế độ bảo trì đang bật: Kiểm tra danh tính người dùng
        actor = load_actor_from_session(request)
        
        # Nếu là Admin hoặc có vai trò quản trị hệ thống -> Cho phép đi tiếp
        if actor:
            is_admin = (
                actor.email.split("@", 1)[0] in {"admin", "director", "policy_admin"}
                or bool(actor.roles.intersection(ADMIN_ROLES))
            )
            if is_admin:
                return self.get_response(request)

        # 4. Người dùng thông thường hoặc chưa đăng nhập -> Trả về HTTP 503
        meta = get_maintenance_metadata()
        return JsonResponse(
            {
                "error": "SYSTEM_UNDER_MAINTENANCE",
                "message": "Hệ thống đang bảo trì để cập nhật quy chế doanh nghiệp và tối ưu hóa mô hình AI. Vui lòng quay lại sau ít phút.",
                "maintenance": True,
                "reason": meta.get("reason"),
                "started_at": meta.get("started_at"),
                "estimated_duration_seconds": meta.get("estimated_duration_seconds", 120),
                "retry_after": 60,
            },
            status=503,
            headers={"Retry-After": "60"}
        )
