"""Mô hình xếp hạng người nhận việc thay: đúng thứ tự hiển nhiên, giải thích được, hướng xử lý hợp lý."""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO, os.path.join(REPO, "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import xgboost  # noqa: F401

    HAS_XGB = True
except ImportError:
    HAS_XGB = False

import remediation_ranker as rr

PEER = {"user_id": "peer", "same_department": 1, "same_team": 1, "open_items": 1, "due_in_window": 0,
        "type_experience": 6, "is_superior": 0}
BUSY = {"user_id": "busy", "same_department": 1, "same_team": 0, "open_items": 12, "due_in_window": 4,
        "type_experience": 2, "is_superior": 0}
BOSS = {"user_id": "boss", "same_department": 1, "same_team": 0, "open_items": 2, "due_in_window": 0,
        "type_experience": 3, "is_superior": 1}
OUTSIDER = {"user_id": "out", "same_department": 0, "same_team": 0, "open_items": 0, "due_in_window": 0,
            "type_experience": 0, "is_superior": 0}


class RankerTests(unittest.TestCase):
    @unittest.skipUnless(HAS_XGB and os.path.exists(rr.MODEL_PATH), "xgboost/mô hình chưa có")
    def test_model_prefers_free_experienced_peer(self):
        out = rr.rank([BUSY, OUTSIDER, BOSS, PEER])
        self.assertEqual(out["engine"], "xgboost-ranker")
        self.assertEqual(out["ranked"][0]["user_id"], "peer")
        self.assertEqual(out["ranked"][-1]["user_id"], "busy")

    def test_every_score_is_explained(self):
        out = rr.rank([PEER, BUSY])
        for c in out["ranked"]:
            self.assertTrue(c["why"])
        self.assertIn("cùng nhóm với người xin nghỉ", rr.explain(PEER))
        self.assertIn("có 4 việc đến hạn trong cùng thời gian", rr.explain(BUSY))

    def test_no_candidate_means_postpone_when_due_during_absence(self):
        self.assertEqual(rr.suggest_action("APPROVAL", 10, 48, None)["action"], "POSTPONE_DEADLINE")
        self.assertEqual(rr.suggest_action("APPROVAL", 10, 48, PEER)["action"], "DELEGATE_APPROVALS")
        self.assertEqual(rr.suggest_action("EXECUTION", 10, 48, PEER)["action"], "REASSIGN_WORK")
        self.assertEqual(rr.suggest_action("EXECUTION", 400, 24, None)["action"], "RESCHEDULE_REQUEST")

    def test_empty_candidates(self):
        self.assertEqual(rr.rank([])["ranked"], [])

    @unittest.skipUnless(HAS_XGB and os.path.exists(rr.MODEL_PATH), "xgboost/mô hình chưa có")
    def test_model_is_monotone(self):
        """Thêm việc đến hạn/việc mở/là cấp trên không bao giờ làm điểm tăng (bản 1 có 7 cặp vi phạm)."""
        import itertools

        worse = {"due_in_window": [0, 1, 2, 3, 5], "open_items": [0, 1, 2, 4, 8, 15], "is_superior": [0, 1]}
        better = {"type_experience": [0, 1, 3, 6, 12], "same_team": [0, 1], "same_department": [0, 1]}
        grid = {**worse, **better}
        keys = list(grid)
        candidates, moves = [], []
        for combo in itertools.product(*grid.values()):
            base = dict(zip(keys, combo, strict=True))
            for feat, values in grid.items():
                i = values.index(base[feat])
                if i + 1 < len(values):
                    moves.append((len(candidates), feat))
                    candidates += [base, {**base, feat: values[i + 1]}]
        scores = [c["score"] for c in sorted(
            rr.rank([{**c, "user_id": n} for n, c in enumerate(candidates)])["ranked"], key=lambda c: c["user_id"])]
        bad = [(candidates[i], f) for i, f in moves
               if (scores[i + 1] - scores[i]) * (-1 if f in worse else 1) < -1e-6]
        self.assertEqual(bad, [])

    def test_missing_or_null_fields_count_as_zero(self):
        out = rr.rank([{"user_id": "x", "open_items": None}, {"user_id": "y"}])
        self.assertEqual(len(out["ranked"]), 2)
        self.assertIn("đang mở 0 việc", out["ranked"][0]["why"])

    def test_suggest_action_boundaries(self):
        self.assertEqual(rr.suggest_action("APPROVAL", 10, 48, {**PEER, "due_in_window": 2})["action"],
                         "DELEGATE_APPROVALS")
        self.assertEqual(rr.suggest_action("APPROVAL", 10, 48, {**PEER, "due_in_window": 3})["action"],
                         "POSTPONE_DEADLINE")  # người tốt nhất cũng kín việc
        self.assertEqual(rr.suggest_action("EXECUTION", 72, 48, None)["action"], "POSTPONE_DEADLINE")  # đúng +24h
        self.assertEqual(rr.suggest_action("EXECUTION", 72.5, 48, None)["action"], "RESCHEDULE_REQUEST")


if __name__ == "__main__":
    unittest.main()
