"""
Router: Summarize — Tóm tắt yêu cầu dài bằng Gemini LLM

POST /ai/summarize/request
  - Input: nội dung yêu cầu (title, description, data JSON, request_type)
  - Output: tóm tắt 2-3 câu ngắn gọn để Approver đọc nhanh trên Mobile

Không train model — dùng Gemini 1.5 Flash với prompt engineering.
"""

import json
import re
from typing import Any

try:
    from config import get_settings
except (ImportError, AttributeError):
    from ai_service.config import get_settings

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

settings = get_settings()
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SummarizeRequest(BaseModel):
    title: str
    description: str | None = None
    request_type: str  # "purchase", "leave", "expense_claim"...
    requester_name: str
    data: dict[str, Any] | None = None  # JSONB data từ requests.data
    risk_score: int | None = None
    amount: float | None = None  # Rút ra từ data để dễ đưa vào prompt


class SummarizeResult(BaseModel):
    summary: str  # 2-3 câu tóm tắt
    key_points: list[str]  # Bullet points quan trọng
    sentiment: str  # "normal" | "urgent" | "high_risk"
    tokens_used: int


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

REQUEST_TYPE_LABELS = {
    "leave_short": "Nghỉ phép ngắn ngày",
    "leave_long": "Nghỉ phép dài ngày",
    "purchase_low": "Mua sắm giá trị thấp",
    "purchase_high": "Mua sắm giá trị cao",
    "room_booking": "Đặt phòng họp",
    "expense_claim": "Hoàn ứng/Thanh toán",
    "overtime": "Đăng ký làm thêm giờ",
    "asset_request": "Yêu cầu cấp thiết bị",
    "late_checkin": "Đăng ký đi muộn/về sớm",
    "contract_approval": "Duyệt hợp đồng",
    "it_request": "Yêu cầu IT",
    "facility_repair": "Sửa chữa cơ sở vật chất",
    "flashsale_voucher": "Flash Sale/Voucher",
    "data_extract": "Trích xuất dữ liệu",
    "refund": "Hoàn tiền/Đền bù",
    "onboarding": "Onboarding nhân viên mới",
}


_PAN_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_CCCD_REGEX = re.compile(r"\b0\d{11}\b")
_SECRET_KEY_REGEX = re.compile(
    r"(?i)(bearer\s+[a-z0-9_\-\.]{20,}|(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?)"
)


def sanitize_prompt_text(text: str) -> str:
    """Mask PII and secrets before dispatching to external LLM (ISO 27001 / SOC 2 Privacy)."""
    if not text:
        return text
    text = _SECRET_KEY_REGEX.sub("[REDACTED_SECRET]", text)
    text = _PAN_REGEX.sub("[REDACTED_PAN]", text)
    text = _CCCD_REGEX.sub("[REDACTED_ID]", text)
    return text


def build_summarize_prompt(req: SummarizeRequest) -> str:
    type_label = REQUEST_TYPE_LABELS.get(req.request_type, req.request_type)

    data_str = ""
    if req.data:
        # Chỉ lấy các key quan trọng, bỏ qua field kỹ thuật
        ignore_keys = {"id", "created_at", "updated_at", "requester_id", "status"}
        important_data = {k: v for k, v in req.data.items() if k not in ignore_keys}
        raw_json = json.dumps(important_data, ensure_ascii=False, indent=2)
        sanitized_json = sanitize_prompt_text(raw_json)
        data_str = f"\nDữ liệu bổ sung: {sanitized_json}"

    amount_str = f"\nSố tiền: {req.amount:,.0f} VNĐ" if req.amount else ""
    risk_str = f"\nĐiểm rủi ro AI: {req.risk_score}/5" if req.risk_score else ""
    title_sanitized = sanitize_prompt_text(req.title)
    desc_sanitized = sanitize_prompt_text(req.description or "(không có)")

    return f"""Bạn là trợ lý tóm tắt yêu cầu nội bộ doanh nghiệp. 
Hãy tóm tắt yêu cầu sau bằng tiếng Việt, NGẮN GỌN, RÕ RÀNG để người phê duyệt có thể đọc trong 10 giây.

=== THÔNG TIN YÊU CẦU ===
Loại: {type_label}
Người yêu cầu: {req.requester_name}
Tiêu đề: {title_sanitized}
Mô tả: {desc_sanitized}
{amount_str}{risk_str}{data_str}

=== YÊU CẦU ĐẦU RA (JSON) ===
Trả về JSON với cấu trúc sau, KHÔNG thêm gì ngoài JSON:
{{
  "summary": "<2-3 câu tóm tắt súc tích, nêu ai xin gì, bao nhiêu/bao lâu, lý do>",
  "key_points": ["<điểm quan trọng 1>", "<điểm quan trọng 2>", "<điểm quan trọng 3 nếu có>"],
  "sentiment": "<normal|urgent|high_risk>"
}}

Lưu ý: "urgent" nếu có từ khẩn cấp/gấp/ngay. "high_risk" nếu risk_score >= 4 hoặc số tiền > 50 triệu.
"""


