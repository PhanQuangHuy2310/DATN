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

v3 (18/11) hiểu thêm:
  amount_lte / days_lte / percent_lte   cận trên ("dưới X" -> X-1; "không quá / tối đa / X trở xuống / đến X" -> X)
  percent_gt                            phần trăm ("từ 15%" -> 14; "trên 20 phần trăm" -> 20)
  location_contains                     địa điểm ("khu vực tầng 10", "chi nhánh Đà Nẵng", "kho Bình Dương")
  repeat_window                         ROLLING_<N>D bất kỳ, CALENDAR_QUARTER, CALENDAR_YEAR (ngoài 7/30 ngày, tháng)
  retro_days_gt                         điều chỉnh cho ngày đã quá N ngày (ngày của hồ sơ cách lúc gửi > N ngày)
  effective_from / effective_until      ngày hiệu lực ("kể từ ngày 01/01/2027", "đến hết ngày 31/12/2026")
"X hoặc Y" giữa hai nhóm điều kiện sinh hai luật. Điều kiện định tính không đo được (khách hàng thân thiết, ngày lễ,
số người, "hồi tố" chung chung, mệnh đề khi/nếu lạ) làm câu bị bỏ qua thay vì sinh một luật chặn cả loại.

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
WINDOWS = (
    "CALENDAR_MONTH",
    "ROLLING_7D",
    "ROLLING_30D",
    "CALENDAR_QUARTER",
    "CALENDAR_YEAR",
)
WINDOW_RE = re.compile(
    r"^(?:CALENDAR_(?:MONTH|QUARTER|YEAR)|ROLLING_(?:[1-9]\d{0,2})D)$"
)
SENTENCE_WIDE = ("effective_from", "effective_until", "location_contains")
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


