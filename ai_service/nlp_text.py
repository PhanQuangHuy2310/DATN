"""Text and request-type helpers shared by training (training/train.py) and the
inference routers, so both sides normalise input identically.

Standard library only: the AI Docker image and the training script both import
this module, and nothing here is pickled into a model file.
"""

from __future__ import annotations

import re
import unicodedata

# Old 16-label taxonomy (models trained before 2026-11) and deprecated catalog
# codes, mapped to the active catalog code (api_core/catalog/catalog_v2.json).
LEGACY_TYPE_ALIASES = {
    "access_permission": "ACCESS",
    "advance_payment": "ADVANCE_MEDIUM",
    "budget_approval": "BUDGET_REALLOCATION",
    "contract_payment": "VENDOR_PAYMENT",
    "equipment_new": "EQUIPMENT",
    "equipment_repair": "IT_SUPPORT",
    "expense_reimbursement": "EXPENSE_CLAIM",
    "leave_annual": "LEAVE",
    "leave_unpaid": "LEAVE",
    "leave_short": "LEAVE",
    "meeting_room": "ROOM_BOOKING",
    "overtime": "OVERTIME_REQ",
    "remote_work": "WFH_REQ",
    "stationery": "OFFICE_SUPPLIES",
    "travel": "BUSINESS_TRIP",
    "vpn_access": "ACCESS",
    "late_checkin": "ATTENDANCE_ADJUSTMENT",
    "refund": "REFUND_COMPENSATION",
    "ASSET_PURCHASE": "EQUIPMENT",
    "SOFTWARE_ACCESS": "ACCESS",
    "ROOM_STUDIO": "ROOM_BOOKING",
    "ROOM_VEHICLE": "VEHICLE_BOOKING",
    "LEAVE_ANNUAL": "LEAVE",
    "LEAVE_LONG": "LEAVE",
    "OVERTIME_APPROVAL": "OVERTIME_REQ",
    "FACILITY_MAINTENANCE": "FACILITY_REPAIR",
}

ADVANCE_TIERS = ("ADVANCE_SMALL", "ADVANCE_MEDIUM", "ADVANCE_LARGE")

_SPACES = re.compile(r"\s+")
_AMOUNT = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(tỷ|ty|tỉ|triệu|trieu|tr|nghìn|nghin|ngàn|ngan|k|đồng|dong|đ|vnđ|vnd)?",
    re.IGNORECASE,
)
_UNIT = {
    "tỷ": 1e9, "ty": 1e9, "tỉ": 1e9,
    "triệu": 1e6, "trieu": 1e6, "tr": 1e6,
    "nghìn": 1e3, "nghin": 1e3, "ngàn": 1e3, "ngan": 1e3, "k": 1e3,
}


def normalize_text(text: str) -> str:
    """Lowercase, NFC, đ→d and collapsed whitespace (diacritics are kept)."""
    value = unicodedata.normalize("NFC", str(text or "")).lower()
    value = value.replace("đ", "d")
    return _SPACES.sub(" ", value).strip()


def strip_diacritics(text: str) -> str:
    """Vietnamese without accents, the way many users type on a phone."""
    value = unicodedata.normalize("NFD", str(text or "").replace("đ", "d").replace("Đ", "D"))
    return unicodedata.normalize(
        "NFC", "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    )


def canonical_request_type(value: str | None) -> str:
    """Map any accepted spelling (legacy, deprecated, lowercase) to a catalog code."""
    raw = str(value or "").strip()
    if raw in LEGACY_TYPE_ALIASES:
        return LEGACY_TYPE_ALIASES[raw]
    upper = raw.upper()
    return LEGACY_TYPE_ALIASES.get(upper, upper)


def extract_amount_vnd(text: str) -> float | None:
    """Largest money amount written in the text, e.g. '15 triệu', '3tr', '1,2 tỷ'."""
    best: float | None = None
    for number, unit in _AMOUNT.findall(str(text or "")):
        unit_key = unit.lower()
        if unit_key in _UNIT:
            # "1,5 triệu" / "1.5tr": comma or dot is a decimal separator here.
            try:
                amount = float(number.replace(",", ".")) * _UNIT[unit_key]
            except ValueError:
                continue
        elif unit_key or re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", number):
            # "5.000.000 đồng" / "450.000đ": separators group thousands.
            digits = re.sub(r"[.,]", "", number)
            if not digits.isdigit():
                continue
            amount = float(digits)
        else:
            continue  # a bare number such as "3 ngày" is not money
        if amount >= 1_000 and (best is None or amount > best):
            best = amount
    return best


def advance_tier(amount_vnd: float) -> str:
    """Catalog tiers: <10 triệu, 10–50 triệu, >50 triệu."""
    if amount_vnd < 10_000_000:
        return "ADVANCE_SMALL"
    if amount_vnd <= 50_000_000:
        return "ADVANCE_MEDIUM"
    return "ADVANCE_LARGE"


def refine_advance_tier(code: str, text: str) -> str:
    """The three advance types differ only by amount: trust the written amount."""
    if code not in ADVANCE_TIERS:
        return code
    amount = extract_amount_vnd(text)
    return advance_tier(amount) if amount else code
