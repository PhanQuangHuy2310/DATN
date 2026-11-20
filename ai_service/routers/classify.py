"""
Router: Smart Request Classifier (NLP Text Classification)

POST /ai/classify/request
  - Input: title (tiêu đề) + description (mô tả yêu cầu do nhân viên nhập)
  - Output:
      + predicted_request_type: mã loại yêu cầu trong catalog v2 (VD: LEAVE, PURCHASE_REQUEST)
      + predicted_department: bộ phận xử lý (FINANCE, HR, IT, ADMIN, ...)
      + predicted_template: biểu mẫu phê duyệt A, B, C của loại đó
      + alternatives: 3 loại khả dĩ nhất kèm độ tin cậy

Mô hình (training/train.py):
  - TF-IDF từ + ký tự không dấu → Logistic Regression, một file nlp_classifier.pkl.
  - Bộ phận, nhóm và biểu mẫu suy ra từ catalog của loại dự đoán (nlp_labels.json),
    nên ba kết quả luôn nhất quán với nhau.
"""

import json
import os
from collections import defaultdict

import joblib
import numpy as np

try:
    import type_memory as tm
    from config import get_settings
    from nlp_text import ADVANCE_TIERS, normalize_text, refine_advance_tier
except (ImportError, AttributeError):
    from ai_service import type_memory as tm
    from ai_service.config import get_settings
    from ai_service.nlp_text import ADVANCE_TIERS, normalize_text, refine_advance_tier

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

settings = get_settings()
router = APIRouter()

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"
)
LOW_CONFIDENCE = 0.35

_model = None
_labels: dict | None = None
_load_error: str | None = None


def get_nlp_model():
    """Load the classifier pipeline and catalog metadata once (lazy)."""
    global _model, _labels, _load_error
    if _model is not None:
        return _model, _labels
    try:
        model = joblib.load(os.path.join(MODELS_DIR, "nlp_classifier.pkl"))
        with open(os.path.join(MODELS_DIR, "nlp_labels.json"), encoding="utf-8") as f:
            labels = json.load(f)
        if "catalog" not in labels:
            raise ValueError("nlp_labels.json thiếu catalog; chạy lại training/train.py")
        _model, _labels = model, labels
        logger.success("Loaded NLP classifier ({} loại yêu cầu)", len(model.classes_))
        return _model, _labels
    except Exception as e:  # noqa: BLE001
        _load_error = str(e)
        logger.warning(f"Chưa load được NLP model: {e}")
        return None, None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LearnedType(BaseModel):
    """Loại yêu cầu tạo sau khi huấn luyện (admin hoặc AI tạo); lõi nghiệp vụ gửi kèm, cùng các ví dụ đã có."""

    code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    category: str = Field("", max_length=40)
    category_label: str = Field("", max_length=120)
    department: str = Field("", max_length=40)
    lifecycle: str = Field("B", pattern="^[ABC]$")
    approval_route: str = Field("", max_length=400)
    examples: list[str] = Field(default_factory=list, max_length=50)


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
    learned_types: list[LearnedType] = Field(
        default_factory=list, max_length=300, description="Loại mới chưa có trong mô hình (bộ nhớ loại mới)"
    )


class ClassifyAlternative(BaseModel):
    request_type: str
    name: str
    confidence: float
    source: str = "model"  # "learned": loại mới nhận ra nhờ bộ nhớ loại mới


class ClassifyRequestResult(BaseModel):
    predicted_request_type: str = Field(..., description="Mã loại yêu cầu (catalog v2)")
    predicted_request_name: str = Field("", description="Tên loại yêu cầu")
    predicted_category: str = Field("", description="Nhóm yêu cầu (catalog v2)")
    predicted_category_label: str = Field("", description="Tên nhóm yêu cầu")
    predicted_department: str = Field(..., description="Bộ phận xử lý")
    predicted_template: str = Field(..., description="Biểu mẫu phê duyệt A, B hoặc C")
    confidence_request_type: float = Field(
        ..., description="Độ tin cậy dự đoán loại yêu cầu (0-1)"
    )
    confidence_category: float = Field(0.0, description="Độ tin cậy của nhóm (0-1)")
    confidence_department: float = Field(
        ..., description="Độ tin cậy dự đoán bộ phận (0-1)"
    )
    confidence_template: float = Field(
        ..., description="Độ tin cậy dự đoán template (0-1)"
    )
    low_confidence: bool = Field(
        False, description="True khi model không chắc; chỉ nên gợi ý, không tự đổi loại"
    )
    alternatives: list[ClassifyAlternative] = Field(
        default_factory=list, description="Các loại khả dĩ nhất"
    )
    workflow_suggestion: str = Field(..., description="Gợi ý quy trình xử lý")
    method: str = Field("nlp_model", description="nlp_model | keyword_heuristic")
    fallback_used: bool = Field(
        False, description="True khi model chưa sẵn sàng và dùng quy tắc từ khóa"
    )
    source: str = Field("model", description="model | learned (loại mới nhận từ bộ nhớ loại mới)")
    novel: bool = Field(False, description="AI đánh giá nhu cầu này chưa có loại phù hợp trong danh mục")
    unclear: bool = Field(False, description="Nội dung không có từ nào mô hình hiểu (chuỗi vô nghĩa)")
    vocab_support: float | None = Field(None, description="Tỉ lệ từ nội dung khớp từ vựng của các loại được đoán")


