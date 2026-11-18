"""Mô hình hồ sơ quy trình (ai_service/process_profile.py): đáp án kịch bản không bị sửa, đầu vào không lộ nhãn,
đề xuất chỉ tăng nghĩa vụ và luôn chờ quản trị viên duyệt, API được bảo vệ bằng secret nội bộ."""

import hashlib
import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_DIR = os.path.join(REPO_ROOT, "ai_service")
DATA = os.path.join(AI_DIR, "training", "data")
MODEL = os.path.join(AI_DIR, "models", "process_profile.joblib")

PROBE = r"""
import json, sys
import joblib
from process_profile import clean_description, PROFILE_VERSION
from fastapi.testclient import TestClient
import main
m = joblib.load("models/process_profile.joblib")
out = {"version": m.version, "expected_version": PROFILE_VERSION}
out["clean_route"] = clean_description("QL trực tiếp → HR ⇒ thực hiện: HR")
out["clean_placeholder"] = clean_description("Loại yêu cầu X; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.")
out["clean_keep"] = clean_description("Đặt trước phòng họp.")
a = m.predict_one({"name": "Thanh lý tài sản", "description": "Thanh lý tài sản cố định, biên bản bàn giao",
                   "category": "ASSET", "fields": ["asset_code", "amount_vnd"]})
out["assess"] = a
scen = []
for f in ("regulation_scenarios.json", "regulation_scenarios_holdout.json", "regulation_scenarios_holdout2.json"):
    scen += json.load(open("training/data/" + f, encoding="utf-8"))["scenarios"]
mono, unrel = True, {}
for s in scen:
    r = m.regulation_impact(s["text"])
    assert r["requires_admin_approval"] is True
    for p in r["proposals"]:
        lc = "ABC"
        if p["proposed"]["risk_weight"] < p["current"]["risk_weight"] or \
           lc.index(p["proposed"]["lifecycle"]) < lc.index(p["current"]["lifecycle"]):
            mono = False
    if s.get("no_change_expected"):
        unrel[s["id"]] = len(r["proposals"])
out["monotonic"] = mono
out["unrelated_proposals"] = unrel
c = TestClient(main.app)
body = {"name": "Mua sắm thiết bị", "description": "Mua laptop cho nhân viên", "fields": ["amount_vnd"]}
out["no_secret"] = c.post("/ai/process-profile/assess", json=body).status_code
H = {"X-Internal-Secret": "x" * 48}
out["assess_http"] = c.post("/ai/process-profile/assess", json=body, headers=H).status_code
bad = {"text": "Mọi đề nghị mua sắm phải nghiệm thu.", "types": [{"code": "X", "name": "X", "lifecycle": "D", "risk_weight": 3}]}
out["bad_lifecycle"] = c.post("/ai/process-profile/regulation-impact", json=bad, headers=H).status_code
ok = {"text": "Mọi đề nghị mua sắm hàng hóa phải được nghiệm thu và ký biên bản bàn giao trước khi thanh toán.",
      "types": [{"code": "PURCHASE_REQUEST", "name": "Đề nghị mua sắm", "category": "PROCUREMENT",
                 "fields": ["amount_vnd", "item_name"], "lifecycle": "B", "risk_weight": 3}]}
r = c.post("/ai/process-profile/regulation-impact", json=ok, headers=H)
out["impact_http"] = r.status_code
out["impact"] = r.json()
out["info_http"] = c.get("/ai/process-profile/info", headers=H).status_code
print(json.dumps(out, ensure_ascii=False))
"""


def _probe():
    env = {**os.environ, "EAS_ENV": "development", "INTERNAL_API_SECRET": "x" * 48,
           "PYTHONPATH": os.pathsep.join([AI_DIR, REPO_ROOT]), "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=AI_DIR, env=env, capture_output=True,
                         text=True, encoding="utf-8", timeout=300, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


try:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import joblib  # noqa: F401
    import loguru  # noqa: F401
    import sklearn  # noqa: F401

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class ScenarioAnswerKeysTests(unittest.TestCase):
    """Đáp án viết và băm trước khi xây từng phiên bản mô hình; không được sửa sau đó."""

    def test_hashes_match(self):
        for name in ("regulation_scenarios", "regulation_scenarios_holdout", "regulation_scenarios_holdout2"):
            with open(os.path.join(DATA, name + ".sha256"), encoding="utf-8") as f:
                want = f.read().split()[0]
            with open(os.path.join(DATA, name + ".json"), "rb") as f:
                got = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(got, want, name)


@unittest.skipUnless(HAS_DEPS and os.path.exists(MODEL), "ai_service deps and trained model are required")
class ProcessProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _probe()

    def test_model_version_matches_code(self):
        self.assertEqual(self.out["version"], self.out["expected_version"])

    def test_route_summaries_and_placeholders_are_removed(self):
        self.assertEqual(self.out["clean_route"], "")
        self.assertEqual(self.out["clean_placeholder"], "")
        self.assertEqual(self.out["clean_keep"], "Đặt trước phòng họp.")

    def test_assess_returns_valid_profile_with_reasons(self):
        a = self.out["assess"]
        self.assertIn(a["lifecycle"], ("A", "B", "C"))
        self.assertTrue(1 <= a["risk_weight"] <= 5)
        self.assertIsInstance(a["reasons_lifecycle"], list)

    def test_regulation_proposals_never_lower_obligations(self):
        self.assertTrue(self.out["monotonic"])

    def test_unrelated_regulations_produce_no_proposal(self):
        self.assertTrue(self.out["unrelated_proposals"])
        self.assertEqual(set(self.out["unrelated_proposals"].values()), {0})

    def test_api_requires_internal_secret_and_validates_input(self):
        self.assertEqual(self.out["no_secret"], 401)
        self.assertEqual(self.out["assess_http"], 200)
        self.assertEqual(self.out["bad_lifecycle"], 422)
        self.assertEqual(self.out["info_http"], 200)

    def test_api_impact_uses_supplied_current_config(self):
        self.assertEqual(self.out["impact_http"], 200)
        imp = self.out["impact"]
        self.assertTrue(imp["requires_admin_approval"])
        codes = {p["code"]: p for p in imp["proposals"]}
        self.assertIn("PURCHASE_REQUEST", codes)
        self.assertEqual(codes["PURCHASE_REQUEST"]["proposed"]["lifecycle"], "C")


if __name__ == "__main__":
    unittest.main()
