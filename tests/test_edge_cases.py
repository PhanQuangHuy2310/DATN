"""Ca oái oăm ở ranh giới: bad case, bộ máy luật quy định (v3) và trình biên dịch.

Mỗi ca ghi rõ vì sao là ranh giới: đúng bằng ngưỡng, thiếu dữ liệu, chữ có/không dấu, ranh giới quý/năm, ngày hiệu lực
đúng hôm nay, vùng loại trừ, phủ định trong câu quy định...
"""

import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO, os.path.join(REPO, "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

import bad_cases as bc

try:
    from routers.policy import PolicyRule, PolicySignals, rule_applies

    HAS_ROUTER_DEPS = True
except ImportError:  # venv gốc không cài fastapi: chạy phần này bằng ai_service/.venv-ai
    HAS_ROUTER_DEPS = False

from api_core.workflow import regulation_compiler as rc

S = bc.Signals


def hits(sig):
    return [c["code"] for c in bc.evaluate(sig).cases]


class BadCaseBoundaryTests(unittest.TestCase):

    def test_repeated_exemption_starts_at_the_fourth(self):
        self.assertNotIn("BC_REPEATED_EXEMPTION", hits(S("ATTENDANCE_ADJUSTMENT", attendance_count_30d=3)))
        self.assertIn("BC_REPEATED_EXEMPTION", hits(S("ATTENDANCE_ADJUSTMENT", attendance_count_30d=4)))

    def test_wfh_frequent_starts_at_the_eighth(self):
        self.assertNotIn("BC_WFH_FREQUENT", hits(S("WFH_REQ", same_type_count_month=7)))
        self.assertIn("BC_WFH_FREQUENT", hits(S("WFH_REQ", same_type_count_month=8)))

    def test_deadline_exactly_24_hours_counts_but_not_a_minute_more(self):
        self.assertIn("BC_DEADLINE_CONFLICT", hits(S("LEAVE", open_work_due_hours=[24.0], handover_assigned=False)))
        self.assertNotIn("BC_DEADLINE_CONFLICT", hits(S("LEAVE", open_work_due_hours=[24.02], handover_assigned=False)))

    def test_deadline_with_unknown_handover_is_treated_as_not_covered(self):
        self.assertIn("BC_DEADLINE_CONFLICT", hits(S("LEAVE", open_work_due_hours=[3.0], handover_assigned=None)))

    def test_team_absence_needs_a_real_team(self):
        self.assertNotIn("BC_TEAM_ABSENCE_PEAK", hits(S("LEAVE", team_size=2, team_absence_ratio=1.0)))
        self.assertIn("BC_TEAM_ABSENCE_PEAK", hits(S("LEAVE", team_size=3, team_absence_ratio=0.4)))

    def test_split_amount_needs_total_strictly_over_and_this_one_at_or_under(self):
        base = {"requester_finance_count_7d": 2}
        self.assertNotIn("BC_SPLIT_AMOUNT_EVASION",
                         hits(S("EXPENSE_CLAIM", amount=9_000_000, requester_amount_7d=20_000_000, **base)))
        self.assertIn("BC_SPLIT_AMOUNT_EVASION",
                      hits(S("EXPENSE_CLAIM", amount=20_000_000, requester_amount_7d=20_000_001, **base)))
        self.assertNotIn("BC_SPLIT_AMOUNT_EVASION",
                         hits(S("EXPENSE_CLAIM", amount=20_000_001, requester_amount_7d=40_000_000, **base)))

    def test_refund_and_off_hours_thresholds(self):
        self.assertNotIn("BC_REFUND_FREQUENT", hits(S("REFUND_COMPENSATION", same_type_count_7d=2)))
        self.assertIn("BC_REFUND_FREQUENT", hits(S("REFUND_COMPENSATION", same_type_count_7d=3)))
        self.assertNotIn("BC_OFF_HOURS_BULK", hits(S("EXPENSE_CLAIM", off_hours_count_7d=2)))
        self.assertIn("BC_OFF_HOURS_BULK", hits(S("EXPENSE_CLAIM", off_hours_count_7d=3)))

    def test_revoked_history_applies_to_any_type_even_lowercase_code(self):
        self.assertIn("BC_AI_REVOKED_HISTORY", hits(S("wfh_req", ai_revoked_90d=2)))
        self.assertNotIn("BC_AI_REVOKED_HISTORY", hits(S("LEAVE", ai_revoked_90d=1)))

    def test_bad_case_of_another_type_never_leaks(self):
        self.assertEqual(hits(S("ROOM_BOOKING", same_type_count_month=30, attendance_count_30d=30)), [])


def applies(rule: dict, type_code="EXPENSE_CLAIM", amount=0.0, days=0, **signals) -> bool:
    return rule_applies(PolicyRule(id="R", auto_approve=False, **rule), type_code, amount, days,
                        PolicySignals(**signals))


@unittest.skipUnless(HAS_ROUTER_DEPS, "fastapi/pydantic not installed")
class PolicyEngineEdgeTests(unittest.TestCase):

    def test_from_20_million_means_20_million_is_included(self):
        rule = {"amount_gt": 19_999_999}
        self.assertTrue(applies(rule, amount=20_000_000))
        self.assertFalse(applies(rule, amount=19_999_999))

    def test_upper_bound_is_inclusive(self):
        rule = {"amount_lte": 2_000_000}
        self.assertTrue(applies(rule, amount=2_000_000))
        self.assertFalse(applies(rule, amount=2_000_001))

    def test_missing_percent_never_matches(self):
        self.assertFalse(applies({"percent_gt": 14}, "SPECIAL_DISCOUNT"))
        self.assertTrue(applies({"percent_gt": 14}, "SPECIAL_DISCOUNT", percent=15))

    def test_location_ignores_case_and_diacritics(self):
        rule = {"location_contains": "Tầng 10"}
        self.assertTrue(applies(rule, "ROOM_BOOKING", location_text="phong hop TANG 10 - P1001"))
        self.assertFalse(applies(rule, "ROOM_BOOKING", location_text="Tầng 1"))

    def test_effective_dates_include_the_boundary_days(self):
        self.assertTrue(applies({"effective_from": "2027-01-01"}, today="2027-01-01"))
        self.assertFalse(applies({"effective_from": "2027-01-01"}, today="2026-12-31"))
        self.assertTrue(applies({"effective_until": "2026-12-31"}, today="2026-12-31"))
        self.assertFalse(applies({"effective_until": "2026-12-31"}, today="2027-01-01"))

    def test_rolling_window_edge_and_quarter_boundary(self):
        rule14 = {"repeat_count_gte": 2, "repeat_window": "ROLLING_14D"}
        self.assertTrue(applies(rule14, today="2027-01-15", same_type_dates=["2027-01-02"]))   # 13 ngày trước
        self.assertFalse(applies(rule14, today="2027-01-15", same_type_dates=["2027-01-01"]))  # đúng 14 ngày trước
        quarter = {"repeat_count_gte": 2, "repeat_window": "CALENDAR_QUARTER"}
        self.assertFalse(applies(quarter, today="2027-04-01", same_type_dates=["2027-03-31"]))  # khác quý
        self.assertTrue(applies(quarter, today="2027-06-30", same_type_dates=["2027-04-01"]))

    def test_retro_needs_a_known_date(self):
        self.assertFalse(applies({"retro_days_gt": 7}, "ATTENDANCE_ADJUSTMENT"))
        self.assertTrue(applies({"retro_days_gt": 7}, "ATTENDANCE_ADJUSTMENT", notice_hours=-24 * 8))
        self.assertFalse(applies({"retro_days_gt": 7}, "ATTENDANCE_ADJUSTMENT", notice_hours=-24 * 7))

    def test_exclude_zone_with_type_only_hits_that_type(self):
        rule = {"amount_gt": 100_000_000, "exclude": [{"request_type": "EXPENSE_CLAIM"}]}
        self.assertFalse(applies(rule, "EXPENSE_CLAIM", amount=150_000_000))
        self.assertTrue(applies(rule, "REFUND_COMPENSATION", amount=150_000_000))

    def test_partial_exclude_zone(self):
        rule = {"amount_gt": 4_000_000, "exclude": [{"amount_gt": 3_999_999, "amount_lte": 6_000_000}]}
        self.assertFalse(applies(rule, amount=5_000_000))
        self.assertFalse(applies(rule, amount=6_000_000))
        self.assertTrue(applies(rule, amount=6_000_001))


def load_types():
    with open(os.path.join(REPO, "ai_service", "training", "data", "request_types_snapshot.json"),
              encoding="utf-8") as handle:
        return [rc.RequestTypeName(r["code"], r["name"], r["lifecycle"]) for r in json.load(handle)["types"]]


TYPES = load_types()


def compiled(text):
    return [{k: v for k, v in r.items() if k not in ("id", "description", "approvers", "min_risk")}
            for r in rc.compile_text("R", text, TYPES)]


class CompilerOddityTests(unittest.TestCase):

    def test_threshold_without_control_word_is_not_a_rule(self):
        self.assertEqual(compiled("Yêu cầu Thanh toán chi phí trên 50 triệu đồng."), [])

    def test_amount_written_in_full_with_vnd(self):
        self.assertEqual(compiled("Yêu cầu Thanh toán chi phí trên 50.000.000 VNĐ bắt buộc duyệt thủ công.")[0]
                         ["amount_gt"], 50_000_000)

    def test_negated_auto_approval_is_manual(self):
        rule = compiled("Yêu cầu Mượn xe công vụ không được tự động duyệt.")[0]
        self.assertFalse(rule["auto_approve"])

    def test_article_header_with_title_does_not_leak_numbers(self):
        rules = compiled("Điều 12 (Hạn mức 2026): Yêu cầu Thanh toán chi phí trên 30 triệu đồng bắt buộc duyệt "
                         "thủ công.")
        self.assertEqual(rules[0]["amount_gt"], 30_000_000)

    def test_date_never_read_as_a_day_count(self):
        rules = compiled("Từ ngày 05/01/2027, yêu cầu Nghỉ phép trên 3 ngày bắt buộc duyệt thủ công.")
        self.assertEqual((rules[0]["days_gt"], rules[0]["effective_from"]), (3, "2027-01-05"))

    def test_invalid_date_is_not_guessed(self):
        self.assertEqual(compiled("Từ ngày 31/02/2027, yêu cầu Nghỉ phép trên 3 ngày bắt buộc duyệt thủ công."), [])

    def test_or_conditions_keep_shared_effective_date(self):
        rules = compiled("Kể từ ngày 01/03/2027, yêu cầu Thanh toán chi phí trên 50 triệu đồng hoặc lần thứ 4 trở "
                         "lên trong tháng bắt buộc duyệt thủ công.")
        self.assertEqual(len(rules), 2)
        self.assertTrue(all(r["effective_from"] == "2027-03-01" for r in rules))



class CompilerSafetyTests(unittest.TestCase):
    """Lỗi tìm ra khi dò ca oái oăm (18/11): trước khi sửa, các câu dưới đây hoặc mất ngưỡng tiền (thành luật chặn MỌI
    đơn của loại đó), hoặc đọc ngược nghĩa. Nguyên tắc: không chắc thì KHÔNG sinh luật, đưa câu lên admin kèm lý do."""

    def skip(self, text):
        return rc.skip_reason(text, TYPES)

    def test_abbreviated_million(self):
        self.assertEqual(compiled("Yêu cầu Thanh toán chi phí trên 50tr bắt buộc duyệt thủ công.")[0]["amount_gt"],
                         50_000_000)
        self.assertEqual(compiled("Yêu cầu Thanh toán chi phí từ 500k bắt buộc duyệt thủ công.")[0]["amount_gt"],
                         499_999)

    def test_negative_amount_is_not_dropped_into_block_all(self):
        text = "Yêu cầu Thanh toán chi phí trên -5 triệu bắt buộc duyệt thủ công."
        self.assertEqual(compiled(text), [])
        self.assertIn("không rõ", self.skip(text))

    def test_number_without_direction_is_not_dropped(self):
        self.assertEqual(compiled("Yêu cầu Thanh toán chi phí 50 triệu bắt buộc duyệt thủ công."), [])

    def test_split_threshold_without_direction_is_the_total(self):
        rules = compiled("Yêu cầu Thanh toán chi phí bị chia nhỏ để né ngưỡng 30 triệu bắt buộc duyệt thủ công.")
        self.assertEqual(rules[0]["split_total_gt"], 30_000_000)

    def test_not_required_is_not_manual(self):
        text = "Yêu cầu Thanh toán chi phí trên 50 triệu đồng không bắt buộc duyệt thủ công."
        self.assertEqual(compiled(text), [])
        self.assertIn("phủ định", self.skip(text))
        self.assertEqual(compiled("Yêu cầu Nghỉ phép không cần phê duyệt thủ công."), [])

    def test_not_allowed_auto_is_still_manual(self):
        self.assertFalse(compiled("Yêu cầu Nghỉ phép trên 5 ngày không được tự động duyệt.")[0]["auto_approve"])

    def test_empty_range(self):
        text = "Yêu cầu Thanh toán chi phí trên 50 triệu và dưới 20 triệu bắt buộc duyệt thủ công."
        self.assertEqual(compiled(text), [])
        self.assertIn("Khoảng rỗng", self.skip(text))

    def test_percent_over_100(self):
        text = "Yêu cầu Phê duyệt chiết khấu thương mại đặc biệt trên 150% bắt buộc duyệt thủ công."
        self.assertEqual(compiled(text), [])
        self.assertIn("100%", self.skip(text))

    def test_effective_dates_in_wrong_order(self):
        text = "Từ ngày 01/01/2028 đến ngày 01/01/2027, yêu cầu Nghỉ phép trên 5 ngày bắt buộc duyệt thủ công."
        self.assertEqual(compiled(text), [])
        self.assertIn("hiệu lực", self.skip(text))

    def test_type_name_without_leading_verb(self):
        rules = compiled("Yêu cầu Chiết khấu thương mại đặc biệt trên 15% bắt buộc duyệt thủ công.")
        self.assertEqual((rules[0]["request_type"], rules[0]["percent_gt"]), ("SPECIAL_DISCOUNT", 15))

    def test_short_type_name_after_verb_is_not_used(self):
        # "Đăng ký đi công tác" -> "đi công tác" quá ngắn, dễ trùng văn xuôi: không dùng làm tên loại.
        rules = compiled("Nhân viên đi công tác trên 5 ngày bắt buộc duyệt thủ công.")
        self.assertNotIn("BUSINESS_TRIP", [r["request_type"] for r in rules])

    def test_unaccented_sentence_is_flagged_not_silently_ignored(self):
        text = "yeu cau nghi phep tren 3 ngay bat buoc duyet thu cong."
        self.assertEqual(compiled(text), [])
        self.assertIn("không dấu", self.skip(text))

    def test_floor_without_area_word_is_a_location(self):
        # Trước đây "tầng 10" bị bỏ qua và luật thành "chặn mọi đơn đặt phòng họp" (tìm ra khi soạn quy định mẫu 19/11).
        rule = compiled("Yêu cầu Đặt phòng họp tầng 10 bắt buộc duyệt thủ công.")[0]
        self.assertEqual((rule["request_type"], rule["location_contains"]), ("ROOM_BOOKING", "tầng 10"))

    def test_orphan_number_does_not_become_block_all(self):
        text = "Yêu cầu Mượn xe công vụ loại 16 chỗ bắt buộc duyệt thủ công."
        self.assertEqual(compiled(text), [])
        self.assertIn("con số", self.skip(text))


if __name__ == "__main__":
    unittest.main()
