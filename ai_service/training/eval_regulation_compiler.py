r"""Chấm điểm AI hiểu quy định có điều kiện ngữ cảnh (regulation_clauses*.json).

So sánh các bộ máy trên cùng bộ điều khoản có đáp án viết trước:
  v1   trình biên dịch cũ (chỉ ngưỡng tiền/ngày + tên loại), mốc so sánh
  v2   trình biên dịch có điều kiện ngữ cảnh (api_core/workflow/regulation_compiler.py)
  llm  Gemini trích xuất luật có cấu trúc + kiểm tra bằng luật (ai_service/regulation_rules_llm.py)

Tập test chỉ được chấm với --final và chỉ khi SHA-256 khớp tệp đã băm trước khi phát triển.

Chạy (môi trường có Django, ví dụ .venv của repo):
  .venv\Scripts\python ai_service\training\eval_regulation_compiler.py              # dev + demo
  .venv\Scripts\python ai_service\training\eval_regulation_compiler.py --final      # thêm test
  ... --llm-runs ai_service\training\data\regulation_rules_llm_runs.json           # chấm thêm đầu ra LLM đã lưu
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ai_service" / "training" / "data"
sys.path.insert(0, str(ROOT))

from api_core.workflow.regulation_compiler import (
    MATCH_KEYS,
    RequestTypeName,
    compile_text,
)


def load_types() -> list[RequestTypeName]:
    catalog = json.loads(
        (ROOT / "api_core" / "catalog" / "catalog_v2.json").read_text(encoding="utf-8")
    )
    return [
        RequestTypeName(i["code"], i["name"], i.get("lifecycle"))
        for i in catalog["items"]
        if i.get("status", "ACTIVE") == "ACTIVE"
    ]


def v1_compile(text: str, types: list[RequestTypeName]) -> list[dict]:
    """Mốc so sánh: bản v1 đóng băng (regulation_compiler_v1_baseline.py, commit 565c96b)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import regulation_compiler_v1_baseline as v1

    legacy = [v1.RequestTypeName(t.code, t.name) for t in types]
    return v1.compile_regulations([{"code": "X", "content": text}], legacy)


def key(rule: dict) -> tuple:
    out = []
    for k in MATCH_KEYS:
        v = rule.get(k)
        if k != "auto_approve" and (v is None or v is False):
            continue
        out.append((k, v))
    return tuple(out)


def score(items: list[dict], predict) -> dict:
    tp = fp = fn = exact = over_block = missed_control = esc_ok = esc_n = appr_ok = (
        appr_n
    ) = 0
    errors = []
    for item in items:
        expected = item["expected"]
        predicted = predict(item["text"])
        e = {key(r): r for r in expected}
        p = {key(r): r for r in predicted}
        hit = set(e) & set(p)
        tp += len(hit)
        fp += len(set(p) - set(e))
        fn += len(set(e) - set(p))
        ok = set(e) == set(p)
        exact += ok
        for k in set(p) - set(e):
            r = p[k]
            if r.get("auto_approve") is False:
                # Luật bắt buộc thủ công mà đáp án không có: chặn tràn (block rộng hơn quy định).
                over_block += 1
        for k in set(e) - set(p):
            if e[k].get("auto_approve") is False:
                missed_control += 1
        for k in hit:
            esc_n += 1
            esc_ok += (e[k].get("escalate_to") or None) == (
                p[k].get("escalate_to") or None
            )
            if e[k].get("approvers"):
                appr_n += 1
                appr_ok += set(e[k]["approvers"]) == set(p[k].get("approvers") or [])
        if not ok:
            errors.append(
                {
                    "id": item["id"],
                    "missing": [dict(k) for k in set(e) - set(p)],
                    "extra": [dict(k) for k in set(p) - set(e)],
                }
            )
    n = len(items)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "clauses": n,
        "exact": exact,
        "exact_rate": round(exact / n, 3) if n else None,
        "rule_precision": round(precision, 3),
        "rule_recall": round(recall, 3),
        "rule_f1": round(f1, 3),
        "over_block_rules": over_block,
        "missed_control_rules": missed_control,
        "escalate_accuracy": round(esc_ok / esc_n, 3) if esc_n else None,
        "approver_accuracy": round(appr_ok / appr_n, 3) if appr_n else None,
        "errors": errors,
    }


def verify_test_hash() -> list[dict]:
    raw = (DATA / "regulation_clauses_test.json").read_bytes()
    want = (
        (DATA / "regulation_clauses_test.sha256").read_text(encoding="ascii").split()[0]
    )
    got = hashlib.sha256(raw).hexdigest()
    if got != want:
        sys.exit(f"Từ chối chấm: SHA-256 của tập test đã đổi ({got} != {want}).")
    return json.loads(raw)["test"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="chấm cả tập test đã băm")
    ap.add_argument(
        "--llm-runs", default="", help="JSON đầu ra LLM đã lưu {clause_id: [rules]}"
    )
    ap.add_argument("--json", default="", help="ghi kết quả ra tệp JSON")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    types = load_types()
    sets = json.loads((DATA / "regulation_clauses.json").read_text(encoding="utf-8"))
    splits = {"dev": sets["dev"], "demo": sets["demo"]}
    if a.final:
        splits["test"] = verify_test_hash()

    by_text = {}
    llm = {}
    if a.llm_runs:
        llm = json.loads(Path(a.llm_runs).read_text(encoding="utf-8")).get(
            "outputs", {}
        )
    for items in splits.values():
        for it in items:
            by_text[it["text"]] = it["id"]

    engines = {
        "v1": lambda text: v1_compile(text, types),
        "v2": lambda text: compile_text("X", text, types),
    }
    if llm:
        engines["llm"] = lambda text: llm.get(by_text[text], [])
        # Chốt TRƯỚC khi chấm test: dùng v2; v2 không sinh luật nào thì lấy luật LLM đã qua kiểm tra.
        engines["hybrid"] = lambda text: (
            compile_text("X", text, types) or llm.get(by_text[text], [])
        )

    result = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "splits": {},
    }
    for split, items in splits.items():
        result["splits"][split] = {}
        for name, fn in engines.items():
            if name in ("llm", "hybrid") and not all(it["id"] in llm for it in items):
                continue
            s = score(items, fn)
            result["splits"][split][name] = s
            print(
                f"{split:5} {name:4} exact {s['exact']}/{s['clauses']}  P {s['rule_precision']:.3f} "
                f"R {s['rule_recall']:.3f} F1 {s['rule_f1']:.3f}  chặn tràn {s['over_block_rules']}  "
                f"bỏ sót {s['missed_control_rules']}  luồng {s['escalate_accuracy']}  cấp duyệt {s['approver_accuracy']}"
            )
            if a.verbose:
                for err in s["errors"]:
                    print(
                        "    ", err["id"], "thiếu", err["missing"], "thừa", err["extra"]
                    )
    if a.json:
        Path(a.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
