"""Chấm trình biên dịch quy định (mọi kiểu điều kiện) và luật thay thế quy định cũ trên bộ test băm trước.

  ai_service\\.venv-ai\\Scripts\\python -I ai_service\\training\\eval_regulation_v3.py [--json out.json]

Bộ test: data/regulation_v3_test.json (sha256 e7ef2366…, commit 91dc93d), viết tay trước khi cài v3.
  - clauses: so khớp đúng tập luật (các khóa trong KEYS) sinh ra từ mỗi câu.
  - supersede: chạy lần lượt các bước ban hành / sửa / bãi bỏ như lượt học thật (kiểm tra văn bản -> biên dịch ->
    luật mới thay thế luật cũ), rồi thử từng hồ sơ: MANUAL nếu còn luật bắt duyệt thủ công áp dụng, FREE nếu không.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai_service"))

from api_core.workflow import regulation_compiler as rc  # noqa: E402
from api_core.workflow import regulation_precedence as rp  # noqa: E402
from api_core.workflow.regulation_validation import validate  # noqa: E402
from routers.policy import PolicyRule, PolicySignals, rule_applies  # noqa: E402

TEST_SHA256 = "e7ef23667475eb34e203d8b271c08ea42fe1bde478da66947a40f08facd6c60c"
KEYS = ("request_type", "amount_gt", "amount_lte", "days_gt", "days_lte", "percent_gt", "percent_lte",
        "location_contains", "due_within_hours", "require_no_handover", "repeat_count_gte", "repeat_window",
        "split_suspect", "retro_days_gt", "effective_from", "effective_until", "auto_approve", "escalate_to")


def load_test() -> dict:
    raw = (DATA / "regulation_v3_test.json").read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != TEST_SHA256:
        raise SystemExit(f"Bộ test đã bị sửa (sha256 {digest}), dừng chấm.")
    return json.loads(raw)


def load_types() -> list[rc.RequestTypeName]:
    rows = json.loads((DATA / "request_types_snapshot.json").read_text(encoding="utf-8"))["types"]
    return [rc.RequestTypeName(r["code"], r["name"], r["lifecycle"]) for r in rows]


def norm(rule: dict) -> tuple:
    out = []
    for k in KEYS:
        v = rule.get(k)
        if v is None or v is False and k != "auto_approve":
            continue
        if isinstance(v, str) and k == "location_contains":
            v = " ".join(v.lower().split())
        out.append((k, v))
    return tuple(out)


def score_clauses(items: list[dict], types) -> dict:
    ok, errors = 0, []
    for item in items:
        got = sorted(norm(r) for r in rc.compile_text("T", item["sentence"], types))
        want = sorted(norm(r) for r in item["expect"])
        if got == want:
            ok += 1
        else:
            errors.append({"id": item["id"], "want": [dict(x) for x in want], "got": [dict(x) for x in got]})
    return {"n": len(items), "correct": ok, "accuracy": round(ok / len(items), 3), "errors": errors}


def simulate(scenario: dict, types) -> list[dict]:
    """Chạy các bước như lượt học: văn bản lỗi bị trả lại; luật mới thay thế luật cũ; trả về bộ luật cuối."""
    regs: dict[str, dict] = {}
    origins: dict = {}
    applied: list[dict] = []
    version = 1
    for step in scenario["steps"]:
        version += 1
        candidate = {k: dict(v) for k, v in regs.items()}
        changed = None
        if "publish" in step or "edit" in step:
            body = step.get("publish") or step.get("edit")
            candidate[body["code"]] = {"code": body["code"], "title": body["code"], "content": body["content"]}
            changed = body["code"]
        else:
            candidate.pop(step["delete"], None)
        if changed:
            others = [r for c, r in candidate.items() if c != changed]
            check = validate(code=changed, title=changed, content=candidate[changed]["content"], types=types,
                             others=others)
            if not check["ok"]:
                continue  # trả lại: hiệu lực giữ nguyên
        regs = candidate
        rules = rc.compile_regulations(list(regs.values()), types)
        for r in rules:
            r["source_code"] = next(c for c in sorted(regs, key=len, reverse=True) if r["id"].startswith(f"{c}-"))
        resolved = rp.resolve(rules, origins)
        applied = resolved[0]
        origins = rp.next_origins(rules, origins, f"{version}.0", superseded=resolved[1]) \
            if "superseded" in rp.next_origins.__code__.co_varnames else rp.next_origins(rules, origins, f"{version}.0")
    return applied


def verdict(rules: list[dict], probe: dict) -> str:
    sig = PolicySignals(
        same_type_count_month=probe.get("repeat", 1), same_type_count_7d=probe.get("repeat", 1),
        same_type_count_30d=probe.get("repeat", 1), percent=probe.get("percent"), today=probe.get("today"),
    )
    for raw in rules:
        rule = PolicyRule(**{k: v for k, v in raw.items() if k in PolicyRule.model_fields})
        if rule.auto_approve is False and rule_applies(
                rule, probe["type"], float(probe.get("amount", 0)), int(probe.get("days", 0)), sig):
            return "MANUAL"
    return "FREE"


def score_supersede(scenarios: list[dict], types) -> dict:
    ok_s, ok_p, total_p, errors = 0, 0, 0, []
    for sc in scenarios:
        try:
            rules = simulate(sc, types)
            results = [(p, verdict(rules, p)) for p in sc["probes"]]
        except Exception as exc:  # noqa: BLE001
            errors.append({"id": sc["id"], "error": f"{type(exc).__name__}: {exc}"})
            total_p += len(sc["probes"])
            continue
        good = [r == p["expect"] for p, r in results]
        total_p += len(good)
        ok_p += sum(good)
        if all(good):
            ok_s += 1
        else:
            errors.append({"id": sc["id"], "about": sc["about"],
                           "probes": [{**p, "got": r} for p, r in results if r != p["expect"]]})
    return {"scenarios": len(scenarios), "scenarios_correct": ok_s, "probes": total_p, "probes_correct": ok_p,
            "errors": errors}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    test = load_test()
    types = load_types()
    result = {"label": args.label, "date": date.today().isoformat(),
              "clauses": score_clauses(test["clauses"], types),
              "supersede": score_supersede(test["supersede"], types)}
    c, s = result["clauses"], result["supersede"]
    print(f"Câu: {c['correct']}/{c['n']} ({c['accuracy']:.1%}) | Thay thế: {s['scenarios_correct']}/{s['scenarios']} "
          f"tình huống, {s['probes_correct']}/{s['probes']} hồ sơ thử")
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
