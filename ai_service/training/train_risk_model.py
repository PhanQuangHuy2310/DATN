"""
Training Script: Train Enterprise Risk Scoring & Anomaly Detection Model (XGBoost)

Hỗ trợ tự động nhận diện dataset:
  1. training/data/enterprise_requests_dataset_large.csv (50.000 mẫu đa dạng)
  2. training/data/eapproval_risk_10000.csv (10.000 mẫu)

Bao gồm các chỉ số phát hiện gian lận nâng cao:
  - is_split_amount_suspect: Nghi vấn chia nhỏ giao dịch lách hạn mức
  - is_over_budget: Vượt ngân sách phòng ban
  - no_receipt_has_amount: Đơn có tiền nhưng không có hóa đơn
  - high_rejection_rate: Lịch sử bị reject cao
  - is_off_hours: Gửi ban đêm / ngày nghỉ

Output:
  - models/risk_model.pkl
  - models/feature_columns.json
  - models/encoders.json
  - training/data/evaluation_report.txt

Cách chạy:
  python training/train_risk_model.py
"""
import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
# Cấu hình đường dẫn
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "training", "data")

CANDIDATE_DATA_PATHS = [
    os.path.join(DATA_DIR, "enterprise_requests_dataset_large.csv"),
    os.path.join(DATA_DIR, "eapproval_risk_10000.csv"),
    os.path.join(DATA_DIR, "synthetic_requests.csv"),
]

MODEL_PATH = os.path.join(MODELS_DIR, "risk_model.pkl")
FEATURE_COLS_PATH = os.path.join(MODELS_DIR, "feature_columns.json")
ENCODERS_PATH = os.path.join(MODELS_DIR, "encoders.json")
REPORT_PATH = os.path.join(DATA_DIR, "evaluation_report.txt")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def load_dataset() -> pd.DataFrame:
    for path in CANDIDATE_DATA_PATHS:
        if os.path.exists(path):
            print(f"[*] Tìm thấy file dữ liệu: {path}")
            df = pd.read_csv(path)
            print(f"[+] Tải thành công {len(df):,} dòng dữ liệu.")
            print("\n[+] Phân bố nhãn risk_score:")
            dist = df["risk_score"].value_counts().sort_index()
            for score, cnt in dist.items():
                print(f"    - Risk Score {score}: {cnt:,} mẫu ({cnt/len(df)*100:.1f}%)")
            return df

    raise FileNotFoundError(f"Không tìm thấy file dữ liệu nào trong: {CANDIDATE_DATA_PATHS}")


def preprocess_and_feature_engineer(df: pd.DataFrame):
    df = df.copy()

    # 1. Mã hóa các biến phân loại (Categorical Encoders)
    categorical_cols = ["request_type", "department", "user_role", "priority_level"]
    encoders = {}

    for col in categorical_cols:
        if col in df.columns:
            le = LabelEncoder()
            df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
            encoders[col] = {label: int(idx) for idx, label in enumerate(le.classes_)}

    # 2. Xử lý logic nghiệp vụ & Feature Engineering
    if "amount_vnd" in df.columns:
        df["amount_log"] = np.log1p(df["amount_vnd"].astype(float))
        df["amount_millions"] = df["amount_vnd"] / 1_000_000.0

    if "budget_remaining_vnd" in df.columns:
        df["budget_log"] = np.log1p(np.maximum(0, df["budget_remaining_vnd"].astype(float)))
        df["amount_to_budget_ratio"] = df["amount_vnd"] / (df["budget_remaining_vnd"] + 1.0)
        if "is_over_budget" not in df.columns:
            df["is_over_budget"] = (df["amount_vnd"] > df["budget_remaining_vnd"]).astype(int)

    if "has_receipt" in df.columns and "amount_vnd" in df.columns:
        df["no_receipt_has_amount"] = ((df["amount_vnd"] > 0) & (df["has_receipt"] == 0)).astype(int)

    if "past_rejection_rate" in df.columns:
        df["high_rejection_rate"] = (df["past_rejection_rate"].astype(float) > 0.25).astype(int)

    # 3. Danh sách đặc trưng phục vụ huấn luyện
    candidate_features = [
        # Categorical encoded
        "request_type_enc",
        "department_enc",
        "user_role_enc",
        "priority_level_enc",
        # Tài chính & ngân sách
        "amount_log",
        "amount_millions",
        "budget_log",
        "amount_to_budget_ratio",
        "is_over_budget",
        # Gian lận & bất thường
        "is_split_amount_suspect",
        "has_receipt",
        "num_attachments",
        "no_receipt_has_amount",
        # Người dùng & thâm niên
        "user_tenure_months",
        "past_requests_count",
        "past_rejection_rate",
        "high_rejection_rate",
        # Bối cảnh gửi đơn
        "is_off_hours",
        "is_template_matched",
    ]

    selected_features = [f for f in candidate_features if f in df.columns]

    X = df[selected_features].values.astype(np.float32)
    y = df["risk_score"].values.astype(int)
    y_zero_indexed = y - 1  # 1..5 -> 0..4

    print(f"\n[+] Số lượng features sử dụng: {len(selected_features)}")
    print(f"[+] Danh sách features: {selected_features}")
    print(f"[+] Kích thước ma trận X: {X.shape}, y: {y_zero_indexed.shape}")

    return X, y_zero_indexed, selected_features, encoders


