"""
Router: Hồ sơ quy trình — học máy nội bộ đề xuất mẫu vòng đời (A/B/C), trọng số rủi ro (1-5) và tác động của quy định mới.

POST /ai/process-profile/assess             nội dung một loại yêu cầu → mẫu vòng đời + trọng số + lý do
POST /ai/process-profile/regulation-impact  văn bản quy định (+ cấu hình hiện tại) → loại liên quan + đề xuất
GET  /ai/process-profile/info               phiên bản, giá học được cho từng tín hiệu, số đo đánh giá

Mọi kết quả chỉ là ĐỀ XUẤT: API core lưu lại để quản trị viên duyệt, không tự sửa cấu hình.
Mô hình được huấn luyện bởi training/train_process_profile.py từ 58 loại yêu cầu của hệ thống.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

import joblib
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter()

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
MODEL_PATH = os.path.join(MODELS_DIR, "process_profile.joblib")
METRICS_PATH = os.path.join(MODELS_DIR, "process_profile_metrics.json")

_lock = threading.Lock()
_model: Any = None


def get_model():
    """Nạp mô hình từ file trong image (không bao giờ từ dữ liệu người dùng gửi lên)."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                try:
                    import process_profile  # noqa: F401  (lớp ProcessProfiler phải import được khi nạp)
                except ImportError:
                    import sys

                    sys.path.insert(0, os.path.dirname(MODELS_DIR))
                _model = joblib.load(MODEL_PATH)
                logger.info("process_profile model loaded: {}", getattr(_model, "version", "?"))
    return _model


class TypeContent(BaseModel):
    code: str = Field("", max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    category: str = Field("", max_length=64)
    fields: list[str] = Field(default_factory=list, max_length=100)


class TypeConfig(TypeContent):
    code: str = Field(..., min_length=1, max_length=64)
    lifecycle: str = Field(..., pattern="^[ABC]$")
    risk_weight: int = Field(..., ge=1, le=5)


class RegulationIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=5000)
    types: list[TypeConfig] | None = Field(None, max_length=300,
                                           description="Cấu hình hiện tại; bỏ trống thì dùng 58 loại lúc huấn luyện")


def _unavailable(exc: Exception) -> HTTPException:
    logger.exception("process_profile model unavailable: {}", exc)
    return HTTPException(status_code=503, detail="Process profile model is not available")


@router.post("/assess")
def assess(body: TypeContent) -> dict[str, Any]:
    try:
        model = get_model()
    except Exception as exc:  # noqa: BLE001
        raise _unavailable(exc) from None
    out = model.predict_one(body.model_dump())
    return {"version": model.version, **out, "requires_admin_approval": True}


@router.post("/regulation-impact")
def regulation_impact(body: RegulationIn) -> dict[str, Any]:
    try:
        model = get_model()
    except Exception as exc:  # noqa: BLE001
        raise _unavailable(exc) from None
    items = [t.model_dump() for t in body.types] if body.types else None
    return model.regulation_impact(body.text, items)


@router.get("/info")
def info() -> dict[str, Any]:
    try:
        model = get_model()
    except Exception as exc:  # noqa: BLE001
        raise _unavailable(exc) from None
    metrics: dict[str, Any] = {}
    try:
        with open(METRICS_PATH, encoding="utf-8") as f:
            m = json.load(f)
        metrics = {"trained_at": m.get("trained_at"), "chosen": m.get("chosen"),
                   "loo": m.get("loo", {}).get("model"), "baselines": m.get("baselines"),
                   "holdout": m.get("holdout", {}).get("summary"),
                   "holdout_rules": m.get("holdout_rules", {}).get("summary")}
    except (OSError, ValueError):
        pass
    return {"version": model.version, "cue_prices": model.cue_prices(), "n_types": len(model.corpus), "metrics": metrics}
