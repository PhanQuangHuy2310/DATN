"""Suy luận tình huống xấu (bad cases) trước khi cho phép AI tự duyệt hồ sơ luồng A.

Danh mục và ngưỡng nằm ở ``data/bad_case_catalog.json`` (Gemini sinh ứng viên, nhóm rà lại).
API core tính TÍN HIỆU NGỮ CẢNH từ lịch sử thật trong CSDL (api_core/workflow/bad_case_signals.py)
và gửi kèm yêu cầu đánh giá; module này chỉ suy luận trên các tín hiệu đó (đếm, tổng, số giờ),
không truy cập dữ liệu cá nhân và không gọi dịch vụ bên ngoài, nên kết quả tái lập và giải thích được.

Mỗi tình huống trả về: mã, mức rủi ro hiệu lực, luồng nâng cấp (B/C) cho chính hồ sơ, bằng chứng
(tín hiệu đã dùng) và các hướng xử lý gốc rễ để quản lý chọn sau khi duyệt.

Xung đột lợi ích / bất kiêm nhiệm được cưỡng chế bằng trigger CSDL cho mọi quyết định (kể cả của
tài khoản AI), nên không lặp lại ở đây.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from functools import lru_cache
from typing import Any

try:
    from nlp_text import canonical_request_type
except ImportError:  # chạy từ gốc repo
    from ai_service.nlp_text import canonical_request_type

CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "bad_case_catalog.json"
)
FINANCE_TYPES = {
    "ADVANCE_SMALL",
    "ADVANCE_MEDIUM",
    "ADVANCE_LARGE",
    "EXPENSE_CLAIM",
    "REIMBURSEMENT",
    "SALARY_ADVANCE",
    "REFUND_COMPENSATION",
}


@dataclass
class Signals:
    request_type: str
    amount: float = 0.0
    # việc đang giữ
    open_work_due_hours: list[float] = field(default_factory=list)
    work_due_in_absence: int = 0
    active_tasks_due_24h: int = 0
    handover_assigned: bool | None = None
    handover_open_work_in_absence: int = 0
    handover_absent: bool = False
    # phòng ban
    team_absence_ratio: float = 0.0
    team_size: int = 0
    # lịch sử người gửi
    same_type_count_7d: int = 0
    same_type_count_30d: int = 0
    same_type_count_month: int = 0
    attendance_count_30d: int = 0
    requester_amount_7d: float = 0.0
    requester_finance_count_7d: int = 0
    duplicate_invoice_count: int = 0
    same_customer_count_7d: int = 0
    requester_absent_on_event: bool = False
    ai_revoked_90d: int = 0
    off_hours_count_7d: int = 0
    uncovered_work: int = (
        0  # việc đến hạn mà người nhận bàn giao không đủ vai trò làm thay
    )
    handover_named: bool = False  # đơn có điền người nhận bàn giao

    @classmethod
    def from_input(cls, body: Any) -> Signals:
        """Lấy các tín hiệu cần cho suy luận từ AutoApproveInput (thiếu trường thì dùng mặc định)."""
        values = {}
        for f in fields(cls):
            if hasattr(body, f.name):
                value = getattr(body, f.name)
                if value is not None or f.name == "handover_assigned":
                    values[f.name] = value
        return cls(**values)


@dataclass
class BadCaseResult:
    cases: list[dict] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.cases)

    @property
    def effective_risk(self) -> int | None:
        return max((c["risk"] for c in self.cases), default=None)


@lru_cache(maxsize=1)
def load_catalog(path: str = CATALOG_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _vnd(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".") + " VNĐ"


# --------------------------------------------------------------------------- bộ phát hiện
# Mỗi hàm trả (khớp?, thông điệp, bằng chứng). Tham số lấy từ danh mục.


def _deadline_conflict(s: Signals, p: dict) -> tuple[bool, str, dict]:
    hours = p.get("due_within_hours", 24)
    due = [h for h in s.open_work_due_hours if h <= hours]
    count = max(len(due), s.active_tasks_due_24h if hours >= 24 else 0)
    hit = (count > 0 or s.work_due_in_absence > 0) and not s.handover_assigned
    parts = []
    if count:
        parts.append(f"{count} việc đến hạn trong {hours} giờ tới")
    if s.work_due_in_absence:
        parts.append(f"{s.work_due_in_absence} việc đến hạn ngay trong thời gian nghỉ")
    if s.handover_named and s.uncovered_work:
        why = (
            f"người được chọn nhận bàn giao không đủ thẩm quyền làm thay {s.uncovered_work} việc "
            "(không có vai trò duyệt/xử lý phù hợp hoặc chính là người gửi việc đó)"
        )
    else:
        why = "chưa chỉ định người nhận bàn giao"
    msg = (
        f"Người gửi đang giữ {', '.join(parts)} và {why}; "
        "không tự duyệt, cần quản lý chốt phương án bàn giao."
    )
    return (
        hit,
        msg,
        {
            "due_within_hours": count,
            "due_in_absence": s.work_due_in_absence,
            "handover_assigned": bool(s.handover_assigned),
            "uncovered_work": s.uncovered_work,
        },
    )


def _handover_overloaded(s: Signals, p: dict) -> tuple[bool, str, dict]:
    limit = p.get("max_handover_items", 3)
    hit = bool(s.handover_assigned) and (
        s.handover_absent or s.handover_open_work_in_absence >= limit
    )
    why = (
        "cũng vắng trong thời gian này"
        if s.handover_absent
        else f"đang giữ {s.handover_open_work_in_absence} việc đến hạn trong thời gian nghỉ (≥ {limit})"
    )
    msg = f"Người nhận bàn giao {why}: bàn giao không khả thi, cần chọn người khác."
    return (
        hit,
        msg,
        {
            "handover_absent": s.handover_absent,
            "handover_open_work_in_absence": s.handover_open_work_in_absence,
        },
    )


def _team_absence_peak(s: Signals, p: dict) -> tuple[bool, str, dict]:
    ratio = p.get("min_ratio", 0.4)
    hit = s.team_size >= 3 and s.team_absence_ratio >= ratio
    msg = (
        f"{s.team_absence_ratio:.0%} thành viên khác của phòng đã vắng trùng ngày (ngưỡng {ratio:.0%}): "
        "nguy cơ thiếu người trực."
    )
    return (
        hit,
        msg,
        {"team_absence_ratio": s.team_absence_ratio, "team_size": s.team_size},
    )


def _repeated_exemption(s: Signals, p: dict) -> tuple[bool, str, dict]:
    limit = p.get("max_in_30d", 3)
    count = max(s.attendance_count_30d, s.same_type_count_30d)
    hit = count > limit
    msg = (
        f"Đây là lần điều chỉnh chấm công thứ {count} trong 30 ngày (quá {limit} lần): "
        "không còn đủ điều kiện tự duyệt, cần giải trình với quản lý."
    )
    return hit, msg, {"attendance_count_30d": count}


def _wfh_frequent(s: Signals, p: dict) -> tuple[bool, str, dict]:
    limit = p.get("max_in_month", 7)
    hit = s.same_type_count_month > limit
    msg = f"Đây là đơn WFH thứ {s.same_type_count_month} trong tháng (quá {limit}): cần quản lý xem xét."
    return hit, msg, {"wfh_count_month": s.same_type_count_month}


def _split_amount(s: Signals, p: dict) -> tuple[bool, str, dict]:
    threshold = p.get("threshold_vnd", 20_000_000)
    hit = (
        s.amount <= threshold
        and s.requester_finance_count_7d >= p.get("min_requests", 2)
        and s.requester_amount_7d > threshold
    )
    msg = (
        f"{s.requester_finance_count_7d} đề xuất tài chính trong {p.get('window_days', 7)} ngày, tổng "
        f"{_vnd(s.requester_amount_7d)} vượt ngưỡng {_vnd(threshold)} trong khi từng hồ sơ dưới ngưỡng: "
        "nghi chia nhỏ chứng từ để tránh cấp duyệt cao hơn."
    )
    return (
        hit,
        msg,
        {
            "amount_7d": s.requester_amount_7d,
            "count_7d": s.requester_finance_count_7d,
            "threshold": threshold,
        },
    )


def _duplicate_invoice(s: Signals, p: dict) -> tuple[bool, str, dict]:
    hit = s.duplicate_invoice_count > 0
    msg = (
        f"Số hóa đơn đã xuất hiện ở {s.duplicate_invoice_count} hồ sơ thanh toán khác trong "
        f"{p.get('window_days', 180)} ngày: nguy cơ thanh toán trùng."
    )
    return hit, msg, {"duplicate_invoice_count": s.duplicate_invoice_count}


def _refund_frequent(s: Signals, p: dict) -> tuple[bool, str, dict]:
    limit = p.get("max_in_7d", 2)
    hit = s.same_type_count_7d > limit
    msg = f"Đây là hồ sơ hoàn tiền thứ {s.same_type_count_7d} trong 7 ngày (quá {limit}): cần kế toán đối soát."
    return hit, msg, {"refund_count_7d": s.same_type_count_7d}


def _discount_repeat(s: Signals, p: dict) -> tuple[bool, str, dict]:
    hit = s.same_customer_count_7d > 0
    msg = (
        f"Đã có {s.same_customer_count_7d} hồ sơ chiết khấu khác cho cùng khách hàng trong "
        f"{p.get('window_days', 7)} ngày: cần xét tổng chiết khấu."
    )
    return hit, msg, {"same_customer_count_7d": s.same_customer_count_7d}


def _absent_on_event(s: Signals, p: dict) -> tuple[bool, str, dict]:
    hit = s.requester_absent_on_event
    msg = "Người gửi có lịch nghỉ/công tác trùng đúng ngày sự kiện: cần đổi người đón/chủ trì hoặc đổi ngày."
    return hit, msg, {"requester_absent_on_event": hit}


def _ai_revoked(s: Signals, p: dict) -> tuple[bool, str, dict]:
    limit = p.get("min_revoked_90d", 2)
    hit = s.ai_revoked_90d >= limit
    msg = f"{s.ai_revoked_90d} quyết định tự duyệt của AI cho người gửi đã bị quản lý thu hồi trong 90 ngày."
    return hit, msg, {"ai_revoked_90d": s.ai_revoked_90d}


def _off_hours_bulk(s: Signals, p: dict) -> tuple[bool, str, dict]:
    limit = p.get("min_in_7d", 3)
    hit = s.off_hours_count_7d >= limit
    msg = f"{s.off_hours_count_7d} hồ sơ gửi ngoài giờ hành chính trong 7 ngày (ngưỡng {limit})."
    return hit, msg, {"off_hours_count_7d": s.off_hours_count_7d}


DETECTORS = {
    "BC_DEADLINE_CONFLICT": _deadline_conflict,
    "BC_HANDOVER_OVERLOADED": _handover_overloaded,
    "BC_TEAM_ABSENCE_PEAK": _team_absence_peak,
    "BC_REPEATED_EXEMPTION": _repeated_exemption,
    "BC_WFH_FREQUENT": _wfh_frequent,
    "BC_SPLIT_AMOUNT_EVASION": _split_amount,
    "BC_DUPLICATE_INVOICE": _duplicate_invoice,
    "BC_REFUND_FREQUENT": _refund_frequent,
    "BC_DISCOUNT_REPEAT_CUSTOMER": _discount_repeat,
    "BC_REQUESTER_ABSENT_ON_EVENT": _absent_on_event,
    "BC_AI_REVOKED_HISTORY": _ai_revoked,
    "BC_OFF_HOURS_BULK": _off_hours_bulk,
}


def evaluate(
    sig: Signals,
    catalog: dict[str, Any] | None = None,
    split_threshold: float | None = None,
) -> BadCaseResult:
    """Mọi tình huống xấu khớp với hồ sơ, theo thứ tự trong danh mục."""
    catalog = catalog or load_catalog()
    code = canonical_request_type(sig.request_type)
    actions = catalog.get("remediation_actions", {})
    out = BadCaseResult()
    for case in catalog["cases"]:
        types = case.get("request_types") or []
        if "*" not in types and code not in types:
            continue
        detector = DETECTORS.get(case["code"])
        if detector is None:
            continue
        params = dict(case.get("params") or {})
        if split_threshold is not None and case["code"] == "BC_SPLIT_AMOUNT_EVASION":
            params["threshold_vnd"] = split_threshold
        hit, message, evidence = detector(sig, params)
        if not hit:
            continue
        out.cases.append(
            {
                "code": case["code"],
                "title": case.get("title"),
                "risk": int(case["risk"]),
                "escalate_to": case.get("escalate_to"),
                "action": "BLOCK_AUTO_APPROVE_AND_ESCALATE",
                "message": message,
                "evidence": evidence,
                "remediation": [
                    {"action": a, "text": actions.get(a, a)}
                    for a in case.get("remediation") or []
                ],
                "catalog_version": catalog.get("version"),
            }
        )
    return out
