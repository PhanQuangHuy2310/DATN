from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from django.core.cache import cache
from django.db import connection

CACHE_KEY_MAINTENANCE = "eas:system:maintenance"
ADMIN_ROLES = frozenset({"POLICY_ADMIN", "OPS_ADMIN"})

MAINTENANCE_MSG_USER = (
    "Hệ thống đang bảo trì để cập nhật quy định mới, vui lòng quay lại sau."
)
MAINTENANCE_MSG_ADMIN_ACTIVE = "Hệ thống đang trong quá trình cập nhật quy định mới. Chỉ quản trị viên mới có thể truy cập web-admin."
MAINTENANCE_MSG_ADMIN_COMPLETED = "Hệ thống đã cập nhật xong quy định mới. Các tài khoản người dùng đã có thể sử dụng bình thường với phiên bản mới nhất."


def get_maintenance_info() -> dict[str, Any]:
    """Retrieve current system maintenance state from shared cache."""
    data = cache.get(CACHE_KEY_MAINTENANCE)
    if not data or not isinstance(data, dict):
        return {
            "active": False,
            "status": "NORMAL",
            "message": "Hệ thống đang hoạt động bình thường.",
            "admin_message": None,
            "started_at": None,
            "completed_at": None,
            "release_id": None,
            "updated_by": None,
        }
    return data


def is_maintenance_active() -> bool:
    """Return True if system is currently under maintenance / updating regulations."""
    info = get_maintenance_info()
    return bool(info.get("active", False))


def start_maintenance(
    *,
    actor_id: str | None = None,
    release_id: str | None = None,
    message: str | None = None,
    admin_message: str | None = None,
) -> dict[str, Any]:
    """Put the system into maintenance mode (e.g. while publishing new policy / training AI)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    info = {
        "active": True,
        "status": "UPDATING",
        "message": message or MAINTENANCE_MSG_USER,
        "admin_message": admin_message or MAINTENANCE_MSG_ADMIN_ACTIVE,
        "started_at": now_iso,
        "completed_at": None,
        "release_id": str(release_id) if release_id else None,
        "updated_by": str(actor_id) if actor_id else None,
    }
    cache.set(CACHE_KEY_MAINTENANCE, info, timeout=None)
    return info


def complete_maintenance(
    *,
    actor_id: str | None = None,
    admin_message: str | None = None,
) -> dict[str, Any]:
    """Complete maintenance mode, allowing normal users back in."""
    now_iso = datetime.now(timezone.utc).isoformat()
    old_info = get_maintenance_info()
    info = {
        "active": False,
        "status": "COMPLETED",
        "message": "Hệ thống đang hoạt động bình thường.",
        "admin_message": admin_message or MAINTENANCE_MSG_ADMIN_COMPLETED,
        "started_at": old_info.get("started_at"),
        "completed_at": now_iso,
        "release_id": old_info.get("release_id"),
        "updated_by": str(actor_id) if actor_id else None,
    }
    # Keep the COMPLETED notification for 2 hours for admins to see
    cache.set(CACHE_KEY_MAINTENANCE, info, timeout=7200)
    return info


def reset_maintenance_for_test() -> None:
    """Helper to clear maintenance state in test teardowns."""
    cache.delete(CACHE_KEY_MAINTENANCE)


def is_admin_actor(actor: Any) -> bool:
    """Check if an Actor has administrative privileges (web-admin access)."""
    if not actor or not hasattr(actor, "roles"):
        return False
    return bool(actor.roles.intersection(ADMIN_ROLES))


def is_admin_user_id(user_id: str) -> bool:
    """Check whether user_id possesses active admin role memberships in the database."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM eas.role_membership
              WHERE user_id = %s
                AND role IN ('POLICY_ADMIN', 'OPS_ADMIN')
                AND revoked_at IS NULL
                AND valid_from <= statement_timestamp()
                AND (valid_to IS NULL OR valid_to > statement_timestamp())
            )
            """,
            [user_id],
        )
        row = cursor.fetchone()
        return bool(row and row[0])
