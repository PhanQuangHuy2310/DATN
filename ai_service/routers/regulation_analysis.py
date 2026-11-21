"""
Router: Phân tích quy định mới bằng mô hình ngôn ngữ lớn có truy xuất (xem regulation_llm.py).

POST /ai/regulation-llm/analyze
  - Input: văn bản quy định mới, cấu hình hiện tại của các loại yêu cầu, các quy định cũ (tùy chọn)
  - Output: quy tắc nguyên tử, xung đột với quy định cũ, đề xuất phân loại luồng A/B/C và trọng số (chờ duyệt)
Không gọi được Gemini thì dùng mô hình nội bộ process_profile.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    import regulation_llm
    from config import get_settings
except ImportError:
    from ai_service import regulation_llm
    from ai_service.config import get_settings

from .process_profile import TypeConfig, get_model

router = APIRouter()


class OldRegulation(BaseModel):
    code: str = Field("", max_length=40)
    title: str = Field("", max_length=300)
    content: str = Field("", max_length=20000)


class AnalyzeIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=5000)
    types: list[TypeConfig] = Field(..., min_length=1, max_length=300)
    old_regulations: list[OldRegulation] = Field(default_factory=list, max_length=200)


def _fallback(text: str, types: list[dict]) -> dict:
    try:
        return get_model().regulation_impact(text, types)
    except Exception:  # noqa: BLE001
        return {"version": "none", "proposals": []}


@router.post("/analyze")
async def analyze(body: AnalyzeIn) -> dict[str, Any]:
    settings = get_settings()
    out = await asyncio.to_thread(
        regulation_llm.analyze,
        body.text,
        [t.model_dump() for t in body.types],
        [o.model_dump() for o in body.old_regulations],
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
        fallback=_fallback,
        timeout=30.0,
        retries=1,
        retry_wait=3.0,
    )
    out.pop("raw_response", None)
    return out


class ClauseType(BaseModel):
    code: str = Field(..., max_length=60)
    name: str = Field("", max_length=200)
    lifecycle: str | None = Field(None, max_length=1)


class ClauseIn(BaseModel):
    clause: str = Field(..., min_length=5, max_length=2000)
    types: list[ClauseType] = Field(..., min_length=1, max_length=300)


@router.post("/rules")
async def clause_rules(body: ClauseIn) -> dict[str, Any]:
    """Đề xuất luật có cấu trúc cho MỘT câu trình biên dịch chưa hiểu (chờ admin duyệt, không tự áp dụng).

    Đầu ra đã qua kiểm tra bằng luật (regulation_rules_llm.validate). Không có khóa / lỗi Gemini thì trả
    rules rỗng kèm lỗi, admin tự soạn luật.
    """
    try:
        import regulation_rules_llm as rl
    except ImportError:
        from ai_service import regulation_rules_llm as rl
    settings = get_settings()
    if not settings.gemini_api_key:
        return {"rules": [], "rejected": [], "error": "GEMINI_NOT_CONFIGURED"}
    try:
        return await asyncio.to_thread(
            rl.extract,
            body.clause,
            [t.model_dump() for t in body.types],
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
            timeout=25.0,
        )
    except Exception as exc:  # noqa: BLE001
        return {"rules": [], "rejected": [], "error": type(exc).__name__}


@router.get("/key-pool-status")
async def key_pool_status() -> dict[str, Any]:
    """Trả về trạng thái pool các Gemini API key (đã che ký tự bí mật) phục vụ giám sát xoay vòng key."""
    try:
        from gemini_key_pool import get_pool_status
    except ImportError:
        from ai_service.gemini_key_pool import get_pool_status
    settings = get_settings()
    return get_pool_status(settings.gemini_api_key)
