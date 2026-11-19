"""
Router: Policy — Nạp quy định nghiệp vụ dạng bộ luật cho AI

POST /ai/policy/rules  — thay toàn bộ bộ luật đang áp dụng (atomic)
GET  /ai/policy/rules  — bộ luật hiện hành

Bộ luật được đọc lại theo mtime ở mỗi lần đánh giá auto-approve, nên có hiệu
lực ngay ở request kế tiếp mà không cần train lại model hay restart service.
"""

import json
import os
import re
import tempfile
import unicodedata
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

router = APIRouter()

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
POLICY_FILE = os.path.join(DATA_DIR, "active_enterprise_policy.json")

_cache: dict = {"mtime": None, "path": None, "policy": None}


WINDOWS = ("CALENDAR_MONTH", "ROLLING_7D", "ROLLING_30D", "CALENDAR_QUARTER", "CALENDAR_YEAR")
WINDOW_RE = re.compile(r"^(?:CALENDAR_(?:MONTH|QUARTER|YEAR)|ROLLING_(?:[1-9]\d{0,2})D)$")
DATE_RE = r"^\d{4}-\d{2}-\d{2}$"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# Khóa điều kiện được phép trong một vùng loại trừ (vùng đã bị quy định mới hơn thay thế).
EXCLUDE_KEYS = {
    "request_type", "amount_gt", "amount_lte", "days_gt", "days_lte", "percent_gt", "percent_lte",
    "location_contains", "due_within_hours", "require_no_handover", "repeat_count_gte", "repeat_window",
    "split_suspect", "split_total_gt", "retro_days_gt", "effective_from", "effective_until",
}


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
    # v3: cận trên, phần trăm, địa điểm, ngày đã quá N ngày, ngày hiệu lực.
    amount_lte: float | None = Field(None, ge=0)
    days_lte: int | None = Field(None, ge=0)
    percent_gt: float | None = Field(None, ge=0, le=100)
    percent_lte: float | None = Field(None, ge=0, le=100)
    location_contains: str | None = Field(None, min_length=1, max_length=120)
    retro_days_gt: int | None = Field(None, ge=0, le=3660)
    effective_from: str | None = Field(None, pattern=DATE_RE)
    effective_until: str | None = Field(None, pattern=DATE_RE)
    # Vùng đã bị quy định mới hơn thay thế: luật KHÔNG áp khi hồ sơ thỏa một vùng loại trừ.
    exclude: list[dict] = Field(default_factory=list, max_length=20)
    # Luật áp cho mọi loại nhưng đã bị quy định mới thay thế ở vài loại (api_core regulation_precedence).
    except_types: list[str] = Field(default_factory=list, max_length=60)
    source_code: str | None = Field(None, max_length=30)

    @model_validator(mode="after")
    def has_effect(self):
        if self.min_risk is None and self.auto_approve is None:
            raise ValueError("rule needs min_risk or auto_approve")
        if self.repeat_window is not None and not WINDOW_RE.match(self.repeat_window):
            raise ValueError(
                "repeat_window must be CALENDAR_MONTH/QUARTER/YEAR or ROLLING_<N>D"
            )
        for zone in self.exclude:
            if not isinstance(zone, dict) or not zone or set(zone) - EXCLUDE_KEYS:
                raise ValueError("exclude zones may only use condition keys")
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
    # v3
    percent: float | None = Field(None, ge=0, le=100)
    location_text: str = Field("", max_length=600)
    notice_hours: float | None = None
    same_type_dates: list[str] = Field(default_factory=list, max_length=500)  # hồ sơ cùng loại TRƯỚC đây
    today: str | None = Field(None, pattern=DATE_RE)  # mặc định: hôm nay giờ Việt Nam (để kiểm thử)


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
    "CALENDAR_QUARTER": "trong quý",
    "CALENDAR_YEAR": "trong năm",
}


def _today(sig: PolicySignals) -> date:
    return date.fromisoformat(sig.today) if sig.today else datetime.now(TZ).date()


def _fold(text: str) -> str:
    low = unicodedata.normalize("NFC", text or "").lower().replace("đ", "d")
    plain = "".join(c for c in unicodedata.normalize("NFD", low) if unicodedata.category(c) != "Mn")
    return " ".join(plain.split())


