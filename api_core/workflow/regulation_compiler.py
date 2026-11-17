"""Biên dịch văn bản quy định tiếng Việt thành luật kiểm soát có ĐIỀU KIỆN NGỮ CẢNH (v2).

Module thuần (không phụ thuộc Django) để API core, worker học quy định và script đánh giá
(`ai_service/training/eval_regulation_compiler.py`) dùng chung một cài đặt.

Mỗi câu có tín hiệu kiểm soát (bắt buộc duyệt thủ công hoặc cho phép tự duyệt) được tách thành
một hoặc nhiều luật. Một luật gồm phạm vi (loại yêu cầu hoặc mọi yêu cầu) và các điều kiện cùng
thỏa (AND):

  amount_gt            số tiền của hồ sơ > ngưỡng ("từ X trở lên" -> X-1)
  days_gt              thời lượng của chính đơn (ngày nghỉ, ngày WFH) > ngưỡng
  due_within_hours     người gửi đang giữ việc đến hạn trong N giờ (hoặc trong thời gian vắng)
  require_no_handover  ... và chưa chỉ định người nhận bàn giao
  repeat_count_gte     đây là lần thứ K trở lên của cùng loại, trong cửa sổ repeat_window
  split_suspect        có dấu hiệu chia nhỏ hồ sơ tài chính để né ngưỡng (split_total_gt)

"X hoặc Y" giữa hai nhóm điều kiện sinh hai luật. Điều kiện nằm ngoài schema (phần trăm, khu vực,
ngày hồi tố, cận trên "dưới X") làm câu bị bỏ qua thay vì sinh một luật chặn cả loại.

Kết quả của luật: auto_approve (False = bắt buộc người duyệt), min_risk, escalate_to (luồng
nâng cấp B/C cho hồ sơ, chỉ đặt khi nghiêm ngặt hơn luồng hiện tại) và approvers (cấp kiểm soát
được nêu tên, để giải thích).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

ORDER = {"A": 0, "B": 1, "C": 2}
DEFAULT_SPLIT_TOTAL_GT = 20_000_000
WINDOWS = ("CALENDAR_MONTH", "ROLLING_7D", "ROLLING_30D")
CONTEXT_KEYS = (
    "due_within_hours",
    "require_no_handover",
    "repeat_count_gte",
    "split_suspect",
)


@dataclass(frozen=True)
class RequestTypeName:
    code: str
    name: str
    lifecycle: str | None = None


def fold(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower()


# --------------------------------------------------------------------------- tín hiệu kiểm soát
_MANUAL_STRONG = ("ban giám đốc", "hội đồng")
_MANUAL = (
    "bắt buộc",
    "duyệt thủ công",
    "phê duyệt thủ công",
    "không được tự động",
    "không tự động",
    "không áp dụng tự động",
    "phải được phê duyệt",
    "phải qua",
    "phải trình",
    "phải chuyển",
    "rủi ro cao",
) + _MANUAL_STRONG
_MANUAL_RE = re.compile(
    r"phải\s+(?:được|do|có|trình|qua|chuyển)\b[^.;]{0,80}?\b(?:phê duyệt|duyệt|xét duyệt|xem xét|thẩm định|xác minh)"
)
_AUTO = ("tự động duyệt", "tự động phê duyệt", "duyệt tự động", "đối chiếu tự động")
_EVERY = (
    "mọi yêu cầu",
    "tất cả yêu cầu",
    "toàn bộ yêu cầu",
    "mọi đề xuất",
    "tất cả đề xuất",
    "mọi hồ sơ",
)

# --------------------------------------------------------------------------- số lượng
_MONEY = re.compile(
    r"(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>tỷ|ty|triệu|trieu|nghìn|nghin|ngàn|vnđ|vnd|đồng|dong|đ)(?![\wà-ỹ])",
)
_DAYS = re.compile(r"(?P<num>\d+)\s*ngày")
_UPPER = r"(?:dưới|không quá|tối đa|nhỏ hơn|thấp hơn|ít hơn)\s*$"
_LOWER_INCL = r"(?:từ|tối thiểu|ít nhất|bằng hoặc lớn hơn)\s*$"
_LOWER_EXCL = r"(?:trên|vượt|vượt quá|quá|lớn hơn|cao hơn|hơn)\s*$"

# --------------------------------------------------------------------------- điều kiện ngữ cảnh
_DEADLINE = re.compile(
    r"(?:hạn chót|đến hạn|hết hạn|deadline|hạn hoàn thành)[^.;]{0,30}?"
    r"(?:trong(?: vòng)?|dưới|còn)\s*(?P<num>\d+)\s*(?P<unit>giờ|tiếng|h|ngày)\b(?:\s*tới)?"
)
_NO_HANDOVER = re.compile(
    r"chưa\s+(?:bàn giao|chỉ định người nhận bàn giao|có người nhận bàn giao)"
)
_VI_ORD = {"hai": 2, "ba": 3, "tư": 4, "bốn": 4, "năm": 5, "sáu": 6}
_REPEAT_NTH = re.compile(
    r"lần\b[^.;]{0,45}?\bthứ\s*(?P<num>\d+|hai|ba|tư|bốn|năm|sáu)\b"
)
_REPEAT_OVER = re.compile(r"(?:quá|vượt quá|nhiều hơn)\s*(?P<num>\d+)\s*lần")
_REPEAT_ATLEAST = re.compile(r"(?P<num>\d+)\s*lần\s*trở lên")
_WINDOW = re.compile(
    r"trong\s+(?:(?:một|1|cùng)\s+)?(?P<w>tháng|tuần)\b|trong\s+(?P<n>\d+)\s*ngày(?:\s*gần nhất|\s*liên tiếp)?"
)
_SPLIT = re.compile(r"chia nhỏ|tách nhỏ|tách thành nhiều")

# --------------------------------------------------------------------------- điều kiện ngoài schema
_UNSUPPORTED = (
    re.compile(r"\d+(?:[.,]\d+)?\s*%"),
    re.compile(r"khu vực|tầng|phòng máy|vùng"),
    re.compile(
        r"(?:ngày|hồ sơ)\s+đã\s+quá|hồi tố|cho ngày\s+\S+\s+đã|quá\s+\d+\s*ngày\s+(?:kể từ|sau|trước)"
    ),
)
# "khi"/"nếu" mở một mệnh đề điều kiện; "sau khi", "trước khi", "kể từ khi" chỉ là mốc thời gian.
_COND_INTRO = re.compile(
    r"(?<!sau )(?<!trước )(?<!từ )\b(?:khi|nếu)\b(?P<body>[^,.;]*)"
)

_APPROVERS = (
    (re.compile(r"trưởng bộ phận|quản lý trực tiếp|trưởng phòng"), "DIRECT_MANAGER"),
    (
        re.compile(
            r"(?:phòng|bộ phận|ban)\s+nhân sự|nhân sự\s+(?:phê duyệt|xét duyệt|xác minh|đối soát|xem xét|kiểm tra)"
            r"|(?:và|cùng|qua|chuyển)\s+(?:phòng\s+)?nhân sự|\bhr\b"
        ),
        "HR_MANAGER",
    ),
    (re.compile(r"kế toán|tài chính"), "FINANCE"),
    (re.compile(r"giám đốc"), "DIRECTOR"),
    (re.compile(r"pháp chế"), "LEGAL"),
    (re.compile(r"bảo mật"), "SECURITY"),
)

_SENTENCE = re.compile(r"(?<=[.;!?])\s+|\n+")
_ARTICLE_HEADER = re.compile(r"^\s*điều\s+\d+[a-z]?\s*(?:\([^)]*\))?\s*[:.\-–]?\s*")


@dataclass
class _Span:
    start: int
    end: int
    kind: str
    value: Any = None


@dataclass
class _Parsed:
    spans: list[_Span] = field(default_factory=list)

    def add(self, start: int, end: int, kind: str, value: Any = None) -> None:
        self.spans.append(_Span(start, end, kind, value))


def _money_value(num: str, unit: str) -> int | None:
    if unit in {"tỷ", "ty", "triệu", "trieu", "nghìn", "nghin", "ngàn"}:
        try:
            value = float(num.replace(",", "."))
        except ValueError:
            return None
        scale = {"tỷ": 1e9, "ty": 1e9, "triệu": 1e6, "trieu": 1e6}.get(unit, 1e3)
        return round(value * scale)
    digits = re.sub(r"[.,]", "", num)
    return int(digits) if digits.isdigit() else None


def _bound(text: str, start: int, end: int, value: int) -> tuple[str, int | None]:
    """('lower', gt) | ('upper', None) | ('none', None) for the number at [start:end]."""
    before = text[max(0, start - 25) : start]
    after = text[end : end + 15]
    if re.search(_UPPER, before):
        return "upper", None
    if re.search(_LOWER_INCL, before) or re.match(r"\s*trở lên", after):
        return "lower", max(value - 1, 0)
    if re.search(_LOWER_EXCL, before):
        return "lower", value
    return "none", None


def _mask(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def _scope(low: str, types: list[RequestTypeName]) -> tuple[list[RequestTypeName], str]:
    """Types named in the sentence (longest name first, masked so it cannot match twice)."""
    found: list[tuple[int, RequestTypeName]] = []
    masked = low
    for t in sorted(types, key=lambda x: -len(x.name or "")):
        name = fold(t.name)
        if not name:
            continue
        pos = masked.find(name)
        if pos < 0:
            continue
        found.append((pos, t))
        masked = _mask(
            masked, [(m.start(), m.end()) for m in re.finditer(re.escape(name), masked)]
        )
    found.sort(key=lambda item: item[0])
    return [t for _pos, t in found], masked


def _parse(low: str) -> tuple[_Parsed, bool]:
    """Find every quantity / context condition. Returns (parsed, unsupported)."""
    p = _Parsed()
    taken: list[tuple[int, int]] = []

    for m in _DEADLINE.finditer(low):
        num = int(m.group("num"))
        hours = num * 24 if m.group("unit") == "ngày" else num
        p.add(m.start(), m.end(), "due_within_hours", hours)
        taken.append((m.start(), m.end()))
    for m in _NO_HANDOVER.finditer(low):
        p.add(m.start(), m.end(), "require_no_handover", True)

    repeat = None
    for regex, plus in ((_REPEAT_NTH, 0), (_REPEAT_OVER, 1), (_REPEAT_ATLEAST, 0)):
        m = regex.search(low)
        if m:
            raw = m.group("num")
            count = int(raw) if raw.isdigit() else _VI_ORD[raw]
            repeat = (m.start(), m.end(), count + plus)
            break
    if repeat:
        window = None
        for w in _WINDOW.finditer(low):
            if w.start() < repeat[0] - 60:
                continue
            if w.group("w") == "tháng":
                window = "CALENDAR_MONTH"
            elif w.group("w") == "tuần" or w.group("n") in {"7"}:
                window = "ROLLING_7D"
            elif w.group("n") in {"30"}:
                window = "ROLLING_30D"
            else:
                return p, True  # cửa sổ thời gian khác: ngoài schema
            taken.append((w.start(), w.end()))
            break
        p.add(
            repeat[0],
            repeat[1],
            "repeat_count_gte",
            (repeat[2], window or "ROLLING_30D"),
        )
        taken.append((repeat[0], repeat[1]))

    for m in _SPLIT.finditer(low):
        p.add(m.start(), m.end(), "split_suspect", True)

    scan = _mask(low, taken)
    for m in _MONEY.finditer(scan):
        value = _money_value(m.group("num"), m.group("unit"))
        if value is None:
            continue
        kind, gt = _bound(scan, m.start(), m.end(), value)
        if kind == "upper":
            return p, True
        if kind == "lower":
            p.add(m.start(), m.end(), "amount_gt", gt)
    money_spans = [(s.start, s.end) for s in p.spans if s.kind == "amount_gt"]
    scan = _mask(scan, money_spans)
    for m in _DAYS.finditer(scan):
        value = int(m.group("num"))
        kind, gt = _bound(scan, m.start(), m.end(), value)
        if kind == "upper":
            return p, True
        if kind == "lower":
            p.add(m.start(), m.end(), "days_gt", gt)
    return p, False


def _unsupported_condition(low: str, parsed: _Parsed) -> bool:
    if any(rx.search(low) for rx in _UNSUPPORTED):
        return True
    for m in _COND_INTRO.finditer(low):
        start, end = m.start("body"), m.end("body")
        if not any(start <= s.start < end + 80 for s in parsed.spans):
            return True
    return False


def _groups(low: str, parsed: _Parsed) -> list[dict[str, Any]]:
    """Split the conditions into OR-alternatives at 'hoặc' between two conditions."""
    spans = sorted(parsed.spans, key=lambda s: s.start)
    if not spans:
        return [{}]
    groups: list[list[_Span]] = [[spans[0]]]
    for prev, cur in pairwise(spans):
        between = low[prev.end : cur.start]
        if re.search(r"\bhoặc\b", between) and not re.search(r"\bvà\b", between):
            groups.append([cur])
        else:
            groups[-1].append(cur)
    out = []
    for group in groups:
        cond: dict[str, Any] = {}
        for s in group:
            if s.kind == "repeat_count_gte":
                cond["repeat_count_gte"], cond["repeat_window"] = s.value
            else:
                cond.setdefault(s.kind, s.value)
        out.append(cond)
    # 'chưa bàn giao' only qualifies a deadline condition.
    for cond in out:
        if cond.get("require_no_handover") and "due_within_hours" not in cond:
            cond.pop("require_no_handover")
    return [c for c in out if c] or [{}]


def _approvers(low: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for rx, code in _APPROVERS:
        m = rx.search(low)
        if m:
            found.append((m.start(), code))
    seen: list[str] = []
    for _pos, code in sorted(found):
        if code not in seen:
            seen.append(code)
    return seen


def _escalate(lifecycle: str | None, low: str, cond: dict[str, Any]) -> str | None:
    current = ORDER.get((lifecycle or "A").upper(), 0)
    if "nghiệm thu" in low and current < ORDER["C"]:
        return "C"
    if any(k in cond for k in CONTEXT_KEYS) and current < ORDER["B"]:
        return "B"
    return None


def compile_sentence(
    sentence: str, types: list[RequestTypeName]
) -> list[dict[str, Any]]:
    """Rules (without id) for one sentence; [] when it carries no enforceable control."""
    low = _ARTICLE_HEADER.sub("", fold(sentence), count=1)
    manual = any(word in low for word in _MANUAL) or bool(_MANUAL_RE.search(low))
    auto = not manual and any(word in low for word in _AUTO)
    if not (manual or auto):
        return []
    scoped, masked = _scope(low, types)
    parsed, unsupported = _parse(masked)
    if unsupported or _unsupported_condition(masked, parsed):
        return []
    groups = _groups(masked, parsed)
    sentence_amount = next(
        (sp.value for sp in parsed.spans if sp.kind == "amount_gt"), None
    )
    unconstrained = all(not g for g in groups)
    if unconstrained and not scoped and not any(word in low for word in _EVERY):
        return []
    approvers = _approvers(masked)
    strong = any(word in low for word in _MANUAL_STRONG)
    rules: list[dict[str, Any]] = []
    for t in scoped or [None]:
        for cond in groups:
            if auto and any(k in cond for k in CONTEXT_KEYS):
                continue  # 'được tự duyệt khi ...' with context: never widen auto approval
            rule: dict[str, Any] = {"request_type": t.code if t else None, **cond}
            if cond.get("split_suspect"):
                # Ngưỡng tiền đi cùng dấu hiệu chia nhỏ là ngưỡng TỔNG bị né, không phải tiền của hồ sơ.
                rule["split_total_gt"] = (
                    rule.pop("amount_gt", None)
                    or sentence_amount
                    or DEFAULT_SPLIT_TOTAL_GT
                )
            if manual:
                contextual = any(
                    k in cond for k in ("due_within_hours", "split_suspect")
                )
                rule["min_risk"] = 5 if strong or contextual else 4
                rule["auto_approve"] = False
                escalate = _escalate(t.lifecycle if t else None, low, cond)
                if escalate:
                    rule["escalate_to"] = escalate
                if approvers:
                    rule["approvers"] = approvers
            else:
                rule["auto_approve"] = True
            rules.append(rule)
    return rules


def compile_text(
    code: str, content: str, types: list[RequestTypeName]
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    sentences = [s.strip() for s in _SENTENCE.split(content or "")]
    for index, sentence in enumerate((s for s in sentences if s), start=1):
        produced = compile_sentence(sentence, types)
        alt = 0
        seen_types: dict[str | None, int] = {}
        for rule in produced:
            seen_types[rule["request_type"]] = (
                seen_types.get(rule["request_type"], 0) + 1
            )
            alt = seen_types[rule["request_type"]]
            base = f"{code}-{index}"
            if rule["request_type"]:
                base = f"{base}-{rule['request_type']}"
            if alt > 1:
                base = f"{base}-{alt}"
            rules.append({"id": base[:50], "description": sentence[:500], **rule})
    return rules


def compile_regulations(
    regulations: list[dict[str, Any]], request_types: list[RequestTypeName]
) -> list[dict[str, Any]]:
    """Rules for every regulation, ordered by regulation code."""
    rules: list[dict[str, Any]] = []
    for reg in sorted(regulations, key=lambda r: r["code"]):
        rules.extend(compile_text(reg["code"], reg.get("content") or "", request_types))
    return rules


MATCH_KEYS = (
    "request_type",
    "amount_gt",
    "days_gt",
    "due_within_hours",
    "require_no_handover",
    "repeat_count_gte",
    "repeat_window",
    "split_suspect",
    "auto_approve",
)


def rule_key(rule: dict[str, Any]) -> tuple:
    """Canonical identity of a rule's scope + conditions + effect (for diff and scoring)."""
    return tuple(
        (k, rule.get(k))
        for k in MATCH_KEYS
        if k == "auto_approve" or not (rule.get(k) is None or rule.get(k) is False)
    )