def strip_marks(text: str) -> str:
    """Bỏ dấu tiếng Việt (chỉ để NHẬN RA câu viết không dấu, không dùng để biên dịch)."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


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
# "không bắt buộc / không cần / không phải duyệt": NỚI LỎNG kiểm soát -> AI không tự suy ra, để admin xác nhận.
_NEG_MANUAL = re.compile(
    r"không\s+(?:bắt buộc|cần|phải|cần thiết phải)\s+(?:phải\s+)?(?:được\s+)?"
    r"(?:duyệt|phê duyệt|xét duyệt|trình|qua|chuyển)"
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
    r"(?P<unit>tỷ|ty|triệu|trieu|trđ|tr|nghìn|nghin|ngàn|k|vnđ|vnd|đồng|dong|đ)(?![\wà-ỹ])",
)
_DAYS = re.compile(r"(?P<num>\d+)\s*ngày")
_UPPER_EXCL = r"(?:dưới|nhỏ hơn|thấp hơn|ít hơn|đến dưới|tới dưới)\s*$"
_UPPER_INCL = r"(?:không quá|không vượt quá|tối đa|nhỏ hơn hoặc bằng|đến|tới)\s*$"
_LOWER_INCL = r"(?:từ|tối thiểu|ít nhất|bằng hoặc lớn hơn|không dưới|không thấp hơn|không ít hơn)\s*$"
_LOWER_EXCL = r"(?:trên|vượt|vượt quá|quá|lớn hơn|cao hơn|hơn)\s*$"
_PERCENT = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?:%|phần trăm)")
_DATE = re.compile(r"(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})")
_DATE_FROM = r"(?:kể từ ngày|kể từ|từ ngày|áp dụng từ ngày|áp dụng từ|có hiệu lực từ ngày|có hiệu lực từ|bắt đầu từ ngày|từ)\s*$"
_DATE_UNTIL = (
    r"(?:đến hết ngày|đến hết|đến ngày|tới ngày|cho đến ngày|đến|tới|hết ngày)\s*$"
)
_RETRO = re.compile(
    r"(?:cho\s+)?ngày\s+(?:đã\s+quá|cách\s+(?:hiện tại|ngày gửi|lúc gửi)\s+(?:hơn|trên|quá))\s+(?P<num>\d+)\s*ngày"
)
_LOCATION = re.compile(
    r"(?:khu vực|chi nhánh|kho|vùng|tỉnh|thành phố|cơ sở)\s+(?P<place>[^\W\d_][\w ]{0,40}?|tầng\s*\d+)"
    r"(?=\s*(?:$|[,.;:]|\bbắt buộc\b|\bphải\b|\bđược\b|\bkhông\b|\bcó\b|\bvới\b|\bhoặc\b|\bvà\b|"
    r"\btrên\b|\bdưới\b|\btừ\b|\bkèm\b|\bcần\b))"
)
# Điều kiện định tính / đơn vị chưa đo được: câu bị bỏ qua thay vì chặn cả loại.
_QUALITATIVE = re.compile(
    r"\bcho\s+(?:khách hàng|nhân viên|đối tác)\s+(?!\d)[^\W\d_]+|trùng\s+(?:ngày lễ|lịch|ca)|ngày lễ|thử việc"
    r"|(?:dưới|trên|từ|không quá|tối đa|quá)\s+\d+\s*(?:người|khách|chiếc|cái|xe|phòng)\b"
    # phần trăm của một đại lượng khác (ngân sách, doanh thu...) chứ không phải mức chiết khấu của hồ sơ
    r"|\d+(?:[.,]\d+)?\s*(?:%|phần trăm)\s+(?:ngân sách|doanh thu|giá trị|lợi nhuận|tổng|của|so với)"
)

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
    r"trong\s+(?:(?:một|1|cùng)\s+)?(?P<w>tháng|tuần|quý|năm)\b|trong\s+(?:vòng\s+)?(?P<n>\d+)\s*ngày"
    r"(?:\s*gần nhất|\s*liên tiếp)?"
)
_SPLIT = re.compile(r"chia nhỏ|tách nhỏ|tách thành nhiều")

# --------------------------------------------------------------------------- điều kiện ngoài schema
_UNSUPPORTED = (
    re.compile(r"hồi tố|cho ngày\s+\S+\s+đã|quá\s+\d+\s*ngày\s+(?:kể từ|sau|trước)"),
    _QUALITATIVE,
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

    loose_money: list[int] = field(default_factory=list)
    loose_percent: list[int] = field(default_factory=list)

    def add(self, start: int, end: int, kind: str, value: Any = None) -> None:
        self.spans.append(_Span(start, end, kind, value))


def _money_value(num: str, unit: str) -> int | None:
    if unit in {
        "tỷ",
        "ty",
        "triệu",
        "trieu",
        "trđ",
        "tr",
        "nghìn",
        "nghin",
        "ngàn",
        "k",
    }:
        try:
            value = float(num.replace(",", "."))
        except ValueError:
            return None
        scale = {
            "tỷ": 1e9,
            "ty": 1e9,
            "triệu": 1e6,
            "trieu": 1e6,
            "trđ": 1e6,
            "tr": 1e6,
        }.get(unit, 1e3)
        return round(value * scale)
    digits = re.sub(r"[.,]", "", num)
    return int(digits) if digits.isdigit() else None


def _bound(text: str, start: int, end: int, value: int) -> tuple[str, int | None]:
    """('lower', gt) | ('upper', lte) | ('none', None) cho con số ở [start:end] (số nguyên: tiền, ngày, %)."""
    before = text[max(0, start - 28) : start]
    after = text[end : end + 15]
    if re.match(r"\s*(?:đồng\s*)?trở xuống", after):
        return "upper", value
    if re.match(r"\s*(?:đồng\s*)?trở lên", after):
        return "lower", max(value - 1, 0)
    if re.search(_LOWER_INCL, before):
        return "lower", max(value - 1, 0)
    if re.search(_UPPER_EXCL, before):
        return "upper", max(value - 1, 0)
    if re.search(_UPPER_INCL, before):
        return "upper", value
    if re.search(_LOWER_EXCL, before):
        return "lower", value
    return "none", None


def _mask(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


_TYPE_VERB = re.compile(r"^(?:phê duyệt|đăng ký|đề nghị|đề xuất)\s+")


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
            short = _TYPE_VERB.sub("", name)
            if short != name and len(short.split()) >= 4:
                name = short
                pos = masked.find(name)
        if pos < 0:
            continue
        found.append((pos, t))
        masked = _mask(
            masked, [(m.start(), m.end()) for m in re.finditer(re.escape(name), masked)]
        )
    found.sort(key=lambda item: item[0])
    return [t for _pos, t in found], masked


def _iso(m: re.Match) -> str | None:
    try:
        from datetime import date as _date

        return _date(
            int(m.group("y")), int(m.group("m")), int(m.group("d"))
        ).isoformat()
    except ValueError:
        return None


def _window(w: re.Match) -> str:
    unit, n = w.group("w"), w.group("n")
    if unit == "tháng":
        return "CALENDAR_MONTH"
    if unit == "quý":
        return "CALENDAR_QUARTER"
    if unit == "năm":
        return "CALENDAR_YEAR"
    if unit == "tuần":
        return "ROLLING_7D"
    days = int(n)
    return f"ROLLING_{days}D" if 1 <= days <= 999 else "ROLLING_30D"


_RANGE_UNIT = re.compile(
    r"(?P<a>\d+(?:[.,]\d+)?)(?P<mid>\s+(?:đến|tới)\s+(?:dưới\s+)?\d+(?:[.,]\d+)?\s*)"
    r"(?P<u>ngày|triệu|trieu|trđ|tr|tỷ|nghìn|ngàn|%|phần trăm)"
)


def _expand_ranges(text: str) -> str:
    """'từ 3 đến 5 ngày' -> 'từ 3 ngày đến 5 ngày': đơn vị viết một lần dùng cho cả hai đầu khoảng."""
    return _RANGE_UNIT.sub(
        lambda m: f"{m.group('a')} {m.group('u')}{m.group('mid')}{m.group('u')}", text
    )


def _bounded(
    p: _Parsed, scan: str, regex: re.Pattern, value_of, lower_kind: str, upper_kind: str
) -> list[int]:
    """Thêm cận dưới/cận trên cho mọi số khớp regex; trả về các giá trị KHÔNG xác định được hướng."""
    loose: list[int] = []
    for m in regex.finditer(scan):
        value = value_of(m)
        if value is None:
            continue
        kind, bound = _bound(scan, m.start(), m.end(), value)
        if kind == "lower":
            p.add(m.start(), m.end(), lower_kind, bound)
        elif kind == "upper":
            p.add(m.start(), m.end(), upper_kind, bound)
        else:
            loose.append(value)
    return loose


def _parse(low: str) -> tuple[_Parsed, bool]:
    """Find every quantity / context condition. Returns (parsed, unsupported)."""
    p = _Parsed()
    taken: list[tuple[int, int]] = []

    # Ngày hiệu lực: phải tách trước để số ngày/tháng trong "01/01/2027" không bị đọc thành số ngày.
    for m in _DATE.finditer(low):
        iso = _iso(m)
        before = low[max(0, m.start() - 30) : m.start()]
        taken.append((m.start(), m.end()))
        if iso is None:
            return p, True
        if re.search(_DATE_UNTIL, before):
            p.add(m.start(), m.end(), "effective_until", iso)
        elif re.search(_DATE_FROM, before):
            p.add(m.start(), m.end(), "effective_from", iso)
        else:
            return p, True  # ngày cụ thể nhưng không rõ là hiệu lực: chưa đo được

    for m in _RETRO.finditer(low):
        p.add(m.start(), m.end(), "retro_days_gt", int(m.group("num")))
        taken.append((m.start(), m.end()))

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
            window = _window(w)
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

    for m in _LOCATION.finditer(_mask(low, taken)):
        place = " ".join(m.group("place").split())
        if place:
            p.add(m.start(), m.end(), "location_contains", place)
            taken.append((m.start(), m.end()))

    scan = _mask(low, taken)
    p.loose_percent = _bounded(
        p,
        scan,
        _PERCENT,
        lambda m: round(float(m.group("num").replace(",", "."))),
        "percent_gt",
        "percent_lte",
    )
    scan = _mask(
        scan, [(sp.start, sp.end) for sp in p.spans if sp.kind.startswith("percent")]
    )
    p.loose_money = _bounded(
        p,
        scan,
        _MONEY,
        lambda m: _money_value(m.group("num"), m.group("unit")),
        "amount_gt",
        "amount_lte",
    )
    scan = _mask(
        scan, [(sp.start, sp.end) for sp in p.spans if sp.kind.startswith("amount")]
    )
    _bounded(p, scan, _DAYS, lambda m: int(m.group("num")), "days_gt", "days_lte")
    # "dưới 1 ngày" (nửa ngày): số ngày là số nguyên nên không biểu diễn được -> chưa đo được, bỏ qua câu.
    if any(sp.kind == "days_lte" and sp.value < 1 for sp in p.spans):
        return p, True
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
    # Ngày hiệu lực và địa điểm áp cho cả câu, không phải một vế "hoặc".
    shared = {k: v for c in out for k, v in c.items() if k in SENTENCE_WIDE}
    out = [{k: v for k, v in c.items() if k not in SENTENCE_WIDE} for c in out]
    out = [c for c in out if c] or [{}]
    return [{**c, **shared} for c in out]


_PAIRS = (
    ("amount_gt", "amount_lte"),
    ("days_gt", "days_lte"),
    ("percent_gt", "percent_lte"),
)


def _invalid(parsed: _Parsed, groups: list[dict[str, Any]]) -> str | None:
    """Lý do câu có điều kiện vô nghĩa (không bao giờ khớp hoặc không đọc chắc được); None nếu ổn."""
    if parsed.loose_percent or (
        parsed.loose_money
        and not any(sp.kind == "split_suspect" for sp in parsed.spans)
    ):
        return "Có số tiền / phần trăm không rõ là cận trên hay cận dưới (ví dụ số âm, thiếu 'trên/dưới/từ')"
    for cond in groups:
        if any(cond.get(k, 0) > 100 for k in ("percent_gt", "percent_lte")):
            return "Phần trăm lớn hơn 100%"
        for low_key, high_key in _PAIRS:
            if low_key in cond and high_key in cond and cond[low_key] >= cond[high_key]:
                return "Khoảng rỗng: cận dưới không nhỏ hơn cận trên, luật sẽ không bao giờ khớp"
        if (
            cond.get("effective_from")
            and cond.get("effective_until")
            and cond["effective_from"] > cond["effective_until"]
        ):
            return "Ngày bắt đầu hiệu lực sau ngày hết hiệu lực"
    return None


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
    if _NEG_MANUAL.search(low):
        return []
    manual = any(word in low for word in _MANUAL) or bool(_MANUAL_RE.search(low))
    auto = not manual and any(word in low for word in _AUTO)
    if not (manual or auto):
        return []
    scoped, masked = _scope(low, types)
    masked = _expand_ranges(masked)
    parsed, unsupported = _parse(masked)
    if unsupported or _unsupported_condition(masked, parsed):
        return []
    groups = _groups(masked, parsed)
    if _invalid(parsed, groups):
        return []
    sentence_amount = next(
        (sp.value for sp in parsed.spans if sp.kind == "amount_gt"), None
    ) or next(iter(parsed.loose_money), None)
    unconstrained = all(
        not {
            k: v for k, v in g.items() if k not in ("effective_from", "effective_until")
        }
        for g in groups
    )
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


def skip_reason(sentence: str, types: list[RequestTypeName]) -> str | None:
    """Vì sao một câu CÓ yêu cầu kiểm soát lại không sinh được luật (để đưa lên admin duyệt); None nếu
    câu không có yêu cầu kiểm soát hoặc đã biên dịch được."""
    low = _ARTICLE_HEADER.sub("", fold(sentence), count=1)
    if _NEG_MANUAL.search(low):
        return "Câu phủ định yêu cầu duyệt ('không bắt buộc / không cần duyệt'): AI không tự nới lỏng kiểm soát"
    manual = any(word in low for word in _MANUAL) or bool(_MANUAL_RE.search(low))
    auto = not manual and any(word in low for word in _AUTO)
    if not (manual or auto):
        plain = strip_marks(low)
        if any(strip_marks(w) in plain for w in (*_MANUAL, *_AUTO)):
            return "Câu viết không dấu: AI chỉ đọc quy định tiếng Việt có dấu"
        return None
    scoped, masked = _scope(low, types)
    masked = _expand_ranges(masked)
    parsed, unsupported = _parse(masked)
    targeted = bool(scoped) or any(word in low for word in _EVERY) or bool(parsed.spans)
    if not targeted:
        return None
    if unsupported:
        return "Có ngày cụ thể nhưng không rõ là ngày hiệu lực, hoặc ngày không hợp lệ"
    if any(rx.search(masked) for rx in _UNSUPPORTED):
        return "Điều kiện định tính chưa đo được (nhóm khách hàng, ngày lễ, số người, hồi tố chung chung)"
    if _unsupported_condition(masked, parsed):
        return "Mệnh đề 'khi/nếu' có điều kiện AI chưa biểu diễn được"
    invalid = _invalid(parsed, _groups(masked, parsed))
    if invalid:
        return invalid
    if compile_sentence(sentence, types):
        return None
    if auto:
        return "Cho phép tự duyệt kèm điều kiện ngữ cảnh (AI không tự mở rộng tự duyệt)"
    return None


def sentences(content: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(content or "") if s.strip()]


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
    "amount_lte",
    "days_gt",
    "days_lte",
    "percent_gt",
    "percent_lte",
    "location_contains",
    "retro_days_gt",
    "effective_from",
    "effective_until",
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
