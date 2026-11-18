"""
Router: Auto-Approve — Quyết định tự động duyệt yêu cầu

POST /ai/auto-approve/evaluate
  - Input: thông tin yêu cầu + risk score đã tính
  - Output: quyết định (auto_approve / escalate_to_human) + lý do

Nguyên tắc (plan.md 2.3):
  ✅ Auto-approve khi: Template A + risk_score ≤ 2 + các rule nghiệp vụ hợp lệ
  ❌ KHÔNG auto-approve khi: Template B/C hoặc risk > 2
"""

from datetime import datetime, timezone

try:
    from config import get_settings
    from nlp_text import canonical_request_type
except (ImportError, AttributeError):
    from ai_service.config import get_settings
    from ai_service.nlp_text import canonical_request_type

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field, field_validator

try:
    import bad_case_reason
    import bad_cases
except ImportError:
    from ai_service import bad_case_reason, bad_cases

from .mock_context import lookup_facility_available, lookup_leave_balance
from .policy import PolicySignals, apply_policy, matched_escalation, policy_citations

settings = get_settings()
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LearnedBadCase(BaseModel):
    code: str = Field(..., pattern=r"^BC_[A-Z0-9_]{2,57}$")
    title: str = Field(..., max_length=200)
    rationale: str = Field("", max_length=2000)
    request_types: list[str] = Field(..., min_length=1, max_length=60)
    condition: dict
    condition_text: str | None = Field(None, max_length=1000)
    risk: int = Field(3, ge=1, le=5)
    escalate_to: str = Field("B", pattern=r"^[BC]$")

    @field_validator("condition")
    @classmethod
    def _valid_condition(cls, value: dict) -> dict:
        return bad_case_reason.validate_condition(value)


class BadCaseOverride(BaseModel):
    disabled: bool = False
    extra_types: list[str] = Field(default_factory=list, max_length=60)


class AutoApproveInput(BaseModel):
    request_id: str = Field(..., description="UUID của yêu cầu")
    request_type: str
    lifecycle_template: str = Field(..., description="A/B/C")
    risk_score: int = Field(..., ge=1, le=5)
    amount: float = Field(0.0, ge=0)
    days_requested: int = Field(0, ge=0)
    leave_balance_remaining: int = Field(0, ge=0)
    room_available: bool | None = Field(
        None, description="Phòng họp còn trống không (cho room_booking)"
    )
    requester_name: str
    requester_dept: str
    requester_email: str | None = Field(
        None, description="Email để tra quỹ phép trong hệ thống HRM"
    )
    room_code: str | None = Field(None, description="Mã phòng họp (ROOM_BOOKING)")
    # Tín hiệu ngữ cảnh do API core tính từ lịch sử trong CSDL (suy luận tình huống xấu).
    active_tasks_due_24h: int = Field(0, ge=0, le=10_000)
    handover_assigned: bool | None = None
    requester_amount_7d: float = Field(0.0, ge=0)
    requester_finance_count_7d: int = Field(0, ge=0, le=10_000)
    attendance_count_30d: int = Field(0, ge=0, le=10_000)
    # Tín hiệu cho luật quy định có điều kiện ngữ cảnh (regulation_compiler v2).
    open_work_due_hours: list[float] = Field(default_factory=list, max_length=200)
    work_due_in_absence: int = Field(0, ge=0, le=10_000)
    same_type_count_7d: int = Field(0, ge=0, le=10_000)
    same_type_count_30d: int = Field(0, ge=0, le=10_000)
    same_type_count_month: int = Field(0, ge=0, le=10_000)
    team_absence_ratio: float = Field(0.0, ge=0, le=1)
    requester_rejected_30d: int = Field(0, ge=0, le=10_000)
    ai_revoked_90d: int = Field(0, ge=0, le=10_000)
    # Tín hiệu cho danh mục tình huống xấu (data/bad_case_catalog.json).
    team_size: int = Field(0, ge=0, le=10_000)
    handover_open_work_in_absence: int = Field(0, ge=0, le=10_000)
    handover_absent: bool = False
    duplicate_invoice_count: int = Field(0, ge=0, le=10_000)
    same_customer_count_7d: int = Field(0, ge=0, le=10_000)
    requester_absent_on_event: bool = False
    off_hours_count_7d: int = Field(0, ge=0, le=10_000)
    uncovered_work: int = Field(0, ge=0, le=10_000)
    handover_named: bool = False
    # Đặc trưng của chính hồ sơ (bad case học từ lý do thu hồi, bad_case_reason.FEATURES).
    notice_hours: float | None = Field(None, ge=-100_000, le=100_000)
    start_day_of_month: int | None = Field(None, ge=1, le=31)
    start_weekday: int | None = Field(None, ge=1, le=7)
    submit_hour: int | None = Field(None, ge=0, le=23)
    # Bảng eas.bad_case (migration 25): bad case học được đang ACTIVE và điều chỉnh danh mục có sẵn.
    learned_bad_cases: list[LearnedBadCase] = Field(default_factory=list, max_length=200)
    bad_case_overrides: dict[str, BadCaseOverride] = Field(default_factory=dict)

    def policy_signals(self) -> PolicySignals:
        return PolicySignals(
            open_work_due_hours=self.open_work_due_hours,
            work_due_in_absence=self.work_due_in_absence,
            handover_assigned=self.handover_assigned,
            same_type_count_7d=self.same_type_count_7d,
            same_type_count_30d=self.same_type_count_30d,
            same_type_count_month=self.same_type_count_month,
            requester_amount_7d=self.requester_amount_7d,
            requester_finance_count_7d=self.requester_finance_count_7d,
        )


