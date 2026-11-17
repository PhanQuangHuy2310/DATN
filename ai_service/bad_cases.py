"""Suy luận tình huống xấu (bad cases) trước khi cho phép tự duyệt.

Lõi nghiệp vụ (API core) tính các TÍN HIỆU NGỮ CẢNH từ lịch sử thật trong cơ sở dữ liệu
(việc đang giữ sắp đến hạn, tổng tiền 7 ngày, số lần điều chỉnh chấm công 30 ngày) và gửi kèm
yêu cầu đánh giá tự duyệt. Module này chỉ suy luận trên các tín hiệu đó, không truy cập dữ liệu
cá nhân và không gọi dịch vụ bên ngoài, nên kết quả tái lập được và giải thích được.

Tình huống xấu 4 (xung đột lợi ích / bất kiêm nhiệm) đã được cưỡng chế bằng trigger ở tầng cơ sở
dữ liệu cho mọi quyết định, kể cả quyết định của tài khoản AI, nên không lặp lại ở đây.
"""
from __future__ import annotations

from dataclasses import dataclass, field

try:
    from nlp_text import canonical_request_type
except ImportError:  # chạy từ gốc repo
    from ai_service.nlp_text import canonical_request_type

ABSENCE_TYPES = {"LEAVE", "LEAVE_SPECIAL", "ATTENDANCE_ADJUSTMENT"}
FINANCE_TYPES = {"ADVANCE_SMALL", "ADVANCE_MEDIUM", "ADVANCE_LARGE", "EXPENSE_CLAIM", "REIMBURSEMENT",
                 "SALARY_ADVANCE", "REFUND_COMPENSATION"}
DEADLINE_HOURS = 24
SPLIT_THRESHOLD_VND = 20_000_000
SPLIT_WINDOW_DAYS = 7
SPLIT_MIN_REQUESTS = 2
REPEAT_WINDOW_DAYS = 30
REPEAT_MAX = 3            # lần thứ 4 trở lên trong 30 ngày thì không tự duyệt


@dataclass
class Signals:
    request_type: str
    amount: float = 0.0
    active_tasks_due_24h: int = 0
    handover_assigned: bool | None = None
    requester_amount_7d: float = 0.0       # tổng tiền các hồ sơ tài chính đã gửi trong 7 ngày, gồm hồ sơ này
    requester_finance_count_7d: int = 0    # số hồ sơ tài chính đã gửi trong 7 ngày, gồm hồ sơ này
    attendance_count_30d: int = 0          # số hồ sơ điều chỉnh chấm công trong 30 ngày, gồm hồ sơ này


@dataclass
class BadCaseResult:
    cases: list[dict] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.cases)

    @property
    def effective_risk(self) -> int | None:
        return max((c["risk"] for c in self.cases), default=None)


def _vnd(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".") + " VNĐ"


def evaluate(sig: Signals, split_threshold: float = SPLIT_THRESHOLD_VND) -> BadCaseResult:
    code = canonical_request_type(sig.request_type)
    out = BadCaseResult()

    # 1. Xin vắng mặt trong khi đang giữ việc sắp đến hạn và chưa chỉ định người nhận bàn giao.
    if code in ABSENCE_TYPES and sig.active_tasks_due_24h > 0 and not sig.handover_assigned:
        out.cases.append({
            "code": "BC_DEADLINE_CONFLICT", "risk": 5, "action": "BLOCK_AUTO_APPROVE_AND_ESCALATE",
            "message": (f"Người gửi đang giữ {sig.active_tasks_due_24h} việc đến hạn trong {DEADLINE_HOURS} giờ tới và "
                        "chưa chỉ định người nhận bàn giao; không tự duyệt, cần quản lý xác nhận phương án bàn giao."),
            "evidence": {"active_tasks_due_24h": sig.active_tasks_due_24h, "handover_assigned": bool(sig.handover_assigned)},
        })

    # 2. Chia nhỏ đề xuất tài chính: từng hồ sơ dưới ngưỡng nhưng tổng 7 ngày vượt ngưỡng.
    if (code in FINANCE_TYPES and sig.amount <= split_threshold
            and sig.requester_finance_count_7d >= SPLIT_MIN_REQUESTS
            and sig.requester_amount_7d > split_threshold):
        out.cases.append({
            "code": "BC_SPLIT_AMOUNT_EVASION", "risk": 5, "action": "FLAG_COMPLIANCE_RISK",
            "message": (f"{sig.requester_finance_count_7d} đề xuất tài chính trong {SPLIT_WINDOW_DAYS} ngày, tổng "
                        f"{_vnd(sig.requester_amount_7d)} vượt ngưỡng {_vnd(split_threshold)} trong khi từng hồ sơ dưới "
                        "ngưỡng: nghi chia nhỏ chứng từ để tránh cấp duyệt cao hơn."),
            "evidence": {"amount_7d": sig.requester_amount_7d, "count_7d": sig.requester_finance_count_7d,
                         "threshold": split_threshold},
        })

    # 3. Lạm dụng ngưỡng miễn trừ: điều chỉnh chấm công lặp lại.
    if code == "ATTENDANCE_ADJUSTMENT" and sig.attendance_count_30d > REPEAT_MAX:
        out.cases.append({
            "code": "BC_REPEATED_EXEMPTION", "risk": 3, "action": "BLOCK_AUTO_APPROVE",
            "message": (f"Đây là lần điều chỉnh chấm công thứ {sig.attendance_count_30d} trong {REPEAT_WINDOW_DAYS} ngày "
                        f"(quá {REPEAT_MAX} lần): không còn đủ điều kiện tự duyệt, cần giải trình với quản lý."),
            "evidence": {"attendance_count_30d": sig.attendance_count_30d},
        })
    return out