def train_xgboost(X_train, y_train, X_val, y_val):
    print("\n[+] Đang khởi tạo và huấn luyện XGBClassifier trên tập dữ liệu lớn...")
    model = xgb.XGBClassifier(
        n_estimators=350,
        max_depth=6,
        learning_rate=0.07,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=2,
        gamma=0.05,
        reg_alpha=0.1,
        reg_lambda=1.0,
        num_class=5,
        objective="multi:softmax",
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
        early_stopping_rounds=30,
        verbosity=1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=50,
    )
    return model


def evaluate_and_save(model, X_test, y_test, feature_cols, encoders):
    print("\n" + "=" * 65)
    print("      KẾT QUẢ ĐÁNH GIÁ MÔ HÌNH RISK & FRAUD SCORING")
    print("=" * 65)

    y_pred = model.predict(X_test)
    y_test_orig = y_test + 1
    y_pred_orig = y_pred + 1

    acc = accuracy_score(y_test_orig, y_pred_orig)
    f1_macro = f1_score(y_test_orig, y_pred_orig, average="macro")
    f1_weighted = f1_score(y_test_orig, y_pred_orig, average="weighted")

    print(f"\n* Accuracy:       {acc*100:.2f}%")
    print(f"* Macro F1:       {f1_macro:.4f}")
    print(f"* Weighted F1:    {f1_weighted:.4f}")

    target_names = [f"Risk {i}" for i in range(1, 6)]
    report = classification_report(y_test_orig, y_pred_orig, target_names=target_names, digits=4)
    print("\n* Báo cáo phân loại chi tiết (Classification Report):")
    print(report)

    cm = confusion_matrix(y_test_orig, y_pred_orig, labels=[1, 2, 3, 4, 5])
    print("* Ma trận nhầm lẫn (Confusion Matrix):")
    print("        Pred 1  Pred 2  Pred 3  Pred 4  Pred 5")
    for i, row in enumerate(cm):
        row_str = "  ".join(f"{val:6d}" for val in row)
        print(f"True {i+1}: {row_str}")

    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("\n* Top 10 đặc trưng quan trọng nhất (Feature Importance):")
    top_features_report = []
    for rank, idx in enumerate(sorted_idx[:10], 1):
        feat_name = feature_cols[idx]
        score = importances[idx]
        bar = "#" * int(score * 100)
        line = f"  {rank:2d}. {feat_name:26s}: {score*100:5.2f}% {bar}"
        print(line)
        top_features_report.append(line)

    print("\n[+] Đang lưu các files mô hình và cấu hình...")
    joblib.dump(model, MODEL_PATH)
    print(f"    -> Đã lưu mô hình: {MODEL_PATH}")

    with open(FEATURE_COLS_PATH, "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, indent=2, ensure_ascii=False)

    with open(ENCODERS_PATH, "w", encoding="utf-8") as f:
        json.dump(encoders, f, indent=2, ensure_ascii=False)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("BÁO CÁO HUẤN LUYỆN MÔ HÌNH XGBOOST RISK & FRAUD SCORING (50,000 MẪU)\n")
        f.write(f"Thời gian: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Số lượng mẫu test: {len(y_test):,}\n")
        f.write(f"Accuracy: {acc*100:.2f}%\n")
        f.write(f"Macro F1: {f1_macro:.4f}\n")
        f.write(f"Weighted F1: {f1_weighted:.4f}\n\n")
        f.write("CLASSIFICATION REPORT:\n")
        f.write(report + "\n")
        f.write("CONFUSION MATRIX:\n")
        f.write(np.array2string(cm) + "\n\n")
        f.write("TOP 10 FEATURES:\n")
        f.write("\n".join(top_features_report) + "\n")

    print(f"    -> Đã lưu báo cáo: {REPORT_PATH}")
    print("[SUCCESS] Huấn luyện mô hình rủi ro hoàn tất 100%!")


def main():
    print("=" * 65)
    print("   CHẠY HUẤN LUYỆN MÔ HÌNH RISK & FRAUD SCORING (50.000 MẪU)")
    print("=" * 65)

    df = load_dataset()
    X, y, feature_cols, encoders = preprocess_and_feature_engineer(df)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    print(f"[+] Kích thước Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")

    model = train_xgboost(X_train, y_train, X_val, y_val)
    evaluate_and_save(model, X_test, y_test, feature_cols, encoders)


if __name__ == "__main__":
    main()
