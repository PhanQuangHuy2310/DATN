"""Luật quy định có điều kiện ngữ cảnh được AI xét trên tín hiệu thật, không chặn tràn cả loại.

Bộ luật mẫu là đầu ra của trình biên dịch v2 cho Quy chế 05/2026 (Điều 1, 2, 4).
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import fastapi  # noqa: F401
    import loguru  # noqa: F401
    import pydantic_settings  # noqa: F401

    HAS_ROUTER_DEPS = True
except ImportError:
    HAS_ROUTER_DEPS = False

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO_ROOT, os.path.join(REPO_ROOT, "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

POLICY = {
    "version": "v2.0",
    "rules": [
        {
            "id": "QC05-1-LEAVE",
            "description": "Điều 1",
            "request_type": "LEAVE",
            "days_gt": 0,
            "due_within_hours": 24,
            "require_no_handover": True,
            "min_risk": 5,
            "auto_approve": False,
            "escalate_to": "B",
            "approvers": ["DIRECT_MANAGER", "HR_MANAGER"],
        },
        {
            "id": "QC05-2-ATTENDANCE",
            "description": "Điều 2",
            "request_type": "ATTENDANCE_ADJUSTMENT",
            "repeat_count_gte": 4,
            "repeat_window": "CALENDAR_MONTH",
            "min_risk": 4,
            "auto_approve": False,
            "escalate_to": "B",
        },
        {
            "id": "QC05-4-EXPENSE_CLAIM-2",
            "description": "Điều 4",
            "request_type": "EXPENSE_CLAIM",
            "split_suspect": True,
            "split_total_gt": 14_999_999,
            "min_risk": 5,
            "auto_approve": False,
            "escalate_to": "C",
        },
    ],
}


@unittest.skipUnless(HAS_ROUTER_DEPS, "fastapi/loguru/pydantic_settings not installed")
class ContextRuleTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(POLICY, handle, ensure_ascii=False)
        self.addCleanup(os.remove, self.path)

    def run_policy(self, request_type, amount=0.0, days=1, **signals):
        from routers.policy import PolicySignals, apply_policy, matched_escalation

        sig = PolicySignals(**signals)
        risk, manual, matched, _ = apply_policy(
            request_type=request_type,
            amount=amount,
            days=days,
            risk=2,
            path=self.path,
            signals=sig,
        )
        target, _ = matched_escalation(
            request_type=request_type,
            amount=amount,
            days=days,
            path=self.path,
            signals=sig,
        )
        return risk, manual, matched, target

    def test_leave_without_open_work_is_not_blocked(self):
        _risk, manual, matched, target = self.run_policy("LEAVE")
        self.assertEqual((manual, matched, target), (False, [], None))

    def test_leave_with_work_due_and_no_handover_is_escalated_to_b(self):
        risk, manual, matched, target = self.run_policy(
            "LEAVE", open_work_due_hours=[5.0, 60.0]
        )
        self.assertEqual(
            (risk, manual, matched, target), (5, True, ["QC05-1-LEAVE"], "B")
        )

    def test_handover_assigned_clears_the_deadline_rule(self):
        _risk, manual, _matched, target = self.run_policy(
            "LEAVE", open_work_due_hours=[5.0], handover_assigned=True
        )
        self.assertEqual((manual, target), (False, None))

    def test_work_due_during_the_absence_counts(self):
        _risk, manual, _matched, target = self.run_policy(
            "LEAVE", work_due_in_absence=1
        )
        self.assertEqual((manual, target), (True, "B"))

    def test_fourth_attendance_adjustment_of_the_month(self):
        self.assertEqual(
            self.run_policy("ATTENDANCE_ADJUSTMENT", same_type_count_month=3)[3], None
        )
        self.assertEqual(
            self.run_policy("ATTENDANCE_ADJUSTMENT", same_type_count_month=4)[3], "B"
        )

    def test_split_claims_are_escalated_to_c(self):
        target = self.run_policy(
            "EXPENSE_CLAIM",
            amount=9_500_000,
            requester_amount_7d=28_500_000,
            requester_finance_count_7d=3,
        )[3]
        self.assertEqual(target, "C")
        # một hồ sơ lớn đơn lẻ không phải chia nhỏ
        self.assertIsNone(
            self.run_policy(
                "EXPENSE_CLAIM",
                amount=18_000_000,
                requester_amount_7d=18_000_000,
                requester_finance_count_7d=1,
            )[3]
        )

    def test_citation_explains_each_condition(self):
        from routers.policy import PolicySignals, policy_citations

        cites = policy_citations(
            request_type="LEAVE",
            amount=0,
            days=1,
            path=self.path,
            signals=PolicySignals(open_work_due_hours=[3.0]),
        )
        self.assertTrue(cites[0]["applies"])
        self.assertTrue(any("đến hạn trong 24 giờ" in c for c in cites[0]["checks"]))
        self.assertTrue(
            any("Chưa chỉ định người nhận bàn giao" in c for c in cites[0]["checks"])
        )
        self.assertIn("quy trình B", cites[0]["effect"])

    def test_evaluate_reports_escalation_for_the_request(self):
        from routers import auto_approve
        from routers.auto_approve import AutoApproveInput

        body = AutoApproveInput(
            request_id="00000000-0000-4000-8000-000000000009",
            request_type="LEAVE",
            lifecycle_template="A",
            risk_score=2,
            days_requested=1,
            requester_name="Kiểm thử",
            requester_dept="TECH",
            open_work_due_hours=[4.0],
        )
        real_apply, real_match, real_cite = (
            auto_approve.apply_policy,
            auto_approve.matched_escalation,
            auto_approve.policy_citations,
        )
        with (
            patch.object(auto_approve, "lookup_leave_balance", return_value=None),
            patch.object(
                auto_approve,
                "apply_policy",
                lambda **kw: real_apply(path=self.path, **kw),
            ),
            patch.object(
                auto_approve,
                "matched_escalation",
                lambda **kw: real_match(path=self.path, **kw),
            ),
            patch.object(
                auto_approve,
                "policy_citations",
                lambda **kw: real_cite(path=self.path, **kw),
            ),
        ):
            out = asyncio.run(auto_approve.evaluate_auto_approve(body))
        self.assertEqual(out.decision, "escalate_to_human")
        self.assertEqual(out.escalate_to, "B")
        self.assertEqual(out.escalation_causes[0]["code"], "QC05-1-LEAVE")


if __name__ == "__main__":
    unittest.main()
