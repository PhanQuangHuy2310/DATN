"""
Training Script 1/3: Sinh dữ liệu tổng hợp (Synthetic Data Generation)

Vì dự án chưa có dữ liệu thực, script này tạo ~5000 mẫu yêu cầu giả lập
dựa trên các quy tắc nghiệp vụ trong plan.md Section 5.

Output: training/data/synthetic_requests.csv

Chạy: python training/generate_synthetic_data.py
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

# Seed để kết quả reproducible
np.random.seed(42)

# ---------------------------------------------------------------------------
# 1. Định nghĩa các loại yêu cầu (theo plan.md Section 5)
# ---------------------------------------------------------------------------

REQUEST_TYPES = [
    # name, risk_weight, template, dept_categories, has_amount, typical_amount_range
    {"name": "leave_short",      "risk_weight": 1, "template": "A", "depts": ["operations","commerce","hr_admin","technology","booking"],     "has_amount": False, "amount_range": (0, 0)},
    {"name": "leave_long",       "risk_weight": 3, "template": "A", "depts": ["operations","commerce","hr_admin"],                             "has_amount": False, "amount_range": (0, 0)},
    {"name": "purchase_low",     "risk_weight": 2, "template": "B", "depts": ["operations","commerce","hr_admin","technology"],               "has_amount": True,  "amount_range": (500_000, 10_000_000)},
    {"name": "purchase_high",    "risk_weight": 5, "template": "B", "depts": ["operations","commerce","finance"],                             "has_amount": True,  "amount_range": (10_000_000, 200_000_000)},
    {"name": "room_booking",     "risk_weight": 1, "template": "A", "depts": ["operations","commerce","technology","hr_admin","booking"],     "has_amount": False, "amount_range": (0, 0)},
    {"name": "expense_claim",    "risk_weight": 2, "template": "A", "depts": ["operations","commerce","technology"],                          "has_amount": True,  "amount_range": (100_000, 5_000_000)},
    {"name": "overtime",         "risk_weight": 2, "template": "A", "depts": ["operations","technology","booking"],                           "has_amount": False, "amount_range": (0, 0)},
    {"name": "asset_request",    "risk_weight": 3, "template": "C", "depts": ["technology","operations","commerce"],                          "has_amount": True,  "amount_range": (5_000_000, 50_000_000)},
    {"name": "late_checkin",     "risk_weight": 1, "template": "A", "depts": ["operations","commerce","hr_admin","technology","booking","finance"], "has_amount": False, "amount_range": (0, 0)},
    {"name": "contract_approval","risk_weight": 5, "template": "C", "depts": ["commerce","finance","hr_admin"],                               "has_amount": True,  "amount_range": (50_000_000, 2_000_000_000)},
    {"name": "it_request",       "risk_weight": 3, "template": "B", "depts": ["technology","operations","commerce"],                          "has_amount": False, "amount_range": (0, 0)},
    {"name": "facility_repair",  "risk_weight": 2, "template": "B", "depts": ["hr_admin","operations"],                                       "has_amount": True,  "amount_range": (500_000, 20_000_000)},
    {"name": "flashsale_voucher","risk_weight": 4, "template": "B", "depts": ["commerce","operations"],                                       "has_amount": True,  "amount_range": (1_000_000, 100_000_000)},
    {"name": "data_extract",     "risk_weight": 3, "template": "B", "depts": ["technology","finance"],                                        "has_amount": False, "amount_range": (0, 0)},
    {"name": "refund",           "risk_weight": 2, "template": "A", "depts": ["commerce","operations","finance"],                             "has_amount": True,  "amount_range": (50_000, 3_000_000)},
    {"name": "onboarding",       "risk_weight": 3, "template": "C", "depts": ["hr_admin"],                                                    "has_amount": False, "amount_range": (0, 0)},
]

DEPT_BUDGET_LIMITS = {
    "operations": 20_000_000,
    "commerce": 50_000_000,
    "technology": 30_000_000,
    "booking": 10_000_000,
    "finance": 100_000_000,
    "hr_admin": 15_000_000,
    "other": 5_000_000,
}

DEPT_MAP = {d: i for i, d in enumerate(DEPT_BUDGET_LIMITS.keys())}
TEMPLATE_MAP = {"A": 0, "B": 1, "C": 2}
TYPE_MAP = {rt["name"]: i for i, rt in enumerate(REQUEST_TYPES)}


# ---------------------------------------------------------------------------
# 2. Hàm tính risk label (ground truth)
# ---------------------------------------------------------------------------

def compute_risk_label(row: dict) -> int:
    """
    Tính risk score (1-5) dựa trên các điều kiện nghiệp vụ.
    Đây là label được dùng để train XGBoost.
    
    Logic bám sát rule-based trong routers/risk.py nhưng thêm noise để
    XGBoost học được pattern phức tạp hơn rule đơn giản.
    """
    score = row["risk_weight"]

    # --- Tài chính ---
    if row["amount"] > 50_000_000:
        score += 2
    elif row["amount"] > 10_000_000:
        score += 1
    elif row["amount"] > 2_000_000:
        score += 0.5

    # --- Thiếu chứng từ khi có tiền ---
    if row["amount"] > 0 and row["attachment_count"] == 0:
        score += 1

    # --- Nghỉ phép quá hạn mức ---
    if row["days_requested"] > row["leave_balance_remaining"] and row["days_requested"] > 0:
        score += 1.5

    # --- Lịch sử từ chối ---
    if row["reject_count_30d"] >= 3:
        score += 1.5
    elif row["reject_count_30d"] >= 1:
        score += 0.5

    # --- Tần suất nộp đơn cao ---
    if row["request_count_30d"] >= 7:
        score += 1
    elif row["request_count_30d"] >= 4:
        score += 0.5

    # --- Gấp / Cuối tuần ---
    if row["is_near_deadline"]:
        score += 0.5
    if row["is_weekend_or_holiday"]:
        score += 0.5

    # --- Cấp độ người gửi: Staff (level 1) thường rủi ro cao hơn cho đơn lớn ---
    if row["requester_level"] == 1 and row["amount"] > 10_000_000:
        score += 0.5

    # --- Tỷ lệ amount / limit ---
    if row["amount_vs_limit_ratio"] > 1.0:
        score += 1
    elif row["amount_vs_limit_ratio"] > 0.7:
        score += 0.5

    # Thêm noise nhỏ để tránh model overfit vào rule
    noise = np.random.normal(0, 0.3)
    score += noise

    # Clip về [1, 5] và làm tròn
    return int(np.clip(round(score), 1, 5))


# ---------------------------------------------------------------------------
# 3. Sinh một mẫu dữ liệu
# ---------------------------------------------------------------------------

def generate_sample(rt: dict) -> dict:
    dept = np.random.choice(rt["depts"])
    budget_limit = DEPT_BUDGET_LIMITS.get(dept, 5_000_000)

    # Tạo amount
    if rt["has_amount"]:
        lo, hi = rt["amount_range"]
        # Phần lớn giao dịch nhỏ, ít giao dịch lớn (lognormal)
        amount = float(np.clip(np.random.lognormal(
            mean=np.log(max(lo, 1) + (hi - lo) * 0.3),
            sigma=0.8
        ), lo, hi))
        amount = round(amount / 1000) * 1000  # Làm tròn nghìn
    else:
        amount = 0.0

    amount_vs_limit = amount / budget_limit if budget_limit > 0 else 0.0

    # Ngày nghỉ
    if rt["name"] in ("leave_short", "leave_long"):
        days = np.random.choice([1, 2, 3, 4, 5, 7, 10, 14], p=[0.3, 0.25, 0.15, 0.1, 0.1, 0.05, 0.03, 0.02])
    else:
        days = 0

    # Số phép còn lại
    leave_balance = int(np.random.choice([0, 1, 2, 3, 5, 7, 10, 12], p=[0.05, 0.1, 0.15, 0.15, 0.2, 0.15, 0.1, 0.1]))

    # Level người gửi (1-5, phần lớn staff level 1-2)
    level = int(np.random.choice([1, 2, 3, 4, 5], p=[0.45, 0.3, 0.15, 0.07, 0.03]))

    # Lịch sử
    req_count = int(np.random.choice([0, 1, 2, 3, 4, 5, 8, 10], p=[0.1, 0.25, 0.25, 0.15, 0.1, 0.07, 0.05, 0.03]))
    reject_count = int(np.random.choice([0, 1, 2, 3], p=[0.6, 0.25, 0.1, 0.05]))
    reject_count = min(reject_count, req_count)

    # File đính kèm (tài chính thường có file)
    if rt["has_amount"] and amount > 500_000:
        attachment_count = int(np.random.choice([0, 1, 2, 3], p=[0.15, 0.5, 0.25, 0.1]))
    else:
        attachment_count = int(np.random.choice([0, 1, 2], p=[0.5, 0.4, 0.1]))

    # Gấp và cuối tuần
    is_near_deadline = bool(np.random.choice([0, 1], p=[0.85, 0.15]))
    is_weekend = bool(np.random.choice([0, 1], p=[0.8, 0.2]))

    row = {
        "request_type": rt["name"],
        "request_type_enc": TYPE_MAP[rt["name"]],
        "lifecycle_template": rt["template"],
        "lifecycle_template_enc": TEMPLATE_MAP[rt["template"]],
        "risk_weight": rt["risk_weight"],
        "amount": amount,
        "amount_log": float(np.log1p(amount)),
        "amount_millions": amount / 1_000_000,
        "amount_vs_limit_ratio": round(amount_vs_limit, 4),
        "days_requested": days,
        "requester_level": level,
        "requester_dept": dept,
        "requester_dept_enc": DEPT_MAP.get(dept, 6),
        "leave_balance_remaining": leave_balance,
        "leave_deficit": max(0, days - leave_balance),
        "request_count_30d": req_count,
        "reject_count_30d": reject_count,
        "reject_ratio_30d": round(reject_count / max(1, req_count), 4),
        "attachment_count": attachment_count,
        "has_attachment": int(attachment_count > 0),
        "is_near_deadline": int(is_near_deadline),
        "is_weekend_or_holiday": int(is_weekend),
        "no_attachment_financial": int(amount > 0 and attachment_count == 0),
    }

    row["risk_score"] = compute_risk_label(row)
    return row


# ---------------------------------------------------------------------------
# 4. Main: Sinh dataset
# ---------------------------------------------------------------------------

def generate_dataset(n_samples: int = 5000) -> pd.DataFrame:
    rows = []
    # Phân phối đều nhưng có trọng số (loại phổ biến nhiều mẫu hơn)
    type_weights = [0.15, 0.08, 0.1, 0.05, 0.12, 0.08, 0.08, 0.04, 0.1, 0.02, 0.04, 0.04, 0.02, 0.02, 0.04, 0.02]
    type_weights = [w / sum(type_weights) for w in type_weights]  # Normalize

    for _ in range(n_samples):
        rt = np.random.choice(REQUEST_TYPES, p=type_weights)
        rows.append(generate_sample(rt))

    df = pd.DataFrame(rows)

    # Kiểm tra phân phối nhãn
    print("\n📊 Phân phối Risk Score:")
    dist = df["risk_score"].value_counts().sort_index()
    for score, count in dist.items():
        bar = "█" * (count // 50)
        print(f"  Score {score}: {count:4d} mẫu  {bar}")

    print(f"\n📊 Phân phối loại yêu cầu:")
    type_dist = df["request_type"].value_counts()
    for rtype, count in type_dist.items():
        print(f"  {rtype:25s}: {count:4d} mẫu")

    return df


if __name__ == "__main__":
    print("🚀 Đang sinh synthetic data cho Risk Scoring model...")
    print(f"   Số mẫu: 5,000")
    print(f"   Số loại yêu cầu: {len(REQUEST_TYPES)}")

    os.makedirs("training/data", exist_ok=True)

    df = generate_dataset(n_samples=5000)

    output_path = "training/data/synthetic_requests.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # Lưu feature columns (để serve đúng thứ tự)
    feature_cols = [
        "request_type_enc", "lifecycle_template_enc", "risk_weight",
        "amount_log", "amount_millions", "amount_vs_limit_ratio",
        "days_requested", "requester_level", "requester_dept_enc",
        "leave_balance_remaining", "leave_deficit",
        "request_count_30d", "reject_count_30d", "reject_ratio_30d",
        "attachment_count", "has_attachment",
        "is_near_deadline", "is_weekend_or_holiday", "no_attachment_financial",
    ]
    os.makedirs("models", exist_ok=True)
    with open("models/feature_columns.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    print(f"\n✅ Dataset đã lưu tại: {output_path}")
    print(f"✅ Feature columns đã lưu tại: models/feature_columns.json")
    print(f"   Tổng số mẫu: {len(df):,}")
    print(f"   Số features: {len(feature_cols)}")
    print(f"\n➡️  Bước tiếp theo: python training/train_risk_model.py")
