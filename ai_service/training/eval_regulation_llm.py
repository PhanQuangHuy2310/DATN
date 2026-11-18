"""Đánh giá phân tích quy định bằng mô hình ngôn ngữ lớn (regulation_llm) trên 30 kịch bản QD-01..QD-30.

  python ai_service/training/eval_regulation_llm.py            (cần GEMINI_API_KEY trong .env)
  python ai_service/training/eval_regulation_llm.py --rescore  (chấm lại từ tệp lượt chạy đã lưu, không gọi API)

- Đáp án của cả 30 kịch bản được viết và băm SHA-256 TRƯỚC khi có mô-đun này, nên với mô hình ngôn ngữ lớn
  cả 30 đều là dữ liệu chưa thấy. Câu lệnh (prompt) được cố định trước khi chạy; mã băm của nó được lưu lại.
- Mỗi kịch bản gọi một lần, nhiệt độ 0; toàn bộ đầu vào/đầu ra được lưu ở regulation_llm_runs.json.
- So sánh cùng bộ chấm với mô hình nội bộ process-profile-3 và luật từ khóa.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "training"))

import joblib  # noqa: E402

import regulation_llm as R  # noqa: E402
from train_process_profile import (  # noqa: E402
    HOLDOUT, HOLDOUT2, HOLDOUT2_SHA, HOLDOUT_SHA, SCENARIOS, SCENARIOS_SHA, check_scenarios, rule_impact, run_scenarios,
)

DATA = ROOT / "training" / "data"
RUNS = DATA / "regulation_llm_runs.json"
REPORT_MD = DATA / "regulation_llm_report.md"
METRICS = ROOT / "models" / "regulation_llm_metrics.json"
SETS = [("QD-01..10", SCENARIOS, SCENARIOS_SHA), ("QD-11..20", HOLDOUT, HOLDOUT_SHA), ("QD-21..30", HOLDOUT2, HOLDOUT2_SHA)]


def load_types() -> list[dict]:
    return json.loads((DATA / "process_profiles.json").read_text(encoding="utf-8"))["items"]


def run_llm(types: list[dict], specs: list[dict]) -> dict:
    from config import get_settings

    s = get_settings()
    runs = {"engine": R.ENGINE_VERSION, "model": s.gemini_model,
            "prompt_template_sha256": hashlib.sha256(R.PROMPT_TEMPLATE.encode("utf-8")).hexdigest(),
            "run_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z"), "scenarios": {}}
    for spec in specs:
        for sc in spec["scenarios"]:
            out = R.analyze(sc["text"], types, [], api_key=s.gemini_api_key, model_name=s.gemini_model)
            runs["scenarios"][sc["id"]] = out
            print(sc["id"], "fallback" if out["fallback_used"] else f"{out.get('latency_ms')} ms",
                  [(p["code"], p["proposed"]) for p in out["proposals"]], out.get("error") or "")
    RUNS.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")
    return runs


def llm_impact_from(runs: dict):
    by_text = {}

    def impact(_model, text):
        return by_text[text]

    return impact, by_text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--retry-failed", action="store_true",
                    help="chỉ gọi lại các kịch bản lần trước lỗi kết nối/giới hạn tần suất (không tính là kết quả)")
    a = ap.parse_args()
    types = load_types()
    specs = [check_scenarios(p, h) for _, p, h in SETS]
    if a.retry_failed:
        from config import get_settings

        s = get_settings()
        runs = json.loads(RUNS.read_text(encoding="utf-8"))
        runs.setdefault("retried", [])
        for spec in specs:
            for sc in spec["scenarios"]:
                if runs["scenarios"][sc["id"]].get("fallback_used"):
                    out = R.analyze(sc["text"], types, [], api_key=s.gemini_api_key, model_name=s.gemini_model,
                                    retries=4, retry_wait=10.0)
                    runs["scenarios"][sc["id"]] = out
                    runs["retried"].append({"id": sc["id"], "reason": "HTTP 429 ở lượt đầu", "ok": not out["fallback_used"]})
                    print(sc["id"], "retry", "fallback" if out["fallback_used"] else "ok",
                          [(p["code"], p["proposed"]) for p in out["proposals"]])
        RUNS.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        runs = json.loads(RUNS.read_text(encoding="utf-8")) if a.rescore else run_llm(types, specs)
    if any(r.get("fallback_used") for r in runs["scenarios"].values()):
        print("CẢNH BÁO: còn kịch bản chưa có kết quả của mô hình ngôn ngữ lớn (lỗi kết nối); không dùng số liệu này.")
    profiler = joblib.load(ROOT / "models" / "process_profile.joblib")

    texts = {sc["text"]: sc["id"] for spec in specs for sc in spec["scenarios"]}

    def llm_impact(_model, text):
        out = runs["scenarios"][texts[text]]
        return {"related": [{"code": c} for c in out["retrieved_types"]], "proposals": out["proposals"]}

    results = {}
    for (name, _, _), spec in zip(SETS, specs):
        results[name] = {"llm": run_scenarios(profiler, spec, impact=llm_impact),
                         "process_profile": run_scenarios(profiler, spec),
                         "rules": run_scenarios(profiler, spec, impact=rule_impact)}
    allspec = {"scenarios": [sc for spec in specs for sc in spec["scenarios"]]}
    total = {"llm": run_scenarios(profiler, allspec, impact=llm_impact)["summary"],
             "process_profile": run_scenarios(profiler, allspec)["summary"],
             "rules": run_scenarios(profiler, allspec, impact=rule_impact)["summary"]}
    # độ phủ của bước truy xuất: loại phải đổi/giữ nguyên có nằm trong 12 loại đưa cho mô hình ngôn ngữ không
    need, hit = 0, 0
    for sc in allspec["scenarios"]:
        got = set(runs["scenarios"][sc["id"]]["retrieved_types"])
        for code in list(sc["expected_changes"]) + list(sc["expected_unchanged"]):
            need += 1
            hit += code in got
    sc_runs = list(runs["scenarios"].values())
    lat = sorted(r["latency_ms"] for r in sc_runs if r.get("latency_ms"))
    grounded = [p["clause_grounded"] for r in sc_runs for p in r["proposals"]]
    stats = {"retrieval_recall": f"{hit}/{need}", "fallbacks": sum(r["fallback_used"] for r in sc_runs),
             "latency_ms_p50": lat[len(lat) // 2] if lat else None,
             "latency_ms_max": lat[-1] if lat else None,
             "tokens_total": sum(r.get("tokens") or 0 for r in sc_runs),
             "proposals_grounded": f"{sum(grounded)}/{len(grounded)}",
             "rejected_by_validator": sum(len(r["rejected"]) for r in sc_runs),
             "atomic_rules_total": sum(len(r["atomic_rules"]) for r in sc_runs)}
    res = {"engine": runs["engine"], "model": runs["model"], "run_at": runs["run_at"],
           "prompt_template_sha256": runs["prompt_template_sha256"], "total": total, "by_set": results, "stats": stats}
    METRICS.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"# Đánh giá phân tích quy định bằng mô hình ngôn ngữ lớn ({runs['engine']}, {runs['model']})", "",
         f"Chạy lúc {runs['run_at']}; nhiệt độ 0; mã băm câu lệnh {runs['prompt_template_sha256'][:16]}. Đáp án 30 kịch bản "
         "được băm trước khi có mô-đun này.", "",
         "| Phương pháp | Kịch bản đạt | Thay đổi bắt buộc tìm đúng | Giữ nguyên đúng | Không liên quan, không đề xuất | Đề xuất ngoài đáp án |",
         "|---|---:|---:|---:|---:|---:|"]
    for k, label in (("llm", "Mô hình ngôn ngữ lớn + truy xuất"), ("process_profile", "Mô hình nội bộ process-profile-3"),
                     ("rules", "Luật từ khóa")):
        s = total[k]
        L.append(f"| {label} | {s['scenarios_pass']}/{s['scenarios']} | {s['required_changes_found']} | {s['kept_unchanged']} | "
                 f"{s['no_change_scenarios_ok']} | {s['proposals_outside_answer_key']} |")
    L += ["", f"Thống kê: {json.dumps(stats, ensure_ascii=False)}", "", "## Chi tiết từng kịch bản (mô hình ngôn ngữ lớn)", "",
          "| Mã | Kết quả | Đề xuất | Ngoài đáp án |", "|---|---|---|---|"]
    for name in results:
        for row in results[name]["llm"]["rows"]:
            props = "; ".join(f"{p['code']} {p['current']['lifecycle']}{p['current']['risk_weight']}→"
                              f"{p['proposed']['lifecycle']}{p['proposed']['risk_weight']}" for p in row["proposals"]) or "-"
            L.append(f"| {row['id']} | {'Đạt' if row['pass'] else 'Không đạt'} | {props} | {', '.join(row['extra_proposals']) or '-'} |")
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(json.dumps(total, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
