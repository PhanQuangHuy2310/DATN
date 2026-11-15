"""
Router: Smart Risk Scoring — Tự động chọn mô hình XGBoost theo Domain nghiệp vụ

POST /ai/risk/score
  - Input: thông tin yêu cầu (loại, số tiền, người gửi, lịch sử...)
  - Output: risk_score (1-5), explanation, auto_approve_eligible

Kiến trúc Model Ensemble:
  - Master Model (risk_model.pkl):         Mô hình tổng quát mọi loại yêu cầu — fallback
  - Finance Model (risk_model_finance.pkl): Chuyên phát hiện gian lận tài chính
  - HR Model (risk_model_hr.pkl):          Chuyên phát hiện bất thường nhân sự
  - IT Model (risk_model_it.pkl):          Chuyên phát hiện rủi ro bảo mật IT

Quy tắc định tuyến (Routing):
  - request_type thuộc nhóm finance → dùng Finance Model
  - request_type thuộc nhóm hr/admin  → dùng HR Model
  - request_type thuộc nhóm it        → dùng IT Model
  - Không khớp / lỗi                 → fallback Master Model → Rule-based
"""

import json
import os
from typing import Any

import numpy as np

try:
    from config import get_settings
    from nlp_text import advance_tier, canonical_request_type
except (ImportError, AttributeError):
    from ai_service.config import get_settings
    from ai_service.nlp_text import advance_tier, canonical_request_type

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field, model_validator

settings = get_settings()
router = APIRouter()

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"
)

# ---------------------------------------------------------------------------
# Phân nhóm request_type theo domain để định tuyến model
# ---------------------------------------------------------------------------
# Mặc định khi registry chưa có "type_domains"; training/train.py ghi bảng đầy đủ
# (58 mã catalog v2) vào models/domain_model_registry.json.
FINANCE_TYPES = {
    "ADVANCE_SMALL", "ADVANCE_MEDIUM", "ADVANCE_LARGE", "EXPENSE_CLAIM",
    "REIMBURSEMENT", "VENDOR_PAYMENT", "BUDGET_REALLOCATION", "PURCHASE_REQUEST",
    "EQUIPMENT", "CONTRACT_APPROVAL",
}
HR_TYPES = {
    "LEAVE", "LEAVE_SPECIAL", "OVERTIME_REQ", "WFH_REQ", "BUSINESS_TRIP",
    "ATTENDANCE_ADJUSTMENT", "SALARY_ADJUSTMENT", "RESIGNATION",
}
IT_TYPES = {"ACCESS", "PROD_DATA_ACCESS", "SERVER_FIREWALL", "IT_SUPPORT", "LAPTOP_PROVISION"}
OTHER_TYPE = "__OTHER__"

_registry: dict | None = None


def _domain_registry() -> dict:
    global _registry
    if _registry is None:
        path = os.path.join(MODELS_DIR, "domain_model_registry.json")
        try:
            with open(path, encoding="utf-8") as f:
                _registry = json.load(f)
        except (OSError, ValueError):
            _registry = {}
    return _registry


def resolve_request_type(request_type: str, amount_vnd: float = 0.0) -> str:
    """Catalog code for any accepted spelling; legacy 'advance_payment' uses the amount."""
    if str(request_type or "").strip().lower() == "advance_payment" and amount_vnd > 0:
        return advance_tier(amount_vnd)
    return canonical_request_type(request_type)


def resolve_domain(request_type: str) -> str:
    code = canonical_request_type(request_type)
    type_domains = _domain_registry().get("type_domains")
    if type_domains:
        return type_domains.get(code, "master")
    if code in FINANCE_TYPES:
        return "finance"
    if code in HR_TYPES:
        return "hr"
    if code in IT_TYPES:
        return "it"
    return "master"


# ---------------------------------------------------------------------------
# Lazy model cache (load khi request đầu tiên đến, cache suốt vòng đời)
# ---------------------------------------------------------------------------
_model_cache: dict[str, Any] = {}
_model_load_error: str | None = None

MODEL_FILES = {
    "finance": ("risk_model_finance.pkl", "feature_cols_finance.json"),
    "hr": ("risk_model_hr.pkl", "feature_cols_hr.json"),
    "it": ("risk_model_it.pkl", "feature_cols_it.json"),
    "master": ("risk_model.pkl", "feature_columns.json"),
}


