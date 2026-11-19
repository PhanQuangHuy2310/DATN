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
    "amount_gt",
    "days_gt",
    "due_within_hours",
    "require_no_handover",
    "repeat_count_gte",
    "repeat_window",
    "split_suspect",
    "split_total_gt",
)


def _issue(
    severity: str,
    kind: str,
    message: str,
    *,
    sentence: str | None = None,
    article: str | None = None,
    related: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        (
            _CONTROL,
            "Văn bản có ký tự lạ hoặc ký tự điều khiển (thường do sao chép từ file hỏng)",
        ),
        (
            _MOJIBAKE,
            'Chữ tiếng Việt bị hỏng mã hóa (ví dụ "Ä‘" thay cho "đ"): lưu lại file dạng UTF-8 rồi dán lại',
        ),
    ):
        m = pattern.search(text)
        if m:
            start = max(m.start() - 30, 0)
            issues.append(
                _issue(ERROR, "GARBLED", message, sentence=text[start : m.end() + 30])
            )
    hits = list(_QUESTION_IN_WORD.finditer(text))
    if len(hits) >= 2:
        start = max(hits[0].start() - 30, 0)
        issues.append(
            _issue(
                ERROR,
                "GARBLED",
                f'{len(hits)} chỗ dấu "?" nằm giữa chữ (ví dụ "Ngh? ph?p"): chữ có dấu bị mất khi sao chép',
                sentence=text[start : hits[0].end() + 30],
            )
        )
    letters = [c for c in text if not c.isspace()]
    odd = [c for c in letters if unicodedata.category(c)[0] not in "LNPSZ"]
    if letters and len(odd) / len(letters) > 0.05:
        issues.append(
            _issue(ERROR, "GARBLED", f"{len(odd)} ký tự không đọc được trong văn bản")
        )
    return issues


def _article(sentence: str, fallback: str | None) -> str | None:
    m = _ARTICLE.match(sentence)
    return f"{m.group(1).capitalize()} {m.group(2)}" if m else fallback


def clauses(
    code: str, content: str, types: list[RequestTypeName]
) -> list[dict[str, Any]]:
    """Mỗi câu của văn bản: điều khoản, các luật AI hiểu được, lý do chưa hiểu (nếu có)."""
    out, current = [], None
    for sentence in sentences(content):
        current = _article(sentence, current)
        out.append(
            {
                "code": code,
                "article": current,
                "sentence": sentence,
                "rules": compile_sentence(sentence, types),
                "skip": skip_reason(sentence, types),
            }
        )
    return out


def _cond_text(rule: dict[str, Any]) -> str:
    parts = []
    if rule.get("amount_gt") is not None:
        parts.append(f"số tiền > {int(rule['amount_gt']):,}".replace(",", "."))
    if rule.get("days_gt") is not None:
        parts.append(f"số ngày > {rule['days_gt']}")
    if rule.get("due_within_hours"):
        parts.append(f"đang giữ việc đến hạn trong {rule['due_within_hours']} giờ")
    if rule.get("repeat_count_gte"):
        parts.append(f"lần thứ {rule['repeat_count_gte']} trở lên")
    if rule.get("split_suspect"):
        parts.append("nghi chia nhỏ hồ sơ")
    return ", ".join(parts) or "mọi hồ sơ"


