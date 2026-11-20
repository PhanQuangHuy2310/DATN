r"""Chấm bộ phân loại trên câu ngắn đời thường (data/request_eval_everyday.json, băm trước khi sửa).

    ai_service\.venv-ai\Scripts\python -I ai_service\training\eval_request_everyday.py [--json out.json]

Dùng đúng đường đi của dịch vụ (routers.classify.predict: mô hình + nhận biết nhu cầu mới), không có loại học thêm.
Chỉ số:
  * đúng top-1 / top-3 (câu trong danh mục, nhãn nằm trong 'accept');
  * báo nhầm "nhu cầu mới / không hiểu" cho câu trong danh mục;
  * SAI MÀ TỰ TIN: top-1 sai nhưng không bị coi là chưa chắc -> giao diện sẽ gợi ý chuyển sang biểu mẫu sai;
  * câu ngoài danh mục được nhận ra (nhu cầu mới, không hiểu, hoặc chưa chắc).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT), str(ROOT.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from routers import classify as cl

SETS = {
    "1": "request_eval_everyday",   # lỗi của bộ này được dùng để sửa dữ liệu huấn luyện (chấm lại = sau-sự-kiện)
    "2": "request_eval_everyday2",  # giữ kín: chỉ in số tổng, không in từng câu sai
}
OUT_OF_SCOPE = "OUT_OF_SCOPE"
SURE = 0.5  # cùng ngưỡng "AI đủ chắc để gợi ý chuyển" ở web_client/src/aiTypeSwitch.js
CLEAR_MIN, CLEAR_RATIO = 0.35, 3


def is_sure(result) -> bool:
    conf = result.confidence_request_type
    if result.low_confidence or result.novel or result.unclear:
        return False
    if conf >= SURE:
        return True
    runner = max([a.confidence for a in result.alternatives if a.request_type != result.predicted_request_type],
                 default=0.0)
    return conf >= CLEAR_MIN and conf >= CLEAR_RATIO * runner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json")
    parser.add_argument("--set", choices=sorted(SETS), default="1")
    parser.add_argument("--quiet", action="store_true", help="chỉ in số tổng (bộ giữ kín)")
    args = parser.parse_args()
    name = SETS[args.set]
    raw = (HERE / "data" / f"{name}.json").read_bytes()
    expected = (HERE / "data" / f"{name}.sha256").read_text(encoding="utf-8").split()[0]
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected:
        raise SystemExit(f"Bộ test đã bị sửa (sha256 {digest}), dừng chấm.")
    items = json.loads(raw)["items"]
    model, labels = cl.get_nlp_model()
    if model is None:
        raise SystemExit("Chưa có mô hình")
    rows, inscope, oos = [], [], []
    for item in items:
        r = cl.predict(model, labels, item["text"], [])
        accept = set(item.get("accept") or [item["label"]])
        top3 = [a.request_type for a in r.alternatives][:3]
        row = {"text": item["text"], "label": item["label"], "pred": r.predicted_request_type,
               "conf": round(r.confidence_request_type, 3), "novel": r.novel, "unclear": r.unclear,
               "low": r.low_confidence, "sure": is_sure(r), "top3": top3}
        if item["label"] == OUT_OF_SCOPE:
            row["handled"] = r.novel or r.unclear or not row["sure"] or r.predicted_request_type in accept
            oos.append(row)
        else:
            row["top1"] = r.predicted_request_type in accept
            row["in_top3"] = bool(accept & set(top3)) or row["top1"]
            row["flagged"] = r.novel or r.unclear
            row["confident_wrong"] = (not row["top1"]) and row["sure"]
            inscope.append(row)
        rows.append(row)
    n = len(inscope)
    summary = {
        "in_scope": n,
        "top1": sum(r["top1"] for r in inscope),
        "top3": sum(r["in_top3"] for r in inscope),
        "flagged_new_or_unclear": sum(r["flagged"] for r in inscope),
        "confident_wrong": sum(r["confident_wrong"] for r in inscope),
        "out_of_scope": len(oos),
        "oos_handled": sum(r["handled"] for r in oos),
    }
    print(f"Trong danh mục {n} câu: đúng top-1 {summary['top1']}/{n} ({summary['top1'] / n:.1%}), "
          f"top-3 {summary['top3']}/{n}; báo nhầm 'nhu cầu mới/không hiểu' {summary['flagged_new_or_unclear']}; "
          f"SAI MÀ TỰ TIN {summary['confident_wrong']}")
    print(f"Ngoài danh mục {len(oos)} câu: nhận ra {summary['oos_handled']}/{len(oos)}")
    if args.quiet:
        inscope, oos = [], []
    for r in inscope:
        if not r["top1"]:
            tag = "TỰ TIN" if r["confident_wrong"] else ("mới" if r["flagged"] else "chưa chắc")
            print(f"  SAI [{tag}] «{r['text']}» -> {r['pred']} {r['conf']} (đúng: {r['label']})")
    for r in oos:
        if not r["handled"]:
            print(f"  NGOÀI DANH MỤC bị gán tự tin «{r['text']}» -> {r['pred']} {r['conf']}")
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
