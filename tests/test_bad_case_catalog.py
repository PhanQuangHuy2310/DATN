"""Mỗi tình huống xấu trong data/bad_case_catalog.json: một ca phải bắt và một ca không được bắt nhầm."""

import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO, os.path.join(REPO, "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

import bad_cases as bc

S = bc.Signals


def codes(sig):
    return [c["code"] for c in bc.evaluate(sig).cases]


CASES = {
    "BC_DEADLINE_CONFLICT": (
        S("LEAVE", open_work_due_hours=[6.0], handover_assigned=False),
        S("LEAVE", open_work_due_hours=[6.0], handover_assigned=True),
    ),
    "BC_HANDOVER_OVERLOADED": (
        S("LEAVE_SPECIAL", handover_assigned=True, handover_open_work_in_absence=3),
        S("LEAVE_SPECIAL", handover_assigned=True, handover_open_work_in_absence=2),
    ),
    "BC_TEAM_ABSENCE_PEAK": (
        S("LEAVE", team_absence_ratio=0.5, team_size=6),
        S("LEAVE", team_absence_ratio=0.5, team_size=2),
    ),
    "BC_REPEATED_EXEMPTION": (
        S("ATTENDANCE_ADJUSTMENT", attendance_count_30d=4),
        S("ATTENDANCE_ADJUSTMENT", attendance_count_30d=3),
    ),
    "BC_WFH_FREQUENT": (
        S("WFH_REQ", same_type_count_month=8),
        S("WFH_REQ", same_type_count_month=7),
    ),
    "BC_SPLIT_AMOUNT_EVASION": (
        S(
            "EXPENSE_CLAIM",
            amount=9_500_000,
            requester_amount_7d=28_500_000,
            requester_finance_count_7d=3,
        ),
        S(
            "EXPENSE_CLAIM",
            amount=25_000_000,
            requester_amount_7d=25_000_000,
            requester_finance_count_7d=1,
        ),
    ),
    "BC_DUPLICATE_INVOICE": (
        S("EXPENSE_CLAIM", duplicate_invoice_count=1),
        S("EXPENSE_CLAIM", duplicate_invoice_count=0),
    ),
    "BC_REFUND_FREQUENT": (
        S("REFUND_COMPENSATION", same_type_count_7d=3),
        S("REFUND_COMPENSATION", same_type_count_7d=2),
    ),
    "BC_DISCOUNT_REPEAT_CUSTOMER": (
        S("SPECIAL_DISCOUNT", same_customer_count_7d=1),
        S("SPECIAL_DISCOUNT", same_customer_count_7d=0),
    ),
    "BC_REQUESTER_ABSENT_ON_EVENT": (
        S("VISITOR_SECURITY_PASS", requester_absent_on_event=True),
        S("VISITOR_SECURITY_PASS", requester_absent_on_event=False),
    ),
    "BC_AI_REVOKED_HISTORY": (
        S("ROOM_BOOKING", ai_revoked_90d=2),
        S("ROOM_BOOKING", ai_revoked_90d=1),
    ),
    "BC_OFF_HOURS_BULK": (
        S("REFUND_COMPENSATION", off_hours_count_7d=3),
        S("REFUND_COMPENSATION", off_hours_count_7d=2),
    ),
}


class CatalogTests(unittest.TestCase):
    def test_every_catalog_case_has_a_detector_and_a_test(self):
        catalog = bc.load_catalog()
        listed = {c["code"] for c in catalog["cases"]}
        self.assertEqual(listed, set(bc.DETECTORS))
        self.assertEqual(listed, set(CASES))
        for case in catalog["cases"]:
            self.assertIn(case["escalate_to"], ("B", "C"))
            self.assertTrue(
                set(case["remediation"]) <= set(catalog["remediation_actions"])
            )

    def test_each_case_fires_and_has_a_near_miss(self):
        for code, (hit, miss) in CASES.items():
            with self.subTest(code=code):
                self.assertIn(code, codes(hit))
                self.assertNotIn(code, codes(miss))

    def test_case_reports_escalation_evidence_and_remediation(self):
        case = bc.evaluate(CASES["BC_SPLIT_AMOUNT_EVASION"][0]).cases[0]
        self.assertEqual((case["escalate_to"], case["risk"]), ("C", 5))
        self.assertEqual(case["evidence"]["count_7d"], 3)
        self.assertIn("MERGE_REQUESTS", [r["action"] for r in case["remediation"]])

    def test_cases_only_apply_to_their_request_types(self):
        self.assertEqual(
            codes(
                S("ROOM_BOOKING", open_work_due_hours=[1.0], handover_assigned=False)
            ),
            [],
        )
        self.assertEqual(codes(S("LEAVE", duplicate_invoice_count=3)), [])

    def test_clean_request_has_no_bad_case(self):
        for code in (
            "LEAVE",
            "ATTENDANCE_ADJUSTMENT",
            "WFH_REQ",
            "ROOM_BOOKING",
            "REFUND_COMPENSATION",
        ):
            self.assertEqual(codes(S(code)), [], code)

    def test_catalog_records_its_provenance(self):
        with open(bc.CATALOG_PATH, encoding="utf-8") as handle:
            about = json.load(handle)["about"]
        self.assertIn("Gemini", about)
        self.assertIn("rà lại", about)


if __name__ == "__main__":
    unittest.main()
