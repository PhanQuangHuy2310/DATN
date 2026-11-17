"""Auto-approve business rules must apply to catalog v2 codes.

The API sends catalog codes (LEAVE, ROOM_BOOKING, REFUND_COMPENSATION...).
The rule table used to be keyed by legacy names only (leave_short, refund...),
so every catalog request fell through to the generic "approve on risk" rule:
leave without enough balance, a booked room or a large refund were approved.
"""

import asyncio
import os
import sys
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
AI_SERVICE_DIR = os.path.join(REPO_ROOT, "ai_service")
for path in (REPO_ROOT, AI_SERVICE_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


def _body(**overrides):
    from routers.auto_approve import AutoApproveInput

    values = {
        "request_id": "00000000-0000-4000-8000-000000000001",
        "request_type": "LEAVE",
        "lifecycle_template": "A",
        "risk_score": 1,
        "amount": 0.0,
        "days_requested": 1,
        "leave_balance_remaining": 10,
        "requester_name": "Kiểm thử",
        "requester_dept": "TECH",
    }
    values.update(overrides)
    return AutoApproveInput(**values)


@unittest.skipUnless(HAS_ROUTER_DEPS, "fastapi/pydantic-settings not installed")
class CatalogCodeRuleTests(unittest.TestCase):
    def decide(self, **overrides):
        from routers import auto_approve

        # No external lookups and no loaded regulation: only the coded rules.
        with (
            patch.object(auto_approve, "lookup_leave_balance", return_value=None),
            patch.object(auto_approve, "lookup_facility_available", return_value=None),
            patch.object(
                auto_approve,
                "apply_policy",
                side_effect=lambda request_type, amount, days, risk, signals=None: (
                    risk,
                    False,
                    [],
                    None,
                ),
            ),
            patch.object(auto_approve, "matched_escalation", return_value=(None, [])),
            patch.object(auto_approve, "policy_citations", return_value=[]),
        ):
            result = asyncio.run(auto_approve.evaluate_auto_approve(_body(**overrides)))
        return result.decision, result.detail_reasons

    def test_short_leave_with_balance_is_approved(self):
        decision, _ = self.decide(request_type="LEAVE", days_requested=2)
        self.assertEqual(decision, "auto_approve")

    def test_leave_over_balance_is_escalated(self):
        decision, reasons = self.decide(
            request_type="LEAVE", days_requested=2, leave_balance_remaining=1
        )
        self.assertEqual(decision, "escalate_to_human")
        self.assertTrue(any("vượt quá số phép" in r for r in reasons))

    def test_leave_of_three_days_or_more_is_escalated(self):
        decision, _ = self.decide(request_type="LEAVE", days_requested=3)
        self.assertEqual(decision, "escalate_to_human")

    def test_leave_without_dates_is_escalated(self):
        decision, _ = self.decide(request_type="LEAVE", days_requested=0)
        self.assertEqual(decision, "escalate_to_human")

    def test_booked_room_is_escalated(self):
        decision, _ = self.decide(request_type="ROOM_BOOKING", room_available=False)
        self.assertEqual(decision, "escalate_to_human")

    def test_free_room_is_approved(self):
        decision, _ = self.decide(request_type="ROOM_BOOKING", room_available=True)
        self.assertEqual(decision, "auto_approve")

    def test_unchecked_room_is_escalated(self):
        decision, _ = self.decide(request_type="ROOM_BOOKING")
        self.assertEqual(decision, "escalate_to_human")

    def test_large_refund_is_escalated(self):
        decision, _ = self.decide(
            request_type="REFUND_COMPENSATION", risk_score=2, amount=5_000_000
        )
        self.assertEqual(decision, "escalate_to_human")

    def test_small_refund_is_approved(self):
        decision, _ = self.decide(
            request_type="REFUND_COMPENSATION", risk_score=2, amount=1_500_000
        )
        self.assertEqual(decision, "auto_approve")

    def test_legacy_names_still_map_to_the_same_rules(self):
        self.assertEqual(
            self.decide(request_type="leave_short", days_requested=5)[0],
            "escalate_to_human",
        )
        self.assertEqual(
            self.decide(request_type="refund", amount=9_000_000)[0], "escalate_to_human"
        )
        self.assertEqual(
            self.decide(request_type="ROOM_STUDIO", room_available=False)[0],
            "escalate_to_human",
        )

    def test_gates_still_apply_before_rules(self):
        self.assertEqual(self.decide(lifecycle_template="B")[0], "escalate_to_human")
        self.assertEqual(self.decide(risk_score=4)[0], "escalate_to_human")


if __name__ == "__main__":
    unittest.main()
