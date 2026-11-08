#!/usr/bin/env python3
"""Read-only EAS local smoke tests; no credentials and no database mutations.

Run after starting local services:
    .venv\\Scripts\\python.exe scripts\\system_smoke_local.py
Options: --frontend-port 5173 --admin-port 8081 --redis-port 6380

This is a reachability and UI entry-point check, NOT a substitute for
role-specific, authenticated end-to-end testing with a real database.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def probe_http(url: str, *, timeout: float = 4.0) -> tuple[int | None, bytes, dict]:
    request = Request(url, headers={"Accept": "application/json, text/html"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read(4096), dict(response.headers.items())
    except HTTPError as error:
        return error.code, error.read(4096), dict(error.headers.items())
    except (URLError, OSError, TimeoutError):
        return None, b"", {}


def probe_redis(port: int, *, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(b"*1\r\n$4\r\nPING\r\n")
            return conn.recv(128).startswith(b"+PONG")
    except (OSError, TimeoutError):
        return False


def classify_http(name: str, status: int | None, data: bytes, headers: dict) -> tuple[str, str]:
    if status is None:
        return "FAIL", f"{name}: unreachable, verify server/port"
    if status == 429:
        delay = headers.get("Retry-After") or headers.get("Retry-after") or "unknown"
        return "WARN", f"{name}: HTTP 429 rate limited, Retry-After={delay}s"
    if name == "Backend readiness":
        try:
            body = json.loads(data)
        except (UnicodeError, ValueError):
            body = {}
        if status == 200 and body.get("status") in ("ready", "ok"):
            return "PASS", f"{name}: ready"
        return "WARN", f"{name}: HTTP {status}, inspect readiness checks"
    if name == "Backend auth/CSRF":
        if status == 200:
            return "PASS", f"{name}: HTTP 200"
        return "FAIL", f"{name}: HTTP {status}, inspect backend logs"
    if name in {"Employee UI", "Admin UI"}:
        if status == 200 and b"<html" in data.lower():
            return "PASS", f"{name}: page available (UI interactions not verified)"
        return "FAIL", f"{name}: HTTP {status}, missing HTML entry point"
    if status == 200:
        return "PASS", f"{name}: HTTP 200"
    return "FAIL", f"{name}: HTTP {status}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--admin-port", type=int, default=8081)
    parser.add_argument("--redis-port", type=int, default=6380)
    args = parser.parse_args(argv)
    urls = [
        ("Backend liveness", "http://127.0.0.1:8000/health/live"),
        ("Backend readiness", "http://127.0.0.1:8000/health/ready"),
        ("Backend auth/CSRF", "http://127.0.0.1:8000/api/v1/auth/csrf"),
        ("AI Service", "http://127.0.0.1:8001/health"),
        ("Employee UI", f"http://127.0.0.1:{args.frontend_port}/"),
        ("Admin UI", f"http://127.0.0.1:{args.admin_port}/"),
    ]
    results = []
    print("EAS local smoke checks (read-only, no credentials):")
    for name, url in urls:
        status, data, headers = probe_http(url)
        result = classify_http(name, status, data, headers)
        results.append(result)
        print(f"[{result[0]}] {result[1]}")
    redis_ok = probe_redis(args.redis_port)
    results.append(("PASS" if redis_ok else "FAIL", "Redis PING"))
    print(f"[{'PASS' if redis_ok else 'FAIL'}] Redis localhost:{args.redis_port}: {'PONG' if redis_ok else 'unreachable'}")
    totals = {level: sum(status == level for status, _ in results) for level in ("PASS", "WARN", "FAIL")}
    print("TOTAL:", totals, "(authenticated E2E still requires a live environment)")
    return 1 if totals["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
