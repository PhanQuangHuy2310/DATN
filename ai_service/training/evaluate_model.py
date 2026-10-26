"""
Training Script 3/3: Evaluate và kiểm tra model đã train

Dùng để:
- Kiểm tra model sau khi train
- So sánh XGBoost vs rule-based
- Phân tích lỗi phổ biến
- Kiểm tra predict latency

Chạy: python training/evaluate_model.py
"""

import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

MODEL_PATH = "models/risk_model.pkl"
DATA_PATH = "training/data/synthetic_requests.csv"
FEATURE_COLS_PATH = "models/feature_columns.json"


def rule_based_predict(row: pd.Series) -> int:
    """Rule-based fallback để so sánh với XGBoost."""
    score = row["risk_weight"]
    if row["amount_millions"] > 50:
        score += 2
    elif row["amount_millions"] > 10:
        score += 1
    if row["amount"] > 0 and row["attachment_count"] == 0:
        score += 1
    if row["leave_deficit"] > 0:
        score += 1
    if row["reject_count_30d"] >= 2:
        score += 1
    if row["request_count_30d"] >= 5:
        score += 1
    if row["is_near_deadline"]:
        score += 0.5
    if row["is_weekend_or_holiday"]:
        score += 0.5
    return int(np.clip(round(score), 1, 5))


def main():
    print("=" * 60)
    print("🔍 Model Evaluation Tool")
    print("=" * 60)

    # --- Kiểm tra file tồn tại ---
    if not os.path.exists(MODEL_PATH):
        print("❌ Model chưa train. Chạy: python training/train_risk_model.py")
        return

    if not os.path.exists(DATA_PATH):
        print("❌ Chưa có data. Chạy: python training/generate_synthetic_data.py")
        return

    # --- Load ---
    print(f"\n📦 Loading model từ {MODEL_PATH}...")
    model = joblib.load(MODEL_PATH)

    print(f"📦 Loading data từ {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)

    with open(FEATURE_COLS_PATH) as f:
        feature_cols = json.load(f)

    X = df[feature_cols].values.astype(np.float32)
    y_true = df["risk_score"].values.astype(int)

    # --- XGBoost predict ---

    print("\n🤖 XGBoost predictions...")
    t0 = time.time()
    y_pred_0 = model.predict(X)
    xgb_latency = (time.time() - t0) * 1000 / len(X)
    y_pred = y_pred_0 + 1

    xgb_acc = accuracy_score(y_true, y_pred)
    xgb_f1 = f1_score(y_true, y_pred, average="weighted")

    # --- Rule-based predict ---
    print("📏 Rule-based predictions...")
    t0 = time.time()
    y_rule = df.apply(rule_based_predict, axis=1).values
    rule_latency = (time.time() - t0) * 1000 / len(df)

    rule_acc = accuracy_score(y_true, y_rule)
    rule_f1 = f1_score(y_true, y_rule, average="weighted")

    # --- Kết quả so sánh ---
    print("\n" + "=" * 60)
    print("📊 SO SÁNH HIỆU SUẤT")
    print("=" * 60)
    print(f"{'Metric':<25} {'XGBoost':>12} {'Rule-based':>12}")
    print("-" * 50)
    print(f"{'Accuracy':<25} {xgb_acc:>12.4f} {rule_acc:>12.4f}")
    print(f"{'F1 (weighted)':<25} {xgb_f1:>12.4f} {rule_f1:>12.4f}")
    print(f"{'Latency (ms/sample)':<25} {xgb_latency:>12.4f} {rule_latency:>12.4f}")

    print("\n📋 XGBoost Classification Report:")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=[f"Risk {i}" for i in range(1, 6)],
        )
    )

    # --- Error Analysis ---
    errors = df.copy()
    errors["predicted"] = y_pred
    errors = errors[errors["risk_score"] != errors["predicted"]]

    print(
        f"\n❌ Số mẫu dự đoán sai: {len(errors)} / {len(df)} ({len(errors) / len(df) * 100:.1f}%)"
    )

    if len(errors) > 0:
        print("\n🔍 Phân tích lỗi theo loại yêu cầu:")
        error_by_type = (
            errors.groupby("request_type").size().sort_values(ascending=False)
        )
        for rtype, count in error_by_type.items():
            total = len(df[df["request_type"] == rtype])
            print(
                f"   {rtype:25s}: {count:3d}/{total:3d} ({count / total * 100:.0f}% sai)"
            )

    # --- Latency test ---
    print("\n⚡ Latency Test (1000 requests đơn lẻ):")
    single_x = X[0:1]
    times = []
    for _ in range(1000):
        t = time.time()
        model.predict(single_x)
        times.append((time.time() - t) * 1000)

    p50 = np.percentile(times, 50)
    p95 = np.percentile(times, 95)
    p99 = np.percentile(times, 99)
    print(f"   P50: {p50:.3f}ms | P95: {p95:.3f}ms | P99: {p99:.3f}ms")
    print(f"   ADR-007 target: < 50ms — {'✅ ĐẠT' if p95 < 50 else '❌ CHƯA ĐẠT'}")

    # --- Feature Importance ---
    print("\n🔍 Top 10 Feature Importance:")
    importance = dict(zip(feature_cols, model.feature_importances_))
    top10 = sorted(importance.items(), key=lambda x: -x[1])[:10]
    for feat, imp in top10:
        bar = "█" * int(imp * 80)
        print(f"   {feat:35s}: {imp:.4f}  {bar}")

    # --- Auto-approve accuracy ---
    print("\n🤖 Auto-Approve Accuracy:")
    can_auto_approve_mask = (y_true <= 2) & (df["lifecycle_template"] == "A")
    should_not_mask = (y_true > 2) | (df["lifecycle_template"] != "A")

    xgb_approve = (y_pred <= 2) & (df["lifecycle_template"] == "A")
    xgb_tp = (xgb_approve & can_auto_approve_mask).sum()
    xgb_fp = (xgb_approve & should_not_mask).sum()
    xgb_fn = (~xgb_approve & can_auto_approve_mask).sum()

    if xgb_tp + xgb_fp > 0:
        precision = xgb_tp / (xgb_tp + xgb_fp)
        recall = xgb_tp / (xgb_tp + xgb_fn)
        print(f"   Auto-approve Precision: {precision:.4f} (tỷ lệ duyệt đúng)")
        print(f"   Auto-approve Recall:    {recall:.4f} (tỷ lệ bắt được đủ case đúng)")
        print(f"   False Positive (duyệt nhầm high risk): {xgb_fp}")

    print("\n✅ Evaluation hoàn tất!")


if __name__ == "__main__":
    main()
