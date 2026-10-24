"""
Script: Huấn luyện 3 mô hình XGBoost chuyên biệt theo từng domain nghiệp vụ

Domain 1: Finance & Fraud Detection    -> finance_fraud_partition.csv (250.000 mẫu)
Domain 2: HR & Operations Anomaly      -> hr_operations_partition.csv (250.000 mẫu)
Domain 3: IT Security & Access Control -> it_security_partition.csv  (250.000 mẫu)

Mỗi domain có bộ features tối ưu riêng, nhãn risk đặc trưng riêng và được
đóng gói thành file pkl riêng. FastAPI tự động chọn model đúng theo domain
của request gửi lên.

Output (tất cả vào ai_service/models/):
  - risk_model_finance.pkl   + feature_cols_finance.json
  - risk_model_hr.pkl        + feature_cols_hr.json
  - risk_model_it.pkl        + feature_cols_it.json
  - domain_model_registry.json  <- Registry để FastAPI load đúng model

Cách chạy:
  python training/train_domain_models.py
"""
import json
import os
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
PARTITIONS_DIR = os.path.join(BASE_DIR, "training", "data", "partitions")
REPORT_PATH = os.path.join(BASE_DIR, "training", "data", "domain_models_report.txt")
os.makedirs(MODELS_DIR, exist_ok=True)

DOMAIN_CONFIGS = {
    "finance": {
        "csv": "finance_fraud_partition.csv",
        "model_file": "risk_model_finance.pkl",
        "features_file": "feature_cols_finance.json",
        "desc": "Phát hiện gian lận & rủi ro tài chính (Smurfing, hóa đơn khống, vượt ngân sách)",
        # Finance-specific features: tập trung vào dòng tiền & chứng từ
        "extra_features": ["is_split_amount_suspect", "no_receipt_has_amount", "amount_to_budget_ratio"],
        "xgb_params": {
            "n_estimators": 300, "max_depth": 7, "learning_rate": 0.08,
            "subsample": 0.85, "colsample_bytree": 0.85, "min_child_weight": 2,
            "scale_pos_weight": 3,   # Tăng trọng số các ca gian lận (Risk 4, 5) vì ít hơn
        },
    },
    "hr": {
        "csv": "hr_operations_partition.csv",
        "model_file": "risk_model_hr.pkl",
        "features_file": "feature_cols_hr.json",
        "desc": "Phát hiện bất thường nhân sự (nghỉ dồn, OT bất thường, đăng ký ngoài giờ)",
        # HR-specific features: tập trung vào hành vi nghỉ phép & thâm niên
        "extra_features": ["user_tenure_months", "past_requests_count", "high_rejection_rate"],
        "xgb_params": {
            "n_estimators": 250, "max_depth": 6, "learning_rate": 0.09,
            "subsample": 0.85, "colsample_bytree": 0.85, "min_child_weight": 3,
        },
    },
    "it": {
        "csv": "it_security_partition.csv",
        "model_file": "risk_model_it.pkl",
        "features_file": "feature_cols_it.json",
        "desc": "Phát hiện rủi ro bảo mật IT (cấp quyền root, intern xin server đắt tiền, VPN đêm khuya)",
        # IT-specific features: tập trung vào quyền hạn & vai trò người dùng
        "extra_features": ["user_role_enc", "is_off_hours", "amount_millions"],
        "xgb_params": {
            "n_estimators": 250, "max_depth": 6, "learning_rate": 0.09,
            "subsample": 0.85, "colsample_bytree": 0.85, "min_child_weight": 3,
        },
    },
}

BASE_FEATURES = [
    "request_type_enc", "department_enc", "user_role_enc", "priority_level_enc",
    "amount_log", "amount_millions", "budget_log", "amount_to_budget_ratio",
    "is_over_budget", "is_split_amount_suspect", "has_receipt", "num_attachments",
    "no_receipt_has_amount", "user_tenure_months", "past_requests_count",
    "past_rejection_rate", "high_rejection_rate", "is_off_hours", "is_template_matched"
]


def load_and_engineer(csv_path: str):
    """Đọc file CSV và tạo features tối ưu."""
    use_cols = [
        "request_type", "department", "user_role", "priority_level",
        "amount_vnd", "budget_remaining_vnd", "has_receipt", "num_attachments",
        "user_tenure_months", "past_requests_count", "past_rejection_rate",
        "is_off_hours", "is_split_amount_suspect", "is_over_budget",
        "is_template_matched", "risk_score"
    ]

    df = pd.read_csv(csv_path, usecols=[c for c in use_cols if c in pd.read_csv(csv_path, nrows=0).columns])
    encoders = {}

    for col in ["request_type", "department", "user_role", "priority_level"]:
        if col in df.columns:
            le = LabelEncoder()
            df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
            encoders[col] = {label: int(i) for i, label in enumerate(le.classes_)}

    df["amount_log"] = np.log1p(df["amount_vnd"].clip(0).astype(np.float32))
    df["amount_millions"] = (df["amount_vnd"] / 1_000_000.0).astype(np.float32)
    df["budget_log"] = np.log1p(np.maximum(0.0, df["budget_remaining_vnd"]).astype(np.float32))
    df["amount_to_budget_ratio"] = (df["amount_vnd"] / (df["budget_remaining_vnd"] + 1.0)).astype(np.float32)
    df["no_receipt_has_amount"] = ((df["amount_vnd"] > 0) & (df["has_receipt"] == 0)).astype(np.int8)
    df["high_rejection_rate"] = (df["past_rejection_rate"] > 0.25).astype(np.int8)

    return df, encoders