def _local_extractive_summarize(req: SummarizeRequest) -> SummarizeResult:
    """Tóm tắt trích xuất cục bộ khi không có Gemini API key hoặc khi LLM lỗi."""
    type_label = REQUEST_TYPE_LABELS.get(req.request_type, req.request_type)

    desc_lower = (req.description or "").lower()
    title_lower = (req.title or "").lower()
    text_corpus = f"{title_lower} {desc_lower}"
    is_urgent = any(kw in text_corpus for kw in ("khẩn cấp", "gấp", "ngay", "urgent"))
    is_high_risk = (req.risk_score is not None and req.risk_score >= 4) or (
        req.amount is not None and req.amount > 50_000_000
    )

    if is_high_risk:
        sentiment = "high_risk"
    elif is_urgent:
        sentiment = "urgent"
    else:
        sentiment = "normal"

    key_points = [
        f"Người yêu cầu: {req.requester_name} ({type_label})",
    ]
    if req.amount:
        key_points.append(f"Số tiền: {req.amount:,.0f} VNĐ")
    if req.risk_score:
        key_points.append(f"Điểm rủi ro: {req.risk_score}/5")

    if req.data and isinstance(req.data, dict):
        for k in ("reason", "department", "vendor", "period", "purpose", "item_name"):
            if req.data.get(k):
                key_points.append(f"{k.capitalize()}: {req.data[k]}")

    details = []
    if req.amount:
        details.append(f"số tiền {req.amount:,.0f} VNĐ")
    if req.description:
        clean_desc = req.description.strip()
        if len(clean_desc) > 120:
            clean_desc = clean_desc[:117] + "..."
        details.append(f"nội dung: {clean_desc}")

    details_str = f" ({'; '.join(details)})" if details else ""
    summary = f"{req.requester_name} đề xuất '{req.title}' thuộc quy trình {type_label}{details_str}."

    return SummarizeResult(
        summary=summary,
        key_points=key_points[:5],
        sentiment=sentiment,
        tokens_used=0,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/request", response_model=SummarizeResult, summary="Tóm tắt nội dung yêu cầu"
)
async def summarize_request(body: SummarizeRequest):
    """
    Tóm tắt yêu cầu bằng Gemini 1.5 Flash (fallback về trích xuất cục bộ nếu thiếu API key hoặc lỗi).

    Trả về:
    - **summary**: 2-3 câu tóm tắt
    - **key_points**: bullet points quan trọng
    - **sentiment**: mức độ (normal/urgent/high_risk)
    - **tokens_used**: số token Gemini đã dùng
    """
    if not settings.gemini_api_key:
        logger.info(
            f"Gemini API key chưa cấu hình, dùng tóm tắt trích xuất cục bộ: {body.title}"
        )
        return _local_extractive_summarize(body)

    response = None
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = build_summarize_prompt(body)

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=512,
            ),
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw.removeprefix("json")
        raw = raw.strip()

        parsed = json.loads(raw)
        tokens = (
            response.usage_metadata.total_token_count if response.usage_metadata else 0
        )

        logger.info(f"Summarize OK | type={body.request_type} | tokens={tokens}")

        return SummarizeResult(
            summary=parsed.get("summary", ""),
            key_points=parsed.get("key_points", []),
            sentiment=parsed.get("sentiment", "normal"),
            tokens_used=tokens,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Gemini trả về không phải JSON: {e}")
        return _local_extractive_summarize(body)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Summarize fallback to local extractive due to error: {e}")
        return _local_extractive_summarize(body)
