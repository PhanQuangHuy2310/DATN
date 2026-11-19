"""AI đọc văn bản quy định trước khi học: lỗi ký tự, mâu thuẫn, trùng lặp; và phát hiện thay đổi so với bản đã áp dụng."""

import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from api_core.workflow.regulation_compiler import RequestTypeName
from api_core.workflow.regulation_precedence import next_origins, resolve
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

    def test_opposite_rule_in_another_regulation_is_replaced_not_blocked(self):
        # Quy định mới thắng quy định cũ: không còn là lỗi, AI báo sẽ thay thế điều nào.
        result = self.run_check("Điều 1: Yêu cầu Làm việc từ xa (WFH) được tự động duyệt.",
                                others=[{"code": "QC05", "content": qc05()}])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(kinds(result, "supersedes"), ["SUPERSEDES"])
        self.assertIn("Điều 5 của QC05", result["supersedes"][0]["message"])

    def test_higher_threshold_replaces_the_old_one(self):
        old = {"code": "QD-CU", "content": "Điều 1: Yêu cầu Thanh toán chi phí từ 40 triệu đồng trở lên bắt buộc "
                                           "Kế toán phê duyệt thủ công."}
        result = self.run_check("Điều 1: Yêu cầu Thanh toán chi phí từ 50 triệu đồng trở lên bắt buộc Giám đốc phê "
                                "duyệt thủ công.", others=[old])
        self.assertTrue(result["ok"])
        self.assertIn("49.999.999 thay cho số tiền > 39.999.999", result["supersedes"][0]["message"])

    def test_different_condition_kind_does_not_replace(self):
        old = {"code": "QD-CU", "content": "Yêu cầu Nghỉ phép từ 5 ngày trở lên bắt buộc duyệt thủ công."}
        result = self.run_check("Yêu cầu Thanh toán chi phí từ 50 triệu đồng trở lên bắt buộc duyệt thủ công.",
                                others=[old])
        self.assertEqual(result["supersedes"], [])

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
        self.assertIn("SUPERSEDES", kinds(dup, "supersedes"))
        unparsed = self.run_check("Yêu cầu Hoàn tiền / Đền bù cho khách hàng thân thiết bắt buộc duyệt thủ công.")
        self.assertTrue(unparsed["ok"])
        self.assertTrue(any(k in ("UNPARSED", "NO_CONTROL") for k in kinds(unparsed, "warnings")))

    def test_empty_content_is_an_error(self):
        self.assertIn("EMPTY", kinds(self.run_check("   ")))


def rule(rid, text, **kw):
    return {"id": rid, "description": text, "source_code": rid.rsplit("-", 2)[0], **kw}


