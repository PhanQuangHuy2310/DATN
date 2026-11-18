"""Huấn luyện và đánh giá mô hình hồ sơ quy trình (mẫu vòng đời A/B/C + trọng số rủi ro 1-5).

  python -m ai_service.training.train_process_profile          (từ gốc repo)

1. Đánh giá leave-one-out (58 loại, mỗi lần bỏ 1 loại ra, huấn luyện trên 57, dự đoán loại bị bỏ) cho một lưới nhỏ
   biến thể (C x có/không dùng từ ngữ) và so với 2 mốc: (a) đoán lớp/giá trị phổ biến nhất; (b) luật từ khóa viết tay.
2. Chọn biến thể trên tập PHÁT TRIỂN (LOO + kịch bản QD-01..QD-20; QD-11..QD-20 từng là tập giữ lại của phiên bản 2).
3. Chấm phiên bản 3 MỘT LẦN trên tập GIỮ LẠI thứ hai QD-21..QD-30 (đáp án băm SHA-256 trước khi xây phiên bản 3),
   so với luật từ khóa dùng cùng bước tìm loại liên quan.
4. Huấn luyện trên toàn bộ 58 loại, lưu ai_service/models/process_profile.joblib + báo cáo.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from process_profile import PROFILE_VERSION, ProcessProfiler, cue_features, type_text  # noqa: E402

DATA = ROOT / "training" / "data"
PROFILES = DATA / "process_profiles.json"
SCENARIOS = DATA / "regulation_scenarios.json"
SCENARIOS_SHA = DATA / "regulation_scenarios.sha256"
HOLDOUT = DATA / "regulation_scenarios_holdout.json"
HOLDOUT_SHA = DATA / "regulation_scenarios_holdout.sha256"
VARIANTS = [{"lc_c": c, "use_words": w} for w in (True, False) for c in (0.3, 1.0, 3.0)]
HOLDOUT2 = DATA / "regulation_scenarios_holdout2.json"
HOLDOUT2_SHA = DATA / "regulation_scenarios_holdout2.sha256"
V1_METRICS = DATA / "process_profile_v1_metrics.json"
V2_METRICS = DATA / "process_profile_v2_metrics.json"
MODEL_OUT = ROOT / "models" / "process_profile.joblib"
REPORT_JSON = ROOT / "models" / "process_profile_metrics.json"
REPORT_MD = DATA / "process_profile_report.md"


def load_items() -> list[dict]:
    return json.loads(PROFILES.read_text(encoding="utf-8"))["items"]


def check_scenarios(path: Path = SCENARIOS, sha: Path = SCENARIOS_SHA) -> dict:
    raw = path.read_bytes()
    want = sha.read_text(encoding="utf-8").split()[0].strip()
    got = hashlib.sha256(raw).hexdigest()
    if got != want:
        raise SystemExit(f"{path.name} đã bị sửa sau khi chốt đáp án (sha256 {got} != {want})")
    return json.loads(raw.decode("utf-8"))


# ------------------------------------------------------------------------------------------- mốc so sánh
def rule_baseline(item: dict, extra_text: str = "") -> tuple[str, int]:
    """Luật từ khóa viết tay: có tín hiệu bàn giao/nghiệm thu → C; có tín hiệu thực hiện → B; còn lại A.
    Trọng số = 2 + (tiền) + (nhạy cảm) + (pháp lý) - (thường nhật), kẹp 1..5."""
    c = cue_features(type_text(item) + (" " + extra_text if extra_text else ""))
    lc = "C" if c["cue:acceptance"] else ("B" if c["cue:execution"] else "A")
    w = 2 + (c["cue:money"] > 0) + (c["cue:sensitive"] > 0) + (c["cue:legal"] > 0) - (c["cue:routine"] > 0)
    return lc, int(min(5, max(1, w)))


def weight_metrics(y: list[int], p: list[int]) -> dict:
    d = np.abs(np.array(y) - np.array(p))
    return {"mae": round(float(d.mean()), 3), "exact": round(float((d == 0).mean()), 3),
            "within_1": round(float((d <= 1).mean()), 3)}


def lc_metrics(y: list[str], p: list[str]) -> dict:
    return {"accuracy": round(accuracy_score(y, p), 3),
            "macro_f1": round(f1_score(y, p, average="macro", zero_division=0), 3)}


def leave_one_out(items: list[dict], **cfg) -> dict:
    y_lc = [i["lifecycle"] for i in items]
    y_w = [int(i["risk_weight"]) for i in items]
    p_lc, p_w, errors = [], [], []
    for k, item in enumerate(items):
        model = ProcessProfiler(**cfg).fit(items[:k] + items[k + 1:])
        pred = model.predict_one(item)
        p_lc.append(pred["lifecycle"])
        p_w.append(pred["risk_weight"])
        if pred["lifecycle"] != item["lifecycle"] or abs(pred["risk_weight"] - item["risk_weight"]) > 1:
            errors.append({"code": item["code"], "true": [item["lifecycle"], item["risk_weight"]],
                           "pred": [pred["lifecycle"], pred["risk_weight"]],
                           "reasons": pred["reasons_lifecycle"]})
    # mốc (a): phổ biến nhất trong 57 loại còn lại
    maj_lc, maj_w = [], []
    for k in range(len(items)):
        rest = items[:k] + items[k + 1:]
        maj_lc.append(Counter(i["lifecycle"] for i in rest).most_common(1)[0][0])
        maj_w.append(int(np.median([i["risk_weight"] for i in rest])))
    rules = [rule_baseline(i) for i in items]
    labels = ["A", "B", "C"]
    cm = [[sum(1 for t, p in zip(y_lc, p_lc) if t == a and p == b) for b in labels] for a in labels]
    return {
        "n": len(items),
        "label_distribution": {"lifecycle": dict(Counter(y_lc)), "risk_weight": dict(sorted(Counter(y_w).items()))},
        "model": {"lifecycle": lc_metrics(y_lc, p_lc), "risk_weight": weight_metrics(y_w, p_w), "confusion_ABC": cm},
        "baseline_majority": {"lifecycle": lc_metrics(y_lc, maj_lc), "risk_weight": weight_metrics(y_w, maj_w)},
        "baseline_rules": {"lifecycle": lc_metrics(y_lc, [r[0] for r in rules]),
                           "risk_weight": weight_metrics(y_w, [r[1] for r in rules])},
        "errors": errors,
    }


# ------------------------------------------------------------------------------------------- kịch bản
def rule_impact(model: ProcessProfiler, text: str) -> dict:
    """Mốc so sánh: cùng bước tìm loại liên quan, nhưng đề xuất = chênh lệch của luật từ khóa viết tay."""
    order = {"A": 0, "B": 1, "C": 2}
    proposals = []
    related = []
    for item, sim in model.related_types(text):
        b_lc, b_w = rule_baseline(item)
        n_lc, n_w = rule_baseline(item, text)
        cur = {"lifecycle": item["lifecycle"], "risk_weight": int(item["risk_weight"])}
        prop = dict(cur)
        if n_w != b_w:
            prop["risk_weight"] = int(min(5, max(1, cur["risk_weight"] + (n_w - b_w))))
        if n_lc != b_lc and order[n_lc] > order[cur["lifecycle"]]:
            prop["lifecycle"] = n_lc
        entry = {"code": item["code"], "current": cur, "proposed": prop, "reasons": ["luật từ khóa"]}
        related.append(entry)
        if prop != cur:
            proposals.append(entry)
    return {"related": related, "proposals": proposals}


def run_scenarios(model: ProcessProfiler, spec: dict, impact=None) -> dict:
    rows = []
    tot = Counter()
    for sc in spec["scenarios"]:
        res = impact(model, sc["text"]) if impact else model.regulation_impact(sc["text"])
        props = {p["code"]: p for p in res["proposals"]}
        related = [r["code"] for r in res["related"]]
        checks = []
        for code, exp in sc["expected_changes"].items():
            p = props.get(code)
            ok = p is not None
            if ok and "lifecycle" in exp:
                ok = p["proposed"]["lifecycle"] == exp["lifecycle"]
            if ok and "weight" in exp:
                ok = p["proposed"]["risk_weight"] > p["current"]["risk_weight"]
            checks.append({"kind": "phải đổi", "code": code, "expected": exp, "ok": ok,
                           "got": p["proposed"] if p else None, "related": code in related})
            tot["change_total"] += 1
            tot["change_ok"] += ok
        for code in sc["expected_unchanged"]:
            p = props.get(code)
            ok = p is None
            if not ok and sc["id"] == "QD-05":  # đáp án chấp nhận tăng trọng số, cấm giảm hoặc đổi mẫu
                ok = (p["proposed"]["lifecycle"] == p["current"]["lifecycle"]
                      and p["proposed"]["risk_weight"] >= p["current"]["risk_weight"])
            checks.append({"kind": "giữ nguyên", "code": code, "ok": ok, "got": p["proposed"] if p else None})
            tot["keep_total"] += 1
            tot["keep_ok"] += ok
        expected_codes = set(sc["expected_changes"]) | set(sc["expected_unchanged"])
        extra = [c for c in props if c not in expected_codes]
        if sc.get("no_change_expected"):
            tot["nochange_total"] += 1
            tot["nochange_ok"] += not props
        tot["proposals"] += len(props)
        tot["extra"] += len(extra)
        rows.append({"id": sc["id"], "title": sc["title"], "related": related,
                     "proposals": [{"code": c, "current": p["current"], "proposed": p["proposed"],
                                    "reasons": p["reasons"]} for c, p in props.items()],
                     "checks": checks, "extra_proposals": extra,
                     "pass": all(c["ok"] for c in checks) and (not sc.get("no_change_expected") or not props)})
    summary = {
        "scenarios_pass": sum(r["pass"] for r in rows), "scenarios": len(rows),
        "required_changes_found": f"{tot['change_ok']}/{tot['change_total']}",
        "kept_unchanged": f"{tot['keep_ok']}/{tot['keep_total']}",
        "no_change_scenarios_ok": f"{tot['nochange_ok']}/{tot['nochange_total']}",
        "proposals_total": tot["proposals"], "proposals_outside_answer_key": tot["extra"],
    }
    return {"summary": summary, "rows": rows}


# ------------------------------------------------------------------------------------------- báo cáo
def fmt_row(name: str, v: dict) -> str:
    return (f"| {name} | {v['lifecycle']['accuracy']:.1%} | {v['lifecycle']['macro_f1']:.3f} | "
            f"{v['risk_weight']['mae']:.2f} | {v['risk_weight']['exact']:.1%} | {v['risk_weight']['within_1']:.1%} |")


def scenario_table(sc: dict) -> list[str]:
    s = sc["summary"]
    L = [f"Đạt {s['scenarios_pass']}/{s['scenarios']} kịch bản; tìm đúng thay đổi bắt buộc {s['required_changes_found']}; "
         f"giữ nguyên đúng {s['kept_unchanged']}; kịch bản không liên quan không đề xuất {s['no_change_scenarios_ok']}; "
         f"tổng {s['proposals_total']} đề xuất, {s['proposals_outside_answer_key']} đề xuất nằm ngoài đáp án.", "",
         "| Mã | Kịch bản | Kết quả | Đề xuất (hiện tại → đề xuất) | Lý do | Ngoài đáp án |", "|---|---|---|---|---|---|"]
    for row in sc["rows"]:
        props = "; ".join(f"{p['code']} {p['current']['lifecycle']}{p['current']['risk_weight']}→"
                          f"{p['proposed']['lifecycle']}{p['proposed']['risk_weight']}" for p in row["proposals"]) or "-"
        why = "; ".join(", ".join(p["reasons"][:3]) for p in row["proposals"]) or "-"
        L.append(f"| {row['id']} | {row['title']} | {'Đạt' if row['pass'] else 'Không đạt'} | {props} | {why} | "
                 f"{', '.join(row['extra_proposals']) or '-'} |")
    return L


def write_report(res: dict) -> None:
    v1 = json.loads(V1_METRICS.read_text(encoding="utf-8")) if V1_METRICS.exists() else None
    v2 = json.loads(V2_METRICS.read_text(encoding="utf-8")) if V2_METRICS.exists() else None
    loo = res["loo"]
    L = [f"# Báo cáo mô hình hồ sơ quy trình ({PROFILE_VERSION})", "",
         f"Sinh lúc {res['trained_at']}. Dữ liệu: {loo['n']} loại yêu cầu trong `process_profiles.json` (nhãn do nhóm "
         f"cấu hình). Phân bố mẫu vòng đời: {loo['label_distribution']['lifecycle']}; trọng số: "
         f"{loo['label_distribution']['risk_weight']}.", "",
         "Đầu vào chỉ là nội dung quy trình (tên, mô tả, nhóm nghiệp vụ, các trường biểu mẫu). Người thực hiện, người "
         "nghiệm thu, cấp duyệt và các mô tả dạng tóm tắt tuyến duyệt bị loại vì chúng suy ra trực tiếp từ nhãn.", "",
         "## 1. Leave-one-out", "",
         "| Phương pháp | Vòng đời: accuracy | Vòng đời: macro-F1 | Trọng số: MAE | Trọng số: đúng | Trọng số: lệch ≤ 1 |",
         "|---|---:|---:|---:|---:|---:|",
         fmt_row("Đoán phổ biến nhất", loo["baseline_majority"]), fmt_row("Luật từ khóa viết tay", loo["baseline_rules"])]
    if v1:
        L.append(fmt_row("Phiên bản 1 (chốt trước; mô tả còn lộ nhãn)", v1["loo"]["model"]))
    for name, v in res["variants"].items():
        L.append(fmt_row(f"Phiên bản 2, {name}{' (chọn)' if name == res['chosen'] else ''}", v))
    L += ["", "Biến thể được chọn theo macro-F1 vòng đời rồi MAE trọng số trên leave-one-out, nên số của biến thể được "
          "chọn hơi lạc quan (chọn 1 trong 6).", "",
          f"Ma trận nhầm lẫn vòng đời của biến thể được chọn (hàng = thật A/B/C, cột = dự đoán): "
          f"{loo['model']['confusion_ABC']}", "", "Các loại sai mẫu vòng đời hoặc lệch trọng số > 1:", ""]
    for e in loo["errors"]:
        L.append(f"- {e['code']}: thật {e['true']}, dự đoán {e['pred']}; lý do: {', '.join(e['reasons']) or '-'}")
    if v1:
        L += ["", "## 2. Kịch bản quy định mới, phiên bản 1 (đáp án QD-01..QD-10 chốt trước)", ""] + \
             scenario_table(v1["scenarios"])
    if v2:
        L += ["", "## 3. Phiên bản 2 trên tập giữ lại QD-11..QD-20 (chấm một lần)", "", "### Mô hình", ""] +              scenario_table(v2["holdout"]) + ["", "### Mốc luật từ khóa", ""] + scenario_table(v2["holdout_rules"])
    L += ["", "## 4. Phiên bản 3 (bản cuối) trên tập phát triển QD-01..QD-20", ""] + scenario_table(res["dev"])
    L += ["", "## 5. Phiên bản 3 trên tập giữ lại thứ hai QD-21..QD-30 (chấm một lần)", "", "### Mô hình", ""] +          scenario_table(res["holdout"]) + ["", "### Mốc: luật từ khóa với cùng bước tìm loại liên quan", ""] +          scenario_table(res["holdout_rules"])
    L += ["", "Giá học được cho mỗi tín hiệu nghiệp vụ (mức tăng trọng số, ràng buộc không âm): "
          f"{res['cue_prices']}"]
    L += ["", "## 6. Giới hạn", "",
          "- Chỉ có 58 mẫu, nhãn do chính nhóm cấu hình; nhiều mô tả loại chỉ là câu giữ chỗ nên mô hình chủ yếu dựa vào "
          "tên loại, nhóm nghiệp vụ và tên trường. Số đo là ước lượng thô, khoảng tin cậy rộng.",
          "- Đáp án kịch bản do nhóm viết; 10 kịch bản mỗi tập là quá ít để kết luận mạnh.",
          "- Đề xuất chỉ để quản trị viên duyệt; mô hình không tự sửa cấu hình. Chỉ đề xuất NÂNG mẫu vòng đời.", ""]
    REPORT_MD.write_text("\n".join(L), encoding="utf-8")


def key(v: dict) -> tuple:
    return (v["lifecycle"]["macro_f1"], -v["risk_weight"]["mae"])


def main() -> None:
    items = load_items()
    dev_spec = check_scenarios()
    dev_spec = {"scenarios": dev_spec["scenarios"] + check_scenarios(HOLDOUT, HOLDOUT_SHA)["scenarios"]}
    hold_spec = check_scenarios(HOLDOUT2, HOLDOUT2_SHA)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    variants, loos = {}, {}
    for cfg in VARIANTS:
        name = f"C={cfg['lc_c']}, {'có' if cfg['use_words'] else 'không'} TF-IDF từ"
        loos[name] = leave_one_out(items, **cfg)
        variants[name] = loos[name]["model"]
        v = variants[name]
        print(f"{name:28s} vòng đời acc {v['lifecycle']['accuracy']:.1%} F1 {v['lifecycle']['macro_f1']:.3f} | "
              f"trọng số MAE {v['risk_weight']['mae']:.2f} ±1 {v['risk_weight']['within_1']:.1%}")
    chosen = max(variants, key=lambda n: key(variants[n]))
    cfg = VARIANTS[list(variants).index(chosen)]
    model = ProcessProfiler(**cfg).fit(items)
    dev = run_scenarios(model, dev_spec)
    print("Chọn:", chosen, "| dev:", json.dumps(dev["summary"], ensure_ascii=False))
    holdout = run_scenarios(model, hold_spec)
    holdout_rules = run_scenarios(model, hold_spec, impact=rule_impact)
    print("Giữ lại (mô hình):", json.dumps(holdout["summary"], ensure_ascii=False))
    print("Giữ lại (luật):  ", json.dumps(holdout_rules["summary"], ensure_ascii=False))
    for row in dev["rows"] + holdout["rows"]:
        print(row["id"], "ĐẠT" if row["pass"] else "KHÔNG",
              [(p["code"], p["current"], p["proposed"]) for p in row["proposals"]], "related:", row["related"])
    res = {"version": PROFILE_VERSION, "trained_at": stamp, "chosen": chosen, "config": cfg, "variants": variants,
           "loo": loos[chosen], "baselines": {"majority": loos[chosen]["baseline_majority"],
                                              "rules": loos[chosen]["baseline_rules"]},
           "dev": dev, "holdout": holdout, "holdout_rules": holdout_rules, "cue_prices": model.cue_prices()}
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_OUT)
    REPORT_JSON.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(res)


if __name__ == "__main__":
    main()
