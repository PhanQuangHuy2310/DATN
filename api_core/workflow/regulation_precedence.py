"""Quy định mới thay thế quy định cũ tương tự (yêu cầu 18/11: "lớn hơn 40 tr phải duyệt" -> mới "50 tr" thì bác bỏ 40 tr).

Hai luật của HAI văn bản khác nhau bị coi là "tương tự / chồng lên nhau" khi cùng phạm vi loại yêu cầu và:
  - cùng KIỂU điều kiện (cùng tập khóa: số tiền / số ngày / lần lặp / giữ việc đến hạn / chia nhỏ), dù ngưỡng,
    người duyệt hay mức chuyển luồng khác nhau (40 tr -> 50 tr; Kế toán -> Giám đốc), hoặc
  - ngược chiều nhau (một luật cho AI tự duyệt, một luật bắt duyệt thủ công) và cùng áp được cho một hồ sơ.
Khi đó luật MỚI HƠN thắng, luật cũ bị bỏ khỏi bộ luật AI (chỉ trong phạm vi bị chồng: luật cũ áp cho mọi loại mà luật
mới chỉ cho một loại thì luật cũ vẫn áp cho các loại còn lại, qua except_types). Hai luật cùng một văn bản không thay
thế nhau (người soạn đã viết cả hai).

"Mới hơn" tính theo TỪNG CÂU: lần đầu câu đó được AI áp dụng (origins lưu trong bộ luật đã áp dụng). Sửa câu khác của
văn bản cũ không làm câu 40 tr "mới" lại; sửa chính câu 40 tr thì đó là quyết định mới nhất. Câu chưa từng áp dụng
(đang ban hành) là mới nhất. Văn bản mới bị trả lại thì không thay thế gì, vì chỉ áp dụng khi AI học xong.
"""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Any

CONDITION_KEYS = ("amount_gt", "days_gt", "due_within_hours", "repeat_count_gte", "split_suspect")
NEWEST = (10**9, 0)


def sentence_sha(sentence: str) -> str:
    text = " ".join(unicodedata.normalize("NFC", sentence or "").lower().split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def code_of(rule: dict[str, Any]) -> str:
    return str(rule.get("source_code") or rule["id"].rsplit("-", 2)[0])


def _version_tuple(version: str | None) -> tuple[int, int]:
    try:
        major, _, minor = str(version or "0.0").lstrip("v").partition(".")
        return int(major), int(minor or 0)
    except ValueError:
        return 0, 0


def _kind(rule: dict[str, Any]) -> frozenset[str]:
    return frozenset(k for k in CONDITION_KEYS if rule.get(k) not in (None, False))


def _overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ta, tb = a.get("request_type"), b.get("request_type")
    if ta and tb and ta != tb:
        return False
    if ta and ta in (b.get("except_types") or []):
        return False
    return not (tb and tb in (a.get("except_types") or []))


def _contradicts(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a.get("auto_approve") is not None and b.get("auto_approve") is not None \
        and bool(a["auto_approve"]) != bool(b["auto_approve"])


def similar(new: dict[str, Any], old: dict[str, Any]) -> bool:
    return _overlaps(new, old) and (_kind(new) == _kind(old) or _contradicts(new, old))


def resolve(
    rules: list[dict[str, Any]],
    origins: dict[str, dict[str, Any]],
    *,
    current_version: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Áp luật "mới thắng" cho các luật đã biên dịch (mỗi luật có description = câu gốc, id bắt đầu bằng mã văn bản).

    origins: {sha câu: {"version": "12.0"}} lần đầu câu được áp dụng; câu không có trong origins là mới nhất.
    Trả (luật giữ lại [có thể thêm except_types], danh sách thay thế để hiển thị/thông báo).
    """
    def order(rule: dict[str, Any]) -> tuple[int, int]:
        seen = origins.get(sentence_sha(rule.get("description") or ""))
        return _version_tuple(seen["version"]) if seen else NEWEST

    ranked = sorted(rules, key=order, reverse=True)  # mới nhất trước
    kept: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    for rule in ranked:
        rule = dict(rule)
        dropped = False
        for winner in kept:
            if code_of(winner) == code_of(rule) or order(winner) <= order(rule) or not similar(winner, rule):
                continue
            entry = {
                "old_code": code_of(rule), "old_rule": rule["id"], "old_text": (rule.get("description") or "")[:300],
                "new_code": code_of(winner), "new_rule": winner["id"],
                "new_text": (winner.get("description") or "")[:300],
                "request_type": winner.get("request_type") or rule.get("request_type"),
            }
            if winner.get("request_type") and not rule.get("request_type"):
                # Luật cũ áp cho mọi loại, luật mới chỉ thay cho một loại: luật cũ vẫn áp cho các loại khác.
                rule["except_types"] = sorted({*(rule.get("except_types") or []), winner["request_type"]})
                entry["scope"] = "TYPE"
                superseded.append(entry)
                continue
            entry["scope"] = "ALL"
            superseded.append(entry)
            dropped = True
            break
        if not dropped:
            kept.append(rule)
    order_ids = {r["id"]: i for i, r in enumerate(rules)}
    kept.sort(key=lambda r: order_ids.get(r["id"], 0))
    return kept, superseded


def next_origins(
    rules: list[dict[str, Any]], origins: dict[str, dict[str, Any]], version: str
) -> dict[str, dict[str, Any]]:
    """Origins sau lượt học: giữ câu cũ (đúng phiên bản lần đầu áp dụng), thêm câu mới với phiên bản này."""
    out = {}
    for rule in rules:
        sha = sentence_sha(rule.get("description") or "")
        out[sha] = origins.get(sha) or {"version": str(version).lstrip("v"), "code": code_of(rule)}
    return out


def describe(entry: dict[str, Any], type_names: dict[str, str] | None = None) -> str:
    names = type_names or {}
    kind = names.get(entry.get("request_type") or "", entry.get("request_type") or "mọi loại yêu cầu")
    tail = " (chỉ với loại này; luật cũ vẫn áp cho các loại khác)" if entry.get("scope") == "TYPE" else ""
    return (f"{entry['new_code']} thay thế {entry['old_code']} ở {kind}: “{entry['new_text'][:140]}” thay cho "
            f"“{entry['old_text'][:140]}”{tail}")
