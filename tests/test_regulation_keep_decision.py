"""Nạp quy định mới: AI đánh giá nên GIỮ hay BỎ điều cũ bị đè lên; quyết định giữ được lượt học tôn trọng (20/11).

Câu mẫu do "Mẫu nạp nhanh" (web_client/src/regulationTemplate.js) sinh ra cũng được biên dịch thật ở đây.
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from api_core.workflow import regulation_precedence as rp
from api_core.workflow.regulation_compiler import (
    RequestTypeName,
    compile_sentence,
    compile_text,
)
from api_core.workflow.regulation_validation import validate

TYPES = [
    RequestTypeName("EXPENSE_CLAIM", "Thanh toán chi phí", "A"),
    RequestTypeName("LEAVE", "Nghỉ phép", "A"),
    RequestTypeName("WFH_REQ", "Làm việc từ xa (WFH)", "A"),
]
OLD = {"code": "QD-CU", "content": (
    "Điều 1: Yêu cầu Thanh toán chi phí có dấu hiệu chia nhỏ hóa đơn bắt buộc Kế toán phê duyệt thủ công.\n"
    "Điều 2: Yêu cầu Thanh toán chi phí có giá trị từ 40 triệu đồng trở lên bắt buộc Giám đốc phê duyệt thủ công.")}


def rules(code, content):
    return [{**r, "source_code": code} for r in compile_text(code, content, TYPES)]


class RecommendTests(unittest.TestCase):

    def test_relaxing_rule_keeps_an_old_control_on_another_condition(self):
        result = validate(code="QD-MOI", title="t", content="Điều 1: Yêu cầu Thanh toán chi phí có giá trị dưới 5 "
                          "triệu đồng được tự động duyệt.", types=TYPES, others=[OLD])
        recs = {i["related"]["article"]: i["recommendation"] for i in result["supersedes"]}
        self.assertEqual(recs.get("Điều 1"), "KEEP")  # chia nhỏ hóa đơn: không tự gỡ
        keep = next(i for i in result["supersedes"] if i["recommendation"] == "KEEP")
        self.assertIn("nghi chia nhỏ", keep["reason"])
        self.assertTrue(keep["key"].startswith("QD-CU|"))
        self.assertFalse(any(w["kind"] == "RELAXES" and "Điều 1" in w["message"] for w in result["warnings"]))

    def test_new_threshold_drops_the_old_one(self):
        result = validate(code="QD-MOI", title="t", content="Điều 1: Yêu cầu Thanh toán chi phí có giá trị từ 50 "
                          "triệu đồng trở lên bắt buộc Giám đốc phê duyệt thủ công.", types=TYPES, others=[OLD])
        item = next(i for i in result["supersedes"] if i["related"]["article"] == "Điều 2")
        self.assertEqual(item["recommendation"], "DROP")
        self.assertIn("đổi ngưỡng", item["reason"])

    def test_kept_pair_is_not_superseded_by_learning(self):
        new = rules("QD-MOI", "Điều 1: Yêu cầu Thanh toán chi phí có giá trị dưới 5 triệu đồng được tự động duyệt.")
        old = rules("QD-CU", OLD["content"])
        origins = {rp.sentence_sha(r["description"]): {"version": "1.0"} for r in old}
        split = next(r for r in old if r.get("split_suspect"))
        _, superseded = rp.resolve(new + old, origins)
        self.assertTrue(any(e["old_rule"] == split["id"] for e in superseded))
        keep = {("QD-MOI", rp.sentence_sha(split["description"]))}
        kept, superseded = rp.resolve(new + old, origins, keep=keep)
        self.assertFalse(any(e["old_rule"] == split["id"] for e in superseded))
        self.assertFalse(next(r for r in kept if r["id"] == split["id"]).get("exclude"))


class QuickTemplateTests(unittest.TestCase):
    """Câu do mẫu nạp nhanh sinh ra (giống e2e/regulation-template.test.mjs)."""

    def test_template_sentences_compile_to_the_intended_rule(self):
        cases = {
            "Điều 2: Yêu cầu Thanh toán chi phí có giá trị trên 5 triệu đồng bắt buộc Giám đốc phê duyệt thủ công.":
                {"request_type": "EXPENSE_CLAIM", "amount_gt": 5_000_000, "auto_approve": False},
            "Điều 1: Yêu cầu Thanh toán chi phí có giá trị không quá 5 triệu đồng được tự động duyệt.":
                {"request_type": "EXPENSE_CLAIM", "amount_lte": 5_000_000, "auto_approve": True},
            "Điều 1: Yêu cầu Nghỉ phép từ 3 ngày trở lên bắt buộc Trưởng bộ phận phê duyệt thủ công kèm nghiệm thu độc "
            "lập.": {"request_type": "LEAVE", "days_gt": 2, "auto_approve": False, "escalate_to": "C"},
            "Điều 1: Yêu cầu Làm việc từ xa (WFH) lần thứ 4 trở lên trong tháng bắt buộc Trưởng bộ phận phê duyệt thủ "
            "công.": {"request_type": "WFH_REQ", "repeat_count_gte": 4, "auto_approve": False},
        }
        for sentence, expected in cases.items():
            (rule,) = compile_sentence(sentence, TYPES)
            for key, value in expected.items():
                self.assertEqual(rule.get(key), value, (sentence, key, rule))


if __name__ == "__main__":
    unittest.main()
