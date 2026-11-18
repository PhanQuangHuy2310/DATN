"""Điều kiện của bad case học được (bảng eas.bad_case, cột condition): kiểm tra, so khớp, diễn giải.

Module thuần, không truy cập CSDL. Bản đối chiếu phía AI ở ai_service/bad_case_reason.py (validate_condition,
condition_matches); tests/test_bad_case_learning.py kiểm tra hai bên cho cùng kết quả.

Dạng: {"all": [{"feature": "<đặc trưng>", "op": "<=|>=|==|in", "value": số | [số...]}]}, tối đa 4 vế, chỉ dùng
đặc trưng trong FEATURES; thiếu giá trị thì không khớp (không chặn nhầm khi thiếu dữ liệu).
"""

from __future__ import annotations

import math
from typing import Any

FEATURES: dict[str, str] = {
    "notice_hours": "số giờ báo trước (từ lúc gửi đơn tới lúc bắt đầu)",
    "start_day_of_month": "ngày trong tháng của ngày bắt đầu",
    "start_weekday": "thứ của ngày bắt đầu (1 = Thứ Hai … 7 = Chủ nhật)",
    "submit_hour": "giờ gửi đơn (0–23, giờ Việt Nam)",
    "days_requested": "số ngày của đơn",
    "amount": "số tiền của hồ sơ",
    "requester_rejected_30d": "số hồ sơ của người gửi bị từ chối trong 30 ngày",
    "same_type_count_7d": "số hồ sơ cùng loại của người gửi trong 7 ngày",
    "same_type_count_30d": "số hồ sơ cùng loại của người gửi trong 30 ngày",
    "same_type_count_month": "số hồ sơ cùng loại của người gửi trong tháng",
    "team_absence_ratio": "tỉ lệ đồng nghiệp cùng phòng vắng trùng ngày",
    "work_due_in_absence": "số việc đến hạn trong thời gian vắng",
    "requester_finance_count_7d": "số hồ sơ tài chính của người gửi trong 7 ngày",
    "requester_amount_7d": "tổng tiền hồ sơ tài chính của người gửi trong 7 ngày",
    "off_hours_count_7d": "số hồ sơ gửi ngoài giờ trong 7 ngày",
    "ai_revoked_90d": "số lần tự duyệt của AI cho người gửi bị thu hồi trong 90 ngày",
    "duplicate_invoice_count": "số hồ sơ khác dùng cùng số hóa đơn",
    "same_customer_count_7d": "số hồ sơ chiết khấu khác cho cùng khách trong 7 ngày",
}
# Tính được cho MỌI hồ sơ cũ bằng một truy vấn (để đo độ phủ trên lịch sử trước khi kích hoạt).
HISTORY_FEATURES = frozenset({
    "notice_hours", "start_day_of_month", "start_weekday", "submit_hour", "days_requested", "amount",
    "requester_rejected_30d",
})
OPS = ("<=", ">=", "==", "in")
MAX_TERMS = 4
WEEKDAYS = {1: "Thứ Hai", 2: "Thứ Ba", 3: "Thứ Tư", 4: "Thứ Năm", 5: "Thứ Sáu", 6: "Thứ Bảy", 7: "Chủ nhật"}


def _num(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def validate(cond: Any) -> dict[str, Any]:
    if not isinstance(cond, dict) or set(cond) != {"all"} or not isinstance(cond["all"], list):
        raise ValueError('Điều kiện phải có dạng {"all": [{"feature": ..., "op": ..., "value": ...}]}')
    if not 1 <= len(cond["all"]) <= MAX_TERMS:
        raise ValueError(f"Điều kiện cần 1–{MAX_TERMS} vế")
    out = []
    for term in cond["all"]:
        if not isinstance(term, dict) or set(term) != {"feature", "op", "value"}:
            raise ValueError("Mỗi vế chỉ gồm feature, op, value")
        feature, op, value = term["feature"], term["op"], term["value"]
        if feature not in FEATURES:
            raise ValueError(f"Đặc trưng không hỗ trợ: {feature}")
        if op not in OPS:
            raise ValueError(f"Phép so sánh không hỗ trợ: {op}")
        if op == "in":
            if not isinstance(value, list) or not 1 <= len(value) <= 24 or not all(_num(v) for v in value):
                raise ValueError("Phép 'in' cần danh sách 1–24 số")
            value = sorted({int(v) if float(v).is_integer() else float(v) for v in value})
        else:
            if not _num(value):
                raise ValueError("Giá trị phải là số")
            value = int(value) if float(value).is_integer() else float(value)
        if feature == "start_weekday" and any(not 1 <= v <= 7 for v in (value if op == "in" else [value])):
            raise ValueError("Thứ trong tuần là 1–7")
        out.append({"feature": feature, "op": op, "value": value})
    return {"all": out}


def matches(cond: dict[str, Any] | None, values: dict[str, Any]) -> bool:
    if not cond or not cond.get("all"):
        return False
    for term in cond["all"]:
        v = values.get(term["feature"])
        if not _num(v):
            return False
        v, op, ref = float(v), term["op"], term["value"]
        if (op == "<=" and not v <= ref) or (op == ">=" and not v >= ref) or (op == "==" and v != ref):
            return False
        if op == "in" and v not in [float(x) for x in ref]:
            return False
    return True


def history_computable(cond: dict[str, Any] | None) -> bool:
    return bool(cond and cond.get("all")) and all(t["feature"] in HISTORY_FEATURES for t in cond["all"])


def _fmt(feature: str, value: Any) -> str:
    if feature == "start_weekday":
        return ", ".join(WEEKDAYS.get(int(v), str(v)) for v in (value if isinstance(value, list) else [value]))
    if feature in ("amount", "requester_amount_7d"):
        return f"{float(value):,.0f}".replace(",", ".") + " VNĐ"
    if feature == "team_absence_ratio":
        return f"{float(value):.0%}"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def describe(cond: dict[str, Any] | None) -> str:
    if not cond or not cond.get("all"):
        return "chưa có điều kiện đo được"
    words = {"<=": "≤", ">=": "≥", "==": "=", "in": "thuộc"}
    return " và ".join(f"{FEATURES[t['feature']]} {words[t['op']]} {_fmt(t['feature'], t['value'])}"
                       for t in cond["all"])
