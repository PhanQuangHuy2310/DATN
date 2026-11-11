"""Thesis "10 core request types" mapped to existing catalog records (C1).

The report (§1.3 scope: "danh mục 10 loại yêu cầu") never lists the ten
types; it only gives examples. This mapping ties each example to an existing
published type so nothing is duplicated or removed. All 53 published types
and the 18 plan templates stay available.
"""

from __future__ import annotations

THESIS_CORE_TYPES: tuple[dict[str, str], ...] = (
    {
        "code": "LEAVE",
        "example": "Nghỉ phép",
        "reference": "§1.1, Bảng 2.4 (A), Bảng 2.6 R01/R02",
    },
    {
        "code": "OFFICE_SUPPLIES",
        "example": "Văn phòng phẩm",
        "reference": "§1.1, Bảng 2.4 (A)",
    },
    {
        "code": "ROOM_VEHICLE",
        "example": "Xe công vụ",
        "reference": "§1.1, Bảng 2.4 (A)",
    },
    {"code": "ROOM_BOOKING", "example": "Đăng ký phòng họp", "reference": "§1.1"},
    {"code": "EQUIPMENT", "example": "Mua thiết bị IT", "reference": "Bảng 2.4 (B)"},
    {
        "code": "EXPENSE_CLAIM",
        "example": "Thanh toán chi phí",
        "reference": "Bảng 2.4 (B)",
    },
    {
        "code": "PURCHASE_REQUEST",
        "example": "Mua sắm / chi tiêu",
        "reference": "Bảng 2.6 R03–R05",
    },
    {
        "code": "ADVANCE_LARGE",
        "example": "Tạm ứng hợp đồng",
        "reference": "Bảng 2.4 (C)",
    },
    {"code": "ACCESS", "example": "Cấp quyền CNTT", "reference": "§1.1, Bảng 2.6 R06"},
    {
        "code": "ASSET_PURCHASE",
        "example": "Tài sản lớn / tài sản cố định",
        "reference": "§1.3 Template C, Bảng 2.4 (C)",
    },
)

THESIS_CORE_CODES = frozenset(item["code"] for item in THESIS_CORE_TYPES)
