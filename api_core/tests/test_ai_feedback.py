"""Vòng phản hồi: bộ nhớ ca sửa quyết định của AI đúng phạm vi, luật admin duyệt được kiểm tra."""

from unittest.mock import patch

from django.test import SimpleTestCase

from api_core.workflow import ai_feedback
from api_core.workflow.ai_learning import validate_review_rules
from api_core.workflow.regulation_compiler import RequestTypeName, skip_reason

REVOKED = [{"id": "f1", "request_code": "EAS-1", "case_codes": [], "reason": "Trùng họp", "human_decision": {},
            "actor_name": "Quản lý A", "created_at": "2026-11-18T00:00:00"}]
OVERRULED = [{"id": "f2", "request_code": "EAS-2", "case_codes": ["BC_WFH_FREQUENT"], "reason": "Làm tại khách hàng",
              "human_decision": {}, "actor_name": "Quản lý B", "created_at": "2026-11-18T00:00:00"}]


def fake_memory(revoked=(), overruled=()):
    def memory(cursor, *, kind, type_code, subject_id):
        return {"AUTO_APPROVE_REVOKED": list(revoked), "ESCALATION_UNNECESSARY": list(overruled)}.get(kind, [])

    return memory


class MemoryTests(SimpleTestCase):
    def apply(self, verdict, revoked=(), overruled=(), lifecycle="A"):
        with patch.object(ai_feedback, "memory", side_effect=fake_memory(revoked, overruled)):
            return ai_feedback.apply_to_verdict(None, verdict=verdict, type_code="WFH_REQ",
                                                requester_id="u1", lifecycle=lifecycle)

    def test_no_memory_keeps_the_decision(self):
        out = self.apply({"decision": "auto_approve"})
        self.assertEqual(out["decision"], "auto_approve")
        self.assertEqual(out["learned"], [])

    def test_revoked_before_means_no_auto_approval_and_escalation(self):
        out = self.apply({"decision": "auto_approve"}, revoked=REVOKED)
        self.assertEqual(out["decision"], "escalate_to_human")
        self.assertEqual(out["escalate_to"], "B")
        self.assertEqual(out["escalation_causes"][-1]["code"], "LEARNED_REVOKE")
        self.assertIn("EAS-1", out["learned"][0]["text"])

    def test_overruled_bad_case_is_not_escalated_again(self):
        verdict = {"decision": "escalate_to_human", "escalate_to": "B",
                   "escalation_causes": [{"source": "BAD_CASE", "code": "BC_WFH_FREQUENT", "escalate_to": "B"}]}
        out = self.apply(verdict, overruled=OVERRULED)
        self.assertIsNone(out["escalate_to"])
        self.assertEqual(out["decision"], "escalate_to_human")  # vẫn có người duyệt
        self.assertEqual(out["learned"][0]["suppressed"], ["BC_WFH_FREQUENT"])

    def test_other_bad_case_still_escalates(self):
        verdict = {"escalate_to": "B",
                   "escalation_causes": [{"source": "BAD_CASE", "code": "BC_DEADLINE_CONFLICT", "escalate_to": "B"}]}
        self.assertEqual(self.apply(verdict, overruled=OVERRULED)["escalate_to"], "B")

    def test_regulation_cause_is_never_suppressed_by_memory(self):
        verdict = {"escalate_to": "C", "escalation_causes": [
            {"source": "BAD_CASE", "code": "BC_WFH_FREQUENT", "escalate_to": "B"},
            {"source": "REGULATION", "code": "QC05-4", "escalate_to": "C"}]}
        self.assertEqual(self.apply(verdict, overruled=OVERRULED)["escalate_to"], "C")


CODES = frozenset({"SPECIAL_DISCOUNT", "LEAVE"})
TYPES = (
    RequestTypeName("SPECIAL_DISCOUNT", "Phê duyệt chiết khấu thương mại đặc biệt", "A"),
    RequestTypeName("EXPENSE_CLAIM", "Thanh toán chi phí", "A"),
)


class ReviewRuleValidationTests(SimpleTestCase):

    def test_valid_rule_gets_default_risk(self):
        rules = validate_review_rules([{"request_type": "SPECIAL_DISCOUNT", "auto_approve": False}], CODES)
        self.assertEqual(rules[0]["min_risk"], 4)

    def test_rejects_unknown_type_field_and_widening(self):
        for bad in (
            [{"request_type": "NOPE", "auto_approve": False}],
            [{"request_type": "LEAVE", "auto_approve": False, "drop_table": 1}],
            [{"request_type": "LEAVE", "auto_approve": True, "due_within_hours": 24}],
            [{"request_type": "LEAVE", "auto_approve": False, "escalate_to": "D"}],
            [],
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_review_rules(bad, CODES)


class SkipReasonTests(SimpleTestCase):

    def test_reports_only_controlled_sentences_that_could_not_compile(self):
        self.assertIsNotNone(skip_reason("Phê duyệt chiết khấu thương mại đặc biệt từ 25% trở lên bắt buộc "
                                         "duyệt thủ công.", list(TYPES)))
        self.assertIsNone(skip_reason("Thanh toán chi phí từ 40 triệu đồng trở lên bắt buộc duyệt thủ công.",
                                      list(TYPES)))
        self.assertIsNone(skip_reason("Phòng họp giao ban sáng thứ Hai.", list(TYPES)))