def _same_scope(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ta, tb = a.get("request_type"), b.get("request_type")
    return ta is None or tb is None or ta == tb


def _where(c: dict[str, Any], code: str) -> str:
    return (
        f"{c['article'] or 'một điều'} của {c['code']}"
        if c["code"] != code
        else (c["article"] or "một điều")
    )


def validate(
    *,
    code: str,
    title: str,
    content: str,
    types: list[RequestTypeName],
    others: list[dict[str, Any]] | None = None,
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
    theirs = [
        c
        for o in others or []
        for c in clauses(o["code"], o.get("content") or "", types)
    ]
    for c in mine:
        if c["skip"]:
            warnings.append(
                _issue(
                    WARNING,
                    "UNPARSED",
                    f"AI chưa hiểu điều kiện của câu này ({c['skip']}); câu sẽ vào hàng chờ để "
                    "admin duyệt cách hiểu, chưa áp dụng ngay",
                    sentence=c["sentence"],
                    article=c["article"],
                )
            )

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
                        if (
                            how
                            and (a["sentence"], b["code"], b["sentence"])
                            not in seen_supersede
                        ):
                            seen_supersede.add(
                                (a["sentence"], b["code"], b["sentence"])
                            )
                            only_type = ra.get("request_type") and not rb.get(
                                "request_type"
                            )
                            kind = name.get(
                                ra.get("request_type") or rb.get("request_type") or "",
                                "mọi loại yêu cầu",
                            )
                            if how == "UNTIL":
                                tail = f" (điều cũ còn áp đến trước ngày {ra['effective_from']})"
                            elif how == "EXCLUDE" and not only_type:
                                tail = " (chỉ trong vùng của điều mới; ngoài vùng đó điều cũ vẫn áp)"
                            elif only_type:
                                tail = " (chỉ với loại này; điều cũ vẫn áp cho các loại khác)"
                            else:
                                tail = ""
                            supersedes.append(
                                _issue(
                                    INFO,
                                    "SUPERSEDES",
                                    f"Sẽ thay thế {_where(b, code)} ở {kind}: {_cond_text(ra)} thay cho {_cond_text(rb)}"
                                    + tail
                                    + ". Khi AI áp dụng xong, phần bị thay của điều cũ hết hiệu lực vĩnh viễn.",
                                    sentence=a["sentence"],
                                    article=a["article"],
                                    related={
                                        "code": b["code"],
                                        "article": b["article"],
                                        "sentence": b["sentence"][:400],
                                    },
                                )
                            )
                        continue
                    if not overlaps(ra, rb):
                        continue  # cùng văn bản nhưng không chồng (vd. "trên 5 ngày" và "không quá 5 ngày")
                    if (
                        ra.get("auto_approve") is not None
                        and rb.get("auto_approve") is not None
                        and bool(ra["auto_approve"]) != bool(rb["auto_approve"])
                    ):
                        allow, deny = (ra, rb) if ra["auto_approve"] else (rb, ra)
                        allow_c, deny_c = (a, b) if ra["auto_approve"] else (b, a)
                        kind = name.get(
                            allow.get("request_type") or deny.get("request_type"),
                            "mọi loại yêu cầu",
                        )
                        errors.append(
                            _issue(
                                ERROR,
                                "CONTRADICTION",
                                f"Mâu thuẫn ở {kind}: {_where(allow_c, code)} cho AI tự duyệt ({_cond_text(allow)}), "
                                f"nhưng {_where(deny_c, code)} bắt duyệt thủ công ({_cond_text(deny)}). Hồ sơ thỏa cả "
                                "hai điều kiện sẽ luôn bị duyệt thủ công, nên điều cho phép tự duyệt không có tác dụng. "
                                "Sửa lại cho hai điều không chồng nhau, hoặc bỏ một điều.",
                                sentence=a["sentence"],
                                article=a["article"],
                                related={
                                    "code": b["code"],
                                    "article": b["article"],
                                    "sentence": b["sentence"][:400],
                                },
                            )
                        )
    rules = [r for c in mine for r in c["rules"]]
    if (
        content.strip()
        and not rules
        and not errors
        and not any(w["kind"] == "UNPARSED" for w in warnings)
    ):
        warnings.append(
            _issue(
                WARNING,
                "NO_CONTROL",
                "Văn bản không có câu nào thay đổi cách duyệt hồ sơ; AI học xong cũng không đổi hành vi",
            )
        )
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "supersedes": supersedes,
        "rules": len(rules),
    }


def summary_text(result: dict[str, Any], limit: int = 3) -> str:
    """Một đoạn ngắn cho thông báo: các lỗi đầu tiên."""
    items = result.get("errors") or []
    parts = [
        f"{e.get('article') + ': ' if e.get('article') else ''}{e['message'].rstrip('. ')}"
        for e in items[:limit]
    ]
    more = len(items) - limit
    return "; ".join(parts) + (f" (và {more} lỗi khác)" if more > 0 else "")
