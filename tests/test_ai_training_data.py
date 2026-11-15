"""Training data and shared text helpers of the AI service (standard library only).

Guards against the drift that made the old classifier useless: every request
type in the training corpus and evaluation set must be an ACTIVE catalog code.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI = ROOT / "ai_service"
DATA = AI / "training" / "data"
if str(AI) not in sys.path:
    sys.path.insert(0, str(AI))

from nlp_text import (
    advance_tier,
    canonical_request_type,
    extract_amount_vnd,
    normalize_text,
    refine_advance_tier,
    strip_diacritics,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TrainingDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = _load(ROOT / "api_core" / "catalog" / "catalog_v2.json")
        cls.active = {i["code"] for i in catalog["items"] if i["status"] == "ACTIVE"}
        cls.corpus = _load(DATA / "request_corpus.json")
        cls.evaluation = _load(DATA / "request_eval_realistic.json")["items"]

    def test_corpus_covers_exactly_the_active_catalog(self):
        self.assertEqual(set(self.corpus["types"]), self.active)

    def test_corpus_slots_are_defined(self):
        for code, spec in self.corpus["types"].items():
            slots = {**self.corpus["slots"], **spec.get("slots", {})}
            self.assertGreaterEqual(len(spec["titles"]), 3, code)
            self.assertTrue(spec["details"], code)
            for template in [*spec["titles"], *spec["details"]]:
                for name in re.findall(r"\{(\w+)\}", template):
                    with self.subTest(code=code, slot=name):
                        self.assertIn(name, slots)

    def test_evaluation_set_is_labelled_with_active_codes(self):
        labels = {item["label"] for item in self.evaluation}
        self.assertLessEqual(labels, self.active)
        self.assertEqual(labels, self.active, "every type needs hand-written cases")
        self.assertEqual({item["split"] for item in self.evaluation}, {"dev", "test"})

    def test_evaluation_sentences_are_not_training_templates(self):
        templates = {
            normalize_text(t)
            for spec in self.corpus["types"].values()
            for t in spec["titles"]
        }
        for item in self.evaluation:
            self.assertNotIn(normalize_text(item["title"]), templates, item["title"])

    def test_only_one_training_entry_point(self):
        scripts = sorted(p.name for p in (AI / "training").glob("*.py"))
        self.assertEqual(scripts, ["__init__.py", "train.py"])


class TextHelperTests(unittest.TestCase):
    def test_amounts(self):
        cases = {
            "Tạm ứng 3tr": 3_000_000,
            "5.000.000 đồng": 5_000_000,
            "1,2 tỷ": 1_200_000_000,
            "450.000đ": 450_000,
            "tam ung 40 trieu": 40_000_000,
            "500 nghìn": 500_000,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(extract_amount_vnd(text), expected)
        self.assertIsNone(extract_amount_vnd("Xin nghỉ 3 ngày từ 15/12"))

    def test_advance_tiers_follow_the_catalog_thresholds(self):
        self.assertEqual(advance_tier(9_999_000), "ADVANCE_SMALL")
        self.assertEqual(advance_tier(10_000_000), "ADVANCE_MEDIUM")
        self.assertEqual(advance_tier(50_000_000), "ADVANCE_MEDIUM")
        self.assertEqual(advance_tier(50_001_000), "ADVANCE_LARGE")
        self.assertEqual(refine_advance_tier("ADVANCE_SMALL", "tạm ứng 80 triệu"), "ADVANCE_LARGE")
        self.assertEqual(refine_advance_tier("LEAVE", "nghỉ 80 triệu"), "LEAVE")

    def test_legacy_codes_map_to_the_catalog(self):
        self.assertEqual(canonical_request_type("leave_annual"), "LEAVE")
        self.assertEqual(canonical_request_type("expense_reimbursement"), "EXPENSE_CLAIM")
        self.assertEqual(canonical_request_type("LEAVE_LONG"), "LEAVE")
        self.assertEqual(canonical_request_type("purchase_request"), "PURCHASE_REQUEST")

    def test_text_normalisation(self):
        self.assertEqual(normalize_text("  Đề  XUẤT "), "dề xuất")
        self.assertEqual(strip_diacritics("Đề xuất nghỉ phép"), "De xuat nghi phep")


if __name__ == "__main__":
    unittest.main()
