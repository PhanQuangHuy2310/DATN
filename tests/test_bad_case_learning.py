"""Học bad case từ lý do thu hồi: điều kiện (hai bản ai_service / api_core khớp nhau), đề xuất ngưỡng,
bộ phát hiện dùng bad case học được, migration 25 seed đúng danh mục có sẵn."""

import json
import os
import random
import re
import sys
import unittest
import unittest.mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO, os.path.join(REPO, "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

import bad_case_reason as bcr
import bad_cases as bc

from api_core.workflow import bad_case_conditions as bcc


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


LEARNED = [{
    "code": "BC_NOTICE_HOURS_WFH_REQ",
    "title": "Báo trước quá sát giờ (WFH_REQ)",
    "rationale": "Người duyệt đã thu hồi vì báo quá sát giờ.",
    "request_types": ["WFH_REQ"],
    "condition": {"all": [{"feature": "notice_hours", "op": "<=", "value": 12}]},
    "condition_text": "số giờ báo trước ≤ 12 giờ",
    "risk": 3,
    "escalate_to": "B",
}]


class ConditionParityTests(unittest.TestCase):
    """api_core (kiểm tra khi admin duyệt, đo độ phủ) và ai_service (phát hiện) phải hiểu điều kiện như nhau."""

    def test_same_feature_whitelist(self):
        self.assertEqual(set(bcr.FEATURES), set(bcc.FEATURES))

    def test_validate_agrees(self):
        cases = [
            {"all": [{"feature": "notice_hours", "op": "<=", "value": 12}]},
            {"all": [{"feature": "start_weekday", "op": "in", "value": [5, 1, 5]}]},
            {"all": [{"feature": "amount", "op": ">=", "value": 5_000_000.0}, {"feature": "submit_hour", "op": "in", "value": [22, 23]}]},
            {"all": [{"feature": "nope", "op": "<=", "value": 1}]},
            {"all": [{"feature": "notice_hours", "op": "<", "value": 1}]},
            {"all": [{"feature": "notice_hours", "op": "<=", "value": True}]},
            {"all": [{"feature": "start_weekday", "op": "in", "value": [8]}]},
            {"all": []},
            {"any": []},
            {"all": [{"feature": "amount", "op": ">=", "value": 1, "extra": 1}]},
        ]
        for cond in cases:
            with self.subTest(cond=cond):
                try:
                    a = bcr.validate_condition(cond)
                except ValueError:
                    a = "ERR"
                try:
                    b = bcc.validate(cond)
                except ValueError:
                    b = "ERR"
                self.assertEqual(a, b)

    def test_matches_agree_on_random_values(self):
        rng = random.Random(7)
        conds = [
            {"all": [{"feature": "notice_hours", "op": "<=", "value": 12}]},
            {"all": [{"feature": "start_day_of_month", "op": ">=", "value": 25}]},
            {"all": [{"feature": "start_weekday", "op": "in", "value": [1, 5]}]},
            {"all": [{"feature": "days_requested", "op": ">=", "value": 5}, {"feature": "amount", "op": "==", "value": 0}]},
        ]
        for _ in range(300):
            values = {
                "notice_hours": rng.choice([None, rng.uniform(-5, 100)]),
                "start_day_of_month": rng.choice([None, rng.randint(1, 31)]),
                "start_weekday": rng.choice([None, rng.randint(1, 7)]),
                "days_requested": rng.randint(0, 10),
                "amount": rng.choice([0, 1_000_000]),
            }
            for cond in conds:
                self.assertEqual(bcr.condition_matches(cond, values), bcc.matches(cond, values))

    def test_missing_value_never_matches(self):
        cond = {"all": [{"feature": "notice_hours", "op": "<=", "value": 12}]}
        self.assertFalse(bcc.matches(cond, {"notice_hours": None}))
        self.assertFalse(bcr.condition_matches(cond, {}))


class ProposeConditionTests(unittest.TestCase):

    def term(self, feature, reason, values):
        cond = bcr.propose_condition(feature, reason, values)
        return cond and cond["all"][0]

    def test_threshold_comes_from_the_revoked_request(self):
        self.assertEqual(self.term("notice_hours", "Báo nghỉ quá sát giờ", {"notice_hours": 3.2})["value"], 4)
        self.assertEqual(self.term("notice_hours", "Báo sát giờ", {"notice_hours": 30})["value"], 48)
        self.assertEqual(self.term("start_day_of_month", "Nghỉ đúng tuần chốt sổ", {"start_day_of_month": 28})["value"], 25)
        self.assertEqual(self.term("start_day_of_month", "cuối tháng", {"start_day_of_month": 22})["value"], 22)

    def test_numbers_and_weekdays_in_the_reason_win(self):
        self.assertEqual(self.term("start_weekday", "Tuần nào cũng xin WFH thứ Sáu", {"start_weekday": None})["value"], [5])
        self.assertEqual(self.term("days_requested", "Nghỉ liền 6 ngày là quá dài", {"days_requested": 7})["value"], 6)
        self.assertEqual(self.term("amount", "Hoàn 15 triệu là bất thường", {"amount": 15_200_000})["value"], 15_000_000)

    def test_condition_must_catch_the_revoked_request_itself(self):
        # Lý do nói thứ Sáu nhưng hồ sơ bị thu hồi rơi vào thứ Tư; báo trước 26 ngày mà bảo "sát giờ": không đặt điều kiện.
        self.assertIsNone(bcr.propose_condition("start_weekday", "hay xin thứ Sáu", {"start_weekday": 3}))
        self.assertIsNone(bcr.propose_condition("notice_hours", "báo sát giờ", {"notice_hours": 630.0}))
        self.assertIsNone(bcr.propose_condition("days_requested", "nghỉ 6 ngày quá dài", {"days_requested": 2}))

    def test_no_feature_means_no_condition(self):
        self.assertIsNone(bcr.propose_condition(None, "Khách là đối thủ", {}))
        self.assertIsNone(bcr.propose_condition("start_weekday", "hay xin nghỉ", {"start_weekday": None}))


CAND = {"code": "BC_NOTICE_HOURS_WFH_REQ", "verdict": "NEW_PATTERN", "feature": "notice_hours",
        "base_code": None, "type_codes": ["WFH_REQ"],
        "reasons": ["Báo WFH quá sát giờ, phòng không kịp sắp xếp."],
        "condition": {"all": [{"feature": "notice_hours", "op": "<=", "value": 24}]}}


class CandidateConsistencyTests(unittest.TestCase):
    """Một lý do chỉ được gom vào ứng viên có điều kiện khi điều kiện đó bắt được chính hồ sơ bị thu hồi.
    Đầu ra của bộ phân loại được cố định để chỉ kiểm tra luật gom."""

    def analyze(self, notice):
        fixed = {"label": bcr.NEW, "confidence": 0.8, "top": [], "feature": "notice_hours", "engine": "test"}
        with unittest.mock.patch.object(bcr, "classify", return_value=fixed),                 unittest.mock.patch.object(bcr, "_cosine_max", return_value=0.9):
            return bcr.analyze(reason="Báo WFH quá sát giờ", type_code="WFH_REQ",
                               values={"notice_hours": notice}, cases=[], candidates=[CAND], model={"label": None})

    def test_request_outside_the_condition_never_joins(self):
        self.assertIsNone(self.analyze(630.0)["match"])

    def test_same_mechanism_joins(self):
        self.assertEqual(self.analyze(10.0)["match"], "BC_NOTICE_HOURS_WFH_REQ")


class LearnedDetectorTests(unittest.TestCase):

    def test_learned_case_blocks_and_explains(self):
        sig = bc.Signals("WFH_REQ", notice_hours=3.0)
        cases = bc.evaluate(sig, learned=LEARNED).cases
        self.assertEqual([c["code"] for c in cases], ["BC_NOTICE_HOURS_WFH_REQ"])
        self.assertEqual(cases[0]["escalate_to"], "B")
        self.assertEqual(cases[0]["source"], "LEARNED_CASE")
        self.assertIn("thu hồi", cases[0]["rationale"])

    def test_learned_case_respects_type_and_threshold(self):
        self.assertEqual(bc.evaluate(bc.Signals("WFH_REQ", notice_hours=30.0), learned=LEARNED).cases, [])
        self.assertEqual(bc.evaluate(bc.Signals("LEAVE", notice_hours=3.0), learned=LEARNED).cases, [])
        self.assertEqual(bc.evaluate(bc.Signals("WFH_REQ"), learned=LEARNED).cases, [])  # thiếu dữ liệu

    def test_admin_can_retire_a_builtin_case(self):
        sig = bc.Signals("WFH_REQ", same_type_count_month=9)
        self.assertEqual([c["code"] for c in bc.evaluate(sig).cases], ["BC_WFH_FREQUENT"])
        self.assertEqual(bc.evaluate(sig, overrides={"BC_WFH_FREQUENT": {"disabled": True}}).cases, [])

    def test_scope_extension_runs_builtin_detector_on_new_type(self):
        sig = bc.Signals("WFH_REQ", team_size=5, team_absence_ratio=0.6)
        self.assertEqual(bc.evaluate(sig).cases, [])
        cases = bc.evaluate(sig, overrides={"BC_TEAM_ABSENCE_PEAK": {"extra_types": ["WFH_REQ"]}}).cases
        self.assertEqual([(c["code"], c["source"]) for c in cases], [("BC_TEAM_ABSENCE_PEAK", "SCOPE")])

    def test_every_builtin_hit_carries_its_rationale(self):
        sig = bc.Signals("EXPENSE_CLAIM", duplicate_invoice_count=1)
        self.assertEqual(bc.evaluate(sig).cases[0]["rationale"], "Thanh toán hai lần cho một chứng từ.")


class MigrationSeedTests(unittest.TestCase):

    def test_seed_matches_catalog(self):
        sql = read("database", "migrations", "25_bad_case_learning.sql")
        catalog = json.loads(read("ai_service", "data", "bad_case_catalog.json"))
        seeded = re.findall(r"\('(BC_[A-Z_]+)', '", sql)
        self.assertEqual(seeded, [c["code"] for c in catalog["cases"]])
        for case in catalog["cases"]:
            self.assertIn(case["harm"].replace("'", "''"), sql)

    def test_snippet_copy_is_identical(self):
        a = read("database", "migrations", "25_bad_case_learning.sql")
        b = read("supabase", "snippets", "25_bad_case_learning.sql")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
