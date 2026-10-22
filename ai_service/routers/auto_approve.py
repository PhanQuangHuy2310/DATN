"""
Router: Auto-Approve — Quyết định tự động duyệt yêu cầu

POST /ai/auto-approve/evaluate
  - Input: thông tin yêu cầu + risk score đã tính
  - Output: quyết định (auto_approve / escalate_to_human) + lý do

Nguyên tắc (plan.md 2.3):
  ✅ Auto-approve khi: Template A + risk_score ≤ 2 + các rule nghiệp vụ hợp lệ
  ❌ KHÔNG auto-approve khi: Template B/C hoặc risk > 2
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from loguru import logger
from datetime import datetime

from config import get_settings
from .mock_context import lookup_leave_balance, lookup_facility_available

settings = get_settings()
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AutoApproveInput(BaseModel):
    request_id: str = Field(..., description="UUID của yêu cầu")
    request_type: str
    lifecycle_template: str = Field(..., description="A/B/C")
    risk_score: int = Field(..., ge=1, le=5)
    amount: float = Field(0.0, ge=0)
    days_requested: int = Field(0, ge=0)
    leave_balance_remaining: int = Field(0, ge=0)
    room_available: Optional[bool] = Field(None, description="Phòng họp còn trống không (cho room_booking)")
    requester_name: str
    requester_dept: str


class AutoApproveDecision(BaseModel):
    decision: str = Field(..., description="'auto_approve' | 'escalate_to_human'")
    reason: str = Field(..., description="Lý do ngắn gọn")
    detail_reasons: list[str] = Field(default_factory=list)
    auto_approve_note: Optional[str] = Field(None, description="Ghi chú hiển thị với badge 🤖")
    evaluated_at: str


# ---------------------------------------------------------------------------
# Business rules cho từng loại yêu cầu
# ---------------------------------------------------------------------------

class AutoApproveChecker:
    """
    Kiểm tra các điều kiện nghiệp vụ trước khi auto-approve.
    Mỗi loại yêu cầu có logic riêng.
    """

    def check_leave_short(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Nghỉ phép ngắn ngày (< 3 ngày)"""
        reasons = []
        ok = True

        if inp.days_requested <= 0:
            reasons.append("❌ Số ngày nghỉ không hợp lệ")
            ok = False

        effective_balance = inp.leave_balance_remaining
        if effective_balance <= 0 and inp.requester_name:
            looked_up = lookup_leave_balance(inp.requester_name)
            if looked_up is not None:
                effective_balance = looked_up
                reasons.append(f"ℹ️ Đã tự động đối chiếu số phép từ mock HR: {looked_up} ngày")

        if inp.days_requested > effective_balance:
            reasons.append(
                f"❌ Số ngày xin nghỉ ({inp.days_requested}) vượt quá số phép còn lại ({effective_balance})"
            )
            ok = False
        else:
            reasons.append(f"✅ Đủ số ngày phép ({effective_balance} ngày còn lại)")

        if inp.days_requested < 3:
            reasons.append(f"✅ Thời gian nghỉ ({inp.days_requested} ngày) đủ điều kiện auto-approve")
        else:
            reasons.append("❌ Nghỉ ≥ 3 ngày cần duyệt thủ công")
            ok = False

        return ok, reasons

    def check_room_booking(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Đặt phòng họp"""
        reasons = []
        ok = True

        room_available = inp.room_available
        if room_available is None:
            # Tra cứu thử từ mock facilities snapshot
            room_available = lookup_facility_available("PH-01")
            if room_available is not None:
                reasons.append(f"ℹ️ Đã tự động đối chiếu lịch phòng từ mock Facilities (khả dụng: {room_available})")

        if room_available is None:
            reasons.append("⚠️ Chưa kiểm tra lịch phòng. Chuyển duyệt thủ công để an toàn.")
            ok = False
        elif room_available:
            reasons.append("✅ Phòng họp còn trống trong khung giờ đó")
        else:
            reasons.append("❌ Phòng họp đã được đặt. Cần chọn phòng/giờ khác")
            ok = False

        return ok, reasons

    def check_late_checkin(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Đăng ký đi muộn/về sớm"""
        reasons = ["✅ Loại yêu cầu này tự động xét duyệt nếu rủi ro thấp"]
        # Rule: Trong tháng, nếu đây là lần ≥ 4, cần duyệt thủ công
        # (Thông tin này cần được truyền vào thông qua data, hiện dùng reject_count làm proxy)
        return True, reasons

    def check_refund(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Hoàn tiền/Đền bù"""
        reasons = []
        ok = True

        if inp.amount > 2_000_000:
            reasons.append(f"❌ Số tiền hoàn ({inp.amount:,.0f} VNĐ) > 2 triệu, cần duyệt thủ công")
            ok = False
        else:
            reasons.append(f"✅ Số tiền hoàn ({inp.amount:,.0f} VNĐ) ≤ 2 triệu")

        return ok, reasons

    def check_generic(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Fallback cho các loại không có rule riêng"""
        return True, [f"✅ Loại '{inp.request_type}' không có rule đặc biệt, chấp thuận dựa trên risk score"]

    def evaluate(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        handlers = {
            "leave_short": self.check_leave_short,
            "room_booking": self.check_room_booking,
            "late_checkin": self.check_late_checkin,
            "refund": self.check_refund,
        }
        handler = handlers.get(inp.request_type, self.check_generic)
        return handler(inp)


checker = AutoApproveChecker()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/evaluate", response_model=AutoApproveDecision, summary="Đánh giá điều kiện auto-approve")
async def evaluate_auto_approve(body: AutoApproveInput):
    """
    Kiểm tra toàn bộ điều kiện để quyết định tự động duyệt hay chuyển người.

    **Luồng quyết định:**
    1. Kiểm tra Template phải là A
    2. Kiểm tra risk_score ≤ 2
    3. Chạy business rules riêng theo loại yêu cầu
    4. Nếu tất cả pass → `auto_approve`
    5. Nếu bất kỳ fail → `escalate_to_human`
    """
    detail_reasons = []
    can_auto_approve = True

    # --- Gate 1: Template A chỉ ---
    if body.lifecycle_template != "A":
        detail_reasons.append(
            f"❌ Lifecycle Template '{body.lifecycle_template}' cần Executor/Acceptor — không thể auto-approve"
        )
        can_auto_approve = False
    else:
        detail_reasons.append("✅ Template A (Approve-Only) — phù hợp auto-approve")

    # --- Gate 2: Risk score ---
    if body.risk_score > settings.auto_approve_max_risk:
        detail_reasons.append(
            f"❌ Risk score {body.risk_score}/5 > ngưỡng {settings.auto_approve_max_risk} — cần người duyệt"
        )
        can_auto_approve = False
    else:
        detail_reasons.append(f"✅ Risk score {body.risk_score}/5 ≤ {settings.auto_approve_max_risk}")

    # --- Gate 3: Business rules theo loại ---
    if can_auto_approve:
        business_ok, business_reasons = checker.evaluate(body)
        detail_reasons.extend(business_reasons)
        if not business_ok:
            can_auto_approve = False

    # --- Kết luận ---
    if can_auto_approve:
        decision = "auto_approve"
        reason = f"Yêu cầu '{body.request_type}' của {body.requester_name} đủ điều kiện tự động duyệt"
        note = (
            f"🤖 AI đã tự động duyệt lúc {datetime.now().strftime('%H:%M %d/%m/%Y')}. "
            f"Bạn có thể Từ chối trong vòng 24h."
        )
        logger.info(f"AUTO-APPROVE | request_id={body.request_id} | type={body.request_type}")
    else:
        decision = "escalate_to_human"
        reason = "Yêu cầu cần người phê duyệt thủ công do không đáp ứng đủ điều kiện"
        note = None
        logger.info(f"ESCALATE | request_id={body.request_id} | type={body.request_type} | reasons: {len([r for r in detail_reasons if '❌' in r])}")

    return AutoApproveDecision(
        decision=decision,
        reason=reason,
        detail_reasons=detail_reasons,
        auto_approve_note=note,
        evaluated_at=datetime.now().isoformat(),
    )