def _window_count(window: str, sig: PolicySignals) -> int:
    """Số hồ sơ cùng loại trong cửa sổ, KỂ CẢ hồ sơ này."""
    if window in _WINDOW_FIELD:
        return getattr(sig, _WINDOW_FIELD[window])
    today = _today(sig)
    dates = []
    for raw in sig.same_type_dates:
        try:
            dates.append(date.fromisoformat(str(raw)[:10]))
        except ValueError:
            continue
    if window == "CALENDAR_QUARTER":
        q = (today.month - 1) // 3
        hits = [d for d in dates if d.year == today.year and (d.month - 1) // 3 == q]
    elif window == "CALENDAR_YEAR":
        hits = [d for d in dates if d.year == today.year]
    else:
        n = int(window[len("ROLLING_"):-1])
        hits = [d for d in dates if today - timedelta(days=n) < d <= today]
    return len(hits) + 1


def _window_text(window: str) -> str:
    return _WINDOW_TEXT.get(window) or f"trong {window[len('ROLLING_'):-1]} ngày"


from contextvars import ContextVar

_current_type: ContextVar[str] = ContextVar("policy_request_type", default="")


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
        count = _window_count(window, sig)
        hit = count >= rule.repeat_count_gte
        sign = "≥" if hit else "<"
        out.append(
            (
                hit,
                f"Đây là lần thứ {count} {_window_text(window)} ({sign} {rule.repeat_count_gte})",
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
    if rule.amount_lte is not None:
        hit = amount <= rule.amount_lte
        out.append((hit, f"Số tiền {_vnd(amount)} {'≤' if hit else '>'} {_vnd(rule.amount_lte)}"))
    if rule.days_lte is not None:
        hit = days <= rule.days_lte
        out.append((hit, f"Số ngày {days} {'≤' if hit else '>'} {rule.days_lte} ngày"))
    for key, cmp in (("percent_gt", lambda v, r: v > r), ("percent_lte", lambda v, r: v <= r)):
        ref = getattr(rule, key)
        if ref is None:
            continue
        if sig.percent is None:
            out.append((False, "Hồ sơ không có tỉ lệ phần trăm"))
        else:
            hit = cmp(sig.percent, ref)
            word = (">" if hit else "≤") if key == "percent_gt" else ("≤" if hit else ">")
            out.append((hit, f"Tỉ lệ {sig.percent:g}% {word} {ref:g}%"))
    if rule.location_contains:
        hit = _fold(rule.location_contains) in _fold(sig.location_text)
        out.append((hit, f"Địa điểm {'thuộc' if hit else 'không thuộc'} “{rule.location_contains}”"))
    if rule.retro_days_gt is not None:
        if sig.notice_hours is None:
            out.append((False, "Không xác định được ngày của hồ sơ"))
        else:
            retro = -sig.notice_hours / 24
            hit = retro > rule.retro_days_gt
            text = f"Ngày của hồ sơ cách lúc gửi {max(retro, 0):.0f} ngày ({'>' if hit else '≤'} {rule.retro_days_gt})"
            out.append((hit, text))
    today = _today(sig)
    if rule.effective_from:
        hit = today >= date.fromisoformat(rule.effective_from)
        out.append((hit, f"Hiệu lực từ {rule.effective_from}" + ("" if hit else " (chưa tới ngày)")))
    if rule.effective_until:
        hit = today <= date.fromisoformat(rule.effective_until)
        out.append((hit, f"Hiệu lực đến {rule.effective_until}" + ("" if hit else " (đã hết hiệu lực)")))
    for zone in rule.exclude:
        try:
            probe = PolicyRule(id="exclude", auto_approve=False, **zone)
        except ValueError:
            continue
        inside = covers(probe, _current_type.get()) if probe.request_type else True
        if inside and all(h for h, _t in _checks(probe, amount, days, sig)):
            out.append((False, "Thuộc vùng đã được quy định mới hơn thay thế"))
            break
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
    token = _current_type.set(request_type)
    try:
        return all(
            hit for hit, _text in _checks(rule, amount, days, sig or PolicySignals())
        )
    finally:
        _current_type.reset(token)


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
