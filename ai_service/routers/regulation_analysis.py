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
