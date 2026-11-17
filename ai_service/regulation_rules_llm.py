"""Trích xuất luật kiểm soát có điều kiện ngữ cảnh từ một điều khoản quy định bằng Gemini.

Đầu ra cùng schema với trình biên dịch v2 (api_core/workflow/regulation_compiler.py) và luôn
được kiểm tra bằng luật trước khi dùng:
  - request_type phải là mã có trong danh mục (hoặc null = mọi loại);
  - các trường điều kiện đúng kiểu, repeat_window/escalate_to thuộc tập cho phép;
  - escalate_to chỉ được NÂNG so với luồng hiện tại của loại;
  - trích dẫn (clause) phải xuất hiện nguyên văn trong điều khoản, tránh mô hình bịa.
Luật vi phạm bị loại kèm lý do. Chỉ văn bản quy định và danh mục loại được gửi đi.
"""

from __future__ import annotations

import json
import time
import unicodedata
from typing import Any

ENGINE_VERSION = "regulation-rules-llm-1"
ORDER = {"A": 0, "B": 1, "C": 2}
WINDOWS = {"CALENDAR_MONTH", "ROLLING_7D", "ROLLING_30D"}
APPROVERS = {"DIRECT_MANAGER", "HR_MANAGER", "FINANCE", "DIRECTOR", "LEGAL", "SECURITY"}
INT_FIELDS = ("amount_gt", "days_gt", "due_within_hours", "repeat_count_gte")
BOOL_FIELDS = ("require_no_handover", "split_suspect")

PROMPT = """Bạn chuyển một điều khoản quy định nội bộ (tiếng Việt) thành các LUẬT KIỂM SOÁT có cấu trúc cho hệ thống phê duyệt EAS.
Luồng: A = tạo đơn -> phê duyệt (AI có thể tự duyệt); B = + bộ phận chuyên môn xử lý; C = + nghiệm thu độc lập.

Schema một luật (bỏ trường không dùng):
{{"request_type": "MÃ LOẠI hoặc null nếu áp dụng mọi yêu cầu",
  "amount_gt": số nguyên VNĐ (số tiền của hồ sơ > ngưỡng; 'từ X trở lên' ghi X-1; 'trên/vượt X' ghi X),
  "days_gt": số nguyên (thời lượng của chính đơn > ngưỡng ngày; 'từ N ngày trở lên' ghi N-1),
  "due_within_hours": số nguyên (người gửi đang giữ việc đến hạn trong N giờ; N ngày = N*24),
  "require_no_handover": true (chỉ khi nêu 'chưa bàn giao'/'chưa chỉ định người nhận bàn giao'),
  "repeat_count_gte": số nguyên (lần thứ K trở lên; 'quá K lần' ghi K+1),
  "repeat_window": "CALENDAR_MONTH" | "ROLLING_7D" | "ROLLING_30D",
  "split_suspect": true (dấu hiệu chia nhỏ hồ sơ tài chính để né ngưỡng),
  "auto_approve": false (bắt buộc người duyệt) | true (cho phép tự duyệt),
  "escalate_to": "B" | "C" | null (C nếu yêu cầu nghiệm thu; B nếu là điều kiện tình huống xấu deadline/lặp lại/chia nhỏ trên loại luồng A; chỉ khi cao hơn luồng hiện tại),
  "approvers": ["DIRECT_MANAGER","HR_MANAGER","FINANCE","DIRECTOR","LEGAL","SECURITY"] (cấp được nêu tên),
  "clause": "trích NGUYÊN VĂN đoạn điều khoản sinh ra luật"}}

Quy tắc:
- Mỗi loại yêu cầu được nêu tên sinh một luật riêng. 'X hoặc Y' giữa hai nhóm điều kiện sinh hai luật.
- Điều kiện không biểu diễn được bằng schema (phần trăm, khu vực, ngày hồi tố, cận trên 'dưới X') thì KHÔNG sinh luật, để tránh chặn cả loại.
- Câu không có yêu cầu kiểm soát phê duyệt (không bắt buộc duyệt thủ công, không cho phép tự duyệt) thì trả danh sách rỗng.

DANH MỤC LOẠI (mã | tên | luồng hiện tại):
{types}

ĐIỀU KHOẢN:
<<<{clause}>>>

Chỉ trả về JSON: {{"rules": [...]}}"""


