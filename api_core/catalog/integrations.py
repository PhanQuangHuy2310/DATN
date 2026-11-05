"""Integration circuit breaker: request types that depend on a disabled mock API.

The admin toggles eas.mock_apis.is_enabled; every request type in the mapped
catalogue groups (or listed codes) is then closed for create/submit on the
server, and the client shows the same notice.
"""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection

# domain_key -> request types whose workflow calls that external system
# (docs/TICH_HOP_HE_THONG_NGOAI.md §4). Grouping categories are presentation
# only, so the mapping lists type codes explicitly.
BUDGET_TYPES = [
    "ADVANCE_SMALL",
    "ADVANCE_MEDIUM",
    "ADVANCE_LARGE",
    "EXPENSE_CLAIM",
    "PURCHASE_REQUEST",
    "EQUIPMENT",
    "VENDOR_PAYMENT",
    "MARKETING_CAMPAIGN",
    "BUSINESS_TRIP",
]
DOMAIN_MAPPING = {
    "hr": {"categories": [], "extra_codes": ["LEAVE", "LEAVE_SPECIAL"]},
    "finance": {"categories": [], "extra_codes": BUDGET_TYPES},
    "it": {"categories": [], "extra_codes": ["ACCESS"]},
    "procurement": {
        "categories": [],
        "extra_codes": ["PURCHASE_REQUEST", "SUPPLIER_ONBOARDING", "SAAS_LICENSE_BUY"],
    },
    "assets": {"categories": [], "extra_codes": ["EQUIPMENT_BORROW"]},
    "facilities": {
        "categories": [],
        "extra_codes": ["ROOM_BOOKING", "VEHICLE_BOOKING"],
    },
    "travel": {"categories": [], "extra_codes": ["BUSINESS_TRIP"]},
    "crm": {"categories": [], "extra_codes": ["SPECIAL_DISCOUNT"]},
}
CACHE_KEY = "eas:integrations:disabled"
CACHE_SECONDS = 5


def notice_for(source: str) -> str:
    return (
        f"Yêu cầu này hiện không thể sử dụng do kết nối API [{source}] "
        "đang bị tắt bởi Quản trị viên."
    )


def disabled_apis() -> list[tuple[str, str, str]]:
    """(api_code, domain_key, source) of disabled APIs; cached a few seconds."""
    rows = cache.get(CACHE_KEY)
    if rows is None:
        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass('eas.mock_apis') IS NOT NULL")
            if not cur.fetchone()[0]:
                return []
            cur.execute(
                "SELECT api_code, lower(COALESCE(domain_key, '')), "
                "COALESCE(source_system, api_name) FROM eas.mock_apis WHERE NOT is_enabled"
            )
            rows = [tuple(r) for r in cur.fetchall()]
        cache.set(CACHE_KEY, rows, CACHE_SECONDS)
    return rows


def invalidate() -> None:
    cache.delete(CACHE_KEY)


def blocks(domain_key: str, type_code: str, category: str | None) -> bool:
    mapping = DOMAIN_MAPPING.get(domain_key, {"categories": [], "extra_codes": []})
    return (category or "").upper() in mapping["categories"] or type_code in mapping[
        "extra_codes"
    ]


def unavailable_notice(type_code: str, category: str | None) -> str | None:
    """Notice when type_code depends on a disabled integration, else None."""
    for _code, domain, source in disabled_apis():
        if blocks(domain, type_code, category):
            return notice_for(source)
    return None
