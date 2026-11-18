"""Trình biên dịch quy định v1 (đóng băng) — chỉ dùng làm MỐC SO SÁNH trong eval_regulation_compiler.py.

Sao nguyên văn từ commit 565c96b, api_core/workflow/ai_learning.py dòng 61-186 (trước khi thay bằng
regulation_compiler.py v2). Không sửa tệp này: sửa sẽ làm sai mốc so sánh.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# 1. Regulation compiler: Vietnamese text -> policy rules (pure functions)
# ---------------------------------------------------------------------------

_MONEY = re.compile(
    r"(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>tỷ|ty|triệu|trieu|nghìn|nghin|ngàn|vnđ|vnd|đồng|dong|đ)\b",
    re.IGNORECASE,
)
_DAYS = re.compile(r"(?P<num>\d+)\s*ngày", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.;!?])\s+|\n+")
_MANUAL_STRONG = ("ban giám đốc", "hội đồng")
_MANUAL = (
    "bắt buộc",
    "duyệt thủ công",
    "phê duyệt thủ công",
    "không được tự động",
    "không tự động",
    "phải được phê duyệt",
    "phải qua",
    "rủi ro cao",
) + _MANUAL_STRONG
_AUTO = ("tự động duyệt", "tự động phê duyệt", "duyệt tự động", "đối chiếu tự động")
_EVERY = ("mọi yêu cầu", "tất cả yêu cầu", "toàn bộ yêu cầu")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def _money_value(num: str, unit: str) -> int | None:
    unit = _fold(unit)
    if unit in {"tỷ", "ty", "triệu", "trieu", "nghìn", "nghin", "ngàn"}:
        try:
            value = float(num.replace(",", "."))
        except ValueError:
            return None
        scale = {"tỷ": 1e9, "ty": 1e9, "triệu": 1e6, "trieu": 1e6}.get(unit, 1e3)
        return round(value * scale)
    digits = re.sub(r"[.,]", "", num)
    return int(digits) if digits.isdigit() else None


def _lower_bound(sentence: str, start: int, end: int, value: int) -> int | None:
    """amount_gt for the number at [start:end] (strict '>' semantics)."""
    before = sentence[max(0, start - 25) : start]
    after = sentence[end : end + 15]
    if re.search(r"(dưới|không quá|tối đa|nhỏ hơn|thấp hơn)\s*$", before):
        return None  # upper bound: not expressible as a policy rule
    if re.search(r"(từ|tối thiểu|ít nhất|bằng hoặc lớn hơn)\s*$", before) or re.match(
        r"\s*trở lên", after
    ):
        return max(value - 1, 0)
    if re.search(r"(trên|vượt|vượt quá|quá|lớn hơn|cao hơn|hơn)\s*$", before):
        return value
    return None


def _threshold(pattern: re.Pattern, sentence: str, money: bool) -> int | None:
    for match in pattern.finditer(sentence):
        value = (
            _money_value(match.group("num"), match.group("unit"))
            if money
            else int(match.group("num"))
        )
        if value is None:
            continue
        bound = _lower_bound(sentence, match.start(), match.end(), value)
        if bound is not None:
            return bound
    return None


@dataclass(frozen=True)
class RequestTypeName:
    code: str
    name: str


def compile_regulations(
    regulations: list[dict[str, Any]], request_types: list[RequestTypeName]
) -> list[dict[str, Any]]:
    """Extract enforceable approval rules from regulation sentences.

    A sentence becomes a rule when it carries an approval signal (forced manual
    review or explicit auto approval) and something to match on: an amount or
    day threshold, a named request type, or an explicit "mọi yêu cầu".
    """
    rules: list[dict[str, Any]] = []
    types = sorted(request_types, key=lambda t: -len(t.name))
    for reg in sorted(regulations, key=lambda r: r["code"]):
        sentences = [s.strip() for s in _SENTENCE.split(reg.get("content") or "")]
        for index, sentence in enumerate((s for s in sentences if s), start=1):
            low = _fold(sentence)
            manual = any(word in low for word in _MANUAL)
            auto = not manual and any(word in low for word in _AUTO)
            if not (manual or auto):
                continue
            amount_gt = _threshold(_MONEY, low, money=True)
            days_gt = _threshold(_DAYS, low, money=False)
            scoped = [t.code for t in types if t.name and _fold(t.name) in low]
            unconstrained = amount_gt is None and days_gt is None and not scoped
            if unconstrained and not any(word in low for word in _EVERY):
                continue
            base = {
                "description": sentence[:500],
                "amount_gt": amount_gt,
                "days_gt": days_gt,
            }
            if manual:
                base["min_risk"] = (
                    5 if any(word in low for word in _MANUAL_STRONG) else 4
                )
                base["auto_approve"] = False
            else:
                base["auto_approve"] = True
            rule_id = f"{reg['code']}-{index}"
            for code in scoped or [None]:
                rules.append(
                    {
                        "id": (f"{rule_id}-{code}" if code else rule_id)[:50],
                        "request_type": code,
                        **{k: v for k, v in base.items() if v is not None},
                    }
                )
    return rules
