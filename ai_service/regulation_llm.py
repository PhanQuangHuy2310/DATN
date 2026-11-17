"""Phân tích quy định mới bằng mô hình ngôn ngữ lớn có truy xuất ngữ cảnh (retrieval-augmented).

Luồng (mỗi bước đều kiểm tra được):
  1. Truy xuất: chọn các loại yêu cầu và các quy định cũ gần nhất với văn bản mới bằng TF-IDF theo từ
     và theo ký tự không dấu (không dùng cơ sở dữ liệu vector; với vài chục loại yêu cầu TF-IDF là đủ).
  2. Gemini (nhiệt độ 0, đầu ra JSON): tách quy định thành các quy tắc nguyên tử có trích dẫn nguyên văn,
     chỉ ra xung đột với quy định cũ, đề xuất phân loại luồng A/B/C và trọng số cho các loại bị tác động.
  3. Kiểm tra bằng luật: mã loại phải nằm trong danh sách đã truy xuất, A/B/C và 1-5 hợp lệ, chỉ đề xuất
     NÂNG nghĩa vụ, trích dẫn phải xuất hiện trong văn bản quy định; đề xuất sai bị loại và ghi lý do.
  4. Kết quả chỉ là đề xuất, quản trị viên duyệt mới áp dụng. Không gọi được Gemini thì dùng mô hình
     nội bộ process_profile (học máy, chạy trong dịch vụ).

Chỉ văn bản quy định và cấu hình loại yêu cầu được gửi tới Gemini; không gửi dữ liệu hồ sơ hay dữ liệu cá nhân.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from process_profile import _plain, type_text
except ImportError:
    from ai_service.process_profile import _plain, type_text

ENGINE_VERSION = "regulation-llm-1"
TOP_TYPES = 12
TOP_REGULATIONS = 3
ORDER = {"A": 0, "B": 1, "C": 2}

PROMPT_TEMPLATE = """Bạn là chuyên viên phân tích quy trình phê duyệt nội bộ của doanh nghiệp. Hệ thống EAS phân loại mỗi loại yêu cầu theo luồng xử lý:
- A (2 bước): người gửi tạo đơn -> phê duyệt; rủi ro thấp (trọng số 1-2) thì AI được tự duyệt.
- B (3 bước): tạo đơn -> trưởng bộ phận thẩm định/phê duyệt -> bộ phận chuyên môn xử lý; trọng số thường 3.
- C (4 bước, kiểm soát chặt): như B và thêm bước kiểm tra/nghiệm thu kết quả hoặc cấp thẩm quyền cao; trọng số thường 4-5.
Trọng số rủi ro 1 (thấp nhất) đến 5 (cao nhất).

QUY ĐỊNH MỚI:
<<<{regulation}>>>

CÁC QUY ĐỊNH CŨ GẦN NHẤT (để phát hiện xung đột; có thể rỗng):
{old_regulations}

CÁC LOẠI YÊU CẦU LIÊN QUAN NHẤT (mã | tên | nhóm | luồng hiện tại | trọng số hiện tại | các trường biểu mẫu):
{types}

Nhiệm vụ:
1. Tách quy định mới thành các quy tắc nguyên tử. Mỗi quy tắc gồm: trích nguyên văn đoạn quy định (clause), đối tượng chịu tác động (subject), ngưỡng định lượng nếu có (threshold), chế tài hoặc yêu cầu kiểm soát (control).
2. Nêu xung đột hoặc thay thế với quy định cũ nếu có.
3. Chỉ liệt kê những loại yêu cầu (chỉ dùng mã trong danh sách trên) mà quy định mới bắt buộc phải TĂNG kiểm soát: nâng luồng (A->B->C) hoặc tăng trọng số. Không liệt kê loại đã đủ kiểm soát, loại không liên quan, hoặc trường hợp quy định nới lỏng. Nếu quy định không liên quan tới loại nào, trả danh sách rỗng.

