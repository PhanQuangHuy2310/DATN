"""AI đọc văn bản quy định trước khi học: lỗi ký tự, mâu thuẫn, trùng lặp; và phát hiện thay đổi so với bản đã áp dụng."""

import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from api_core.workflow.regulation_compiler import RequestTypeName
from api_core.workflow.regulation_rejection import changes
from api_core.workflow.regulation_validation import validate

TYPES = [
    RequestTypeName("LEAVE", "Nghỉ phép", "A"),
    RequestTypeName("WFH_REQ", "Làm việc từ xa (WFH)", "A"),
    RequestTypeName("REFUND_COMPENSATION", "Hoàn tiền / Đền bù", "A"),
    RequestTypeName("EXPENSE_CLAIM", "Thanh toán chi phí", "A"),
    RequestTypeName("ATTENDANCE_ADJUSTMENT", "Điều chỉnh chấm công", "A"),
    RequestTypeName("LEAVE_SPECIAL", "Nghỉ phép đặc biệt", "A"),
    RequestTypeName("ADVANCE_SMALL", "Tạm ứng chi phí (<10tr)", "B"),
    RequestTypeName("ADVANCE_MEDIUM", "Tạm ứng chi phí (10-50tr)", "B"),
]


def qc05() -> str:
    with open(os.path.join(REPO, "tests", "live", "test_ai_escalation.py"), encoding="utf-8") as handle:
        return re.search(r"QC05_TEXT = '(.*?)'\n", handle.read()).group(1)


def kinds(result, severity="errors"):
    return [i["kind"] for i in result[severity]]


class ValidateTests(unittest.TestCase):

    def run_check(self, content, title="Quy định thử", others=None):
        return validate(code="QD-TEST", title=title, content=content, types=TYPES, others=others)

    def test_real_regulation_passes(self):
        result = self.run_check(qc05(), title="Quy chế 05/2026")
        self.assertTrue(result["ok"], result["errors"])
        self.assertGreaterEqual(result["rules"], 8)

    def test_contradiction_inside_one_text_names_both_articles(self):
        result = self.run_check(
            "Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 5 triệu đồng được phép tự động duyệt. "
            "Điều 2: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 2 triệu đồng không được tự động duyệt."
        )
        self.assertFalse(result["ok"])
        error = result["errors"][0]
        self.assertEqual(error["kind"], "CONTRADICTION")
        self.assertIn("Điều 1", error["message"])
        self.assertIn("Điều 2", error["message"])
        self.assertEqual(error["related"]["article"], "Điều 2")

    def test_contradiction_with_regulation_in_force(self):
        result = self.run_check("Điều 1: Yêu cầu Làm việc từ xa (WFH) được tự động duyệt.",
                                others=[{"code": "QC05", "content": qc05()}])
        self.assertEqual(kinds(result), ["CONTRADICTION"])
        self.assertIn("QC05", result["errors"][0]["message"])

    def test_broken_encoding_and_lost_diacritics_are_blocked(self):
        mojibake = "Äiá»u 1: YÃªu cáº§u Nghá»‰ phÃ©p tá»« 5 ngÃ y báº¯t buá»™c duyá»‡t thá»§ cÃ´ng."
        self.assertIn("GARBLED", kinds(self.run_check(mojibake)))
        self.assertIn("GARBLED", kinds(self.run_check("Di?u 1: Y?u c?u Ngh? ph?p b?t bu?c duy?t th? c?ng.")))
        self.assertIn("GARBLED", kinds(self.run_check("Yêu cầu Nghỉ phép � từ 5 ngày bắt buộc duyệt thủ công.")))

    def test_question_mark_in_a_normal_sentence_is_fine(self):
        result = self.run_check("Nhân viên có câu hỏi? Liên hệ phòng Nhân sự.")
        self.assertNotIn("GARBLED", kinds(result))

    def test_warnings_do_not_block(self):
        dup = self.run_check("Yêu cầu Hoàn tiền / Đền bù có giá trị trên 2 triệu đồng không được tự động duyệt.",
                             others=[{"code": "QC05", "content": qc05()}])
        self.assertTrue(dup["ok"])
        self.assertIn("DUPLICATE", kinds(dup, "warnings"))
        unparsed = self.run_check("Phê duyệt chiết khấu thương mại đặc biệt từ 15% trở lên phải qua Ban Giám đốc.")
        self.assertTrue(unparsed["ok"])
        self.assertTrue(any(k in ("UNPARSED", "NO_CONTROL") for k in kinds(unparsed, "warnings")))

    def test_empty_content_is_an_error(self):
        self.assertIn("EMPTY", kinds(self.run_check("   ")))


class ChangesTests(unittest.TestCase):

    def test_detects_create_update_delete_against_applied_snapshot(self):
        applied = [{"code": "A", "title": "A", "content": "x", "version": "1.0"},
                   {"code": "B", "title": "B", "content": "y", "version": "2.0"},
                   {"code": "C", "title": "C", "content": "z", "version": "3.0"}]
        current = [{"code": "A", "title": "A", "content": "x", "version": "1.0"},
                   {"code": "B", "title": "B", "content": "y2", "version": "4.1"},
                   {"code": "D", "title": "D", "content": "w", "version": "5.0"}]
        got = {c["code"]: c["action"] for c in changes(current, applied)}
        self.assertEqual(got, {"B": "UPDATE", "C": "DELETE", "D": "CREATE"})

    def test_version_only_difference_is_not_a_change(self):
        applied = [{"code": "A", "title": "A", "content": "x", "version": "1.0"}]
        current = [{"code": "A", "title": "A", "content": "x", "version": "7.3"}]
        self.assertEqual(changes(current, applied), [])


if __name__ == "__main__":
    unittest.main()