def _load_model(domain: str):
    """Load model theo domain, trả về (model, feature_cols, label_remap)."""
    global _model_load_error
    if domain in _model_cache:
        return _model_cache[domain]

    model_file, feat_file = MODEL_FILES.get(domain, MODEL_FILES["master"])
    model_path = os.path.join(MODELS_DIR, model_file)
    feat_path = os.path.join(MODELS_DIR, feat_file)

    if not os.path.exists(model_path):
        # Thử fallback về master
        if domain != "master":
            return _load_model("master")
        _model_load_error = f"Chưa có model tại {model_path}. Chạy training script."
        logger.warning(_model_load_error)
        return None, [], {}, {}

    try:
        import joblib

        model = joblib.load(model_path)

        feature_cols = []
        reverse_remap = {}

        if os.path.exists(feat_path):
            with open(feat_path, encoding="utf-8") as f:
                meta = json.load(f)
            if isinstance(meta, dict) and "feature_cols" in meta:
                feature_cols = meta["feature_cols"]
                reverse_remap = {
                    int(k): v for k, v in meta.get("reverse_remap", {}).items()
                }
            elif isinstance(meta, list):
                feature_cols = meta  # master model: plain list

        # Load global encoders (dùng chung)
        encoders = {}
        enc_path = os.path.join(MODELS_DIR, "encoders.json")
        if os.path.exists(enc_path):
            with open(enc_path, encoding="utf-8") as f:
                encoders = json.load(f)

        _model_cache[domain] = (model, feature_cols, encoders, reverse_remap)
        logger.success(
            f"Loaded [{domain}] model: {model_file} | features: {len(feature_cols)}"
        )
        return _model_cache[domain]

    except Exception as e:  # noqa: BLE001
        _model_load_error = str(e)
        logger.error(f"Lỗi load model [{domain}]: {e}")
        return None, [], {}, {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RiskInput(BaseModel):
    request_type: str = Field(
        "EXPENSE_CLAIM",
        description="Mã loại yêu cầu catalog v2 (VD: LEAVE); vẫn nhận mã cũ như leave_annual",
    )
    lifecycle_template: str = Field("A", description="Template A/B/C")
    risk_weight: int = Field(2, ge=1, le=5, description="Trọng số rủi ro mặc định")
    department: str = Field(
        "it",
        description="Phòng ban: it, hr, finance, marketing, sales, operations, legal",
    )
    amount_vnd: float = Field(0.0, ge=0, description="Số tiền yêu cầu (VNĐ)")
    budget_remaining_vnd: float = Field(
        500_000_000.0, ge=0, description="Ngân sách còn lại phòng ban (VNĐ)"
    )
    has_receipt: int = Field(1, description="1 nếu có chứng từ/hóa đơn, 0 nếu không")
    num_attachments: int = Field(1, ge=0, description="Số file đính kèm")
    user_role: str = Field(
        "junior", description="intern, junior, senior, lead, manager, director"
    )
    user_tenure_months: int = Field(12, ge=0, description="Thâm niên (tháng)")
    past_requests_count: int = Field(
        5, ge=0, description="Số yêu cầu đã gửi trong 30 ngày qua"
    )
    past_rejection_rate: float = Field(
        0.0, ge=0.0, le=1.0, description="Tỷ lệ bị từ chối trong quá khứ"
    )
    urgency: str = Field("medium", description="low, medium, high, urgent")
    is_off_hours: int = Field(0, description="1 nếu gửi ngoài giờ/cuối tuần")
    is_split_amount_suspect: int = Field(
        0, description="1 nếu nghi vấn chia nhỏ số tiền"
    )
    is_template_matched: int = Field(1, description="1 nếu điền đúng biểu mẫu chuẩn")
    description_length: int = Field(150, ge=0, description="Độ dài nội dung mô tả")

    @model_validator(mode="before")
    @classmethod
    def _remap_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map amount -> amount_vnd
            if "amount_vnd" not in data and "amount" in data:
                data["amount_vnd"] = data["amount"]
            # Map attachment_count -> num_attachments
            if "num_attachments" not in data and "attachment_count" in data:
                data["num_attachments"] = data["attachment_count"]
            # Map request_count_30d -> past_requests_count
            if "past_requests_count" not in data and "request_count_30d" in data:
                data["past_requests_count"] = data["request_count_30d"]
            # Map reject_count_30d / request_count_30d -> past_rejection_rate
            if "past_rejection_rate" not in data and "reject_count_30d" in data:
                req_cnt = (
                    data.get("request_count_30d")
                    or data.get("past_requests_count")
                    or 1
                )
                rej_cnt = data.get("reject_count_30d") or 0
                data["past_rejection_rate"] = min(
                    1.0, max(0.0, float(rej_cnt) / max(1, req_cnt))
                )
            # Map requester_dept_category -> department
            if "department" not in data and "requester_dept_category" in data:
                data["department"] = data["requester_dept_category"]
            # Map is_weekend_or_holiday -> is_off_hours
            if "is_off_hours" not in data and "is_weekend_or_holiday" in data:
                data["is_off_hours"] = 1 if data["is_weekend_or_holiday"] else 0
        return data


class RiskResult(BaseModel):
    risk_score: int = Field(
        ..., ge=1, le=5, description="Điểm rủi ro (1=thấp nhất, 5=cao nhất)"
    )
    risk_label: str = Field(..., description="low/medium/high/critical")
    confidence: float = Field(..., description="Độ tin cậy dự đoán (0-1)")
    auto_approve_eligible: bool = Field(
        ..., description="Đủ điều kiện Auto-Approve không"
    )
    domain_model_used: str = Field(
        ..., description="Domain model đã sử dụng: finance/hr/it/master"
    )
    explanation: dict = Field(default_factory=dict, description="Lý giải top features")
    fallback_used: bool = Field(False, description="True nếu dùng rule-based fallback")


RISK_LABELS = {1: "low", 2: "medium", 3: "medium", 4: "high", 5: "critical"}


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------


def rule_based_score(inp: RiskInput) -> tuple[int, dict]:
    score = inp.risk_weight
    reasons: dict = {}

    if inp.amount_vnd > inp.budget_remaining_vnd and inp.amount_vnd > 0:
        score += 3
        reasons["over_budget"] = (
            f"+3 (Vượt ngân sách: {inp.amount_vnd:,.0f} > {inp.budget_remaining_vnd:,.0f})"
        )
    elif inp.amount_vnd > 50_000_000:
        score += 2
        reasons["large_amount"] = "+2 (Số tiền lớn > 50 triệu)"

    if inp.amount_vnd > 0 and inp.has_receipt == 0:
        score += 1
        reasons["no_receipt"] = "+1 (Yêu cầu tài chính thiếu chứng từ)"
    if inp.is_split_amount_suspect:
        score += 2
        reasons["split_suspect"] = "+2 (Nghi vấn chia nhỏ giao dịch)"
    if inp.past_rejection_rate > 0.3:
        score += 1
        reasons["high_rejection"] = (
            f"+1 (Lịch sử bị từ chối {inp.past_rejection_rate * 100:.0f}%)"
        )
    if inp.is_template_matched == 0:
        score += 1
        reasons["bad_template"] = "+1 (Biểu mẫu không đúng chuẩn)"
    if inp.is_off_hours:
        score += 1
        reasons["off_hours"] = "+1 (Gửi ngoài giờ làm việc)"

    return min(5, max(1, round(score))), reasons


# ---------------------------------------------------------------------------
# Feature extraction — đồng nhất với training pipeline
# ---------------------------------------------------------------------------


def build_feature_vector(
    inp: RiskInput, feature_cols: list, encoders: dict
) -> np.ndarray:
    type_codes = encoders.get("request_type", {})
    code = resolve_request_type(inp.request_type, inp.amount_vnd)
    req_enc = type_codes.get(code, type_codes.get(OTHER_TYPE, 0))
    dept_enc = encoders.get("department", {}).get(str(inp.department).lower(), 0)
    role_enc = encoders.get("user_role", {}).get(inp.user_role, 2)
    prio_enc = encoders.get("priority_level", {}).get(inp.urgency, 2)

    amt = float(inp.amount_vnd)
    budget = float(inp.budget_remaining_vnd)

    feat_map = {
        "request_type_enc": float(req_enc),
        "risk_weight": float(inp.risk_weight),
        "department_enc": float(dept_enc),
        "user_role_enc": float(role_enc),
        "priority_level_enc": float(prio_enc),
        "amount_log": float(np.log1p(amt)),
        "amount_millions": amt / 1_000_000.0,
        "budget_log": float(np.log1p(max(0.0, budget))),
        "amount_to_budget_ratio": amt / (budget + 1.0),
        "is_over_budget": float(amt > budget),
        "is_split_amount_suspect": float(inp.is_split_amount_suspect),
        "has_receipt": float(inp.has_receipt),
        "num_attachments": float(inp.num_attachments),
        "no_receipt_has_amount": float(amt > 0 and inp.has_receipt == 0),
        "user_tenure_months": float(inp.user_tenure_months),
        "past_requests_count": float(inp.past_requests_count),
        "past_rejection_rate": float(inp.past_rejection_rate),
        "high_rejection_rate": float(inp.past_rejection_rate > 0.25),
        "is_off_hours": float(inp.is_off_hours),
        "is_template_matched": float(inp.is_template_matched),
    }

    if feature_cols:
        return np.array(
            [[feat_map.get(c, 0.0) for c in feature_cols]], dtype=np.float32
        )
    return np.array([list(feat_map.values())], dtype=np.float32)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/score",
    response_model=RiskResult,
    summary="Chấm điểm rủi ro thông minh (Multi-Domain XGBoost)",
)
def score_risk(body: RiskInput):
    """
    Tự động chọn mô hình XGBoost phù hợp theo domain nghiệp vụ của yêu cầu:
    - **Finance** (tạm ứng, thanh toán, mua sắm, bán hàng): rủi ro tài chính
    - **HR** (nghỉ, làm thêm, nhân sự): bất thường nhân sự
    - **IT** (quyền truy cập, server, sự cố bảo mật): rủi ro bảo mật
    - **Master**: các loại còn lại và loại chưa có trong catalog
    """
    resolved_type = resolve_request_type(body.request_type, body.amount_vnd)
    domain = resolve_domain(resolved_type)
    model, feature_cols, encoders, reverse_remap = _load_model(domain)

    if model is not None and feature_cols:
        try:
            X = build_feature_vector(body, feature_cols, encoders)
            pred_idx = int(model.predict(X)[0])

            # Đổi về risk score gốc (1-5) nếu có reverse_remap (domain model)
            if reverse_remap:
                pred = reverse_remap.get(pred_idx, pred_idx + 1)
            else:
                pred = pred_idx + 1  # master model: 0..4 -> 1..5

            probs = model.predict_proba(X)[0]
            confidence = float(np.max(probs))

            importance = dict(zip(feature_cols, model.feature_importances_))
            top_features = {
                k: round(float(v) * 100, 2)
                for k, v in sorted(importance.items(), key=lambda x: -x[1])[:5]
            }

            explanation = {
                "method": f"xgboost_{domain}_model",
                "domain_routing": domain,
                "request_type_resolved": resolved_type,
                "top_features": top_features,
                "proba_per_class": [round(float(p), 4) for p in probs],
            }
            fallback = False

        except Exception as e:  # noqa: BLE001
            logger.error(f"XGBoost [{domain}] predict error: {e}, fallback rule-based")
            pred, reasons = rule_based_score(body)
            confidence = 0.75
            fallback = True
            explanation = {"method": "rule_based_fallback", "reasons": reasons}
    else:
        pred, reasons = rule_based_score(body)
        confidence = 0.80
        fallback = True
        explanation = {
            "method": "rule_based",
            "note": _model_load_error or "Model chưa được load",
            "reasons": reasons,
        }

    auto_approve = pred <= settings.auto_approve_max_risk and (
        not settings.auto_approve_only_template_a or body.lifecycle_template == "A"
    )

    logger.info(
        f"Risk [{domain}]: {pred}/5 | type={body.request_type} "
        f"| auto={auto_approve} | fallback={fallback}"
    )

    return RiskResult(
        risk_score=pred,
        risk_label=RISK_LABELS.get(pred, "unknown"),
        confidence=round(confidence, 4),
        auto_approve_eligible=auto_approve,
        domain_model_used=domain,
        explanation=explanation,
        fallback_used=fallback,
    )
