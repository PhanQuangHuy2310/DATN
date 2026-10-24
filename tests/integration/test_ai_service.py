"""
Unit & Integration Tests for AI Service & Client (tests/integration/test_ai_service.py)

Kiểm thử:
1. Nạp và kiểm tra tính toàn vẹn của 15 model artifacts trong ai_service/models/
2. Đọc và cấu trúc của 8 snapshot mock data trong ai_service/data/mock/
3. Logic định tuyến và suy luận XGBoost đa miền (Finance, HR, IT, Master)
4. Đánh giá quy tắc Auto-Approve & ngưỡng rủi ro
5. Cơ chế fallback an toàn của AIServiceClient khi offline/chưa có HTTP
"""

import json
import os
import sys
import unittest

try:
    import joblib
    import numpy as np
    import xgboost  # noqa: F401

    HAS_ML_DEPS = True
except (ImportError, ModuleNotFoundError):
    joblib = None
    numpy = None
    HAS_ML_DEPS = False

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AI_SERVICE_DIR = os.path.join(REPO_ROOT, "ai_service")

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if AI_SERVICE_DIR not in sys.path:
    sys.path.insert(0, AI_SERVICE_DIR)


class TestAIModelArtifacts(unittest.TestCase):
    """Kiểm tra các file mô hình và metadata đã train."""

    def setUp(self):
        self.models_dir = os.path.join(AI_SERVICE_DIR, "models")

    def test_required_model_files_exist(self):
        required_files = [
            "nlp_vectorizer.pkl",
            "nlp_request_type_model.pkl",
            "nlp_department_model.pkl",
            "nlp_template_model.pkl",
            "nlp_labels.json",
            "risk_model.pkl",
            "risk_model_finance.pkl",
            "risk_model_hr.pkl",
            "risk_model_it.pkl",
            "domain_model_registry.json",
            "feature_columns.json",
            "feature_cols_finance.json",
            "feature_cols_hr.json",
            "feature_cols_it.json",
            "encoders.json",
        ]
        for filename in required_files:
            file_path = os.path.join(self.models_dir, filename)
            self.assertTrue(
                os.path.exists(file_path), f"Thiếu file model bắt buộc: {filename}"
            )
            self.assertGreater(
                os.path.getsize(file_path), 0, f"File model rỗng: {filename}"
            )

    def test_domain_model_registry_valid(self):
        reg_path = os.path.join(self.models_dir, "domain_model_registry.json")
        with open(reg_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        for domain in ["finance", "hr", "it"]:
            self.assertIn(domain, registry, f"Thiếu cấu hình domain {domain}")
            self.assertIn("model_file", registry[domain])
            self.assertIn("features_file", registry[domain])


class TestMockDataSnapshots(unittest.TestCase):
    """Kiểm tra 8 snapshot mock data trong data/mock/."""

    def setUp(self):
        self.mock_dir = os.path.join(AI_SERVICE_DIR, "data", "mock")

    def test_manifest_and_all_8_schemas_exist(self):
        manifest_path = os.path.join(self.mock_dir, "_manifest.json")
        self.assertTrue(os.path.exists(manifest_path), "Thiếu _manifest.json")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        expected_schemas = [
            "mock_hr",
            "mock_assets",
            "mock_facilities",
            "mock_crm",
            "mock_procurement",
            "mock_it",
            "mock_finance",
            "mock_travel",
        ]
        total_records = 0
        for schema in expected_schemas:
            self.assertIn(schema, manifest.get("schemas", {}))
            schema_file = os.path.join(self.mock_dir, f"{schema}.json")
            self.assertTrue(os.path.exists(schema_file), f"Thiếu file {schema}.json")

            with open(schema_file, "r", encoding="utf-8") as sf:
                data = json.load(sf)
                self.assertEqual(data.get("schema"), schema)
                total_records += data.get("meta", {}).get("total_records", 0)

        self.assertGreater(total_records, 100, "Tổng số bản ghi mock phải > 100")

    def test_mock_context_lookups(self):
        try:
            from routers.mock_context import (
                lookup_department_budget,
                lookup_facility_available,
                lookup_leave_balance,
            )
        except ImportError:
            from ai_service.routers.mock_context import (
                lookup_department_budget,
                lookup_facility_available,
                lookup_leave_balance,
            )

        balance = lookup_leave_balance("E0001", "ANNUAL")
        self.assertIsNotNone(balance)
        self.assertGreater(balance, 0)

        facility = lookup_facility_available("MR-HCM-01")
        self.assertIsNotNone(facility)
        self.assertTrue(facility)

        budget_dept = lookup_department_budget("IT")
        self.assertIsNotNone(budget_dept)
        self.assertIn("allocated_amount", budget_dept)
        self.assertEqual(budget_dept["allocated_amount"], 1_000_000_000)

        budget_cc = lookup_department_budget("CC-210")
        self.assertIsNotNone(budget_cc)
        self.assertEqual(budget_cc["allocated_amount"], 1_000_000_000)

    def test_risk_input_schema_remap(self):
        try:
            from routers.risk import RiskInput
        except ImportError:
            from ai_service.routers.risk import RiskInput

        payload = {
            "request_type": "expense_reimbursement",
            "lifecycle_template": "A",
            "risk_weight": 3,
            "amount": 25_000_000,
            "attachment_count": 2,
            "request_count_30d": 8,
            "reject_count_30d": 1,
            "requester_dept_category": "finance",
            "is_weekend_or_holiday": True,
        }
        item = RiskInput(**payload)
        self.assertEqual(item.amount_vnd, 25_000_000)
        self.assertEqual(item.num_attachments, 2)
        self.assertEqual(item.past_requests_count, 8)
        self.assertEqual(item.department, "finance")
        self.assertEqual(item.is_off_hours, 1)
        self.assertAlmostEqual(item.past_rejection_rate, 1 / 8)

    def test_anti_ssrf_validation(self):
        try:
            from routers.ocr import validate_safe_image_url
        except ImportError:
            from ai_service.routers.ocr import validate_safe_image_url

        try:
            from fastapi import HTTPException
        except ImportError:
            HTTPException = Exception

        blocked_urls = [
            "http://127.0.0.1:8000/secret",
            "http://localhost:8080/flag",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/admin",
            "http://192.168.1.1/router",
            "file:///etc/passwd",
            "ftp://fileserver/invoice.png",
            "http://metadata.google.internal/computeMetadata/v1/",
        ]
        for url in blocked_urls:
            with self.subTest(url=url), self.assertRaises(HTTPException):
                validate_safe_image_url(url)


@unittest.skipUnless(
    HAS_ML_DEPS,
    "ML dependencies (joblib, numpy, xgboost) are required for XGBoost inference tests",
)
class TestMultiDomainXGBoostInference(unittest.TestCase):
    """Kiểm tra suy luận trực tiếp từ 4 mô hình XGBoost đã train."""

    def setUp(self):
        self.models_dir = os.path.join(AI_SERVICE_DIR, "models")
        with open(
            os.path.join(self.models_dir, "encoders.json"), "r", encoding="utf-8"
        ) as f:
            self.encoders = json.load(f)

    def test_finance_model_high_risk(self):
        model_path = os.path.join(self.models_dir, "risk_model_finance.pkl")
        feat_path = os.path.join(self.models_dir, "feature_cols_finance.json")
        model = joblib.load(model_path)
        with open(feat_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        feat_cols = meta["feature_cols"] if isinstance(meta, dict) else meta
        rev_remap = (
            {int(k): v for k, v in meta.get("reverse_remap", {}).items()}
            if isinstance(meta, dict)
            else {}
        )

        # Case: Tạm ứng 80 triệu vượt ngân sách 30 triệu, không hóa đơn -> Risk 5
        amount = 80_000_000
        budget = 30_000_000
        feat_map = {
            "request_type_enc": float(
                self.encoders.get("request_type", {}).get("advance_payment", 0)
            ),
            "department_enc": float(
                self.encoders.get("department", {}).get("finance", 0)
            ),
            "user_role_enc": 2.0,
            "priority_level_enc": 2.0,
            "amount_log": float(np.log1p(amount)),
            "amount_millions": float(amount / 1e6),
            "budget_log": float(np.log1p(budget)),
            "amount_to_budget_ratio": float(amount / (budget + 1)),
            "is_over_budget": 1.0,
            "is_split_amount_suspect": 0.0,
            "has_receipt": 0.0,
            "num_attachments": 0.0,
            "no_receipt_has_amount": 1.0,
            "user_tenure_months": 12.0,
            "past_requests_count": 5.0,
            "past_rejection_rate": 0.0,
            "high_rejection_rate": 0.0,
            "is_off_hours": 0.0,
            "is_template_matched": 1.0,
        }
        X = np.array([[feat_map.get(c, 0.0) for c in feat_cols]], dtype=np.float32)
        pred_idx = int(model.predict(X)[0])
        risk_score = (
            rev_remap.get(pred_idx, pred_idx + 1) if rev_remap else pred_idx + 1
        )

        self.assertGreaterEqual(
            risk_score, 4, "Tạm ứng vượt budget không hóa đơn phải có risk >= 4"
        )

    def test_hr_model_normal_risk(self):
        model_path = os.path.join(self.models_dir, "risk_model_hr.pkl")
        feat_path = os.path.join(self.models_dir, "feature_cols_hr.json")
        model = joblib.load(model_path)
        with open(feat_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        feat_cols = meta["feature_cols"] if isinstance(meta, dict) else meta
        rev_remap = (
            {int(k): v for k, v in meta.get("reverse_remap", {}).items()}
            if isinstance(meta, dict)
            else {}
        )

        # Case: Nghỉ phép năm bình thường, không tốn tiền -> Risk thấp (1 hoặc 2)
        budget = 200_000_000
        feat_map = {
            "request_type_enc": float(
                self.encoders.get("request_type", {}).get("leave_annual", 0)
            ),
            "department_enc": float(self.encoders.get("department", {}).get("hr", 0)),
            "user_role_enc": 2.0,
            "priority_level_enc": 2.0,
            "amount_log": 0.0,
            "amount_millions": 0.0,
            "budget_log": float(np.log1p(budget)),
            "amount_to_budget_ratio": 0.0,
            "is_over_budget": 0.0,
            "is_split_amount_suspect": 0.0,
            "has_receipt": 0.0,
            "num_attachments": 0.0,
            "no_receipt_has_amount": 0.0,
            "user_tenure_months": 24.0,
            "past_requests_count": 3.0,
            "past_rejection_rate": 0.0,
            "high_rejection_rate": 0.0,
            "is_off_hours": 0.0,
            "is_template_matched": 1.0,
        }
        X = np.array([[feat_map.get(c, 0.0) for c in feat_cols]], dtype=np.float32)
        pred_idx = int(model.predict(X)[0])
        risk_score = (
            rev_remap.get(pred_idx, pred_idx + 1) if rev_remap else pred_idx + 1
        )

        self.assertLessEqual(
            risk_score, 2, "Nghỉ phép năm bình thường phải có risk <= 2"
        )


class TestAIServiceClientFallback(unittest.TestCase):
    """Kiểm tra khả năng chịu lỗi (fault-tolerance) của ai_client."""

    @staticmethod
    def _get_client():
        try:
            from api_core.ai_client import ai_client_sync
        except ImportError:
            from ai_client import ai_client_sync
        return ai_client_sync

    def test_sync_client_score_risk_fallback(self):
        ai_client_sync = self._get_client()

        res = ai_client_sync.score_risk(
            request_type="leave_annual",
            lifecycle_template="A",
            risk_weight=2,
        )
        self.assertIn("risk_score", res)
        self.assertEqual(res["risk_score"], 2)
        self.assertTrue(res.get("fallback_used", False))

    def test_sync_client_auto_approve_fallback(self):
        ai_client_sync = self._get_client()

        res = ai_client_sync.evaluate_auto_approve(
            request_id="test-fallback",
            request_type="leave_annual",
            lifecycle_template="A",
            risk_score=1,
            requester_name="Test User",
            requester_dept="HR",
        )
        self.assertIn("decision", res)
        self.assertEqual(res["decision"], "escalate_to_human")

    def test_sync_client_classify_fallback(self):
        ai_client_sync = self._get_client()

        res = ai_client_sync.classify_request(
            title="Đề xuất mua màn hình mới", description="Màn hình Dell 27 inch"
        )
        self.assertIn("predicted_request_type", res)
        self.assertIn("predicted_department", res)
        self.assertTrue(res.get("fallback_used", False))


if __name__ == "__main__":
    unittest.main()
