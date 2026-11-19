"""Học bad case từ lý do thu hồi: tiêu chí đủ/chưa đủ, cấu hình gửi bộ phát hiện, admin quyết."""

from unittest.mock import patch

from django.test import SimpleTestCase

from api_core.workflow import bad_case_learning as bcl


class FakeCursor:
    """Trả lần lượt các kết quả đã xếp cho mỗi execute; ghi lại câu lệnh."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self._current = None

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self._current = self.results.pop(0) if self.results else []

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return list(self._current or [])


RULE = {
    "id": "c1",
    "code": "BC_NOTICE_HOURS_WFH_REQ",
    "title": "Báo trước quá sát giờ (WFH_REQ)",
    "request_types": ["WFH_REQ"],
    "detector": "RULE",
    "state": "CANDIDATE",
    "verdict": "NEW_PATTERN",
    "condition": {"all": [{"feature": "notice_hours", "op": "<=", "value": 12}]},
    "base_code": None,
    "escalate_to": "B",
}


def history(n_total, n_hit):
    rows = [{"notice_hours": 3.0}] * n_hit + [{"notice_hours": 72.0}] * (
        n_total - n_hit
    )
    return patch.object(bcl, "history_features", return_value=rows)


class EvaluateCaseTests(SimpleTestCase):
    def evaluate(self, stats, case=RULE, total=20, hit=2, general=None):
        n = stats[0]
        stats = (
            *stats,
            n if general is None else general,
            n,
        )  # số lý do 'kiểu chung', tổng số lý do
        cursor = FakeCursor([[stats], [("WFH_REQ", "Làm việc từ xa (WFH)")]])
        with history(total, hit):
            return bcl.evaluate_case(cursor, case)

    def test_enough_evidence_from_independent_people_activates(self):
        ev = self.evaluate((3, 2, 2, 0.8))
        self.assertTrue(ev["enough"], ev["missing"])
        self.assertIsNone(ev["question"])
        self.assertIn("tự thêm", ev["summary"])

    def test_single_requester_is_not_enough_and_admin_is_asked(self):
        ev = self.evaluate((4, 1, 2, 0.8))
        self.assertFalse(ev["enough"])
        self.assertTrue(any("người gửi" in m for m in ev["missing"]))
        self.assertIn("Có tạo bad case", ev["question"])
        self.assertIn("Làm việc từ xa (WFH)", ev["question"])

    def test_one_strict_approver_is_not_enough(self):
        self.assertFalse(self.evaluate((5, 3, 1, 0.9))["enough"])

    def test_too_broad_condition_is_not_enough(self):
        ev = self.evaluate((5, 3, 3, 0.9), total=10, hit=6)
        self.assertFalse(ev["enough"])
        self.assertTrue(any("60%" in m for m in ev["missing"]))

    def test_reasons_read_as_one_off_need_repetition_across_people(self):
        one = {**RULE, "verdict": "ONE_OFF"}
        self.assertFalse(self.evaluate((2, 1, 1, 0.9), case=one, general=0)["enough"])
        ev = self.evaluate((3, 1, 2, 0.9), case=one, general=0)
        self.assertFalse(ev["enough"])
        self.assertTrue(any("riêng" in m for m in ev["missing"]))

    def test_repetition_across_people_proves_a_pattern(self):
        # Một câu đơn lẻ khó phân biệt chung/riêng; 3 lần, 2 người gửi, 2 người duyệt thì đã là kiểu lặp lại.
        ev = self.evaluate(
            (3, 2, 2, 0.9), case={**RULE, "verdict": "ONE_OFF"}, general=0
        )
        self.assertTrue(ev["enough"], ev["missing"])

    def test_one_off_without_condition_never_auto_activates(self):
        ev = self.evaluate(
            (6, 4, 3, 0.9),
            case={**RULE, "verdict": "ONE_OFF", "condition": None},
            general=0,
        )
        self.assertFalse(ev["enough"])

    def test_unmeasurable_pattern_needs_admin(self):
        ev = self.evaluate((6, 4, 3, 0.9), case={**RULE, "condition": None})
        self.assertFalse(ev["enough"])
        self.assertTrue(any("Chưa đo được" in m for m in ev["missing"]))


class DetectorConfigTests(SimpleTestCase):
    def test_rules_scopes_and_retired_builtins(self):
        rows = [
            (
                "BC_X",
                "X",
                "vì",
                ["WFH_REQ"],
                RULE["condition"],
                "≤ 12",
                3,
                "B",
                "RULE",
                None,
                "ACTIVE",
            ),
            (
                "BC_TEAM_ABSENCE_PEAK_WFH_REQ",
                "T",
                "vì",
                ["WFH_REQ"],
                None,
                None,
                4,
                "B",
                "SCOPE",
                "BC_TEAM_ABSENCE_PEAK",
                "ACTIVE",
            ),
            (
                "BC_OFF_HOURS_BULK",
                "O",
                "vì",
                ["EXPENSE_CLAIM"],
                None,
                None,
                3,
                "B",
                "BUILTIN",
                None,
                "RETIRED",
            ),
        ]
        cfg = bcl.detector_config(FakeCursor([[(True,)], rows]))
        self.assertEqual([c["code"] for c in cfg["learned_bad_cases"]], ["BC_X"])
        self.assertEqual(
            cfg["bad_case_overrides"]["BC_TEAM_ABSENCE_PEAK"],
            {"extra_types": ["WFH_REQ"]},
        )
        self.assertEqual(
            cfg["bad_case_overrides"]["BC_OFF_HOURS_BULK"], {"disabled": True}
        )

    def test_without_migration_nothing_is_sent(self):
        self.assertEqual(
            bcl.detector_config(FakeCursor([[(False,)]])),
            {"learned_bad_cases": [], "bad_case_overrides": {}},
        )


class AdminDecideTests(SimpleTestCase):
    def row(self, state="CANDIDATE", detector="RULE", cond=None):
        return [
            (
                "BC_X",
                state,
                detector,
                cond,
                ["WFH_REQ"],
                "Tên",
                "Vì sao là bad case",
                "B",
                3,
            )
        ]

    def test_rule_needs_a_measurable_condition(self):
        with self.assertRaisesMessage(ValueError, "condition"):
            bcl.admin_decide(
                FakeCursor([self.row()]),
                case_id="c1",
                actor_id="u1",
                decision="approve",
                body={},
            )

    def test_bad_condition_is_rejected(self):
        body = {"condition": {"all": [{"feature": "salary", "op": ">=", "value": 1}]}}
        with self.assertRaises(ValueError):
            bcl.admin_decide(
                FakeCursor([self.row()]),
                case_id="c1",
                actor_id="u1",
                decision="approve",
                body=body,
            )

    def test_approve_with_condition_activates(self):
        cursor = FakeCursor([self.row(), []])
        body = {"condition": RULE["condition"]}
        out = bcl.admin_decide(
            cursor, case_id="c1", actor_id="u1", decision="approve", body=body
        )
        self.assertEqual(out["state"], "ACTIVE")
        self.assertIn("UPDATE eas.bad_case", cursor.calls[-1][0])

    def test_reject_needs_a_reason_and_state_is_checked(self):
        with self.assertRaisesMessage(ValueError, "note"):
            bcl.admin_decide(
                FakeCursor([self.row()]),
                case_id="c1",
                actor_id="u1",
                decision="reject",
                body={},
            )
        with self.assertRaises(PermissionError):
            bcl.admin_decide(
                FakeCursor([self.row(state="ACTIVE")]),
                case_id="c1",
                actor_id="u1",
                decision="approve",
                body={},
            )
