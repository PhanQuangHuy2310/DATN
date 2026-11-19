"""Quy định mới thay thế quy định cũ tương tự (yêu cầu 18/11: "lớn hơn 40 tr phải duyệt" -> mới "50 tr" thì bác bỏ 40 tr).

Hai luật của HAI văn bản khác nhau, cùng phạm vi loại yêu cầu và CHỒNG LÊN NHAU (có hồ sơ thỏa cả hai):
  - cùng KIỂU điều kiện (cùng các chiều: số tiền / số ngày / phần trăm / ngày đã quá / giữ việc / lần lặp / chia nhỏ,
    cùng địa điểm), hoặc
  - ngược chiều (một luật cho AI tự duyệt, một luật bắt duyệt thủ công),
thì luật MỚI HƠN thắng. Cách thay (v2, 18/11):
  DROP     luật mới phủ trọn luật cũ, hoặc chỉ đổi ngưỡng cùng kiểu (40 tr -> 50 tr): luật cũ bị bỏ;
  EXCLUDE  luật mới chỉ phủ một phần (khoảng 4-6 tr trong "trên 4 tr", một loại trong luật "mọi loại"): luật cũ giữ
           nguyên nhưng không áp trong VÙNG của luật mới (exclude);
  UNTIL    luật mới có ngày hiệu lực tương lai: luật cũ còn áp tới hết ngày trước đó.
Hai luật cùng một văn bản không thay thế nhau. Luật khác kiểu điều kiện cùng chiều thì cùng tồn tại.

VĨNH VIỄN: một câu đã bị thay thế thì giữ nguyên trạng thái bị thay (bỏ / vùng loại trừ / hết hạn) kể cả khi văn bản
mới sau đó bị bãi bỏ; muốn dùng lại phải ban hành lại (câu mới, mã băm mới). Thông tin này nằm trong origins của bộ
luật đã áp dụng ({sha câu: {version, code, retired_by?, exclude?, effective_until?}}).

"Mới hơn" tính theo TỪNG CÂU: lần đầu câu đó được AI áp dụng. Câu chưa từng áp dụng (đang ban hành) là mới nhất.
Văn bản mới bị trả lại thì không thay thế gì, vì chỉ áp dụng khi AI học xong.
"""

from __future__ import annotations

import hashlib
import math
import unicodedata
from datetime import date, timedelta
from typing import Any

NEWEST = (10**9, 0)
DIMS = {
    "amount": ("amount_gt", "amount_lte"),
    "days": ("days_gt", "days_lte"),
    "percent": ("percent_gt", "percent_lte"),
    "retro": ("retro_days_gt", None),
}
OTHER_KEYS = (
    "due_within_hours",
    "require_no_handover",
    "repeat_count_gte",
    "repeat_window",
    "split_suspect",
    "split_total_gt",
)
ZONE_KEYS = (
    "amount_gt",
    "amount_lte",
    "days_gt",
    "days_lte",
    "percent_gt",
    "percent_lte",
    "retro_days_gt",
    "location_contains",
    "due_within_hours",
    "require_no_handover",
    "repeat_count_gte",
    "repeat_window",
    "split_suspect",
    "split_total_gt",
    "effective_from",
    "effective_until",
)
# Giữ tên cũ cho mã gọi trước đây.
CONDITION_KEYS = (
    "amount_gt",
    "days_gt",
    "due_within_hours",
    "repeat_count_gte",
    "split_suspect",
)


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


def _present(rule: dict[str, Any], key: str) -> bool:
    return rule.get(key) not in (None, False)


def _dims(rule: dict[str, Any]) -> set[str]:
    return {
        d
        for d, (lo, hi) in DIMS.items()
        if _present(rule, lo) or (hi and _present(rule, hi))
    }


def _kind(rule: dict[str, Any]) -> tuple:
    others = tuple(
        k
        for k in ("due_within_hours", "repeat_count_gte", "split_suspect")
        if _present(rule, k)
    )
    return (
        tuple(sorted(_dims(rule))),
        others,
        (rule.get("location_contains") or "").lower(),
    )


def _interval(rule: dict[str, Any], dim: str) -> tuple[float, float]:
    lo_key, hi_key = DIMS[dim]
    lo = rule.get(lo_key)
    hi = rule.get(hi_key) if hi_key else None
    return (-math.inf if lo is None else float(lo)), (
        math.inf if hi is None else float(hi)
    )


