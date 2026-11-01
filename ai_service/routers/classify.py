"""
Router: Smart Request Classifier (NLP Text Classification)

POST /ai/classify/request
  - Input: title (tiêu đề) + description (mô tả yêu cầu do nhân viên nhập)
  - Output:
      + predicted_request_type (1 trong 16 loại yêu cầu)
      + predicted_department (phòng ban xử lý: hr, it, finance, marketing, ...)
      + predicted_template (biểu mẫu phê duyệt: A, B, C)
      + confidence (độ tin cậy)

Mô hình:
  - TF-IDF Vectorizer + Calibrated Classifier (huấn luyện trên 50.000 mẫu tiếng Việt)
"""

import json
import os

import joblib
import numpy as np

try:
    from config import get_settings
except (ImportError, AttributeError):
    from ai_service.config import get_settings

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

settings = get_settings()
router = APIRouter()

# ---------------------------------------------------------------------------
# Lazy model loaders
# ---------------------------------------------------------------------------
_vectorizer = None
_clf_req_type = None
_clf_dept = None
_clf_template = None
_nlp_labels = None
_load_error: str | None = None


def get_nlp_models():
    global \
        _vectorizer, \
        _clf_req_type, \
        _clf_dept, \
        _clf_template, \
        _nlp_labels, \
        _load_error
    if _vectorizer is not None and _clf_req_type is not None:
        return _vectorizer, _clf_req_type, _clf_dept, _clf_template, _nlp_labels

    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.join(base_dir, "models")

        vec_path = os.path.join(models_dir, "nlp_vectorizer.pkl")
        req_path = os.path.join(models_dir, "nlp_request_type_model.pkl")
        dept_path = os.path.join(models_dir, "nlp_department_model.pkl")
        tpl_path = os.path.join(models_dir, "nlp_template_model.pkl")
        meta_path = os.path.join(models_dir, "nlp_labels.json")

        _vectorizer = joblib.load(vec_path)
        _clf_req_type = joblib.load(req_path)
        _clf_dept = joblib.load(dept_path)
        _clf_template = joblib.load(tpl_path)

        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                _nlp_labels = json.load(f)

        logger.success("Loaded NLP classification models successfully!")
        return _vectorizer, _clf_req_type, _clf_dept, _clf_template, _nlp_labels
    except Exception as e:  # noqa: BLE001
        _load_error = str(e)
        logger.warning(f"Chưa load được NLP models: {e}")
        return None, None, None, None, None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ClassifyRequestInput(BaseModel):
    title: str = Field(
        ...,
        examples=["Đề xuất mua màn hình Dell 27 inch cho team Dev"],
        description="Tiêu đề yêu cầu",
    )
    description: str = Field(
        "",
        examples=["Màn hình cũ bị sọc hình, cần mua màn hình mới để làm việc đồ họa."],
        description="Nội dung chi tiết",
    )


class ClassifyRequestResult(BaseModel):
    predicted_request_type: str = Field(..., description="Loại yêu cầu dự đoán")
    predicted_department: str = Field(..., description="Phòng ban dự đoán")
    predicted_template: str = Field(..., description="Biểu mẫu phê duyệt A, B hoặc C")
    confidence_request_type: float = Field(
        ..., description="Độ tin cậy dự đoán loại yêu cầu (0-1)"
    )
    confidence_department: float = Field(
        ..., description="Độ tin cậy dự đoán phòng ban (0-1)"
    )
    confidence_template: float = Field(
        ..., description="Độ tin cậy dự đoán template (0-1)"
    )
    workflow_suggestion: str = Field(..., description="Gợi ý quy trình xử lý")


# ---------------------------------------------------------------------------
# Heuristic fallback khi model chưa train
# ---------------------------------------------------------------------------


