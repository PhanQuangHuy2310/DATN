"""PERF-05 (Bảng 3.17): đo độ trễ ĐẦU–CUỐI của phân loại AI qua Nginx → API Core → dịch vụ AI.

  python ai_classify_e2e.py --email <tài khoản> --password <mk> [--base http://127.0.0.1:8080] [--n 200 --warmup 20]

Đo cùng lúc tầng T3 (gọi thẳng dịch vụ AI) để tách phần chênh do Nginx + API Core.
Chỉ dùng trên môi trường kiểm thử.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import statistics
import time
import urllib.request

TEXTS = ["Xin nghỉ phép 2 ngày về quê", "Cấp quyền truy cập hệ thống CRM", "Đề nghị mua màn hình Dell 27 inch",
         "Đặt phòng họp tầng 5 chiều mai", "Tạm ứng 25 triệu tổ chức hội thảo", "Máy in tầng 3 bị kẹt giấy"]


def pct(v, q):
    s = sorted(v)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--ai", default="http://127.0.0.1:8001")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdr = {"Origin": a.base, "Referer": a.base + "/", "Content-Type": "application/json"}
    op.open(urllib.request.Request(a.base + "/api/v1/auth/csrf", headers=hdr))
    csrf = next(c.value for c in jar if c.name == "csrftoken")
    hdr["X-CSRFToken"] = csrf
    op.open(urllib.request.Request(a.base + "/api/v1/auth/login", method="POST", headers=hdr,
                                   data=json.dumps({"email": a.email, "password": a.password, "portal": "client"}).encode()))
    secret = os.getenv("INTERNAL_API_SECRET", "")

    def e2e(i):
        body = json.dumps({"title": TEXTS[i % len(TEXTS)], "description": ""}).encode()
        t = time.perf_counter()
        with op.open(urllib.request.Request(a.base + "/api/v1/ai/classify", method="POST", headers=hdr, data=body), timeout=30) as r:
            r.read()
            code = r.status
        return (time.perf_counter() - t) * 1000, code

    def direct(i):
        body = json.dumps({"title": TEXTS[i % len(TEXTS)], "description": ""}).encode()
        t = time.perf_counter()
        with urllib.request.urlopen(urllib.request.Request(
                a.ai + "/ai/classify/request", method="POST", data=body,
                headers={"Content-Type": "application/json", "X-Internal-Secret": secret}), timeout=30) as r:
            r.read()
        return (time.perf_counter() - t) * 1000

    for i in range(a.warmup):
        e2e(i)
    lat, codes = [], []
    for i in range(a.n):
        ms, c = e2e(i)
        lat.append(ms)
        codes.append(c)
        time.sleep(0.06)  # dưới giới hạn 20 req/s mỗi IP của Nginx cổng nhân viên
    d = [direct(i) for i in range(a.n)] if secret else []
    res = {"n": a.n, "http_200": codes.count(200),
           "e2e": {"p50": pct(lat, .5), "p95": pct(lat, .95), "max": max(lat), "mean": statistics.fmean(lat)},
           "direct_ai": ({"p50": pct(d, .5), "p95": pct(d, .95)} if d else None)}
    print(json.dumps(res, indent=1))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as handle:
            json.dump(res, handle, indent=1)


if __name__ == "__main__":
    main()
