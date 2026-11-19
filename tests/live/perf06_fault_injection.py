r"""PERF-06 (Bảng 3.17): ngắt dịch vụ AI và Mock Systems trong lúc có tải nhẹ, trên BẢN SAO CSDL local.

Cần cùng biến môi trường với test_report_scenarios.py và Docker Compose project "eas".
  .venv\Scripts\python.exe tests\live\perf06_fault_injection.py --json perf06.json
Script tự bật lại các dịch vụ đã dừng (khối finally).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_report_scenarios as t


def docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    ).stdout.strip()


def wait_healthy(name: str, timeout: int = 120) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if docker("inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", name) in ("healthy", "running"):
            return
        time.sleep(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--compose-args", default="", help="tham số docker compose để bật lại tự duyệt AI (bỏ override)")
    a = ap.parse_args()
    t._guard()
    o = t.Oracle()
    out: dict = {}

    # --- 1. Dừng dịch vụ AI -------------------------------------------------------------
    docker("stop", "eas-ai-service-1")
    try:
        h = t.login(o.requester("PERF06-AI"))
        st, body = h.call("POST", "/api/v1/ai/classify", {"title": "Xin nghỉ phép 1 ngày", "description": ""})
        data = (body.get("data") or {}) if isinstance(body, dict) else {}
        err = (body.get("error") or {}) if isinstance(body, dict) else {}
        method = (f"{data.get('method') or 'không rõ phương pháp'}, đường lui {'có' if data.get('fallback_used') else 'không'}"
                  if data else (err.get("code") if isinstance(err, dict) else err))
        rid, _, _ = t.submit(o, "WFH_REQ")
        time.sleep(15)  # worker thử tự duyệt nhiều vòng
        r = o.req(rid)
        step = o.active_step(rid)
        ai_dec = o.one("""SELECT count(*) FROM eas.approval_decision d JOIN eas.app_user u ON u.id=d.actor_id
                          WHERE d.request_id=%s AND u.email LIKE 'ai.%%'""", rid)[0]
        human = step is not None and not o.email(step[2]).startswith("ai.")
        out["ai_down"] = (f"phân loại qua API → HTTP {st} ({method}); hồ sơ {r['code']} rủi ro thấp ở {r['status']}, "
                          f"bước duyệt giao cho người ({'có' if human else 'không'}), {ai_dec} quyết định của AI")
        ai_ok = st < 500 and r["status"] == "PENDING_APPROVAL" and human and ai_dec == 0
    finally:
        docker("start", "eas-ai-service-1")
        wait_healthy("eas-ai-service-1")

    # --- 2. Dừng Mock Systems ----------------------------------------------------------
    docker("stop", "eas-mock_systems-1")
    try:
        email = o.requester("PERF06-MOCK")
        h = t.login(email)
        before = o.one("SELECT count(*) FROM eas.request")[0]
        room = o.one("""SELECT resource_code FROM mock_facilities.resource WHERE resource_type ILIKE '%%ROOM%%'
                        AND availability_status ILIKE 'AVAILABLE' ORDER BY resource_code DESC LIMIT 1""")[0]
        payload = {"title": "Đặt phòng khi hệ thống tòa nhà ngừng", "booking_date": "2026-12-28", "start_time": "14:00",
                   "end_time": "15:00", "room_code": room, "attendees_count": 4, "purpose": "Kiểm thử ngắt dịch vụ"}
        st, body = h.call("POST", "/api/v1/requests/submit", {"type_code": "ROOM_BOOKING", "payload": payload})
        after = o.one("SELECT count(*) FROM eas.request")[0]
        code = (body.get("error") or {}).get("code") if isinstance(body.get("error"), dict) else body.get("error")
        out["mock_down"] = f"gửi hồ sơ đặt phòng → HTTP {st} {code}; số hồ sơ {before}→{after}"
        mock_ok = st in (409, 424, 502, 503) and after == before
    finally:
        docker("start", "eas-mock_systems-1")
        wait_healthy("eas-mock_systems-1")

    passed = ai_ok and mock_ok
    out["passed"] = passed
    out["summary"] = (f"{'PASS' if passed else 'FAIL'} (trực tiếp, {time.strftime('%d/%m/%Y')}, có tải nền 3 VU): dừng dịch vụ AI → "
                      f"{out['ai_down']}; dừng Mock Systems → {out['mock_down']}; không tạo trạng thái nửa chừng")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
