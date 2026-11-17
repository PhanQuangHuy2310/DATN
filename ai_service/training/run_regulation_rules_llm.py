r"""Gọi Gemini trích xuất luật cho mọi điều khoản trong bộ đánh giá và lưu đầu ra (để chấm lại không tốn API).

  ai_service\.venv-ai\Scripts\python ai_service\training\run_regulation_rules_llm.py [--model gemini-3.5-flash-lite]

Đọc GEMINI_API_KEY từ biến môi trường hoặc tệp .env ở gốc repo. Tập test chỉ được đọc khi SHA-256 khớp.
Kết quả: ai_service/training/data/regulation_rules_llm_runs.json (chấm bằng eval_regulation_compiler.py --llm-runs).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ai_service" / "training" / "data"
sys.path.insert(0, str(ROOT / "ai_service"))

import regulation_rules_llm as rl


def api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("Thiếu GEMINI_API_KEY")
    return key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--model", default=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="giây nghỉ giữa các lần gọi (giới hạn gói miễn phí)",
    )
    a = ap.parse_args()

    raw = (DATA / "regulation_clauses_test.json").read_bytes()
    want = (
        (DATA / "regulation_clauses_test.sha256").read_text(encoding="ascii").split()[0]
    )
    if hashlib.sha256(raw).hexdigest() != want:
        sys.exit("SHA-256 tập test đã đổi; từ chối chạy.")
    sets = json.loads((DATA / "regulation_clauses.json").read_text(encoding="utf-8"))
    items = sets["dev"] + sets["demo"] + json.loads(raw)["test"]
    catalog = json.loads(
        (ROOT / "api_core" / "catalog" / "catalog_v2.json").read_text(encoding="utf-8")
    )
    types = [
        {"code": i["code"], "name": i["name"], "lifecycle": i.get("lifecycle")}
        for i in catalog["items"]
        if i.get("status", "ACTIVE") == "ACTIVE"
    ]
    key = api_key()
    out = {
        "engine": rl.ENGINE_VERSION,
        "model": a.model,
        "at": None,
        "outputs": {},
        "rejected": {},
        "latency_ms": {},
        "tokens": {},
        "errors": {},
    }
    path = DATA / "regulation_rules_llm_runs.json"
    for n, item in enumerate(items, 1):
        for attempt in range(3):
            try:
                res = rl.extract(item["text"], types, api_key=key, model_name=a.model)
                break
            except Exception as exc:  # noqa: BLE001
                out["errors"][item["id"]] = f"{type(exc).__name__}: {str(exc)[:200]}"
                time.sleep(20 * (attempt + 1))
        else:
            print(item["id"], "LỖI", out["errors"][item["id"]], flush=True)
            continue
        out["errors"].pop(item["id"], None)
        out["outputs"][item["id"]] = res["rules"]
        out["rejected"][item["id"]] = res["rejected"]
        out["latency_ms"][item["id"]] = res["latency_ms"]
        out["tokens"][item["id"]] = res["tokens"]
        print(
            f"{n}/{len(items)} {item['id']} {len(res['rules'])} luật, loại {len(res['rejected'])}, "
            f"{res['latency_ms']} ms",
            flush=True,
        )
        out["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(a.sleep)
    print("xong", len(out["outputs"]), "/", len(items), "lỗi", len(out["errors"]))
    return 0 if not out["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