def heuristic_classify(text: str) -> dict:
    t = text.lower()
    if any(k in t for k in ["nghỉ phép", "phép năm", "nghỉ việc", "ốm", "kết hôn"]):
        return {"type": "leave_annual", "dept": "hr", "template": "A"}
    elif any(k in t for k in ["tăng ca", "làm thêm", "overtime", "ngoài giờ"]):
        return {"type": "overtime", "dept": "hr", "template": "B"}
    elif any(
        k in t
        for k in ["vpn", "truy cập", "mật khẩu", "phần mềm", "máy tính", "laptop"]
    ):
        return {
            "type": "equipment_new" if "mua" in t else "access_permission",
            "dept": "it",
            "template": "B",
        }
    elif any(
        k in t for k in ["hợp đồng", "ngân sách", "tạm ứng", "hoàn ứng", "thanh toán"]
    ):
        return {
            "type": "contract_payment" if "hợp đồng" in t else "advance_payment",
            "dept": "finance",
            "template": "C",
        }
    elif any(k in t for k in ["phòng họp", "đặt phòng"]):
        return {"type": "meeting_room", "dept": "operations", "template": "A"}
    elif any(k in t for k in ["xe công tác", "đặt xe"]):
        return {"type": "vehicle_booking", "dept": "operations", "template": "A"}
    return {"type": "expense_reimbursement", "dept": "finance", "template": "B"}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/classify", include_in_schema=False)  # Backward-compatible old endpoint
@router.post("/request", response_model=ClassifyRequestResult, summary="Phân loại yêu cầu tự động (NLP)")  # fmt: skip
async def classify_request(body: ClassifyRequestInput):
    """
    Tự động nhận diện loại yêu cầu, phòng ban và quy trình phê duyệt dựa trên tiêu đề và nội dung tiếng Việt.
    """
    vectorizer, clf_req, clf_dept, clf_tpl, _labels = get_nlp_models()
    full_text = f"{body.title} {body.description}".strip()

    if not full_text:
        raise HTTPException(
            status_code=400, detail="Tiêu đề hoặc mô tả không được để trống"
        )

    if vectorizer is not None and clf_req is not None:
        try:
            X_vec = vectorizer.transform([full_text])

            # Predict request type
            req_pred = clf_req.predict(X_vec)[0]
            req_probs = clf_req.predict_proba(X_vec)[0]
            req_conf = float(np.max(req_probs))

            # Predict department
            dept_pred = clf_dept.predict(X_vec)[0]
            dept_probs = clf_dept.predict_proba(X_vec)[0]
            dept_conf = float(np.max(dept_probs))

            # Predict template
            tpl_pred = clf_tpl.predict(X_vec)[0]
            tpl_probs = clf_tpl.predict_proba(X_vec)[0]
            tpl_conf = float(np.max(tpl_probs))

            workflow_map = {
                "A": "Quy trình tiêu chuẩn 1 cấp duyệt (Manager / Team Lead). Đủ điều kiện xem xét Auto-approve nếu rủi ro thấp.",
                "B": "Quy trình chuyên môn 2 cấp duyệt (Manager -> Head of Department).",
                "C": "Quy trình trọng yếu đa cấp duyệt (Manager -> Head of Dept -> Finance Director / Board).",
            }

            return ClassifyRequestResult(
                predicted_request_type=req_pred,
                predicted_department=dept_pred,
                predicted_template=tpl_pred,
                confidence_request_type=round(req_conf, 4),
                confidence_department=round(dept_conf, 4),
                confidence_template=round(tpl_conf, 4),
                workflow_suggestion=workflow_map.get(
                    tpl_pred, "Quy trình phê duyệt tiêu chuẩn"
                ),
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Lỗi suy luận NLP: {e}")

    # Fallback nếu model lỗi
    fallback_res = heuristic_classify(full_text)
    return ClassifyRequestResult(
        predicted_request_type=fallback_res["type"],
        predicted_department=fallback_res["dept"],
        predicted_template=fallback_res["template"],
        confidence_request_type=0.75,
        confidence_department=0.70,
        confidence_template=0.70,
        workflow_suggestion="Quy trình gợi ý dựa trên từ khóa (Fallback)",
    )
