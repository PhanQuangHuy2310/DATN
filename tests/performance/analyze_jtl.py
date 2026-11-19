"""Tổng hợp kết quả JMeter (results.jtl dạng CSV) theo từng nhãn và đối chiếu ngưỡng Bảng 2.5.

  python analyze_jtl.py <results.jtl> [--json out.json]

Ngưỡng: API đọc (READ_*) p95 ≤ 800 ms; API ghi (WRITE_*) p95 ≤ 1.500 ms.
HTTP 429 được đếm riêng (giới hạn tốc độ theo chính sách), không gộp vào lỗi ứng dụng.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict

LIMITS = {"READ_": 800, "WRITE_": 1500}


def pct(values: list[int], q: float) -> float:
    s = sorted(values)
    return float(s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))]) if s else 0.0


def summarize(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows = [r for r in rows if r.get("label") and r.get("timeStamp", "").isdigit()]
    t0 = min(int(r["timeStamp"]) for r in rows)
    t1 = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in rows)
    # Người dùng ảo bị Nginx chặn đăng nhập (429) không có phiên: mọi request sau đó 401 là lỗi dây chuyền
    # của kịch bản, không phải lỗi ứng dụng.
    # Chỉ tính là dây chuyền khi đăng nhập bị CHẶN BỞI GIỚI HẠN TỐC ĐỘ (429); đăng nhập lỗi 5xx là sự cố thật.
    blocked = {r["threadName"] for r in rows if r["label"] == "AUTH_LOGIN" and r["responseCode"] == "429"}
    by = defaultdict(list)
    for r in rows:
        by[r["label"]].append(r)
    out = {"duration_s": round((t1 - t0) / 1000, 1), "samples": len(rows), "labels": {}}
    for label, rs in sorted(by.items()):
        el = [int(r["elapsed"]) for r in rs]
        codes = [r["responseCode"] for r in rs]
        n429 = codes.count("429")
        n5xx = sum(c.startswith("5") for c in codes)
        # Lỗi dây chuyền của kịch bản: bước tạo nháp bị 429 nên bước lưu gọi /request-drafts/NONE → 404.
        cascade = sum(1 for r in rs if r["success"] != "true" and r["responseCode"] != "429" and (
            (r["responseCode"] == "404" and r.get("URL", "").endswith("/NONE")) or
            (r["threadName"] in blocked and r["label"] != "AUTH_LOGIN")))
        other_err = sum(1 for r in rs if r["success"] != "true" and r["responseCode"] != "429") - cascade
        ok_el = [int(r["elapsed"]) for r in rs if r["success"] == "true"]
        limit = next((v for k, v in LIMITS.items() if label.startswith(k)), None)
        p95 = pct(ok_el or el, 0.95)
        out["labels"][label] = {
            "n": len(rs), "p50": pct(ok_el or el, 0.50), "p95": p95, "mean": round(statistics.fmean(el), 1),
            "max": max(el), "http_429": n429, "http_5xx": n5xx, "app_errors": other_err, "script_cascade_404": cascade,
            "error_rate": round(other_err / len(rs), 4), "limit_ms": limit,
            "meets_limit": (p95 <= limit) if limit else None,
        }
    tot = out["labels"]
    http = [r for r in rows if r["label"].startswith(("READ_", "WRITE_", "AUTH_"))]
    out["throughput_rps"] = round(len(http) / out["duration_s"], 2)
    out["http_429"] = sum(v["http_429"] for v in tot.values())
    out["http_5xx"] = sum(v["http_5xx"] for v in tot.values())
    out["app_errors"] = sum(v["app_errors"] for v in tot.values())
    out["script_cascade_404"] = sum(v["script_cascade_404"] for v in tot.values())
    out["login_blocked_vus"] = len(blocked)
    out["error_rate"] = round(out["app_errors"] / max(1, len(http)), 4)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jtl")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    s = summarize(a.jtl)
    print(f"Thời lượng {s['duration_s']} s, {s['samples']} mẫu, {s['throughput_rps']} req/s, "
          f"lỗi ứng dụng {s['app_errors']} ({s['error_rate']:.2%}), 429: {s['http_429']}, 5xx: {s['http_5xx']}")
    print(f"{'Nhãn':22} {'n':>6} {'p50':>7} {'p95':>7} {'max':>7} {'429':>5} {'lỗi':>5}  ngưỡng")
    for k, v in s["labels"].items():
        verdict = "" if v["limit_ms"] is None else ("đạt" if v["meets_limit"] else "VƯỢT") + f" {v['limit_ms']}"
        print(f"{k:22} {v['n']:6d} {v['p50']:7.0f} {v['p95']:7.0f} {v['max']:7d} {v['http_429']:5d} {v['app_errors']:5d}  {verdict}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(s, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
