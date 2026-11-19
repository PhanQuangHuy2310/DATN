"""Quy định viết tắt / viết nhanh (19/11): ">3tr người duyệt, <5tr AI duyệt".

Trước đây các câu này không sinh luật nào và cũng không bị báo, nên quy định vẫn nạp được nhưng không có tác dụng:
loại mẫu A tiếp tục để AI tự duyệt mọi hồ sơ. Viết sau khi thấy lỗi (không phải bộ test băm trước).
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from api_core.workflow.regulation_compiler import (
    RequestTypeName,
    compile_sentence,
    skip_reason,
)
from api_core.workflow.regulation_validation import validate

TYPES = [
    RequestTypeName("EXPENSE_CLAIM", "Thanh toán chi phí", "A"),
    RequestTypeName("ADVANCE_SMALL", "Tạm ứng chi phí (<10tr)", "A"),
    RequestTypeName("LEAVE", "Nghỉ phép", "A"),
    RequestTypeName("WFH_REQ", "Làm việc từ xa (WFH)", "A"),
]


def rules(text):
    return [{k: v for k, v in r.items() if k in ("request_type", "amount_gt", "amount_lte", "days_gt", "days_lte",
                                                  "auto_approve")} for r in compile_sentence(text, TYPES)]


def check(content, others=None):
    return validate(code="QD-THU", title="Thử", content=content, types=TYPES, others=others or [])


class ShorthandTests(unittest.TestCase):

    def test_comparison_symbols_and_short_verbs(self):
        self.assertEqual(rules("Thanh toán chi phí >3tr người duyệt."),
                         [{"request_type": "EXPENSE_CLAIM", "amount_gt": 3_000_000, "auto_approve": False}])
        self.assertEqual(rules("Thanh toán chi phí <5tr AI duyệt."),
                         [{"request_type": "EXPENSE_CLAIM", "amount_lte": 4_999_999, "auto_approve": True}])
        self.assertEqual(rules("Thanh toán chi phí ≥ 10 triệu giám đốc duyệt.")[0]["amount_gt"], 9_999_999)
        self.assertEqual(rules("Thanh toán chi phí <= 2 triệu để AI tự duyệt.")[0],
                         {"request_type": "EXPENSE_CLAIM", "amount_lte": 2_000_000, "auto_approve": True})
        self.assertEqual(rules("Nghỉ phép >3 ngày cần quản lý duyệt.")[0]["days_gt"], 3)

    def test_negated_ai_means_a_person_approves(self):
        for text in ("Thanh toán chi phí trên 3 triệu AI không được duyệt.",
                     "Thanh toán chi phí trên 3 triệu không để AI duyệt.",
                     "Thanh toán chi phí trên 3 triệu không được tự duyệt."):
            self.assertEqual(rules(text)[0]["auto_approve"], False, text)

    def test_one_sentence_with_both_directions_is_split(self):
        expected = [{"request_type": "EXPENSE_CLAIM", "amount_gt": 3_000_000, "auto_approve": False},
                    {"request_type": "EXPENSE_CLAIM", "amount_lte": 4_999_999, "auto_approve": True}]
        self.assertEqual(rules("Thanh toán chi phí >3tr người duyệt <5tr AI duyệt"), expected)
        self.assertEqual(rules("Thanh toán chi phí trên 3 triệu cần người duyệt, dưới 5 triệu thì AI tự duyệt."),
                         expected)
        # Vế AI tự duyệt đứng trước, ngăn bằng dấu phẩy.
        self.assertEqual(rules("Thanh toán chi phí AI tự duyệt khi không quá 3 triệu, người duyệt khi trên 3 triệu."),
                         [{"request_type": "EXPENSE_CLAIM", "amount_lte": 3_000_000, "auto_approve": True},
                          {"request_type": "EXPENSE_CLAIM", "amount_gt": 3_000_000, "auto_approve": False}])

    def test_type_names_with_symbols_still_match(self):
        self.assertEqual(rules("Tạm ứng chi phí (<10tr) trên 5 triệu bắt buộc kế toán phê duyệt thủ công.")[0],
                         {"request_type": "ADVANCE_SMALL", "amount_gt": 5_000_000, "auto_approve": False})

    def test_unclear_approval_sentence_is_reported_not_ignored(self):
        self.assertIsNotNone(skip_reason("Thanh toán chi phí 3tr thì duyệt nhanh.", TYPES))
        self.assertEqual(rules("Nhân viên cần duyệt lại hồ sơ trước khi gửi."), [])
        self.assertIsNone(skip_reason("Nhân viên cần duyệt lại hồ sơ trước khi gửi.", TYPES))


class OverlapValidationTests(unittest.TestCase):

    def test_overlapping_thresholds_are_blocked_with_the_zone_and_a_fix(self):
        result = check("Điều 1. Thanh toán chi phí >3tr người duyệt.\nĐiều 2. Thanh toán chi phí <5tr AI duyệt.")
        self.assertFalse(result["ok"])
        message = result["errors"][0]["message"]
        self.assertIn("số tiền ≤ 4.999.999", message)  # không còn "(mọi hồ sơ)"
        self.assertIn("số tiền trên 3.000.000 đến 4.999.999", message)
        self.assertIn("không quá 3.000.000", message)
        self.assertIn("hệ thống sẽ bắt người duyệt", message)

    def test_same_rule_without_overlap_is_accepted(self):
        for content in ("Thanh toán chi phí >3tr người duyệt, ≤3tr AI duyệt.",
                        ("Điều 1. Thanh toán chi phí trên 3 triệu người duyệt.\n"
                         "Điều 2. Thanh toán chi phí không quá 3 triệu AI tự duyệt.")):
            result = check(content)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["rules"], 2)

    def test_newer_regulation_that_relaxes_an_old_control_is_flagged(self):
        old = {"code": "QD-CU", "content": "Điều 1: Thanh toán chi phí trên 3 triệu bắt buộc kế toán phê duyệt thủ công."}
        result = check("Thanh toán chi phí <5tr AI duyệt.", others=[old])
        self.assertTrue(result["ok"])
        relax = [w for w in result["warnings"] if w["kind"] == "RELAXES"]
        self.assertEqual(len(relax), 1)
        self.assertIn("số tiền trên 3.000.000 đến 4.999.999", relax[0]["message"])
        self.assertIn("Điều 1 của QD-CU", relax[0]["message"])


    def test_ai_approval_clause_without_effect_is_flagged(self):
        weighted = [RequestTypeName("EXPENSE_CLAIM", "Thanh toán chi phí", "A", 3),
                    RequestTypeName("LEAVE", "Nghỉ phép", "A", 2)]
        content = "Thanh toán chi phí <5tr AI duyệt. Nghỉ phép dưới 2 ngày AI tự duyệt."
        result = validate(code="QD-THU", title="t", content=content, types=weighted, others=[], auto_max_weight=2)
        flagged = [w for w in result["warnings"] if w["kind"] == "AUTO_NO_EFFECT"]
        self.assertEqual(len(flagged), 1)
        self.assertIn("«Thanh toán chi phí»", flagged[0]["message"])
        self.assertIn("đang là 3", flagged[0]["message"])
        off = validate(code="QD-THU", title="t", content=content, types=weighted, others=[], auto_max_weight=0)
        self.assertEqual(sum(w["kind"] == "AUTO_NO_EFFECT" for w in off["warnings"]), 2)
        unknown = validate(code="QD-THU", title="t", content=content, types=weighted, others=[])
        self.assertFalse(any(w["kind"] == "AUTO_NO_EFFECT" for w in unknown["warnings"]))


if __name__ == "__main__":
    unittest.main()
