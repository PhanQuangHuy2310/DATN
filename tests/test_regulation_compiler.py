"""Trình biên dịch quy định v2: điều kiện ngữ cảnh, tách 'hoặc', không chặn tràn.

Các câu ở đây KHÔNG lấy từ tập test đã băm (ai_service/training/data/regulation_clauses_test.json).
"""

import unittest

from api_core.workflow.regulation_compiler import (
    RequestTypeName,
    compile_regulations,
    compile_text,
    rule_key,
)

TYPES = [
    RequestTypeName("LEAVE", "Nghỉ phép", "A"),
    RequestTypeName("LEAVE_SPECIAL", "Nghỉ phép đặc biệt", "A"),
    RequestTypeName("ATTENDANCE_ADJUSTMENT", "Điều chỉnh chấm công", "A"),
    RequestTypeName("EXPENSE_CLAIM", "Thanh toán chi phí", "A"),
    RequestTypeName("ADVANCE_SMALL", "Tạm ứng chi phí (<10tr)", "B"),
    RequestTypeName("PURCHASE", "Mua sắm", "B"),
]


def only(rules, **keys):
    return [r for r in rules if all(r.get(k) == v for k, v in keys.items())]


class ContextConditionTests(unittest.TestCase):
    def test_deadline_without_handover_is_a_condition_not_a_blanket_block(self):
        rules = compile_text(
            "R",
            "Đơn Nghỉ phép khi người gửi còn việc đến hạn trong 72 giờ mà chưa bàn giao thì "
            "phải được Trưởng bộ phận duyệt thủ công.",
            TYPES,
        )
        self.assertEqual(len(rules), 1)
        r = rules[0]
        self.assertEqual(
            (r["request_type"], r["due_within_hours"], r["require_no_handover"]),
            ("LEAVE", 72, True),
        )
        self.assertIs(r["auto_approve"], False)
        self.assertEqual(r["escalate_to"], "B")  # tình huống xấu trên loại A -> B
        self.assertNotIn("days_gt", r)  # '72 giờ' không phải thời lượng nghỉ

    def test_longer_type_name_is_not_also_matched_as_the_shorter_one(self):
        rules = compile_text(
            "R", "Nghỉ phép đặc biệt quá 5 ngày bắt buộc duyệt thủ công.", TYPES
        )
        self.assertEqual([r["request_type"] for r in rules], ["LEAVE_SPECIAL"])

    def test_repeat_count_and_window(self):
        rules = compile_text(
            "R",
            "Điều chỉnh chấm công quá 4 lần trong 30 ngày bắt buộc duyệt thủ công.",
            TYPES,
        )
        self.assertEqual(
            (rules[0]["repeat_count_gte"], rules[0]["repeat_window"]),
            (5, "ROLLING_30D"),
        )
        self.assertNotIn(
            "days_gt", rules[0]
        )  # '30 ngày' là cửa sổ, không phải thời lượng

    def test_or_between_conditions_yields_two_rules(self):
        rules = compile_text(
            "R",
            "Thanh toán chi phí trên 25 triệu đồng hoặc có dấu hiệu chia nhỏ phải qua Kế toán và "
            "nghiệm thu độc lập.",
            TYPES,
        )
        self.assertEqual(len(rules), 2)
        amount = only(rules, amount_gt=25_000_000)[0]
        split = only(rules, split_suspect=True)[0]
        self.assertNotIn("amount_gt", split)
        self.assertEqual(split["split_total_gt"], 25_000_000)
        self.assertEqual({amount["escalate_to"], split["escalate_to"]}, {"C"})
        self.assertEqual(split["approvers"], ["FINANCE"])

    def test_or_between_type_names_is_not_split(self):
        rules = compile_text(
            "R",
            "Nghỉ phép hoặc Điều chỉnh chấm công từ lần thứ 3 trong tháng bắt buộc duyệt "
            "thủ công.",
            TYPES,
        )
        self.assertEqual(
            sorted(r["request_type"] for r in rules), ["ATTENDANCE_ADJUSTMENT", "LEAVE"]
        )
        self.assertTrue(all(r["repeat_count_gte"] == 3 for r in rules))

    def test_type_b_is_not_escalated_to_b_but_acceptance_lifts_it_to_c(self):
        b = compile_text(
            "R", "Tạm ứng chi phí (<10tr) có dấu hiệu chia nhỏ phải qua Kế toán.", TYPES
        )
        self.assertNotIn("escalate_to", b[0])
        c = compile_text(
            "R",
            "Tạm ứng chi phí (<10tr) có dấu hiệu chia nhỏ phải qua Kế toán và nghiệm thu.",
            TYPES,
        )
        self.assertEqual(c[0]["escalate_to"], "C")


class OverBlockingGuardTests(unittest.TestCase):
    def test_unsupported_conditions_produce_no_rule(self):
        for text in (
            "Mua sắm từ 15% ngân sách trở lên bắt buộc duyệt thủ công.",
            "Nghỉ phép khi đi nước ngoài phải được Trưởng bộ phận phê duyệt thủ công.",
            "Điều chỉnh chấm công cho ngày đã quá 10 ngày bắt buộc duyệt thủ công.",
            "Thanh toán chi phí dưới 1 triệu được tự động duyệt.",
        ):
            with self.subTest(text=text):
                self.assertEqual(compile_text("R", text, TYPES), [])

    def test_context_never_widens_auto_approval(self):
        text = "Nghỉ phép được tự động duyệt khi có việc đến hạn trong 24 giờ."
        self.assertEqual(compile_text("R", text, TYPES), [])

    def test_article_header_is_ignored(self):
        rules = compile_text(
            "R",
            "Điều 9 (Chống chia nhỏ Thanh toán chi phí): Thanh toán chi phí từ 12 triệu đồng trở lên "
            "bắt buộc duyệt thủ công.",
            TYPES,
        )
        self.assertEqual(len(rules), 1)
        self.assertNotIn("split_suspect", rules[0])
        self.assertEqual(rules[0]["amount_gt"], 11_999_999)

    def test_staff_called_nhan_su_is_not_the_hr_department(self):
        rules = compile_text(
            "R",
            "Điều chỉnh chấm công khi nhân sự quên chấm công từ lần thứ 3 trong tháng bắt buộc Trưởng "
            "bộ phận phê duyệt thủ công.",
            TYPES,
        )
        self.assertEqual(rules[0]["approvers"], ["DIRECT_MANAGER"])


class CompatibilityTests(unittest.TestCase):
    def test_v1_behaviour_on_plain_thresholds_is_kept(self):
        reg = {
            "code": "REG-9",
            "content": "Yêu cầu Mua sắm trên 5 triệu bắt buộc duyệt thủ công. "
            "Mọi yêu cầu được AI đối chiếu tự động.",
        }
        rules = {r["id"]: r for r in compile_regulations([reg], TYPES)}
        self.assertEqual(rules["REG-9-1-PURCHASE"]["amount_gt"], 5_000_000)
        self.assertEqual(rules["REG-9-1-PURCHASE"]["min_risk"], 4)
        self.assertIs(rules["REG-9-2"]["auto_approve"], True)

    def test_rule_key_keeps_zero_thresholds(self):
        self.assertIn(
            ("days_gt", 0),
            rule_key({"request_type": "LEAVE", "days_gt": 0, "auto_approve": False}),
        )


if __name__ == "__main__":
    unittest.main()