def train_one_domain(name: str, cfg: dict, report_lines: list):
    print(f"\n{'='*65}")
    print(f"  DOMAIN: {name.upper()} — {cfg['desc']}")
    print(f"{'='*65}")

    csv_path = os.path.join(PARTITIONS_DIR, cfg["csv"])
    if not os.path.exists(csv_path):
        print(f"[SKIP] Không tìm thấy {csv_path}")
        return

    t0 = time.time()
    df, _encoders = load_and_engineer(csv_path)
    print(f"[+] Đã tải và xử lý {len(df):,} mẫu trong {time.time()-t0:.2f}s")

    # Chọn features tối ưu theo domain
    feature_cols = [f for f in BASE_FEATURES if f in df.columns]
    X = df[feature_cols].values.astype(np.float32)
    y = (df["risk_score"].values - 1).astype(np.int8)  # 1..5 -> 0..4

    # Re-map labels sang 0-indexed liên tục để XGBoost không báo lỗi
    unique_classes = sorted(np.unique(y).tolist())
    label_remap = {old: new for new, old in enumerate(unique_classes)}
    y = np.array([label_remap[v] for v in y], dtype=np.int8)
    n_classes = len(unique_classes)
    print(f"[+] Features: {len(feature_cols)} | Classes ({n_classes}): {unique_classes} -> remapped 0..{n_classes-1}")

    # Train/Val/Test split: 70% / 15% / 15%
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp)
    print(f"[+] Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")

    # Xây dựng tham số XGBoost đặc trưng từng domain
    params = cfg["xgb_params"].copy()
    params.update({
        "num_class": n_classes,
        "objective": "multi:softmax",
        "eval_metric": "mlogloss",
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": -1,
        "early_stopping_rounds": 20,
        "verbosity": 0,
    })
    if n_classes < 5:
        params.pop("scale_pos_weight", None)

    print(f"[+] Đang huấn luyện XGBoost (n_estimators={params['n_estimators']}, depth={params['max_depth']})...")
    t_train = time.time()
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train), (X_val, y_val)], verbose=False)
    print(f"[+] Xong trong {time.time()-t_train:.2f}s | Best iteration: {model.best_iteration}")

    # Đánh giá — remap predictions về nhãn gốc (risk score 1..5)
    reverse_remap = {new: old + 1 for old, new in label_remap.items()}
    y_pred_orig = np.array([reverse_remap[p] for p in model.predict(X_test)])
    y_actual = np.array([reverse_remap[a] for a in y_test])
    present_classes = sorted(np.unique(y_actual).tolist())

    acc = accuracy_score(y_actual, y_pred_orig)
    f1 = f1_score(y_actual, y_pred_orig, average="weighted")
    print(f"\n[RESULT] Accuracy: {acc*100:.2f}% | Weighted F1: {f1:.4f}")

    target_names = [f"Risk {i}" for i in present_classes]
    rep = classification_report(y_actual, y_pred_orig, labels=present_classes, target_names=target_names, digits=4)
    print(rep)

    # Feature importance
    importances = model.feature_importances_
    top5 = sorted(zip(feature_cols, importances), key=lambda x: -x[1])[:5]
    print("Top 5 features:")
    for feat, imp in top5:
        print(f"  {feat:26s}: {imp*100:5.2f}%")

    # Lưu model + label mapping
    model_path = os.path.join(MODELS_DIR, cfg["model_file"])
    feat_path = os.path.join(MODELS_DIR, cfg["features_file"])
    joblib.dump(model, model_path)
    meta = {"feature_cols": feature_cols, "label_remap": {str(k): v for k, v in label_remap.items()},
            "reverse_remap": {str(k): v for k, v in reverse_remap.items()}}
    with open(feat_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"[+] Đã lưu: {model_path}")

    # Ghi vào báo cáo chung
    report_lines.append(f"\n{'='*60}")
    report_lines.append(f"DOMAIN: {name.upper()}")
    report_lines.append(f"Mẫu huấn luyện: {len(X_train):,} | Test: {len(X_test):,}")
    report_lines.append(f"Accuracy: {acc*100:.2f}% | Weighted F1: {f1:.4f}")
    report_lines.append(rep)

    return {"name": name, "model_file": cfg["model_file"], "features_file": cfg["features_file"],
            "accuracy": round(acc, 4), "f1_weighted": round(f1, 4)}


def main():
    print("=" * 65)
    print("  HUẤN LUYỆN 3 MÔ HÌNH CHUYÊN BIỆT THEO DOMAIN NGHIỆP VỤ")
    print("=" * 65)

    report_lines = [
        "BÁO CÁO HUẤN LUYỆN MÔ HÌNH CHUYÊN BIỆT THEO DOMAIN",
        f"Thời gian: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n",
    ]

    registry = {}
    for domain_name, cfg in DOMAIN_CONFIGS.items():
        result = train_one_domain(domain_name, cfg, report_lines)
        if result:
            registry[domain_name] = result

    # Ghi domain registry để FastAPI biết model nào serve domain nào
    registry_path = os.path.join(MODELS_DIR, "domain_model_registry.json")
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Đã lưu registry: {registry_path}")

    # Ghi báo cáo tổng hợp
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"[+] Báo cáo chi tiết: {REPORT_PATH}")

    # Tổng kết
    print("\n" + "=" * 65)
    print("                TỔNG KẾT HIỆU NĂNG 3 MÔ HÌNH")
    print("=" * 65)
    print(f"{'Domain':<12} | {'Accuracy':>10} | {'F1-Weighted':>12}")
    print("-" * 40)
    for d, r in registry.items():
        print(f"{d:<12} | {r['accuracy']*100:>9.2f}% | {r['f1_weighted']:>12.4f}")

    print("\n[SUCCESS] Toàn bộ 3 mô hình domain chuyên biệt đã sẵn sàng!")


if __name__ == "__main__":
    main()