# ---------------------------------------------------------------------------
# Heuristic fallback khi model chưa train (mã catalog v2)
# ---------------------------------------------------------------------------

# Checked in order: specific phrases before generic ones ("nghỉ việc" before "nghỉ").
_KEYWORD_RULES = [
    (("nghỉ việc", "thôi việc", "nghi viec"), "RESIGNATION", "HR", "C"),
    (("chịu tang", "đám tang", "tang lễ", "nghỉ cưới", "thai sản", "sinh con"), "LEAVE_SPECIAL", "HR", "A"),
    (("nghỉ phép", "xin nghỉ", "nghi phep"), "LEAVE", "HR", "A"),
    (("tăng ca", "làm thêm", "overtime", "ngoài giờ"), "OVERTIME_REQ", "HR", "B"),
    (("wfh", "làm việc từ xa", "remote", "làm ở nhà"), "WFH_REQ", "HR", "A"),
    (("chấm công", "quên check"), "ATTENDANCE_ADJUSTMENT", "HR", "A"),
    (("lỗ hổng", "tấn công", "mã độc", "hotfix", "rò rỉ dữ liệu"), "SECURITY_INCIDENT_HOTFIX", "TECH", "C"),
    (("vpn", "quyền truy cập", "cấp tài khoản"), "ACCESS", "IT", "B"),
    (("máy tính", "laptop", "máy in", "wifi", "mật khẩu"), "IT_SUPPORT", "IT", "B"),
    (("điều hòa", "bóng đèn", "dột", "sửa chữa", "hỏng"), "FACILITY_REPAIR", "FACILITY", "C"),
    (("phòng họp", "đặt phòng"), "ROOM_BOOKING", "ADMIN", "A"),
    (("xe công", "đặt xe"), "VEHICLE_BOOKING", "ADMIN", "C"),
    (("sự kiện", "team building", "tất niên", "year end"), "MARKETING_CAMPAIGN", "MARKETING", "C"),
    (("ứng lương",), "SALARY_ADVANCE", "FINANCE", "B"),
    (("tạm ứng",), "ADVANCE_SMALL", "FINANCE", "B"),
    (("hợp đồng",), "CONTRACT_APPROVAL", "FINANCE", "C"),
    (("mua",), "PURCHASE_REQUEST", "PROCUREMENT", "B"),
    (("thanh toán", "hóa đơn"), "EXPENSE_CLAIM", "FINANCE", "A"),
]


def heuristic_classify(text: str) -> dict:
    t = text.lower()
    for keywords, code, dept, template in _KEYWORD_RULES:
        if any(k in t for k in keywords):
            return {"type": refine_advance_tier(code, text), "dept": dept, "template": template}
    return {"type": "TASK_REQUEST", "dept": "ADMIN", "template": "C"}


# ---------------------------------------------------------------------------
# Model inference
# ---------------------------------------------------------------------------


def _aggregate(probs: np.ndarray, classes, catalog: dict, field: str) -> dict:
    totals: dict[str, float] = defaultdict(float)
    for code, p in zip(classes, probs):
        totals[catalog[code][field]] += float(p)
    return totals


