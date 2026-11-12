"""AI acceptance scenarios: risk-weight auto-approval and invoice OCR parsing."""

import asyncio
import os
import sys
import unittest
from pathlib import Path

try:
    import fastapi  # noqa: F401
    import loguru  # noqa: F401
    import pydantic_settings  # noqa: F401

    HAS_ROUTER_DEPS = True
except (ImportError, ModuleNotFoundError):
    HAS_ROUTER_DEPS = False

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AI_SERVICE_DIR = os.path.join(REPO_ROOT, "ai_service")
for path in (REPO_ROOT, AI_SERVICE_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


@unittest.skipUnless(HAS_ROUTER_DEPS, "fastapi/loguru/pydantic_settings not installed")
class AutoApproveWeightTests(unittest.TestCase):
    """Scenario 2: weights 1-2 auto-approve, 3-5 go to a human."""

    def evaluate(self, weight, template="A"):
        from routers.auto_approve import AutoApproveInput, evaluate_auto_approve

        body = AutoApproveInput(
            request_id="00000000-0000-4000-8000-000000000001",
            request_type="generic",
            lifecycle_template=template,
            risk_score=weight,
            requester_name="Test",
            requester_dept="IT",
        )
        return asyncio.run(evaluate_auto_approve(body)).decision

    def test_weight_one_and_two_are_auto_approved(self):
        for weight in (1, 2):
            with self.subTest(weight=weight):
                self.assertEqual(self.evaluate(weight), "auto_approve")

    def test_weight_three_and_above_escalate_to_human(self):
        for weight in (3, 4, 5):
            with self.subTest(weight=weight):
                self.assertEqual(self.evaluate(weight), "escalate_to_human")

    def test_low_weight_with_executor_lifecycle_is_not_auto_approved(self):
        self.assertEqual(self.evaluate(1, template="B"), "escalate_to_human")


@unittest.skipUnless(HAS_ROUTER_DEPS, "fastapi/loguru/pydantic_settings not installed")
class PolicyRulesLatencyTests(unittest.TestCase):
    """Scenario 6: a newly loaded policy applies to the very next evaluation."""

    def setUp(self):
        import tempfile
        from unittest.mock import patch

        from routers import policy

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(
            policy, "POLICY_FILE", os.path.join(self.tmp.name, "policy.json")
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.real_pull = policy.pull_active_policy
        no_pull = patch.object(policy, "pull_active_policy", return_value=None)
        no_pull.start()
        self.addCleanup(no_pull.stop)

    def evaluate(self, weight=1, amount=0.0):
        from routers.auto_approve import AutoApproveInput, evaluate_auto_approve

        body = AutoApproveInput(
            request_id="00000000-0000-4000-8000-000000000001",
            request_type="generic",
            lifecycle_template="A",
            risk_score=weight,
            amount=amount,
            requester_name="Test",
            requester_dept="IT",
        )
        return asyncio.run(evaluate_auto_approve(body))

    def publish(self, version, rules):
        from routers.policy import PolicyDocument, publish_rules

        return asyncio.run(
            publish_rules(
                PolicyDocument.model_validate({"version": version, "rules": rules})
            )
        )

    def test_new_rule_applies_to_next_request_within_a_second(self):
        from time import perf_counter

        self.assertEqual(self.evaluate().decision, "auto_approve")
        started = perf_counter()
        self.publish(
            "QD-01",
            [
                {
                    "id": "manual-generic",
                    "request_type": "generic",
                    "auto_approve": False,
                }
            ],
        )
        result = self.evaluate()
        elapsed = perf_counter() - started
        self.assertEqual(result.decision, "escalate_to_human")
        self.assertEqual(result.policy_version, "QD-01")
        self.assertLess(elapsed, 1.0)

    def test_amount_threshold_raises_weight_above_auto_limit(self):
        self.publish(
            "QD-02", [{"id": "big-spend", "amount_gt": 5_000_000, "min_risk": 4}]
        )
        self.assertEqual(self.evaluate(amount=1_000_000).decision, "auto_approve")
        self.assertEqual(self.evaluate(amount=9_000_000).decision, "escalate_to_human")

    def test_replacing_policy_lifts_previous_rule(self):
        self.publish("QD-03", [{"id": "freeze", "auto_approve": False}])
        self.assertEqual(self.evaluate().decision, "escalate_to_human")
        self.publish("QD-04", [])
        self.assertEqual(self.evaluate().decision, "auto_approve")

    def test_empty_cache_pulls_active_version_from_api(self):
        from unittest.mock import MagicMock, patch

        from routers import policy

        response = MagicMock(status_code=200)
        response.json.return_value = {
            "version": "QD-DB",
            "rules": [{"id": "freeze", "auto_approve": False}],
        }
        policy._last_pull["at"] = -1e9
        with patch("httpx.get", return_value=response) as get:
            state = self.real_pull(policy.POLICY_FILE)
        self.assertIn("X-Internal-Secret", get.call_args.kwargs["headers"])
        self.assertEqual(state.version, "QD-DB")
        self.assertTrue(os.path.exists(policy.POLICY_FILE))

    def test_advice_cites_each_relevant_regulation_clause(self):
        self.publish(
            "QD-06",
            [
                {
                    "id": "REG-002-4",
                    "description": "Yêu cầu trên 10 triệu bắt buộc duyệt thủ công.",
                    "amount_gt": 10_000_000,
                    "auto_approve": False,
                },
                {
                    "id": "REG-003-1-OTHER",
                    "request_type": "other_type",
                    "auto_approve": False,
                },
            ],
        )
        small = self.evaluate(amount=5_000_000).citations
        self.assertEqual([c["rule_id"] for c in small], ["REG-002-4"])
        self.assertFalse(small[0]["applies"])
        self.assertIn("5.000.000 VNĐ ≤ ngưỡng 10.000.000 VNĐ", small[0]["checks"][0])
        big = self.evaluate(amount=12_000_000).citations[0]
        self.assertTrue(big["applies"])
        self.assertEqual(big["text"], "Yêu cầu trên 10 triệu bắt buộc duyệt thủ công.")
        self.assertEqual(big["policy_version"], "QD-06")

    def test_at_least_threshold_is_shown_as_written_in_the_regulation(self):
        self.publish(
            "QD-07", [{"id": "REG-002-3", "amount_gt": 29_999_999, "min_risk": 5}]
        )
        below = self.evaluate(amount=12_000_000).citations[0]["checks"][0]
        self.assertIn("12.000.000 VNĐ < ngưỡng 30.000.000 VNĐ", below)
        at = self.evaluate(amount=30_000_000).citations[0]
        self.assertTrue(at["applies"])
        self.assertIn("≥ ngưỡng 30.000.000 VNĐ", at["checks"][0])

    def test_rule_without_effect_is_rejected(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            self.publish("QD-05", [{"id": "noop", "request_type": "generic"}])


@unittest.skipUnless(HAS_ROUTER_DEPS, "fastapi/loguru/pydantic_settings not installed")
class OcrWarmupTests(unittest.TestCase):
    """The OCR engine loads once, in the background, at service startup."""

    def setUp(self):
        from unittest.mock import patch

        from routers import ocr

        self.ocr = ocr
        patcher = patch.object(ocr, "_ocr_engine", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_warmup_builds_engine_once_even_with_concurrent_requests(self):
        import sys
        import threading
        import time
        from types import ModuleType
        from unittest.mock import patch

        calls = []

        class SlowEngine:
            def __init__(self, **kwargs):
                calls.append(kwargs)
                time.sleep(0.2)

        fake = ModuleType("paddleocr")
        fake.PaddleOCR = SlowEngine
        with patch.dict(sys.modules, {"paddleocr": fake}):
            warm = self.ocr.start_ocr_warmup()
            others = [
                threading.Thread(target=self.ocr.get_ocr_engine) for _ in range(3)
            ]
            for t in others:
                t.start()
            warm.join(2)
            for t in others:
                t.join(2)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(self.ocr._ocr_engine, SlowEngine)

    def test_warmup_can_be_disabled(self):
        from unittest.mock import patch

        with patch.object(self.ocr.settings, "ocr_warmup", False):
            self.assertIsNone(self.ocr.start_ocr_warmup())

    def test_service_starts_warmup_on_startup(self):
        main = (Path(AI_SERVICE_DIR) / "main.py").read_text(encoding="utf-8")
        self.assertIn('@app.on_event("startup")', main)
        self.assertIn("ocr.start_ocr_warmup()", main)


@unittest.skipUnless(HAS_ROUTER_DEPS, "fastapi/loguru/pydantic_settings not installed")
class InvoiceFieldExtractionTests(unittest.TestCase):
    """Scenario 5: key invoice fields from Vietnamese OCR text."""

    VAT_INVOICE = (
        "CÔNG TY TNHH THƯƠNG MẠI ĐẠI PHÁT\n"
        "MST: 0312345678\n"
        "HÓA ĐƠN GIÁ TRỊ GIA TĂNG\n"
        "Số hóa đơn: 0001234\n"
        "Ngày 15 tháng 03 năm 2026\n"
        "Văn phòng phẩm  2  250.000 VND\n"
        "Thành tiền: 500.000 VND\n"
        "Tổng cộng thanh toán: 1.540.000 VND\n"
    )
    RECEIPT = "CÔNG TY CỔ PHẦN DỊCH VỤ ÂU LẠC\nNgày 02/11/2026\nTổng tiền: 320.000đ\n"

    def parse(self, text):
        from routers.ocr import parse_invoice_fields

        return parse_invoice_fields(text)

    def test_vat_invoice_total_amount(self):
        self.assertEqual(self.parse(self.VAT_INVOICE)["amount"], 1_540_000)

    def test_vat_invoice_written_vietnamese_date(self):
        self.assertEqual(self.parse(self.VAT_INVOICE)["invoice_date"], "2026-03-15")

    def test_vat_invoice_vendor_keeps_vietnamese_diacritics(self):
        self.assertEqual(
            self.parse(self.VAT_INVOICE)["vendor_name"], "Thương Mại Đại Phát"
        )

    def test_receipt_service_garbled_ocr_vendor_normalized(self):
        garbled = (
            "CÔNG TY C Phân Dļch V Âu Lc\nNgày 02/11/2026\nTổng cộng: 320.000 VND\n"
        )
        fields = self.parse(garbled)
        self.assertEqual(fields["vendor_name"], "Dịch Vụ Âu Lạc")
        self.assertEqual(fields["amount"], 320_000)

    def test_vat_invoice_tax_code_and_number(self):
        fields = self.parse(self.VAT_INVOICE)
        self.assertEqual(fields["tax_code"], "0312345678")
        self.assertEqual(fields["invoice_number"], "0001234")

    def test_ocr_text_with_lost_diacritics(self):
        # Real PaddleOCR "vi" output for the VAT sample (tests/ocr_smoke).
        raw = (
            "CONG TY TNHH THU'O'NG MAI DAI PHAT"
            + chr(10)
            + "MST: 0312345678"
            + chr(10)
            + "Ngäy 15 thäng 03 näm 2026"
            + chr(10)
            + "Vän phng phäm 2 250.000 VND"
            + chr(10)
            + "Thänh tién: 500.000 VND"
            + chr(10)
            + "Tóng cng thanh toán: 1.540.000 VND"
        )
        fields = self.parse(raw)
        self.assertEqual(fields["amount"], 1_540_000)
        self.assertEqual(fields["invoice_date"], "2026-03-15")
        self.assertEqual(fields["vendor_name"], "Thuong Mai Dai Phat")
        self.assertEqual(fields["tax_code"], "0312345678")

    def test_receipt_fields(self):
        fields = self.parse(self.RECEIPT)
        self.assertEqual(fields["amount"], 320_000)
        self.assertEqual(fields["invoice_date"], "2026-11-02")
        self.assertEqual(fields["vendor_name"], "Dịch Vụ Âu Lạc")


if __name__ == "__main__":
    unittest.main()