Chỉ trả về JSON đúng cấu trúc:
{{"atomic_rules": [{{"clause": "...", "subject": "...", "threshold": "...", "control": "..."}}],
 "conflicts": [{{"old_regulation_code": "...", "explanation": "..."}}],
 "impacts": [{{"code": "MA_LOAI", "proposed_class": "A|B|C", "proposed_weight": 1, "reason": "...", "clause": "trích nguyên văn"}}]}}"""


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text.replace("đ", "d").replace("Đ", "D")).strip().lower()


def _rank(query: str, docs: list[str]) -> list[float]:
    if not docs:
        return []
    corpus = [_plain(d) for d in docs] + [_plain(query)]
    word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit_transform(corpus)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(corpus)
    return list(0.5 * cosine_similarity(word[-1], word[:-1]).ravel() + 0.5 * cosine_similarity(char[-1], char[:-1]).ravel())


def retrieve(regulation: str, types: list[dict], old_regulations: list[dict] | None = None) -> dict[str, Any]:
    t_scores = _rank(regulation, [type_text(t) for t in types])
    top_types = [t for t, _ in sorted(zip(types, t_scores), key=lambda x: -x[1])[:TOP_TYPES]]
    olds = old_regulations or []
    o_scores = _rank(regulation, [f"{o.get('title', '')}. {o.get('content', '')}" for o in olds])
    top_old = [o for o, s in sorted(zip(olds, o_scores), key=lambda x: -x[1])[:TOP_REGULATIONS] if s > 0.05]
    return {"types": top_types, "old_regulations": top_old,
            "type_scores": {t["code"]: round(float(s), 3) for t, s in zip(types, t_scores)}}


def build_prompt(regulation: str, ctx: dict[str, Any]) -> str:
    types = "\n".join(
        f"{t['code']} | {t.get('name', '')} | {t.get('category', '')} | {t['lifecycle']} | {t['risk_weight']} | "
        f"{', '.join(map(str, t.get('fields') or []))}" for t in ctx["types"])
    olds = "\n".join(f"[{o.get('code', '')}] {o.get('title', '')}: {str(o.get('content', ''))[:800]}"
                     for o in ctx["old_regulations"]) or "(không có)"
    return PROMPT_TEMPLATE.format(regulation=regulation[:5000], old_regulations=olds, types=types)


def call_gemini(prompt: str, api_key: str, model_name: str, timeout: float = 40.0) -> dict[str, Any]:
    import google.generativeai as genai

    genai.configure(api_key=api_key, transport="rest")
    model = genai.GenerativeModel(model_name)
    started = time.perf_counter()
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0, max_output_tokens=4096,
                                                 response_mime_type="application/json"),
        request_options={"timeout": timeout},
    )
    usage = getattr(response, "usage_metadata", None)
    return {"text": response.text, "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "tokens": getattr(usage, "total_token_count", None) if usage else None}


def validate(raw: dict[str, Any], regulation: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Kiểm tra đầu ra của mô hình ngôn ngữ bằng luật; trả về đề xuất hợp lệ và danh sách bị loại kèm lý do."""
    by_code = {t["code"]: t for t in ctx["types"]}
    folded_reg = _fold(regulation)
    proposals, rejected = [], []
    for imp in raw.get("impacts") or []:
        code = str(imp.get("code", "")).strip().upper()
        if code not in by_code:
            rejected.append({"code": code, "why": "mã loại không nằm trong danh sách đã truy xuất"})
            continue
        cur = by_code[code]
        cur_lc, cur_w = str(cur["lifecycle"]), int(cur["risk_weight"])
        lc = str(imp.get("proposed_class", cur_lc)).strip().upper()[:1]
        try:
            w = int(imp.get("proposed_weight", cur_w))
        except (TypeError, ValueError):
            w = cur_w
        if lc not in ORDER or not 1 <= w <= 5:
            rejected.append({"code": code, "why": "luồng hoặc trọng số ngoài miền A/B/C, 1-5"})
            continue
        lc = lc if ORDER[lc] > ORDER[cur_lc] else cur_lc          # chỉ nâng
        w = max(w, cur_w)
        if lc == cur_lc and w == cur_w:
            rejected.append({"code": code, "why": "không tăng kiểm soát so với cấu hình hiện tại"})
            continue
        clause = str(imp.get("clause", "")).strip()
        grounded = bool(clause) and _fold(clause)[:60] in folded_reg
        proposals.append({"code": code, "name": cur.get("name", ""),
                          "current": {"lifecycle": cur_lc, "risk_weight": cur_w},
                          "proposed": {"lifecycle": lc, "risk_weight": w},
                          "reasons": [str(imp.get("reason", ""))[:400]], "clause": clause[:400],
                          "clause_grounded": grounded})
    rules = [{k: str(r.get(k, ""))[:400] for k in ("clause", "subject", "threshold", "control")}
             for r in (raw.get("atomic_rules") or [])][:20]
    conflicts = [{k: str(c.get(k, ""))[:400] for k in ("old_regulation_code", "explanation")}
                 for c in (raw.get("conflicts") or [])][:10]
    return {"atomic_rules": rules, "conflicts": conflicts, "proposals": proposals, "rejected": rejected}


def analyze(regulation: str, types: list[dict], old_regulations: list[dict] | None, *, api_key: str,
            model_name: str, fallback=None, timeout: float = 40.0, retries: int = 0,
            retry_wait: float = 5.0) -> dict[str, Any]:
    ctx = retrieve(regulation, types, old_regulations)
    prompt = build_prompt(regulation, ctx)
    meta = {"engine": ENGINE_VERSION, "model": model_name,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "retrieved_types": [t["code"] for t in ctx["types"]],
            "retrieved_regulations": [o.get("code", "") for o in ctx["old_regulations"]]}
    error = None
    if api_key:
        try:
            for attempt in range(retries + 1):  # chỉ thử lại khi bị giới hạn tần suất (HTTP 429)
                try:
                    out = call_gemini(prompt, api_key, model_name, timeout)
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == retries or "TooManyRequests" not in type(exc).__name__ + str(exc)[:200]:
                        raise
                    time.sleep(retry_wait * (2 ** attempt))
            raw = json.loads(out["text"])
            result = validate(raw, regulation, ctx)
            return {**meta, **result, "latency_ms": out["latency_ms"], "tokens": out["tokens"], "fallback_used": False,
                    "raw_response": out["text"], "requires_admin_approval": True}
        except Exception as exc:  # noqa: BLE001 - mọi lỗi của LLM đều chuyển sang mô hình nội bộ
            error = type(exc).__name__
    else:
        error = "NO_API_KEY"
    if fallback is None:
        return {**meta, "atomic_rules": [], "conflicts": [], "proposals": [], "rejected": [], "fallback_used": True,
                "error": error, "requires_admin_approval": True}
    fb = fallback(regulation, types)
    return {**meta, "engine": f"{ENGINE_VERSION} -> {fb.get('version')}", "atomic_rules": [], "conflicts": [],
            "proposals": fb.get("proposals", []), "rejected": [], "fallback_used": True, "error": error,
            "requires_admin_approval": True}
