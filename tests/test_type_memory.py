"""Bộ nhớ loại yêu cầu mới và nhận biết "nhu cầu chưa có trong danh mục" (ai_service/type_memory.py).

Loại tạo sau lúc huấn luyện (admin hoặc AI tạo) phải được nhận ra ngay, không cần huấn luyện lại; nhu cầu mà mô hình
đoán bừa ("Xin cấp chỗ đỗ ô tô" -> "Cấp máy tính" 0,84) phải bị nhận ra là mới, không được gợi ý nhầm loại.
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO, os.path.join(REPO, "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import type_memory as tm

    HAS_AI_DEPS = True
except ImportError:  # venv gốc không cài numpy/scikit-learn: chạy bằng ai_service/.venv-ai
    HAS_AI_DEPS = False

try:
    from routers import classify as cl

    HAS_ROUTER_DEPS = True
except ImportError:  # venv gốc không cài fastapi: chạy phần này bằng ai_service/.venv-ai
    HAS_ROUTER_DEPS = False

LUNCH = {
    "code": "AI_LUNCH01",
    "name": "Đăng ký suất ăn trưa",
    "description": "Nhu cầu do AI tạo từ yêu cầu của nhân viên: Đăng ký suất ăn trưa",
    "category": "PEOPLE",
    "category_label": "Nhân sự",
    "department": "HR",
    "lifecycle": "B",
    "approval_route": "QL trực tiếp ⇒ thực hiện: Nhân sự",
    "examples": ["Đăng ký ăn trưa tuần sau", "ăn trưa ở căng tin công ty"],
}
PARKING = {
    "code": "AI_PARK01",
    "name": "Đăng ký chỗ đỗ ô tô",
    "description": "",
    "category": "ASSET",
    "department": "ADMIN",
    "lifecycle": "B",
    "approval_route": "",
    "examples": [],
}


@unittest.skipUnless(HAS_AI_DEPS, "cần numpy/scikit-learn (ai_service/.venv-ai)")
class LearnedMatchTests(unittest.TestCase):

    def test_new_type_is_matched_by_its_name_and_past_titles(self):
        ranked = tm.match_learned("đăng ký suất ăn trưa cho tuần sau", [PARKING, LUNCH])
        self.assertEqual(ranked[0][0]["code"], "AI_LUNCH01")
        self.assertGreaterEqual(ranked[0][1], tm.LEARNED_SURE)
        self.assertLess(ranked[1][1], ranked[0][1])

    def test_accents_and_function_words_do_not_matter(self):
        with_accents = tm.match_learned("Xin đăng ký ăn trưa ở căng tin", [LUNCH])[0][1]
        without = tm.match_learned("xin dang ky an trua o cang tin", [LUNCH])[0][1]
        self.assertAlmostEqual(with_accents, without, places=2)

    def test_each_submitted_title_teaches_the_type_a_new_wording(self):
        before = tm.match_learned("đặt cơm văn phòng", [LUNCH])[0][1]
        taught = {**LUNCH, "examples": [*LUNCH["examples"], "Đặt cơm văn phòng thứ 6"]}
        after = tm.match_learned("đặt cơm văn phòng", [taught])[0][1]
        self.assertGreater(after, before)
        self.assertGreaterEqual(after, tm.LEARNED_SURE)

    def test_nothing_to_match(self):
        self.assertEqual(tm.match_learned("", [LUNCH]), [])
        self.assertEqual(tm.match_learned("nghỉ phép", []), [])
        self.assertEqual(tm.match_learned("xin cho em", [LUNCH]), [])  # chỉ còn từ chức năng

    def test_confidence_scale(self):
        self.assertEqual(tm.learned_confidence(0.25), 0.0)
        self.assertEqual(tm.learned_confidence(0.1), 0.0)
        self.assertAlmostEqual(tm.learned_confidence(0.475), 0.5, places=3)
        self.assertEqual(tm.learned_confidence(1.0), 0.97)


@unittest.skipUnless(HAS_AI_DEPS, "cần numpy/scikit-learn (ai_service/.venv-ai)")
class NoveltyRuleTests(unittest.TestCase):

    def test_weak_vocabulary_support_means_a_new_need_even_when_the_model_is_confident(self):
        self.assertTrue(tm.is_novel(0.84, 0.0))
        self.assertTrue(tm.is_novel(0.6, 0.34))
        self.assertFalse(tm.is_novel(0.6, 0.35))

    def test_a_very_sure_model_is_trusted(self):
        self.assertFalse(tm.is_novel(0.95, 0.0))

    def test_an_unsure_model_with_half_support_is_still_new(self):
        self.assertTrue(tm.is_novel(0.15, 0.45))
        self.assertFalse(tm.is_novel(0.15, 0.5))

    def test_no_content_words_is_not_judged(self):
        self.assertFalse(tm.is_novel(0.1, None))

    def test_route_conditions_are_written_for_people(self):
        self.assertEqual(tm.pretty_route("QL → HR (khi days_gt 3: GĐ)"), "QL → Nhân sự (khi trên 3 ngày: GĐ)")
        self.assertEqual(tm.pretty_route("x (khi amount_gte 20000000)"), "x (khi từ 20.000.000 đồng)")
        self.assertEqual(tm.pretty_route("x (khi amount_gt 5000000)"), "x (khi trên 5.000.000 đồng)")
        self.assertEqual(tm.pretty_route("QL ⇒ thực hiện: ADMIN ⇒ nghiệm thu: CTO"),
                         "QL ⇒ thực hiện: Hành chính ⇒ nghiệm thu: Giám đốc công nghệ")
        self.assertEqual(tm.pretty_route("thực hiện: UNKNOWN_DEPT"), "thực hiện: UNKNOWN_DEPT")
        self.assertEqual(tm.pretty_route("QL trực tiếp → HR → CTO"), "QL trực tiếp → Nhân sự → Giám đốc công nghệ")
        self.assertEqual(tm.pretty_route("QL trực tiếp → TP Mua sắm"), "QL trực tiếp → TP Mua sắm")


@unittest.skipUnless(HAS_ROUTER_DEPS, "cần fastapi (ai_service/.venv-ai)")
class ClassifierWithMemoryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.model, cls.labels = cl.get_nlp_model()
        if cls.model is None:
            raise unittest.SkipTest("chưa có ai_service/models/nlp_classifier.pkl")

    def classify(self, text, learned=()):
        return cl.predict(self.model, self.labels, text, [cl.LearnedType(**t) for t in learned])

    def test_known_need_stays_with_the_trained_type(self):
        result = self.classify("Xin nghỉ phép năm 2 ngày về quê", [LUNCH, PARKING])
        self.assertEqual(result.source, "model")
        self.assertFalse(result.novel)
        self.assertNotIn(result.predicted_request_type, {"AI_LUNCH01", "AI_PARK01"})

    def test_need_outside_the_catalogue_is_flagged_new(self):
        result = self.classify("Xin cấp chỗ đỗ ô tô")
        self.assertTrue(result.novel)
        self.assertTrue(result.low_confidence)

    def test_learned_type_is_chosen_at_once_without_retraining(self):
        result = self.classify("Xin cấp chỗ đỗ ô tô", [LUNCH, PARKING])
        self.assertEqual(result.predicted_request_type, "AI_PARK01")
        self.assertEqual(result.source, "learned")
        self.assertFalse(result.novel)
        lunch = self.classify("Đăng ký suất ăn trưa tuần sau", [LUNCH, PARKING])
        self.assertEqual(lunch.predicted_request_type, "AI_LUNCH01")
        self.assertIn("Nhân sự", lunch.workflow_suggestion)

    def test_learned_alternatives_are_marked(self):
        result = self.classify("Xin cấp chỗ đỗ ô tô", [LUNCH, PARKING])
        learned = {a.request_type for a in result.alternatives if a.source == "learned"}
        self.assertIn("AI_PARK01", learned)

    def test_gibberish_is_unclear_and_never_matched(self):
        result = self.classify("asdf qwer zxcv", [LUNCH, PARKING])
        self.assertTrue(result.unclear)
        self.assertEqual(result.source, "model")


if __name__ == "__main__":
    unittest.main()
