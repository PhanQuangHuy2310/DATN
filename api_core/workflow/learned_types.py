"""Loại yêu cầu mô hình phân loại chưa học (tạo sau danh mục gốc) và ví dụ của chúng, gửi kèm mỗi lần phân loại.

Mỗi hồ sơ gửi thêm của một loại mới là một ví dụ mới (tiêu đề), nên bộ nhớ loại mới ở ai_service học dần theo cách
người dùng viết mà không cần huấn luyện lại. Kết quả được giữ 60 giây; tạo loại mới thì xóa ngay (``invalidate``).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from django.db import connection

from api_core.catalog.plan_catalog import catalog_v2_item

logger = logging.getLogger(__name__)

TTL_SECONDS = 60
MAX_EXAMPLES = 30
EXECUTOR_DEPARTMENT = {
    "EXECUTOR_HR": "HR",
    "EXECUTOR_FINANCE": "FINANCE",
    "EXECUTOR_IT": "IT",
    "EXECUTOR_TECH": "TECH",
    "EXECUTOR_ADMIN": "ADMIN",
    "EXECUTOR_ASSET": "ASSET",
    "EXECUTOR_PROCUREMENT": "PROCUREMENT",
    "EXECUTOR_FACILITY": "FACILITY",
    "EXECUTOR_LEGAL": "LEGAL",
    "EXECUTOR_MARKETING": "MARKETING",
    "EXECUTOR_WAREHOUSE": "WAREHOUSE",
}
APPROVER_LABEL = {
    "DIRECT_MANAGER": "QL trực tiếp",
    "FINANCE": "Kế toán",
    "DIRECTOR": "Giám đốc",
    "HR_MANAGER": "HR",
    "IT_MANAGER": "Trưởng IT",
    "CTO": "CTO",
    "CISO": "CISO",
    "SECURITY": "An ninh",
    "LEGAL": "Pháp chế",
    "MARKETING_MANAGER": "Trưởng Marketing",
    "OPERATIONS_MANAGER": "Trưởng Vận hành",
    "PROCUREMENT_MANAGER": "Trưởng Mua hàng",
    "PROJECT_MANAGER": "Quản lý dự án",
    "WAREHOUSE_MANAGER": "Trưởng Kho",
}
EXECUTOR_LABEL = {
    "EXECUTOR_HR": "Nhân sự",
    "EXECUTOR_FINANCE": "Kế toán",
    "EXECUTOR_IT": "CNTT",
    "EXECUTOR_TECH": "Kỹ thuật",
    "EXECUTOR_ADMIN": "Hành chính",
    "EXECUTOR_ASSET": "Tài sản",
    "EXECUTOR_PROCUREMENT": "Mua hàng",
    "EXECUTOR_FACILITY": "Cơ sở vật chất",
    "EXECUTOR_LEGAL": "Pháp chế",
    "EXECUTOR_MARKETING": "Marketing",
    "EXECUTOR_WAREHOUSE": "Kho vận",
}

_lock = threading.Lock()
_cache: dict[str, Any] = {"at": 0.0, "items": None}


def route_summary(route_rules: dict | None) -> str:
    """"QL trực tiếp → Kế toán ⇒ thực hiện: Kế toán" từ luật mặc định của bản cấu hình."""
    rules = (route_rules or {}).get("rules") or []
    default = next((r for r in rules if r.get("default")), rules[-1] if rules else {})
    approvers = " → ".join(APPROVER_LABEL.get(a, a) for a in default.get("approvers") or [])
    executor = (route_rules or {}).get("executor")
    acceptor = (route_rules or {}).get("acceptor")
    text = approvers or "Quy trình phê duyệt tiêu chuẩn"
    if executor:
        text += f" ⇒ thực hiện: {EXECUTOR_LABEL.get(executor, executor)}"
    if acceptor:
        text += " ⇒ nghiệm thu: " + ("Người yêu cầu" if acceptor == "REQUESTER" else APPROVER_LABEL.get(acceptor, acceptor))
    return text


SQL_TYPES = """
    SELECT rt.id::text, rt.code, rt.name, coalesce(rt.description, ''), coalesce(rt.category, ''),
           coalesce(g.name, ''), rt.lifecycle, cr.route_rules
    FROM eas.request_type rt
    JOIN eas.config_release cr ON cr.id = rt.active_release_id AND cr.state = 'PUBLISHED'
    LEFT JOIN eas.request_group g ON g.code = rt.category
    WHERE rt.is_active
    ORDER BY rt.code
"""
SQL_EXAMPLES = """
    SELECT DISTINCT ON (lower(t.title)) t.title
    FROM (
      SELECT v.payload->>'title' AS title, v.submitted_at AS at
      FROM eas.request_revision v JOIN eas.request r ON r.id = v.request_id
      WHERE r.type_id = %s::uuid AND coalesce(v.payload->>'title', '') <> ''
      ORDER BY v.submitted_at DESC LIMIT 200
    ) t
    LIMIT %s
"""


def load(cursor) -> list[dict[str, Any]]:
    cursor.execute(SQL_TYPES)
    out = []
    for type_id, code, name, description, category, category_label, lifecycle, route in cursor.fetchall():
        if catalog_v2_item(code):  # mô hình đã học loại này
            continue
        cursor.execute(SQL_EXAMPLES, [type_id, MAX_EXAMPLES])
        examples = [str(r[0])[:300] for r in cursor.fetchall()]
        out.append({
            "code": code,
            "name": (name or code)[:200],
            "description": (description or "")[:2000],
            "category": category[:40],
            "category_label": category_label[:120],
            "department": EXECUTOR_DEPARTMENT.get((route or {}).get("executor") or "", "ADMIN"),
            "lifecycle": lifecycle if lifecycle in ("A", "B", "C") else "B",
            "approval_route": route_summary(route)[:400],
            "examples": examples,
        })
    return out


def current() -> list[dict[str, Any]]:
    """Danh sách loại mới (có cache); lỗi CSDL thì trả [] để phân loại vẫn chạy bằng mô hình gốc."""
    with _lock:
        if _cache["items"] is not None and time.monotonic() - _cache["at"] < TTL_SECONDS:
            return _cache["items"]
    try:
        with connection.cursor() as cursor:
            items = load(cursor)
    except Exception:
        logger.warning("learned request types unavailable", exc_info=True)
        return []
    with _lock:
        _cache.update(at=time.monotonic(), items=items)
    return items


def invalidate() -> None:
    with _lock:
        _cache.update(at=0.0, items=None)
