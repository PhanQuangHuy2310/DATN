"""OCR smoke test: synthetic Vietnamese invoices through the real PaddleOCR
engine and the service's field parser (amount, date, vendor).

Skipped when PaddleOCR is not installed, except in CI where
OCR_SMOKE_REQUIRED=1 turns a missing engine into a failure.
"""

import json
import os
import sys
import unicodedata
import unittest
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(ROOT), str(ROOT / "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import paddleocr  # noqa: F401

    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False

REQUIRED = os.getenv("OCR_SMOKE_REQUIRED") == "1"
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "").replace("đ", "d").replace("Đ", "D")
    return " ".join(
        "".join(c for c in text if unicodedata.category(c) != "Mn").lower().split()
    )


class OcrInvoiceSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HAS_PADDLE:
            if REQUIRED:
                raise AssertionError(
                    "OCR_SMOKE_REQUIRED=1 but paddleocr is not installed"
                )
            raise unittest.SkipTest("paddleocr not installed")
        from routers.ocr import ocr_with_paddle, parse_invoice_fields

        cls.results = {}
        for name in EXPECTED:
            raw, confidence = ocr_with_paddle((HERE / name).read_bytes())
            cls.results[name] = (raw, confidence, parse_invoice_fields(raw))

    def test_engine_reads_text_and_reports_diacritics(self):
        from tests.ocr_smoke.generate_invoices import INVOICES

        truth = {i["file"]: "\n".join(i["lines"]) for i in INVOICES}
        for name, (raw, confidence, _fields) in self.results.items():
            with self.subTest(invoice=name):
                self.assertGreater(confidence, 0.8, raw)
                self.assertIn("cong ty", _plain(raw), raw)
                # Text is read: the accent-free form matches the source closely.
                plain = SequenceMatcher(
                    None, _plain(raw), _plain(truth[name]), autojunk=False
                ).ratio()
                self.assertGreaterEqual(plain, 0.85, raw)
                # Diacritic fidelity is reported, not asserted: PaddleOCR "vi"
                # drops or garbles many accents (the field parser folds them).
                exact = SequenceMatcher(
                    None, raw.upper(), truth[name].upper(), autojunk=False
                ).ratio()
                print(
                    f"[OCR] {name}: confidence={confidence:.3f} "
                    f"text={plain:.1%} with-diacritics={exact:.1%}",
                    file=sys.stderr,
                )

    def test_amount_and_date_are_exact(self):
        for name, (raw, _c, fields) in self.results.items():
            with self.subTest(invoice=name):
                self.assertEqual(fields.get("amount"), EXPECTED[name]["amount"], raw)
                self.assertEqual(
                    fields.get("invoice_date"), EXPECTED[name]["invoice_date"], raw
                )

    def test_vendor_name_matches(self):
        for name, (raw, _c, fields) in self.results.items():
            with self.subTest(invoice=name):
                ratio = SequenceMatcher(
                    None,
                    _plain(fields.get("vendor_name", "")),
                    _plain(EXPECTED[name]["vendor_name"]),
                ).ratio()
                self.assertGreaterEqual(ratio, 0.85, (fields.get("vendor_name"), raw))


if __name__ == "__main__":
    unittest.main()
