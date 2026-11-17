"""Suy luận tình huống xấu (ai_service/bad_cases.py) và lớp kiểm tra đầu ra của mô hình ngôn ngữ lớn
(ai_service/regulation_llm.py). Không gọi mạng: phần gọi Gemini được thay bằng hàm giả."""

import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_DIR = os.path.join(REPO_ROOT, "ai_service")
sys.path.insert(0, AI_DIR)

try:
    import sklearn  # noqa: F401

    import bad_cases as bc
    import regulation_llm as rl

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

TYPES = [
    {"code": "PURCHASE_REQUEST", "name": "Đề nghị mua sắm", "category": "PROCUREMENT", "description": "",
     "fields": ["amount_vnd"], "lifecycle": "B", "risk_weight": 3},
    {"code": "ROOM_BOOKING", "name": "Đặt phòng họp", "category": "BORROW", "description": "",
     "fields": ["room_code"], "lifecycle": "A", "risk_weight": 1},
]
REG = "Mọi đề nghị mua sắm hàng hóa phải được nghiệm thu và ký biên bản bàn giao trước khi thanh toán."


@unittest.skipUnless(HAS_DEPS, "ai_service dependencies are required")
class BadCaseTests(unittest.TestCase):
    def test_deadline_conflict_only_without_handover(self):
        sig = bc.Signals("ATTENDANCE_ADJUSTMENT", active_tasks_due_24h=1, handover_assigned=False)
        self.assertEqual([c["code"] for c in bc.evaluate(sig).cases], ["BC_DEADLINE_CONFLICT"])
        sig.handover_assigned = True
        self.assertFalse(bc.evaluate(sig).blocked)

    def test_split_amount_needs_several_requests_each_under_threshold(self):
        hit = bc.Signals("ADVANCE_SMALL", amount=9_500_000, requester_amount_7d=28_500_000, requester_finance_count_7d=3)
        self.assertEqual(bc.evaluate(hit).cases[0]["code"], "BC_SPLIT_AMOUNT_EVASION")
        single = bc.Signals("ADVANCE_SMALL", amount=9_500_000, requester_amount_7d=9_500_000, requester_finance_count_7d=1)
        self.assertFalse(bc.evaluate(single).blocked)
        large = bc.Signals("ADVANCE_LARGE", amount=60_000_000, requester_amount_7d=60_000_000, requester_finance_count_7d=2)
        self.assertFalse(bc.evaluate(large).blocked)  # vượt ngưỡng công khai thì không phải "chia nhỏ"

    def test_repeated_exemption_from_fourth_time(self):
        self.assertFalse(bc.evaluate(bc.Signals("ATTENDANCE_ADJUSTMENT", attendance_count_30d=3)).blocked)
        self.assertTrue(bc.evaluate(bc.Signals("ATTENDANCE_ADJUSTMENT", attendance_count_30d=4)).blocked)

    def test_other_types_unaffected(self):
        sig = bc.Signals("ROOM_BOOKING", active_tasks_due_24h=5, attendance_count_30d=9, requester_amount_7d=10**9,
                         requester_finance_count_7d=9)
        self.assertFalse(bc.evaluate(sig).blocked)


