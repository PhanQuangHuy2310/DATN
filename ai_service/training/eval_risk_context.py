r"""So sánh mô hình rủi ro TRƯỚC và SAU khi thêm đặc trưng ngữ cảnh trên 24 kịch bản đã băm.

  ai_service\.venv-ai\Scripts\python ai_service\training\eval_risk_context.py --before <thư mục model cũ>
  ... --set 2 --json ai_service/training/data/risk_context_results2.json   # bộ thứ 2 (19/11, ranh giới)

Kịch bản: training/data/risk_context_scenarios.json (băm trước khi huấn luyện lại). Mô hình cũ không có
cột ngữ cảnh nên chỉ thấy trọng số gốc; đây đúng là điểm thầy góp ý.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ai_service" / "training" / "data"
MODELS = ROOT / "ai_service" / "models"
sys.path.insert(0, str(ROOT / "ai_service"))

from routers.risk import (
    RiskInput,
    build_feature_vector,
    resolve_domain,
    resolve_request_type,
)

NEUTRAL = {"amount_vnd": 0, "budget_remaining_vnd": 500_000_000, "has_receipt": 1, "num_attachments": 1,
           "user_role": "senior", "user_tenure_months": 24, "past_requests_count": 5,
           "past_rejection_rate": 0.05, "urgency": "medium", "is_off_hours": 0, "is_template_matched": 1,
           "is_split_amount_suspect": 0, "department": "operations"}


def load(folder: Path, domain: str):
    encoders = json.loads((folder / "encoders.json").read_text(encoding="utf-8"))
    if domain == "master":
        cols = json.loads((folder / "feature_columns.json").read_text(encoding="utf-8"))
        return joblib.load(folder / "risk_model.pkl"), cols, encoders, None
    meta = json.loads((folder / f"feature_cols_{domain}.json").read_text(encoding="utf-8"))
    reverse = {int(k): int(v) for k, v in meta["reverse_remap"].items()}
    return joblib.load(folder / f"risk_model_{domain}.pkl"), meta["feature_cols"], encoders, reverse


def predict(folder: Path, scenario: dict) -> int:
    inp = RiskInput(request_type=scenario["request_type"], risk_weight=scenario["risk_weight"],
                    **NEUTRAL, **scenario["context"])
    domain = resolve_domain(resolve_request_type(inp.request_type, inp.amount_vnd))
    model, cols, encoders, reverse = load(folder, domain)
    idx = int(model.predict(build_feature_vector(inp, cols, encoders))[0])
    return reverse.get(idx, idx + 1) if reverse else idx + 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="thư mục chứa mô hình trước khi thêm ngữ cảnh")
    ap.add_argument("--set", choices=("1", "2"), default="1", help="bộ kịch bản: 1 (18/11) hoặc 2 (19/11)")
    ap.add_argument("--json", default=str(DATA / "risk_context_results.json"))
    a = ap.parse_args()
    stem = "risk_context_scenarios" + ("" if a.set == "1" else a.set)
    raw = (DATA / f"{stem}.json").read_bytes()
    want = (DATA / f"{stem}.sha256").read_text(encoding="ascii").split()[0]
    if hashlib.sha256(raw).hexdigest() != want:
        sys.exit("SHA-256 kịch bản đã đổi; từ chối chấm.")
    scenarios = json.loads(raw)["scenarios"]
    rows, summary = [], {}
    for name, folder in (("before", Path(a.before)), ("after", MODELS)):
        exact = within = context_exact = context_n = 0
        for sc in scenarios:
            got = predict(folder, sc)
            ok = got == sc["expected"]
            exact += ok
            within += abs(got - sc["expected"]) <= 1
            if sc["context"] and sc["expected"] != sc["risk_weight"]:
                context_n += 1
                context_exact += ok
            rows.append({"model": name, "id": sc["id"], "expected": sc["expected"], "got": got})
        summary[name] = {"exact": exact, "within_one": within, "n": len(scenarios),
                         "context_changes_exact": context_exact, "context_changes_n": context_n}
        print(f"{name:6} đúng {exact}/{len(scenarios)}, lệch ≤1 bậc {within}/{len(scenarios)}, "
              f"kịch bản ngữ cảnh làm đổi mức rủi ro: đúng {context_exact}/{context_n}")
    for sc in scenarios:
        b = next(r["got"] for r in rows if r["model"] == "before" and r["id"] == sc["id"])
        f = next(r["got"] for r in rows if r["model"] == "after" and r["id"] == sc["id"])
        mark = "" if f == sc["expected"] else "  <-- sai"
        print(f"  {sc['id']} {sc['request_type']:22} kỳ vọng {sc['expected']}  trước {b}  sau {f}{mark}")
    Path(a.json).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
