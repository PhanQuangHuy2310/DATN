"""Router: đề xuất hướng xử lý gốc rễ sau khi hồ sơ dính tình huống xấu được duyệt.

POST /ai/remediation/rank  — với mỗi việc người xin nghỉ đang giữ: xếp hạng người nhận thay (XGBoost
                              rank:pairwise) và chọn hướng xử lý (chuyển việc / lùi hạn / đổi ngày nghỉ).
GET  /ai/remediation/info  — phiên bản và số đo của mô hình.

Chỉ nhận đặc trưng số (tải việc, kinh nghiệm, quan hệ tổ chức) và mã định danh; không nhận nội dung hồ sơ.
Ràng buộc cứng (đúng vai trò, không vắng, không phải người gửi việc) đã được API core lọc trước.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    import remediation_ranker as rr
except ImportError:  # chạy từ gốc repo
    from ai_service import remediation_ranker as rr

router = APIRouter()


class Candidate(BaseModel):
    user_id: str = Field(..., max_length=64)
    display_name: str | None = Field(None, max_length=120)
    same_department: int = Field(0, ge=0, le=1)
    same_team: int = Field(0, ge=0, le=1)
    open_items: int = Field(0, ge=0, le=10_000)
    due_in_window: int = Field(0, ge=0, le=10_000)
    type_experience: int = Field(0, ge=0, le=100_000)
    is_superior: int = Field(0, ge=0, le=1)


class WorkItem(BaseModel):
    item_id: str = Field(..., max_length=64)
    kind: str = Field(..., pattern="^(APPROVAL|EXECUTION|ACCEPTANCE)$")
    hours_to_due: float = Field(..., ge=-10_000, le=100_000)
    candidates: list[Candidate] = Field(default_factory=list, max_length=200)


class RankInput(BaseModel):
    absence_hours: float = Field(0, ge=0, le=24 * 366)
    items: list[WorkItem] = Field(default_factory=list, max_length=100)


@router.post("/rank", summary="Xếp hạng người nhận việc thay và chọn hướng xử lý")
async def rank_items(body: RankInput):
    out = []
    for item in body.items:
        ranked = rr.rank([c.model_dump() for c in item.candidates])
        best = ranked["ranked"][0] if ranked["ranked"] else None
        out.append(
            {
                "item_id": item.item_id,
                "kind": item.kind,
                "suggestion": rr.suggest_action(
                    item.kind, item.hours_to_due, body.absence_hours, best
                ),
                "engine": ranked["engine"],
                "candidates": ranked["ranked"][:5],
            }
        )
    return {"model_version": rr.MODEL_VERSION, "items": out}


@router.get("/info", summary="Thông tin mô hình xếp hạng")
async def info():
    return rr.model_info()


class FeedbackCandidate(Candidate):
    chosen: bool = False


class RetrainInput(BaseModel):
    groups: list[list[FeedbackCandidate]] = Field(default_factory=list, max_length=5000)


@router.post("/retrain", summary="Học dồn từ các lần quản lý chọn khác AI (có cổng kiểm tra)")
async def retrain(body: RetrainInput):
    import asyncio

    groups = [[c.model_dump() for c in g] for g in body.groups]
    return await asyncio.to_thread(rr.retrain_with_feedback, groups)
