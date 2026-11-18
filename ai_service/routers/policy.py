"""
Router: Policy — Nạp quy định nghiệp vụ dạng bộ luật cho AI

POST /ai/policy/rules  — thay toàn bộ bộ luật đang áp dụng (atomic)
GET  /ai/policy/rules  — bộ luật hiện hành

Bộ luật được đọc lại theo mtime ở mỗi lần đánh giá auto-approve, nên có hiệu
lực ngay ở request kế tiếp mà không cần train lại model hay restart service.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

router = APIRouter()

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
POLICY_FILE = os.path.join(DATA_DIR, "active_enterprise_policy.json")

_cache: dict = {"mtime": None, "path": None, "policy": None}


WINDOWS = ("CALENDAR_MONTH", "ROLLING_7D", "ROLLING_30D")


class PolicyRule(BaseModel):
    """Một luật kiểm soát; mọi điều kiện có mặt phải cùng thỏa (AND).

    Ngoài ngưỡng tiền/ngày, luật có thể mang điều kiện NGỮ CẢNH do trình biên dịch v2 tách từ quy
    định (api_core/workflow/regulation_compiler.py). Điều kiện ngữ cảnh được xét trên tín hiệu mà
    API core tính từ CSDL (PolicySignals); thiếu tín hiệu thì điều kiện coi như KHÔNG thỏa.
    """

    id: str = Field(..., min_length=1, max_length=50)
    description: str = Field("", max_length=500)
    request_type: str | None = Field(None, max_length=60)
    amount_gt: float | None = Field(None, ge=0)
    days_gt: int | None = Field(None, ge=0)
    due_within_hours: int | None = Field(None, ge=1, le=24 * 31)
    require_no_handover: bool | None = None
    repeat_count_gte: int | None = Field(None, ge=1, le=1000)
    repeat_window: str | None = None
    split_suspect: bool | None = None
    split_total_gt: float | None = Field(None, ge=0)
    min_risk: int | None = Field(None, ge=1, le=5)
    auto_approve: bool | None = None
    escalate_to: str | None = None
    approvers: list[str] | None = Field(None, max_length=6)
    # Luật áp cho mọi loại nhưng đã bị quy định mới thay thế ở vài loại (api_core regulation_precedence).
    except_types: list[str] = Field(default_factory=list, max_length=60)
    source_code: str | None = Field(None, max_length=30)

    @model_validator(mode="after")
    def has_effect(self):
        if self.min_risk is None and self.auto_approve is None:
            raise ValueError("rule needs min_risk or auto_approve")
        if self.repeat_window is not None and self.repeat_window not in WINDOWS:
            raise ValueError(
                "repeat_window must be CALENDAR_MONTH, ROLLING_7D or ROLLING_30D"
            )
        if self.escalate_to is not None and self.escalate_to not in ("B", "C"):
            raise ValueError("escalate_to must be B or C")
        if self.auto_approve is True and (
            self.due_within_hours or self.repeat_count_gte or self.split_suspect
        ):
            raise ValueError("contextual conditions can only restrict auto approval")
        return self


class PolicySignals(BaseModel):
    """Tín hiệu ngữ cảnh do API core tính từ CSDL (chỉ số đếm, tổng, khoảng giờ)."""

    open_work_due_hours: list[float] = Field(default_factory=list, max_length=200)
    work_due_in_absence: int = Field(0, ge=0)
    handover_assigned: bool | None = None
    same_type_count_7d: int = Field(0, ge=0)
    same_type_count_30d: int = Field(0, ge=0)
    same_type_count_month: int = Field(0, ge=0)
    requester_amount_7d: float = Field(0.0, ge=0)
    requester_finance_count_7d: int = Field(0, ge=0)


class PolicyDocument(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    rules: list[PolicyRule] = Field(default_factory=list, max_length=200)


class PolicyState(PolicyDocument):
    loaded_at: str | None = None


_PULL_RETRY_SECONDS = 60
_last_pull = {"at": 0.0}


def pull_active_policy(path: str | None = None) -> PolicyState | None:
    """Fill an empty cache from the API (eas.ai_policy_version is the source)."""
    import time

    if time.monotonic() - _last_pull["at"] < _PULL_RETRY_SECONDS:
        return None
    _last_pull["at"] = time.monotonic()
    try:
        import httpx

        try:
            from config import get_settings
        except (ImportError, AttributeError):
            from ai_service.config import get_settings
        settings = get_settings()
        response = httpx.get(
            f"{settings.eas_api_internal_url.rstrip('/')}/api/v1/internal/ai-policy/active",
            headers={"X-Internal-Secret": settings.internal_api_secret},
            timeout=3.0,
        )
        if response.status_code != 200:
            return None
        return save_policy(PolicyDocument.model_validate(response.json()), path)
    except Exception:  # noqa: BLE001 - no policy cache keeps the model defaults
        return None


def load_policy(path: str | None = None) -> PolicyState | None:
    path = path or POLICY_FILE
    try:
        mtime = os.stat(path).st_mtime_ns
    except FileNotFoundError:
        return pull_active_policy(path)
    if _cache["path"] == path and _cache["mtime"] == mtime:
        return _cache["policy"]
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    try:
        policy = PolicyState.model_validate(raw)
    except ValueError:
        policy = None  # legacy free-text policy files carry no rules
    _cache.update(mtime=mtime, path=path, policy=policy)
    return policy


def save_policy(document: PolicyDocument, path: str | None = None) -> PolicyState:
    path = path or POLICY_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    state = PolicyState(
        **document.model_dump(), loaded_at=datetime.now(timezone.utc).isoformat()
    )
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(state.model_dump(), handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return state


_WINDOW_FIELD = {
    "CALENDAR_MONTH": "same_type_count_month",
    "ROLLING_7D": "same_type_count_7d",
    "ROLLING_30D": "same_type_count_30d",
}
_WINDOW_TEXT = {
    "CALENDAR_MONTH": "trong tháng",
    "ROLLING_7D": "trong 7 ngày",
    "ROLLING_30D": "trong 30 ngày",
}


def _checks(
    rule: PolicyRule, amount: float, days: int, sig: PolicySignals
) -> list[tuple[bool, str]]:
    """(thỏa?, giải thích) cho từng điều kiện của luật."""
    out: list[tuple[bool, str]] = []
    if rule.amount_gt is not None:
        out.append(_amount_check(amount, rule.amount_gt))
    if rule.days_gt is not None:
        out.append(_days_check(days, rule.days_gt))
    if rule.due_within_hours:
        n = rule.due_within_hours
        due = [h for h in sig.open_work_due_hours if h <= n]
        hit = bool(due) or sig.work_due_in_absence > 0
        if hit:
            text = f"Đang giữ {len(due)} việc đến hạn trong {n} giờ"
            if sig.work_due_in_absence:
                text += f", {sig.work_due_in_absence} việc đến hạn trong thời gian vắng"
        else:
            text = f"Không giữ việc nào đến hạn trong {n} giờ hay trong thời gian vắng"
        out.append((hit, text))
        if rule.require_no_handover:
            free = not sig.handover_assigned
            out.append(
                (
                    free,
                    "Chưa chỉ định người nhận bàn giao"
                    if free
                    else "Đã có người nhận bàn giao",
                )
            )
    if rule.repeat_count_gte:
        window = rule.repeat_window or "ROLLING_30D"
        count = getattr(sig, _WINDOW_FIELD[window])
        hit = count >= rule.repeat_count_gte
        sign = "≥" if hit else "<"
        out.append(
            (
                hit,
                f"Đây là lần thứ {count} {_WINDOW_TEXT[window]} ({sign} {rule.repeat_count_gte})",
            )
        )
    if rule.split_suspect:
        total_gt = rule.split_total_gt or 20_000_000
        over = sig.requester_amount_7d > total_gt
        hit = sig.requester_finance_count_7d >= 2 and over and amount <= total_gt
        text = (
            f"{sig.requester_finance_count_7d} hồ sơ tài chính trong 7 ngày, tổng "
            f"{_vnd(sig.requester_amount_7d)} {'>' if over else '≤'} {_vnd(total_gt)}, "
            f"hồ sơ này {_vnd(amount)}"
        )
        out.append((hit, text + (": dấu hiệu chia nhỏ" if hit else "")))
    return out


def covers(rule: PolicyRule, request_type: str) -> bool:
    """Luật có áp cho loại yêu cầu này không (đúng loại hoặc mọi loại, trừ loại đã bị quy định mới thay thế)."""
    if rule.request_type and rule.request_type != request_type:
        return False
    return request_type not in rule.except_types


def rule_applies(
    rule: PolicyRule,
    request_type: str,
    amount: float,
    days: int,
    sig: PolicySignals | None,
) -> bool:
    if not covers(rule, request_type):
        return False
    return all(
        hit for hit, _text in _checks(rule, amount, days, sig or PolicySignals())
    )


def apply_policy(
    *,
    request_type: str,
    amount: float,
    days: int,
    risk: int,
    path: str | None = None,
    signals: PolicySignals | None = None,
) -> tuple[int, bool, list[str], str | None]:
    """Return (effective risk, manual review forced, matched rule ids, version)."""
    policy = load_policy(path)
    if policy is None:
        return risk, False, [], None
    forced_manual = False
    matched = []
    for rule in policy.rules:
        if not rule_applies(rule, request_type, amount, days, signals):
            continue
        matched.append(rule.id)
        if rule.min_risk is not None:
            risk = max(risk, rule.min_risk)
        if rule.auto_approve is False:
            forced_manual = True
    return risk, forced_manual, matched, policy.version


def matched_escalation(
    *,
    request_type: str,
    amount: float,
    days: int,
    path: str | None = None,
    signals: PolicySignals | None = None,
) -> tuple[str | None, list[dict]]:
    """Luồng nâng cấp cao nhất (B/C) theo các luật đang thỏa, kèm luật gây ra."""
    policy = load_policy(path)
    if policy is None:
        return None, []
    order = {"B": 1, "C": 2}
    target, causes = None, []
    for rule in policy.rules:
        if not rule.escalate_to or not rule_applies(
            rule, request_type, amount, days, signals
        ):
            continue
        causes.append(
            {
                "rule_id": rule.id,
                "escalate_to": rule.escalate_to,
                "text": rule.description,
                "approvers": rule.approvers or [],
                "policy_version": policy.version,
            }
        )
        if target is None or order[rule.escalate_to] > order[target]:
            target = rule.escalate_to
    return target, causes


def _vnd(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".") + " VNĐ"


def _amount_check(amount: float, threshold: float) -> tuple[bool, str]:
    hit = amount > threshold
    # "từ 30 triệu trở lên" is compiled as > 29,999,999: show it as written.
    if (threshold + 1) % 1_000_000 == 0:
        return (
            hit,
            f"Số tiền {_vnd(amount)} {'≥' if hit else '<'} ngưỡng {_vnd(threshold + 1)}",
        )
    return hit, f"Số tiền {_vnd(amount)} {'>' if hit else '≤'} ngưỡng {_vnd(threshold)}"


def _days_check(days: int, threshold: int) -> tuple[bool, str]:
    hit = days > threshold
    return hit, f"Số ngày {days} {'>' if hit else '≤'} ngưỡng {threshold} ngày"


def _effect(rule: PolicyRule) -> str:
    if rule.auto_approve is False and rule.escalate_to:
        return f"Không tự duyệt; chuyển hồ sơ sang quy trình {rule.escalate_to} có người kiểm duyệt"
    if rule.auto_approve is False:
        return "Bắt buộc người có thẩm quyền duyệt thủ công"
    if rule.auto_approve:
        return "Cho phép tự động duyệt"
    return f"Nâng mức rủi ro tối thiểu lên {rule.min_risk}/5"


def _citation(
    rule: PolicyRule,
    version: str,
    amount: float,
    days: int,
    signals: PolicySignals | None = None,
) -> dict:
    results = _checks(rule, amount, days, signals or PolicySignals())
    checks = [text for _hit, text in results]
    if rule.request_type:
        checks.append("Áp dụng riêng cho loại yêu cầu này")
    return {
        "rule_id": rule.id,
        "text": rule.description,
        "applies": all(hit for hit, _text in results),
        "checks": checks,
        "effect": _effect(rule),
        "policy_version": version,
    }


def policy_citations(
    *,
    request_type: str,
    amount: float,
    days: int,
    path: str | None = None,
    signals: PolicySignals | None = None,
) -> list[dict]:
    """Every rule that concerns this request type, with the comparison made.

    Lets an approver see which company regulation clause the advice was checked
    against, including clauses that did not apply and why.
    """
    policy = load_policy(path)
    if policy is None:
        return []
    citations = [
        _citation(rule, policy.version, amount, days, signals)
        for rule in policy.rules
        if covers(rule, request_type)
    ]
    citations.sort(key=lambda c: not c["applies"])
    return citations


@router.post("/rules", response_model=PolicyState, summary="Nạp bộ luật quy định")
async def publish_rules(body: PolicyDocument):
    return save_policy(body)


@router.get("/rules", response_model=PolicyState | None, summary="Bộ luật hiện hành")
async def current_rules():
    return load_policy()