def predict(model, labels: dict, text: str, learned: list | None = None) -> ClassifyRequestResult:
    catalog = labels["catalog"]
    classes = [str(c) for c in model.classes_]
    probs = model.predict_proba([normalize_text(text)])[0]
    order = np.argsort(probs)[::-1]

    code = classes[order[0]]
    confidence = float(probs[order[0]])
    if code in ADVANCE_TIERS:
        # Tiers differ only by amount: score the family, pick the tier by amount.
        refined = refine_advance_tier(code, text)
        if refined != code:
            code = refined
            confidence = float(
                sum(p for c, p in zip(classes, probs) if c in ADVANCE_TIERS)
            )

    info = catalog[code]
    by_dept = _aggregate(probs, classes, catalog, "department")
    by_template = _aggregate(probs, classes, catalog, "lifecycle")
    by_category = _aggregate(probs, classes, catalog, "category")
    alternatives = [
        ClassifyAlternative(
            request_type=classes[i],
            name=catalog[classes[i]]["name"],
            confidence=round(float(probs[i]), 4),
        )
        for i in order[:3]
    ]
    route = tm.pretty_route(info.get("approval_route") or "Quy trình phê duyệt tiêu chuẩn")
    vocab = tm.vocab_for(model)
    support = vocab.support(text, [a.request_type for a in alternatives])
    unclear = vocab.known_words(text) == 0
    novel = not unclear and tm.is_novel(confidence, support)
    base = ClassifyRequestResult(
        predicted_request_type=code,
        predicted_request_name=info["name"],
        predicted_category=info["category"],
        predicted_category_label=info.get("category_label", info["category"]),
        predicted_department=info["department"],
        predicted_template=info["lifecycle"],
        confidence_request_type=round(confidence, 4),
        confidence_category=round(by_category[info["category"]], 4),
        confidence_department=round(by_dept[info["department"]], 4),
        confidence_template=round(by_template[info["lifecycle"]], 4),
        low_confidence=confidence < LOW_CONFIDENCE or novel or unclear,
        alternatives=alternatives,
        workflow_suggestion=f"{info['name']}: {route}",
        novel=novel,
        unclear=unclear,
        vocab_support=None if support is None else round(support, 3),
    )
    return merge_learned(base, text, [t for t in (learned or []) if t.code not in catalog])


def merge_learned(base: ClassifyRequestResult, text: str, learned: list) -> ClassifyRequestResult:
    """Đưa loại mới (bộ nhớ loại mới) vào kết quả: thành loại đề xuất nếu khớp rõ, hoặc vào danh sách khả năng."""
    if not learned or base.unclear:
        return base
    matches = tm.match_learned(text, [t.model_dump() for t in learned])
    scored = [(t, tm.learned_confidence(s)) for t, s in matches if s >= tm.LEARNED_MIN]
    if not scored:
        return base
    extra = [ClassifyAlternative(request_type=t["code"], name=t["name"], confidence=round(c, 4), source="learned")
             for t, c in scored]
    top, conf = scored[0]
    if (conf >= tm.LEARNED_SURE and conf > base.confidence_request_type) or (
        base.novel and conf >= tm.LEARNED_WHEN_NOVEL
    ):
        route = tm.pretty_route(top.get("approval_route") or "Quy trình phê duyệt tiêu chuẩn")
        alternatives = sorted([*extra, *base.alternatives], key=lambda a: -a.confidence)[:3]
        return base.model_copy(update={
            "predicted_request_type": top["code"],
            "predicted_request_name": top["name"],
            "predicted_category": top.get("category") or base.predicted_category,
            "predicted_category_label": top.get("category_label") or base.predicted_category_label,
            "predicted_department": top.get("department") or base.predicted_department,
            "predicted_template": top.get("lifecycle") or base.predicted_template,
            "confidence_request_type": round(conf, 4),
            "low_confidence": conf < LOW_CONFIDENCE,
            "alternatives": alternatives,
            "workflow_suggestion": f"{top['name']}: {route}",
            "source": "learned",
            "novel": False,
        })
    alternatives = sorted([*base.alternatives, *extra], key=lambda a: -a.confidence)[:3]
    return base.model_copy(update={"alternatives": alternatives})


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/classify", include_in_schema=False)  # Backward-compatible old endpoint
@router.post("/request", response_model=ClassifyRequestResult, summary="Phân loại yêu cầu tự động (NLP)")  # fmt: skip
def classify_request(body: ClassifyRequestInput):
    """
    Tự động nhận diện loại yêu cầu (mã catalog), bộ phận xử lý và quy trình phê duyệt
    dựa trên tiêu đề và nội dung tiếng Việt (có dấu hoặc không dấu).
    """
    full_text = f"{body.title}. {body.description}".strip(" .")
    if not full_text:
        raise HTTPException(
            status_code=400, detail="Tiêu đề hoặc mô tả không được để trống"
        )

    model, labels = get_nlp_model()
    if model is not None:
        try:
            return predict(model, labels, full_text, body.learned_types)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Lỗi suy luận NLP: {e}")

    fallback = heuristic_classify(full_text)
    return ClassifyRequestResult(
        predicted_request_type=fallback["type"],
        predicted_department=fallback["dept"],
        predicted_template=fallback["template"],
        # Keyword rules have no statistical confidence; never report a model-like score.
        confidence_request_type=0.0,
        confidence_department=0.0,
        confidence_template=0.0,
        low_confidence=True,
        workflow_suggestion="Quy trình gợi ý dựa trên từ khóa (Fallback)",
        method="keyword_heuristic",
        fallback_used=True,
    )
