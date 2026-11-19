"""Kiểm tra văn bản quy định TRƯỚC khi AI học, chỉ ra từng chỗ chưa ổn (yêu cầu trưởng nhóm 18/11).

Lỗi (ERROR, chặn ban hành; nếu lọt vào lượt học thì quy định bị trả lại và hiệu lực quay về bản cũ):
  GARBLED        văn bản lỗi ký tự: ký tự thay thế (U+FFFD), ký tự điều khiển, chữ Việt bị hỏng mã hóa
                 ("Ä‘", "á»", "Æ°"...), hoặc dấu "?" thay cho chữ có dấu ("Ngh? ph?p").
  CONTRADICTION  hai điều khoản TRONG CÙNG văn bản cùng áp cho một hồ sơ nhưng ngược nhau: một điều cho AI tự duyệt,
                 một điều bắt duyệt thủ công (người soạn tự mâu thuẫn).
Thay thế (INFO, không chặn): luật tương tự / ngược chiều với một văn bản KHÁC đang hiệu lực -> văn bản đang ban hành
  là mới nhất nên thay thế điều cũ khi AI áp dụng xong (regulation_precedence).
Cảnh báo (WARNING, không chặn):
  UNPARSED       câu có yêu cầu kiểm soát nhưng AI chưa hiểu (phần trăm, khu vực, cận trên...): vào hàng chờ duyệt
                 cách hiểu của admin.
  NO_CONTROL     văn bản không có câu nào thay đổi cách duyệt (AI học xong cũng không đổi hành vi).

Module thuần (không truy cập CSDL), dùng chung cho API ban hành (trả lỗi ngay cho admin) và lượt học của AI.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from api_core.workflow.regulation_compiler import (
    RequestTypeName,
    compile_sentence,
    sentences,
    skip_reason,
)
from api_core.workflow.regulation_precedence import overlaps, relation

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"

_MOJIBAKE = re.compile(r"Ã[\u0080-¿]|Ä[\u0080-¿‘’]|á»|áº|Æ°|Æ¡|â€[\u0080-¿™œ\u009d“”˜]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f�]")
_QUESTION_IN_WORD = re.compile(r"[^\W\d_]\?[^\W\d_]")
_ARTICLE = re.compile(r"^\s*(Điều|Khoản|Mục)\s+(\d+[a-z]?)", re.IGNORECASE)
CONDITION_KEYS = (
    "amount_gt", "days_gt", "due_within_hours", "require_no_handover", "repeat_count_gte", "repeat_window",
    "split_suspect", "split_total_gt",
)


def _issue(severity: str, kind: str, message: str, *, sentence: str | None = None, article: str | None = None,
           related: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"severity": severity, "kind": kind, "message": message}
    if sentence:
        out["sentence"] = sentence.strip()[:400]
    if article:
        out["article"] = article
    if related:
        out["related"] = related
    return out


def garbled_issues(text: str) -> list[dict[str, Any]]:
    """Lỗi ký tự, mỗi loại báo một lần kèm đoạn trích quanh chỗ lỗi."""
    issues = []
    for pattern, message in (
        (_CONTROL, "Văn bản có ký tự lạ hoặc ký tự điều khiển (thường do sao chép từ file hỏng)"),
        (_MOJIBAKE, "Chữ tiếng Việt bị hỏng mã hóa (ví dụ \"Ä‘\" thay cho \"đ\"): lưu lại file dạng UTF-8 rồi dán lại"),
    ):
        m = pattern.search(text)
        if m:
            start = max(m.start() - 30, 0)
            issues.append(_issue(ERROR, "GARBLED", message, sentence=text[start:m.end() + 30]))
    hits = list(_QUESTION_IN_WORD.finditer(text))
    if len(hits) >= 2:
        start = max(hits[0].start() - 30, 0)
        issues.append(_issue(ERROR, "GARBLED",
                             f"{len(hits)} chỗ dấu \"?\" nằm giữa chữ (ví dụ \"Ngh? ph?p\"): chữ có dấu bị mất khi sao chép",
                             sentence=text[start:hits[0].end() + 30]))
    letters = [c for c in text if not c.isspace()]
    odd = [c for c in letters if unicodedata.category(c)[0] not in "LNPSZ"]
    if letters and len(odd) / len(letters) > 0.05:
        issues.append(_issue(ERROR, "GARBLED", f"{len(odd)} ký tự không đọc được trong văn bản"))
    return issues


def _article(sentence: str, fallback: str | None) -> str | None:
    m = _ARTICLE.match(sentence)
    return f"{m.group(1).capitalize()} {m.group(2)}" if m else fallback


def clauses(code: str, content: str, types: list[RequestTypeName]) -> list[dict[str, Any]]:
    """Mỗi câu của văn bản: điều khoản, các luật AI hiểu được, lý do chưa hiểu (nếu có)."""
    out, current = [], None
    for sentence in sentences(content):
        current = _article(sentence, current)
        out.append({
            "code": code,
            "article": current,
            "sentence": sentence,
            "rules": compile_sentence(sentence, types),
            "skip": skip_reason(sentence, types),
        })
    return out


def _money(value: float) -> str:
    return f"{int(value):,}".replace(",", ".")


def _range_text(label: str, lo: float | None, hi: float | None, fmt=_money, unit: str = "") -> str | None:
    if lo is None and hi is None:
        return None
    if lo is not None and hi is not None:
        return f"{label} trên {fmt(lo)}{unit} đến {fmt(hi)}{unit}"
    return f"{label} > {fmt(lo)}{unit}" if lo is not None else f"{label} ≤ {fmt(hi)}{unit}"


def _cond_text(rule: dict[str, Any]) -> str:
    parts = [
        _range_text("số tiền", rule.get("amount_gt"), rule.get("amount_lte")),
        _range_text("số ngày", rule.get("days_gt"), rule.get("days_lte"), fmt=str),
        _range_text("mức", rule.get("percent_gt"), rule.get("percent_lte"), fmt=str, unit="%"),
    ]
    parts = [p for p in parts if p]
    if rule.get("retro_days_gt") is not None:
        parts.append(f"ngày đã quá {rule['retro_days_gt']} ngày")
    if rule.get("location_contains"):
        parts.append(f"tại {rule['location_contains']}")
    if rule.get("due_within_hours"):
        parts.append(f"đang giữ việc đến hạn trong {rule['due_within_hours']} giờ")
    if rule.get("repeat_count_gte"):
        parts.append(f"lần thứ {rule['repeat_count_gte']} trở lên")
    if rule.get("split_suspect"):
        parts.append("nghi chia nhỏ hồ sơ")
    return ", ".join(parts) or "mọi hồ sơ"


_BOUNDS = (("amount_gt", "amount_lte", "số tiền", _money, ""), ("days_gt", "days_lte", "số ngày", str, ""),
           ("percent_gt", "percent_lte", "mức", str, "%"))


def _overlap_text(allow: dict[str, Any], deny: dict[str, Any]) -> str:
    """Vùng hồ sơ thỏa cả hai luật, ví dụ "số tiền trên 3.000.000 đến 4.999.999"."""
    parts = []
    for lo_key, hi_key, label, fmt, unit in _BOUNDS:
        los = [r[lo_key] for r in (allow, deny) if r.get(lo_key) is not None]
        his = [r[hi_key] for r in (allow, deny) if r.get(hi_key) is not None]
        text = _range_text(label, max(los) if los else None, min(his) if his else None, fmt=fmt, unit=unit)
        if text:
            parts.append(text)
    return ", ".join(parts) or "mọi hồ sơ của loại này"


def _fix_hint(allow: dict[str, Any], deny: dict[str, Any]) -> str:
    """Gợi ý sửa cụ thể khi hai điều chỉ chồng nhau ở một ngưỡng (">3tr người duyệt" và "<5tr AI duyệt")."""
    for lo_key, hi_key, label, fmt, unit in _BOUNDS:
        if deny.get(lo_key) is not None and allow.get(hi_key) is not None and allow[hi_key] > deny[lo_key]:
            edge = fmt(deny[lo_key]) + unit
            return (f" Nếu ý là AI tự duyệt phần còn lại, sửa điều cho AI tự duyệt thành \"{label} không quá {edge}\"; "
                    f"nếu ý là AI tự duyệt tới {fmt(allow[hi_key])}{unit}, sửa ngưỡng của điều bắt duyệt thủ công.")
    return " Sửa lại cho hai điều không chồng nhau, hoặc bỏ một điều."


def _same_scope(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ta, tb = a.get("request_type"), b.get("request_type")
    return ta is None or tb is None or ta == tb


def _where(c: dict[str, Any], code: str) -> str:
    return f"{c['article'] or 'một điều'} của {c['code']}" if c["code"] != code else (c["article"] or "một điều")


def validate(
    *,
    code: str,
    title: str,
    content: str,
    types: list[RequestTypeName],
    others: list[dict[str, Any]] | None = None,
    auto_max_weight: int | None = None,
) -> dict[str, Any]:
    """Kiểm tra một văn bản (thêm mới hoặc sửa) so với chính nó và các quy định khác đang hiệu lực.

    others: [{code, title, content}] các quy định khác (không gồm bản cũ của chính văn bản này).
    Trả {ok, errors, warnings, rules}: ok=False khi có ít nhất một lỗi chặn.
    """
    name = {t.code: t.name for t in types}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not content.strip():
        errors.append(_issue(ERROR, "EMPTY", "Nội dung quy định đang trống"))
    errors += garbled_issues(f"{title}\n{content}")

    mine = clauses(code, content, types)
    theirs = [c for o in others or [] for c in clauses(o["code"], o.get("content") or "", types)]
    for c in mine:
        if c["skip"]:
            warnings.append(_issue(WARNING, "UNPARSED",
                                   f"AI chưa hiểu điều kiện của câu này ({c['skip']}); câu sẽ vào hàng chờ để "
                                   "admin duyệt cách hiểu, chưa áp dụng ngay",
                                   sentence=c["sentence"], article=c["article"]))

    seen_pairs = set()
    supersedes: list[dict[str, Any]] = []
    seen_supersede = set()
    for i, a in enumerate(mine):
        for ra in a["rules"]:
            for b in mine[i:] + theirs:
                for rb in b["rules"]:
                    if a is b and ra is rb:
                        continue
                    pair = (id(ra), id(rb)) if id(ra) < id(rb) else (id(rb), id(ra))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    if not _same_scope(ra, rb):
                        continue
                    if b["code"] != code:
                        # Văn bản khác: văn bản đang ban hành là MỚI NHẤT nên thay thế luật cũ tương tự / ngược chiều
                        # (regulation_precedence), không còn là lỗi.
                        how = relation(ra, rb)
                        if how and (a["sentence"], b["code"], b["sentence"]) not in seen_supersede:
                            seen_supersede.add((a["sentence"], b["code"], b["sentence"]))
                            only_type = ra.get("request_type") and not rb.get("request_type")
                            kind = name.get(ra.get("request_type") or rb.get("request_type") or "", "mọi loại yêu cầu")
                            if how == "UNTIL":
                                tail = f" (điều cũ còn áp đến trước ngày {ra['effective_from']})"
                            elif how == "EXCLUDE" and not only_type:
                                tail = " (chỉ trong vùng của điều mới; ngoài vùng đó điều cũ vẫn áp)"
                            elif only_type:
                                tail = " (chỉ với loại này; điều cũ vẫn áp cho các loại khác)"
                            else:
                                tail = ""
                            supersedes.append(_issue(
                                INFO, "SUPERSEDES",
                                f"Sẽ thay thế {_where(b, code)} ở {kind}: {_cond_text(ra)} thay cho {_cond_text(rb)}"
                                + tail + ". Khi AI áp dụng xong, phần bị thay của điều cũ hết hiệu lực vĩnh viễn.",
                                sentence=a["sentence"], article=a["article"],
                                related={"code": b["code"], "article": b["article"], "sentence": b["sentence"][:400]},
                            ))
                            if ra.get("auto_approve") is True and rb.get("auto_approve") is False:
                                warnings.append(_issue(
                                    WARNING, "RELAXES",
                                    f"Điều này NỚI LỎNG kiểm soát ở {kind}: hồ sơ có {_overlap_text(ra, rb)} trước "
                                    f"đây bắt người duyệt theo {_where(b, code)}, sau khi áp dụng AI được tự duyệt. "
                                    "Kiểm tra lại nếu đây không phải ý định.",
                                    sentence=a["sentence"], article=a["article"],
                                    related={"code": b["code"], "article": b["article"],
                                             "sentence": b["sentence"][:400]},
                                ))
                        continue
                    if not overlaps(ra, rb):
                        continue  # cùng văn bản nhưng không chồng (vd. "trên 5 ngày" và "không quá 5 ngày")
                    if ra.get("auto_approve") is not None and rb.get("auto_approve") is not None \
                            and bool(ra["auto_approve"]) != bool(rb["auto_approve"]):
                        allow, deny = (ra, rb) if ra["auto_approve"] else (rb, ra)
                        allow_c, deny_c = (a, b) if ra["auto_approve"] else (b, a)
                        kind = name.get(allow.get("request_type") or deny.get("request_type"), "mọi loại yêu cầu")
                        errors.append(_issue(
                            ERROR, "CONTRADICTION",
                            f"Mâu thuẫn ở {kind}: {_where(allow_c, code)} cho AI tự duyệt ({_cond_text(allow)}), "
                            f"nhưng {_where(deny_c, code)} bắt duyệt thủ công ({_cond_text(deny)}). Hai điều chồng "
                            f"nhau ở hồ sơ có {_overlap_text(allow, deny)}: không rõ người hay AI duyệt nhóm này "
                            "(nếu để nguyên, hệ thống sẽ bắt người duyệt)." + _fix_hint(allow, deny),
                            sentence=a["sentence"], article=a["article"],
                            related={"code": b["code"], "article": b["article"], "sentence": b["sentence"][:400]},
                        ))
    warnings += _auto_without_effect(mine, types, auto_max_weight)
    rules = [r for c in mine for r in c["rules"]]
    if content.strip() and not rules and not errors and not any(w["kind"] == "UNPARSED" for w in warnings):
        warnings.append(_issue(WARNING, "NO_CONTROL",
                               "Văn bản không có câu nào thay đổi cách duyệt hồ sơ; AI học xong cũng không đổi hành vi"))
    return {"ok": not errors, "errors": errors, "warnings": warnings, "supersedes": supersedes, "rules": len(rules)}


def _auto_without_effect(mine: list[dict[str, Any]], types: list[RequestTypeName],
                         auto_max_weight: int | None) -> list[dict[str, Any]]:
    """Điều "cho AI tự duyệt" ở loại mà AI không bao giờ tự duyệt (trọng số rủi ro vượt ngưỡng, hoặc AI tự duyệt đang
    tắt): luật vẫn được học nhưng không đổi gì, nên báo để người soạn khỏi hiểu nhầm."""
    if auto_max_weight is None:
        return []
    by_code = {t.code: t for t in types}
    out, seen = [], set()
    for c in mine:
        for rule in c["rules"]:
            t = by_code.get(rule.get("request_type") or "")
            if not rule.get("auto_approve") or t is None or t.risk_weight is None or t.code in seen:
                continue
            if t.risk_weight <= auto_max_weight:
                continue
            seen.add(t.code)
            why = ("AI tự duyệt đang tắt trên hệ thống" if auto_max_weight <= 0 else
                   f"AI chỉ tự duyệt loại có trọng số rủi ro ≤ {auto_max_weight}, loại «{t.name}» đang là "
                   f"{t.risk_weight}")
            out.append(_issue(WARNING, "AUTO_NO_EFFECT",
                              f"Điều cho AI tự duyệt «{t.name}» sẽ không có tác dụng: {why}. Hồ sơ vẫn do người "
                              "duyệt. Muốn AI tự duyệt thì hạ trọng số rủi ro của loại ở trang Yêu cầu & Quy trình.",
                              sentence=c["sentence"], article=c["article"]))
    return out


def summary_text(result: dict[str, Any], limit: int = 3) -> str:
    """Một đoạn ngắn cho thông báo: các lỗi đầu tiên."""
    items = result.get("errors") or []
    parts = [f"{e.get('article') + ': ' if e.get('article') else ''}{e['message'].rstrip('. ')}" for e in items[:limit]]
    more = len(items) - limit
    return "; ".join(parts) + (f" (và {more} lỗi khác)" if more > 0 else "")