@unittest.skipUnless(HAS_DEPS, "ai_service dependencies are required")
class RegulationLlmValidatorTests(unittest.TestCase):
    def ctx(self):
        return rl.retrieve(REG, TYPES)

    def test_valid_grounded_proposal(self):
        raw = {"impacts": [{"code": "PURCHASE_REQUEST", "proposed_class": "C", "proposed_weight": 4, "reason": "nghiệm thu",
                            "clause": "phải được nghiệm thu và ký biên bản bàn giao"}]}
        out = rl.validate(raw, REG, self.ctx())
        self.assertEqual(out["proposals"][0]["proposed"], {"lifecycle": "C", "risk_weight": 4})
        self.assertTrue(out["proposals"][0]["clause_grounded"])

    def test_unknown_code_out_of_range_and_lowering_are_rejected(self):
        raw = {"impacts": [
            {"code": "NOT_A_TYPE", "proposed_class": "C", "proposed_weight": 5},
            {"code": "PURCHASE_REQUEST", "proposed_class": "D", "proposed_weight": 9},
            {"code": "ROOM_BOOKING", "proposed_class": "A", "proposed_weight": 1},
        ]}
        out = rl.validate(raw, REG, self.ctx())
        self.assertEqual(out["proposals"], [])
        self.assertEqual(len(out["rejected"]), 3)

    def test_never_lowers_existing_config(self):
        raw = {"impacts": [{"code": "PURCHASE_REQUEST", "proposed_class": "A", "proposed_weight": 5, "clause": "x"}]}
        p = rl.validate(raw, REG, self.ctx())["proposals"][0]
        self.assertEqual(p["proposed"]["lifecycle"], "B")
        self.assertFalse(p["clause_grounded"])

    def test_fallback_when_llm_unavailable(self):
        out = rl.analyze(REG, TYPES, [], api_key="", model_name="none",
                         fallback=lambda text, types: {"version": "stub", "proposals": [{"code": "X"}]})
        self.assertTrue(out["fallback_used"])
        self.assertEqual(out["error"], "NO_API_KEY")
        self.assertEqual(out["proposals"], [{"code": "X"}])

    def test_prompt_contains_only_regulation_and_config(self):
        prompt = rl.build_prompt(REG, self.ctx())
        self.assertIn("PURCHASE_REQUEST", prompt)
        self.assertIn(REG, prompt)


PROBE = r"""
import json
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
H = {"X-Internal-Secret": "x" * 48}
body = {"request_id": "r", "request_type": "ADVANCE_SMALL", "lifecycle_template": "A", "risk_score": 2,
        "amount": 9500000, "requester_name": "t", "requester_dept": "d",
        "requester_amount_7d": 28500000, "requester_finance_count_7d": 3}
r = c.post("/ai/auto-approve/evaluate", json=body, headers=H).json()
types = [{"code": "PURCHASE_REQUEST", "name": "Đề nghị mua sắm", "category": "PROCUREMENT", "fields": ["amount_vnd"],
          "lifecycle": "B", "risk_weight": 3}]
a = c.post("/ai/regulation-llm/analyze", headers=H, json={"text": "Mọi đề nghị mua sắm phải được nghiệm thu trước khi thanh toán.",
                                                          "types": types})
print(json.dumps({"decision": r["decision"], "bad": [x["code"] for x in r["bad_cases"]], "risk": r["effective_risk"],
                  "analyze_status": a.status_code, "fallback": a.json().get("fallback_used"),
                  "raw_hidden": "raw_response" not in a.json(), "no_secret": c.post("/ai/regulation-llm/analyze",
                  json={"text": "x" * 20, "types": types}).status_code}))
"""


@unittest.skipUnless(HAS_DEPS, "ai_service dependencies are required")
class EndpointTests(unittest.TestCase):
    def test_auto_approve_blocks_bad_case_and_llm_endpoint_falls_back_without_key(self):
        env = {**os.environ, "EAS_ENV": "development", "INTERNAL_API_SECRET": "x" * 48, "GEMINI_API_KEY": "",
               "PYTHONPATH": os.pathsep.join([AI_DIR, REPO_ROOT]), "PYTHONIOENCODING": "utf-8"}
        out = subprocess.run([sys.executable, "-W", "ignore", "-c", PROBE], cwd=AI_DIR, env=env, capture_output=True,
                             text=True, encoding="utf-8", timeout=300, check=True)
        res = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(res["decision"], "escalate_to_human")
        self.assertEqual(res["bad"], ["BC_SPLIT_AMOUNT_EVASION"])
        self.assertEqual(res["risk"], 5)
        self.assertEqual(res["analyze_status"], 200)
        self.assertTrue(res["fallback"])
        self.assertTrue(res["raw_hidden"])
        self.assertEqual(res["no_secret"], 401)


if __name__ == "__main__":
    unittest.main()