def _intersects(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def _contains(outer: tuple[float, float], inner: tuple[float, float]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _types_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ta, tb = a.get("request_type"), b.get("request_type")
    if ta and tb and ta != tb:
        return False
    if ta and ta in (b.get("except_types") or []):
        return False
    return not (tb and tb in (a.get("except_types") or []))


def _dates_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a0, a1 = (
        a.get("effective_from") or "0000-01-01",
        a.get("effective_until") or "9999-12-31",
    )
    b0, b1 = (
        b.get("effective_from") or "0000-01-01",
        b.get("effective_until") or "9999-12-31",
    )
    return max(a0, b0) <= min(a1, b1)


def overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Có hồ sơ nào thỏa cả hai luật không (cùng phạm vi loại, khoảng giao nhau, cùng địa điểm, thời gian giao)."""
    if not _types_overlap(a, b) or not _dates_overlap(a, b):
        return False
    la, lb = (
        (a.get("location_contains") or "").lower(),
        (b.get("location_contains") or "").lower(),
    )
    if la and lb and la != lb:
        return False
    return all(
        _intersects(_interval(a, d), _interval(b, d)) for d in _dims(a) & _dims(b)
    )


def _contradicts(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        a.get("auto_approve") is not None
        and b.get("auto_approve") is not None
        and bool(a["auto_approve"]) != bool(b["auto_approve"])
    )


def _threshold_change(new: dict[str, Any], old: dict[str, Any]) -> bool:
    """Cùng kiểu, cùng chiều, mọi chiều số chỉ có cận dưới: đổi ngưỡng (40 tr -> 50 tr) = thay hẳn."""
    if _kind(new) != _kind(old) or not _dims(new):
        return False
    return all(_interval(r, d)[1] == math.inf for r in (new, old) for d in _dims(new))


def _covers(new: dict[str, Any], old: dict[str, Any]) -> bool:
    """Mọi hồ sơ thỏa luật cũ cũng thỏa luật mới (luật mới phủ trọn luật cũ trong phạm vi loại của luật cũ)."""
    if new.get("request_type") and new.get("request_type") != old.get("request_type"):
        return False
    if (
        new.get("location_contains")
        and (new.get("location_contains") or "").lower()
        != (old.get("location_contains") or "").lower()
    ):
        return False
    if any(_present(new, k) and not _present(old, k) for k in OTHER_KEYS):
        return False
    return all(
        _contains(_interval(new, d), _interval(old, d)) for d in _dims(new) | _dims(old)
    )


def relation(new: dict[str, Any], old: dict[str, Any]) -> str | None:
    """Luật mới thay luật cũ thế nào: DROP / EXCLUDE / UNTIL / None (cùng tồn tại)."""
    if not overlaps(new, old):
        return None
    if not (_contradicts(new, old) or _kind(new) == _kind(old)):
        return None
    full = (
        _threshold_change(new, old)
        and (
            not new.get("request_type")
            or new.get("request_type") == old.get("request_type")
        )
        or _covers(new, old)
    )
    if full and new.get("effective_from"):
        return "UNTIL"
    if full:
        return "DROP"
    return "EXCLUDE"


def similar(new: dict[str, Any], old: dict[str, Any]) -> bool:
    return relation(new, old) is not None


def _zone(new: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    """Vùng của luật mới mà luật cũ không còn áp. Đổi ngưỡng trong một loại của luật 'mọi loại': cả loại đó."""
    if (
        _threshold_change(new, old)
        and new.get("request_type")
        and not old.get("request_type")
    ):
        zone = {"request_type": new["request_type"]}
        if new.get("effective_from"):
            zone["effective_from"] = new["effective_from"]
        return zone
    zone = {k: new[k] for k in ZONE_KEYS if _present(new, k)}
    if new.get("request_type"):
        zone["request_type"] = new["request_type"]
    return zone or {"request_type": new.get("request_type") or old.get("request_type")}


def _day_before(iso: str) -> str:
    return (date.fromisoformat(iso) - timedelta(days=1)).isoformat()


def _apply_persisted(
    rule: dict[str, Any], seen: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Trạng thái bị thay đã lưu (vĩnh viễn): None nếu câu đã bị bỏ."""
    if not seen:
        return rule
    if seen.get("retired_by"):
        return None
    out = dict(rule)
    if seen.get("exclude"):
        out["exclude"] = [
            *out.get("exclude", []),
            *[z for z in seen["exclude"] if z not in out.get("exclude", [])],
        ]
    if seen.get("effective_until") and (
        not out.get("effective_until")
        or seen["effective_until"] < out["effective_until"]
    ):
        out["effective_until"] = seen["effective_until"]
    return out


def resolve(
    rules: list[dict[str, Any]],
    origins: dict[str, dict[str, Any]],
    *,
    current_version: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Áp luật "mới thắng" cho các luật đã biên dịch (description = câu gốc, source_code = mã văn bản).

    origins: {sha câu: {"version": "12.0", ...trạng thái bị thay đã lưu}}; câu chưa có là mới nhất.
    Trả (luật giữ lại [có thể thêm exclude / effective_until], danh sách thay thế để hiển thị/thông báo/lưu).
    """

    def order(rule: dict[str, Any]) -> tuple[int, int]:
        seen = origins.get(sentence_sha(rule.get("description") or ""))
        return _version_tuple(seen["version"]) if seen else NEWEST

    superseded: list[dict[str, Any]] = []
    ranked = sorted(rules, key=order, reverse=True)  # mới nhất trước
    kept: list[dict[str, Any]] = []
    for original in ranked:
        sha = sentence_sha(original.get("description") or "")
        seen = origins.get(sha) or {}
        rule = _apply_persisted(original, seen)
        if rule is None:
            superseded.append(
                {
                    **seen["retired_by"],
                    "old_code": code_of(original),
                    "old_rule": original["id"],
                    "old_text": (original.get("description") or "")[:300],
                    "scope": "ALL",
                    "how": "DROP",
                    "persisted": True,
                    "old_sha": sha,
                }
            )
            continue
        dropped = False
        for winner in kept:
            if code_of(winner) == code_of(rule) or order(winner) <= order(rule):
                continue
            how = relation(winner, rule)
            if how is None:
                continue
            entry = {
                "old_code": code_of(rule),
                "old_rule": rule["id"],
                "old_text": (rule.get("description") or "")[:300],
                "new_code": code_of(winner),
                "new_rule": winner["id"],
                "new_text": (winner.get("description") or "")[:300],
                "request_type": winner.get("request_type") or rule.get("request_type"),
                "how": how,
                "old_sha": sha,
            }
            if how == "DROP":
                entry["scope"] = "ALL"
                superseded.append(entry)
                dropped = True
                break
            if how == "UNTIL":
                until = _day_before(winner["effective_from"])
                if not rule.get("effective_until") or until < rule["effective_until"]:
                    rule = {**rule, "effective_until": until}
                entry.update(scope="ALL", effective_until=until)
                superseded.append(entry)
                continue
            zone = _zone(winner, rule)
            if zone not in (rule.get("exclude") or []):
                rule = {**rule, "exclude": [*(rule.get("exclude") or []), zone]}
            entry.update(
                scope="TYPE"
                if set(zone) <= {"request_type", "effective_from"}
                else "PART",
                zone=zone,
            )
            superseded.append(entry)
        if not dropped:
            kept.append(rule)
    order_ids = {r["id"]: i for i, r in enumerate(rules)}
    kept.sort(key=lambda r: order_ids.get(r["id"], 0))
    return kept, superseded


def next_origins(
    rules: list[dict[str, Any]],
    origins: dict[str, dict[str, Any]],
    version: str,
    superseded: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Origins sau lượt học: giữ phiên bản lần đầu áp dụng của mỗi câu, thêm câu mới, lưu VĨNH VIỄN trạng thái bị thay."""
    out = {}
    for rule in rules:
        sha = sentence_sha(rule.get("description") or "")
        out[sha] = dict(
            origins.get(sha)
            or {"version": str(version).lstrip("v"), "code": code_of(rule)}
        )
    for entry in superseded or []:
        seen = out.get(entry.get("old_sha") or "")
        if seen is None or entry.get("persisted"):
            continue
        if entry["how"] == "DROP":
            seen["retired_by"] = {
                "new_code": entry["new_code"],
                "new_rule": entry["new_rule"],
                "new_text": entry["new_text"],
                "request_type": entry.get("request_type"),
            }
        elif entry["how"] == "UNTIL":
            seen["effective_until"] = entry["effective_until"]
        else:
            zones = seen.setdefault("exclude", [])
            if entry["zone"] not in zones:
                zones.append(entry["zone"])
    return out


def describe(entry: dict[str, Any], type_names: dict[str, str] | None = None) -> str:
    names = type_names or {}
    kind = names.get(
        entry.get("request_type") or "", entry.get("request_type") or "mọi loại yêu cầu"
    )
    tails = {
        "TYPE": " (chỉ với loại này; điều cũ vẫn áp cho các loại khác)",
        "PART": " (chỉ trong vùng của điều mới; ngoài vùng đó điều cũ vẫn áp)",
    }
    tail = tails.get(entry.get("scope"), "")
    if entry.get("how") == "UNTIL":
        tail = f" (điều cũ còn hiệu lực đến hết {entry['effective_until']})"
    return (
        f"{entry.get('new_code', '?')} thay thế {entry['old_code']} ở {kind}: “{entry.get('new_text', '')[:140]}” "
        f"thay cho “{entry['old_text'][:140]}”{tail}"
    )