class PrecedenceTests(unittest.TestCase):
    """Quy định mới thắng quy định cũ tương tự (40 tr -> 50 tr), từng câu, chỉ trong phạm vi bị chồng."""

    OLD40 = rule("QDCU-1-EXPENSE_CLAIM", "Thanh toán từ 40 triệu duyệt thủ công", request_type="EXPENSE_CLAIM",
                 amount_gt=39_999_999, auto_approve=False)
    LEAVE = rule("QDCU-2-LEAVE", "Nghỉ phép từ 5 ngày duyệt thủ công", request_type="LEAVE", days_gt=4,
                 auto_approve=False)
    ALL100 = rule("REGALL-1-X", "Mọi yêu cầu trên 100 triệu duyệt thủ công", amount_gt=100_000_000,
                  auto_approve=False)
    NEW50 = rule("QDMOI-1-EXPENSE_CLAIM", "Thanh toán từ 50 triệu Giám đốc duyệt", request_type="EXPENSE_CLAIM",
                 amount_gt=49_999_999, auto_approve=False, approvers=["DIRECTOR"])

    def origins(self, *rules, version="3.0"):
        return next_origins(list(rules), {}, version)

    def test_new_threshold_drops_the_old_one_and_narrows_general_rule(self):
        kept, sup = resolve([self.OLD40, self.LEAVE, self.ALL100, self.NEW50],
                            self.origins(self.OLD40, self.LEAVE, self.ALL100))
        ids = {r["id"]: r for r in kept}
        self.assertNotIn("QDCU-1-EXPENSE_CLAIM", ids)
        self.assertIn("QDCU-2-LEAVE", ids)  # khác kiểu điều kiện: giữ
        # Luật chung "mọi loại" chỉ bị thay ở loại Thanh toán (vùng loại trừ cả loại đó).
        self.assertEqual(ids["REGALL-1-X"]["exclude"], [{"request_type": "EXPENSE_CLAIM"}])
        self.assertEqual({(e["old_code"], e["scope"]) for e in sup}, {("QDCU", "ALL"), ("REGALL", "TYPE")})

    def test_bounded_new_rule_only_excludes_its_range(self):
        old = rule("QDCU-1-REFUND", "Hoàn tiền trên 4 triệu duyệt thủ công", request_type="REFUND",
                   amount_gt=4_000_000, auto_approve=False)
        new = rule("QDMOI-1-REFUND", "Hoàn tiền 4-6 triệu được tự duyệt", request_type="REFUND",
                   amount_gt=3_999_999, amount_lte=6_000_000, auto_approve=True)
        kept, sup = resolve([old, new], self.origins(old))
        zone = next(r for r in kept if r["id"] == "QDCU-1-REFUND")["exclude"][0]
        self.assertEqual((zone["amount_gt"], zone["amount_lte"]), (3_999_999, 6_000_000))
        self.assertEqual(sup[0]["scope"], "PART")

    def test_future_effective_date_keeps_old_rule_until_the_day_before(self):
        new = rule("QDMOI-1-LEAVE", "Từ 01/01/2027 nghỉ trên 7 ngày duyệt", request_type="LEAVE", days_gt=7,
                   auto_approve=False, effective_from="2027-01-01")
        old = rule("QDCU-2-LEAVE", "Nghỉ trên 4 ngày duyệt", request_type="LEAVE", days_gt=4, auto_approve=False)
        kept, _sup = resolve([old, new], self.origins(old))
        self.assertEqual(next(r for r in kept if r["id"] == "QDCU-2-LEAVE")["effective_until"], "2026-12-31")

    def test_replacement_is_permanent_after_new_regulation_is_removed(self):
        origins = self.origins(self.OLD40, version="3.0")
        _kept, sup = resolve([self.OLD40, self.NEW50], origins)
        origins = next_origins([self.OLD40, self.NEW50], origins, "4.0", sup)
        kept, sup = resolve([self.OLD40], origins)  # QD mới bị bãi bỏ
        self.assertEqual(kept, [])
        self.assertTrue(sup[0]["persisted"])

    def test_without_a_newer_sentence_nothing_is_replaced(self):
        kept, sup = resolve([self.OLD40, self.ALL100], self.origins(self.OLD40, self.ALL100))
        self.assertEqual(sup, [])
        self.assertEqual(len(kept), 2)

    def test_rules_of_the_same_regulation_never_replace_each_other(self):
        same = rule("QDCU-3-EXPENSE_CLAIM", "Thanh toán từ 60 triệu duyệt", request_type="EXPENSE_CLAIM",
                    amount_gt=60_000_000, auto_approve=False)
        _kept, sup = resolve([self.OLD40, same], self.origins(self.OLD40))
        self.assertEqual(sup, [])

    def test_older_sentence_keeps_its_age_when_other_sentences_change(self):
        origins = self.origins(self.OLD40, version="3.0")
        origins.update(self.origins(self.NEW50, version="5.0"))
        # Văn bản cũ được sửa ở câu khác (lên phiên bản 7.0) nhưng câu 40 tr vẫn là câu cũ -> 50 tr vẫn thắng.
        _kept, sup = resolve([self.OLD40, self.NEW50, self.LEAVE], origins)
        self.assertEqual([e["old_rule"] for e in sup], ["QDCU-1-EXPENSE_CLAIM"])


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
