"""
Router: Summarize — Tóm tắt yêu cầu dài bằng Gemini LLM

POST /ai/summarize/request
  - Input: nội dung yêu cầu (title, description, data JSON, request_type)
  - Output: tóm tắt 2-3 câu ngắn gọn để Approver đọc nhanh trên Mobile

Không train model — dùng Gemini 1.5 Flash với prompt engineering.
"""

import json
from typing import Any

from config import get_settings
from fastapi import APIRouter, HTTPException
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


def build_summarize_prompt(req: SummarizeRequest) -> str:
    type_label = REQUEST_TYPE_LABELS.get(req.request_type, req.request_type)

    data_str = ""
    if req.data:
        # Chỉ lấy các key quan trọng, bỏ qua field kỹ thuật
        ignore_keys = {"id", "created_at", "updated_at", "requester_id", "status"}
        important_data = {k: v for k, v in req.data.items() if k not in ignore_keys}
        data_str = f"\nDữ liệu bổ sung: {json.dumps(important_data, ensure_ascii=False, indent=2)}"

    amount_str = f"\nSố tiền: {req.amount:,.0f} VNĐ" if req.amount else ""
    risk_str = f"\nĐiểm rủi ro AI: {req.risk_score}/5" if req.risk_score else ""

    return f"""Bạn là trợ lý tóm tắt yêu cầu nội bộ doanh nghiệp. 
Hãy tóm tắt yêu cầu sau bằng tiếng Việt, NGẮN GỌN, RÕ RÀNG để người phê duyệt có thể đọc trong 10 giây.

=== THÔNG TIN YÊU CẦU ===
Loại: {type_label}
Người yêu cầu: {req.requester_name}
Tiêu đề: {req.title}
Mô tả: {req.description or "(không có)"}
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


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/request", response_model=SummarizeResult, summary="Tóm tắt nội dung yêu cầu"
)
async def summarize_request(body: SummarizeRequest):
    """
    Tóm tắt yêu cầu bằng Gemini 1.5 Flash.

    Trả về:
    - **summary**: 2-3 câu tóm tắt
    - **key_points**: bullet points quan trọng
    - **sentiment**: mức độ (normal/urgent/high_risk)
    - **tokens_used**: số token Gemini đã dùng
    """
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY chưa cấu hình. Xem .env.example",
        )

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = build_summarize_prompt(body)

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3,  # Thấp để output ổn định, không sáng tạo quá
                max_output_tokens=512,
            ),
        )

        raw = response.text.strip()
        # Strip markdown code block nếu Gemini trả về ```json ... ```
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
        # Fallback: trả về raw text như summary
        return SummarizeResult(
            summary=response.text[:300] if response else "Không tóm tắt được.",
            key_points=[],
            sentiment="normal",
            tokens_used=0,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Summarize error: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi LLM: {e}")
