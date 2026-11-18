"""Router: học bad case mới từ lý do người duyệt thu hồi hồ sơ AI đã tự duyệt.

POST /ai/bad-case/analyze-reason  phân loại lý do (bad case có sẵn / kiểu mới / lý do riêng), đề xuất điều kiện
                                  đo được, ghép vào ứng viên giống nhất; với bad case có sẵn thì nói vì sao AI
                                  đã bỏ sót (chưa vượt ngưỡng / loại đơn chưa thuộc phạm vi).
GET  /ai/bad-case/info            phiên bản và số đo của mô hình phân loại lý do.

Mô hình chạy cục bộ; lý do không được gửi tới dịch vụ bên ngoài. Việc quyết định "đủ thường xuyên chưa" nằm ở
API core (cần đếm trong CSDL).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    import bad_case_reason as bcr
    import bad_cases
except ImportError:  # chạy từ gốc repo
    from ai_service import bad_case_reason as bcr
    from ai_service import bad_cases

router = APIRouter()


class CaseRef(BaseModel):
    code: str = Field(..., max_length=60)
    title: str = Field("", max_length=200)
    request_types: list[str] = Field(default_factory=list, max_length=60)


class CandidateRef(BaseModel):
    code: str = Field(..., max_length=60)
    verdict: str | None = Field(None, max_length=15)
    feature: str | None = Field(None, max_length=40)
    base_code: str | None = Field(None, max_length=60)
    type_codes: list[str] = Field(default_factory=list, max_length=60)
    reasons: list[str] = Field(default_factory=list, max_length=50)
    condition: dict | None = None


class AnalyzeInput(BaseModel):
    reason: str = Field(..., min_length=5, max_length=2000)
    type_code: str = Field(..., max_length=30)
    values: dict[str, Any] = Field(default_factory=dict)
    cases: list[CaseRef] = Field(default_factory=list, max_length=500)
    candidates: list[CandidateRef] = Field(default_factory=list, max_length=500)


def _why_missed(code: str, type_code: str, values: dict[str, Any]) -> str | None:
    """Chạy lại bộ phát hiện có sẵn trên tín hiệu lúc thu hồi để nói vì sao AI không chặn."""
    detector = bad_cases.DETECTORS.get(code)
    if detector is None:
        return None
    case = next((c for c in bad_cases.load_catalog()["cases"] if c["code"] == code), None)
    if case is None:
        return None
    known = {f.name for f in bad_cases.fields(bad_cases.Signals)}
    sig = bad_cases.Signals(request_type=type_code, **{k: v for k, v in values.items() if k in known})
    hit, message, evidence = detector(sig, dict(case.get("params") or {}))
    if hit:
        return f"Bộ phát hiện {code} khớp khi chạy lại ({message}); có thể bad case đã bị admin ngưng."
    shown = ", ".join(f"{k} = {v}" for k, v in evidence.items())
    return f"Hồ sơ chưa vượt ngưỡng của {code} ({case.get('condition', '')}); giá trị lúc đó: {shown}."


@router.post("/analyze-reason", summary="Phân tích lý do thu hồi tự duyệt để học bad case")
async def analyze_reason(body: AnalyzeInput):
    values = {k: v for k, v in body.values.items() if isinstance(v, (int, float, bool)) or v is None}
    out = bcr.analyze(
        reason=body.reason,
        type_code=body.type_code,
        values=values,
        cases=[c.model_dump() for c in body.cases],
        candidates=[c.model_dump() for c in body.candidates],
    )
    if out["verdict"] == "EXISTING" and out.get("code"):
        out["why_missed"] = _why_missed(out["code"], body.type_code, values)
    out["condition_text"] = bcr.describe_condition(out.get("condition")) if out.get("condition") else None
    return out


@router.get("/info", summary="Mô hình phân loại lý do thu hồi")
async def info():
    model = bcr.load_model()
    return {"trained": model is not None, "meta": (model or {}).get("meta", {}),
            "features": {k: v["label"] for k, v in bcr.FEATURES.items()}}