def _fold(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text or "").lower().split())


def build_prompt(clause: str, types: list[dict[str, Any]]) -> str:
    lines = "\n".join(
        f"{t['code']} | {t['name']} | {t.get('lifecycle') or '?'}" for t in types
    )
    return PROMPT.format(types=lines, clause=clause)


def validate(
    raw: dict[str, Any], clause: str, types: list[dict[str, Any]]
) -> dict[str, Any]:
    lifecycle = {t["code"]: (t.get("lifecycle") or "A") for t in types}
    folded = _fold(clause)
    rules, rejected = [], []
    # Mô hình đôi khi trả thẳng một mảng luật thay vì {"rules": [...]}.
    items = raw if isinstance(raw, list) else (raw or {}).get("rules") or []
    for item in items:
        if not isinstance(item, dict):
            rejected.append({"rule": item, "why": "không phải object"})
            continue
        code = item.get("request_type")
        if code is not None and code not in lifecycle:
            rejected.append({"rule": item, "why": "mã loại không có trong danh mục"})
            continue
        quote = item.get("clause")
        if (
            not isinstance(quote, str)
            or not quote.strip()
            or _fold(quote) not in folded
        ):
            rejected.append(
                {"rule": item, "why": "trích dẫn không có nguyên văn trong điều khoản"}
            )
            continue
        rule: dict[str, Any] = {"request_type": code}
        bad = None
        for f in INT_FIELDS:
            v = item.get(f)
            if v is None:
                continue
            if (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or v < 0
                or int(v) != v
            ):
                bad = f"{f} không phải số nguyên không âm"
                break
            rule[f] = int(v)
        for f in BOOL_FIELDS:
            if item.get(f) is True:
                rule[f] = True
        if item.get("repeat_count_gte") is not None:
            window = item.get("repeat_window") or "ROLLING_30D"
            if window not in WINDOWS:
                bad = "repeat_window không hợp lệ"
            rule["repeat_window"] = window
        if rule.get("require_no_handover") and "due_within_hours" not in rule:
            rule.pop("require_no_handover")
        aa = item.get("auto_approve")
        if aa not in (True, False):
            bad = bad or "thiếu auto_approve"
        rule["auto_approve"] = aa
        esc = item.get("escalate_to")
        if esc is not None:
            if esc not in ORDER:
                bad = bad or "escalate_to không hợp lệ"
            elif code is not None and ORDER[esc] <= ORDER.get(lifecycle[code], 0):
                esc = None  # không nâng được: bỏ, không loại cả luật
            if esc:
                rule["escalate_to"] = esc
        approvers = [a for a in item.get("approvers") or [] if a in APPROVERS]
        if approvers:
            rule["approvers"] = approvers
        if aa is True and any(
            rule.get(k)
            for k in ("due_within_hours", "repeat_count_gte", "split_suspect")
        ):
            bad = bad or "không mở rộng tự duyệt theo điều kiện ngữ cảnh"
        if bad:
            rejected.append({"rule": item, "why": bad})
            continue
        rule["clause"] = quote
        rules.append(rule)
    return {"rules": rules, "rejected": rejected}


def extract(
    clause: str,
    types: list[dict[str, Any]],
    *,
    api_key: str,
    model_name: str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    import google.generativeai as genai

    genai.configure(api_key=api_key, transport="rest")
    model = genai.GenerativeModel(model_name)
    started = time.perf_counter()
    response = model.generate_content(
        build_prompt(clause, types),
        generation_config=genai.GenerationConfig(
            temperature=0, max_output_tokens=4096, response_mime_type="application/json"
        ),
        request_options={"timeout": timeout},
    )
    usage = getattr(response, "usage_metadata", None)
    out = validate(json.loads(response.text), clause, types)
    out.update(
        engine=ENGINE_VERSION,
        model=model_name,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        tokens=getattr(usage, "total_token_count", None) if usage else None,
    )
    return out