class AutoApproveDecision(BaseModel):
    decision: str = Field(..., description="'auto_approve' | 'escalate_to_human'")
    reason: str = Field(..., description="Lý do ngắn gọn")
    detail_reasons: list[str] = Field(default_factory=list)
    auto_approve_note: str | None = Field(
        None, description="Ghi chú hiển thị với badge 🤖"
    )
    evaluated_at: str
    policy_version: str | None = Field(None, description="Bộ luật quy định đã áp dụng")
    citations: list[dict] = Field(
        default_factory=list,
        description="Điều khoản quy chế đã đối chiếu (áp dụng hoặc không) và phép so sánh",
    )
    bad_cases: list[dict] = Field(
        default_factory=list,
        description="Tình huống xấu suy luận được từ ngữ cảnh; có thì không tự duyệt",
    )
    effective_risk: int | None = Field(
        None, description="Mức rủi ro sau khi xét tình huống xấu"
    )
    escalate_to: str | None = Field(
        None,
        description="Luồng nâng cấp cho CHÍNH hồ sơ này (B/C) khi dính tình huống xấu hoặc quy định",
    )
    escalation_causes: list[dict] = Field(
        default_factory=list,
        description="Tình huống xấu / luật quy định dẫn tới nâng luồng",
    )


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
        if effective_balance <= 0 and (inp.requester_email or inp.requester_name):
            looked_up = lookup_leave_balance(inp.requester_email or inp.requester_name)
            if looked_up is not None:
                effective_balance = looked_up
                reasons.append(
                    f"ℹ️ Đã tự động đối chiếu số phép từ mock HR: {looked_up} ngày"
                )

        if inp.days_requested > effective_balance:
            reasons.append(
                f"❌ Số ngày xin nghỉ ({inp.days_requested}) vượt quá số phép còn lại ({effective_balance})"
            )
            ok = False
        else:
            reasons.append(f"✅ Đủ số ngày phép ({effective_balance} ngày còn lại)")

        if inp.days_requested < 3:
            reasons.append(
                f"✅ Thời gian nghỉ ({inp.days_requested} ngày) đủ điều kiện auto-approve"
            )
        else:
            reasons.append("❌ Nghỉ ≥ 3 ngày cần duyệt thủ công")
            ok = False

        return ok, reasons

    def check_room_booking(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Đặt phòng họp"""
        reasons = []
        ok = True

        room_available = inp.room_available
        if room_available is None and inp.room_code:
            # Hệ thống quản lý toà nhà (qua API), đúng phòng của đơn.
            room_available = lookup_facility_available(inp.room_code)
            if room_available is not None:
                reasons.append(
                    f"ℹ️ Đã đối chiếu tình trạng phòng {inp.room_code} với hệ thống toà nhà"
                )

        if room_available is None:
            reasons.append(
                "⚠️ Chưa kiểm tra lịch phòng. Chuyển duyệt thủ công để an toàn."
            )
            ok = False
        elif room_available:
            reasons.append("✅ Phòng họp còn trống trong khung giờ đó")
        else:
            reasons.append("❌ Phòng họp đã được đặt. Cần chọn phòng/giờ khác")
            ok = False

        return ok, reasons

    def check_late_checkin(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Đăng ký đi muộn/về sớm. Lần thứ 4 trong 30 ngày bị chặn ở Gate -1 (BC_REPEATED_EXEMPTION)."""
        return True, [
            (
                f"✅ Điều chỉnh chấm công lần {max(1, inp.attendance_count_30d)} trong 30 ngày, "
                "rủi ro thấp: tự động xét duyệt"
            )
        ]

    def check_refund(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Hoàn tiền/Đền bù"""
        reasons = []
        ok = True

        if inp.amount > 2_000_000:
            reasons.append(
                f"❌ Số tiền hoàn ({inp.amount:,.0f} VNĐ) > 2 triệu, cần duyệt thủ công"
            )
            ok = False
        else:
            reasons.append(f"✅ Số tiền hoàn ({inp.amount:,.0f} VNĐ) ≤ 2 triệu")

        return ok, reasons

    def check_generic(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        """Fallback cho các loại không có rule riêng"""
        return True, [
            f"✅ Loại '{inp.request_type}' không có rule đặc biệt, chấp thuận dựa trên risk score"
        ]

    def evaluate(self, inp: AutoApproveInput) -> tuple[bool, list[str]]:
        # Keyed by catalog v2 code: the API sends catalog codes (LEAVE,
        # ROOM_BOOKING...); legacy names (leave_short, room_booking, refund,
        # late_checkin) are mapped onto them by canonical_request_type.
        handlers = {
            "LEAVE": self.check_leave_short,
            "ROOM_BOOKING": self.check_room_booking,
            "ATTENDANCE_ADJUSTMENT": self.check_late_checkin,
            "REFUND_COMPENSATION": self.check_refund,
        }
        code = canonical_request_type(inp.request_type)
        handler = handlers.get(code, self.check_generic)
        return handler(inp)


checker = AutoApproveChecker()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/evaluate",
    response_model=AutoApproveDecision,
    summary="Đánh giá điều kiện auto-approve",
)
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
    signals = body.policy_signals()

    # --- Gate -1: Suy luận tình huống xấu từ ngữ cảnh vận hành ---
    bad = bad_cases.evaluate(
        bad_cases.Signals.from_input(body),
        learned=[c.model_dump() for c in body.learned_bad_cases],
        overrides={k: v.model_dump() for k, v in body.bad_case_overrides.items()},
    )
    for case in bad.cases:
        detail_reasons.append(f"⛔ [{case['code']}] {case['message']}")
    if bad.blocked:
        can_auto_approve = False

    # --- Gate 0: Quy định đã nạp (đọc lại theo mtime, hiệu lực ngay) ---
    risk_score, forced_manual, matched_rules, policy_version = apply_policy(
        request_type=body.request_type,
        amount=body.amount,
        days=body.days_requested,
        risk=body.risk_score,
        signals=signals,
    )
    _policy_target, policy_causes = matched_escalation(
        request_type=body.request_type,
        amount=body.amount,
        days=body.days_requested,
        signals=signals,
    )
    if matched_rules:
        detail_reasons.append(
            f"ℹ️ Quy định {policy_version} áp dụng luật: {', '.join(matched_rules)}"
        )
    if forced_manual:
        detail_reasons.append("❌ Quy định yêu cầu duyệt thủ công cho trường hợp này")
        can_auto_approve = False

    # --- Gate 1: Template A chỉ ---
    if body.lifecycle_template != "A":
        detail_reasons.append(
            f"❌ Lifecycle Template '{body.lifecycle_template}' cần Executor/Acceptor — không thể auto-approve"
        )
        can_auto_approve = False
    else:
        detail_reasons.append("✅ Template A (Approve-Only) — phù hợp auto-approve")

    # --- Gate 2: Risk score ---
    if risk_score > settings.auto_approve_max_risk:
        detail_reasons.append(
            f"❌ Risk score {risk_score}/5 > ngưỡng {settings.auto_approve_max_risk} — cần người duyệt"
        )
        can_auto_approve = False
    else:
        detail_reasons.append(
            f"✅ Risk score {risk_score}/5 ≤ {settings.auto_approve_max_risk}"
        )

    if bad.effective_risk:
        risk_score = max(risk_score, bad.effective_risk)

    # --- Gate 3: Business rules theo loại ---
    if can_auto_approve:
        business_ok, business_reasons = checker.evaluate(body)
        detail_reasons.extend(business_reasons)
        if not business_ok:
            can_auto_approve = False

    # --- Nâng luồng cho chính hồ sơ (A -> B/C) khi dính tình huống xấu hoặc luật quy định ---
    order = {"A": 0, "B": 1, "C": 2}
    current = order.get(body.lifecycle_template, 0)
    causes = [
        {
            "source": "BAD_CASE",
            "code": c["code"],
            "escalate_to": c.get("escalate_to"),
            "text": c["message"],
            "why": c.get("rationale"),
            "origin": c.get("source"),
        }
        for c in bad.cases
        if c.get("escalate_to")
    ] + [{"source": "REGULATION", "code": c["rule_id"], **c} for c in policy_causes]
    escalate_to = None
    for cause in causes:
        target = cause.get("escalate_to")
        if (
            target in order
            and order[target] > current
            and (escalate_to is None or order[target] > order[escalate_to])
        ):
            escalate_to = target
    if escalate_to:
        can_auto_approve = False
        detail_reasons.append(
            f"⤴️ Chuyển hồ sơ từ quy trình {body.lifecycle_template} sang quy trình {escalate_to} "
            f"({', '.join(c['code'] for c in causes if c.get('escalate_to') == escalate_to)})"
        )

    # --- Kết luận ---
    if can_auto_approve:
        decision = "auto_approve"
        reason = f"Yêu cầu '{body.request_type}' của {body.requester_name} đủ điều kiện tự động duyệt"
        note = (
            f"🤖 AI đã tự động duyệt lúc {datetime.now(timezone.utc).strftime('%H:%M %d/%m/%Y')}. "
            f"Bạn có thể Từ chối trong vòng 24h."
        )
        logger.info(
            f"AUTO-APPROVE | request_id={body.request_id} | type={body.request_type}"
        )
    else:
        decision = "escalate_to_human"
        reason = (
            ("Phát hiện tình huống xấu: " + "; ".join(c["code"] for c in bad.cases))
            if bad.blocked
            else "Yêu cầu cần người phê duyệt thủ công do không đáp ứng đủ điều kiện"
        )
        note = None
        logger.info(
            f"ESCALATE | request_id={body.request_id} | type={body.request_type} | reasons: {len([r for r in detail_reasons if '❌' in r])}"
        )

    return AutoApproveDecision(
        decision=decision,
        reason=reason,
        detail_reasons=detail_reasons,
        auto_approve_note=note,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        policy_version=policy_version,
        citations=policy_citations(
            request_type=body.request_type,
            amount=body.amount,
            days=body.days_requested,
            signals=signals,
        ),
        bad_cases=bad.cases,
        effective_risk=risk_score,
        escalate_to=escalate_to,
        escalation_causes=causes if escalate_to else [],
    )
