"""
Script tự động chạy toàn bộ training pipeline:
  1. Sinh synthetic data
  2. Train XGBoost model
  3. Evaluate model

Chạy từ thư mục ai_service/:
  python training/run_training_pipeline.py
"""

import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_step(step_name: str, script: str):
    print(f"\n{'=' * 60}")
    print(f"⚙️  BƯỚC: {step_name}")
    print(f"{'=' * 60}")
    t0 = time.time()

    result = subprocess.run(
        [sys.executable, script],
        cwd=BASE_DIR,
        check=False,
    )

    elapsed = round(time.time() - t0, 1)
    if result.returncode != 0:
        print(f"\n❌ {step_name} THẤT BẠI sau {elapsed}s. Dừng pipeline.")
        sys.exit(1)
    else:
        print(f"\n✅ {step_name} hoàn tất trong {elapsed}s")


if __name__ == "__main__":
    print("🚀 AI Training Pipeline — Enterprise Approval System")
    print("=" * 60)
    start = time.time()

    run_step("1/3 Sinh Synthetic Data", "training/generate_synthetic_data.py")
    run_step("2/3 Train XGBoost Model", "training/train_risk_model.py")
    run_step("3/3 Evaluate Model", "training/evaluate_model.py")

    total = round(time.time() - start, 1)
    print(f"\n{'=' * 60}")
    print(f"🎉 Pipeline hoàn tất trong {total}s!")
    print(f"{'=' * 60}")
    print("\n📁 Files tạo ra:")
    print("   training/data/synthetic_requests.csv")
    print("   training/data/evaluation_report.txt")
    print("   models/risk_model.pkl")
    print("   models/feature_columns.json")
    print("\n🚀 Khởi động AI Service:")
    print("   cd ai_service && uvicorn main:app --reload --port 8001")
