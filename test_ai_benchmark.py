r"""Live functional test of the running AI service (all endpoints).

Needs the AI service running (start_ai_local.cmd or Docker) and the repository
.env (INTERNAL_API_SECRET). Read-only: it never loads a regulation
(POST /ai/policy/rules) and never touches the database.

    .\.venv\Scripts\python.exe test_ai_benchmark.py
    set EAS_AI_SERVICE_URL=http://127.0.0.1:8001 & ... (default)

Exit code 0 only when every check passes.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_env import load_project_env

load_project_env()

ROOT = Path(__file__).resolve().parent
AI_BASE = os.getenv("EAS_AI_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
API_BASE = os.getenv("EAS_API_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
SECRET = os.getenv("INTERNAL_API_SECRET") or os.getenv("EAS_AI_INTERNAL_SECRET", "")
AUTH = {"X-Internal-Secret": SECRET}
EVAL_PATH = ROOT / "ai_service" / "training" / "data" / "request_eval_realistic.json"
EVAL_SHORT_PATH = ROOT / "ai_service" / "training" / "data" / "request_eval_short.json"
OCR_DIR = ROOT / "tests" / "ocr_smoke"

# Acceptance thresholds on the hand-written test splits (never used for training).
MIN_TEST_TOP1 = 0.90
MIN_TEST_TOP3 = 0.97
# The web form switches automatically from this confidence (web_client/src/aiTypeSwitch.js).
AUTO_SWITCH_CONFIDENCE = 0.6


@dataclass
class Check:
    group: str
    name: str
    passed: bool
    detail: str
    latency_ms: float = 0.0


RESULTS: list[Check] = []


def record(group: str, name: str, passed: bool, detail: str, latency: float = 0.0) -> None:
    RESULTS.append(Check(group, name, bool(passed), detail, latency))


def call(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 60,
) -> tuple[int, Any, float]:
    data = body if body is not None else (json.dumps(payload).encode() if payload is not None else None)
    req_headers = {"Content-Type": "application/json"} if body is None else {}
    req_headers.update(headers or {})
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {"error": raw[:200]}
        return error.code, parsed, (time.perf_counter() - started) * 1000
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, {"error": str(error)}, (time.perf_counter() - started) * 1000


# ---------------------------------------------------------------------------
# 1. Health and internal authentication
# ---------------------------------------------------------------------------
def check_health_and_auth() -> bool:
    status, data, ms = call("GET", f"{AI_BASE}/health")
    record("1. Health/Auth", "GET /health", status == 200, f"HTTP {status} {data}", ms)
    if status != 200:
        return False
    body = {"title": "Xin nghỉ phép 1 ngày", "description": ""}
    status, _, ms = call("POST", f"{AI_BASE}/ai/classify/request", body)
    record("1. Health/Auth", "No secret is rejected", status == 401, f"HTTP {status}", ms)
    status, _, ms = call("POST", f"{AI_BASE}/ai/classify/request", body, {"X-Internal-Secret": "wrong"})
    record("1. Health/Auth", "Wrong secret is rejected", status == 401, f"HTTP {status}", ms)
    return True


# ---------------------------------------------------------------------------
# 2. Request classification (58 catalog v2 types)
# ---------------------------------------------------------------------------
def check_classifier() -> None:
    group = "2. Classify"
    latencies: list[float] = []
    for path, label in ((EVAL_PATH, "Hand-written"), (EVAL_SHORT_PATH, "Very short (2-8 words)")):
        _score_eval_file(group, path, label, latencies)
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    record(group, "Latency p95 < 300 ms", p95 < 300, f"p95 {p95:.0f} ms over {len(latencies)} calls")

    for text in ("bố mất", "bo mat", "mẹ em qua đời", "đám cưới của em"):
        _status, data, ms = call("POST", f"{AI_BASE}/ai/classify/request", {"title": text, "description": ""}, AUTH)
        conf = data.get("confidence_request_type") or 0
        runner_up = max([a.get("confidence") or 0 for a in data.get("alternatives") or []
                         if a.get("request_type") != data.get("predicted_request_type")] or [0])
        # Same rule as web_client/src/aiTypeSwitch.js
        sure = conf >= AUTO_SWITCH_CONFIDENCE or (conf >= 0.35 and conf >= 3 * runner_up)
        record(group, f"'{text}' → LEAVE_SPECIAL, sure enough to switch the form",
               data.get("predicted_request_type") == "LEAVE_SPECIAL" and sure,
               f"got {data.get('predicted_request_type')} conf={conf} runner-up={runner_up}", ms)
    _classifier_contract_checks(group)


def _score_eval_file(group: str, path: Path, label: str, latencies: list[float]) -> None:
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    for split in ("dev", "test"):
        subset = [i for i in items if i["split"] == split]
        top1 = top3 = 0
        misses: list[str] = []
        for item in subset:
            status, data, ms = call(
                "POST",
                f"{AI_BASE}/ai/classify/request",
                {"title": item["title"], "description": item.get("description") or ""},
                AUTH,
            )
            latencies.append(ms)
            predicted = data.get("predicted_request_type") if status == 200 else None
            ranked = [predicted] + [a.get("request_type") for a in data.get("alternatives") or []]
            top1 += predicted == item["label"]
            top3 += item["label"] in ranked[:3]
            if predicted != item["label"]:
                misses.append(f"{item['title'][:48]!r}: {item['label']} → {predicted}")
        n = len(subset)
        detail = f"top-1 {top1}/{n} = {top1 / n:.1%}, top-3 {top3 / n:.1%}"
        if split == "test":
            record(group, f"{label} TEST split ({n})", top1 / n >= MIN_TEST_TOP1 and top3 / n >= MIN_TEST_TOP3,
                   f"{detail} (need ≥{MIN_TEST_TOP1:.0%} / ≥{MIN_TEST_TOP3:.0%})")
            for miss in misses:
                print(f"      sai: {miss}")
        else:
            record(group, f"{label} DEV split ({n})", top1 / n >= 0.95, detail)


def _classifier_contract_checks(group: str) -> None:
    status, data, ms = call("POST", f"{AI_BASE}/ai/classify/request",
                            {"title": "Xin nghỉ phép 2 ngày về quê", "description": ""}, AUTH)
    fields = {"predicted_request_type", "predicted_request_name", "predicted_category", "predicted_department",
              "predicted_template", "confidence_request_type", "low_confidence", "alternatives", "method"}
    record(group, "Response has the catalog v2 fields", status == 200 and fields <= set(data),
           f"missing {sorted(fields - set(data))}" if status == 200 else f"HTTP {status}", ms)
    record(group, "Uses the trained model (not keyword fallback)",
           data.get("method") == "nlp_model" and not data.get("fallback_used"), f"method={data.get('method')}")

    status, data, ms = call("POST", f"{AI_BASE}/ai/classify/request",
                            {"title": "abc xyz qwe", "description": ""}, AUTH)
    record(group, "Gibberish is flagged low confidence", status == 200 and data.get("low_confidence") is True,
           f"type={data.get('predicted_request_type')} conf={data.get('confidence_request_type')}", ms)

    status, data, ms = call("POST", f"{AI_BASE}/ai/classify/request",
                            {"title": "Tạm ứng 75 triệu đặt cọc gian hàng hội chợ", "description": ""}, AUTH)
    record(group, "Advance tier follows the amount (75tr → LARGE)",
           data.get("predicted_request_type") == "ADVANCE_LARGE", f"got {data.get('predicted_request_type')}", ms)

    status, data, ms = call("POST", f"{AI_BASE}/ai/classify/classify",
                            {"title": "Đặt phòng họp tầng 5 chiều mai", "description": ""}, AUTH)
    record(group, "Legacy endpoint /ai/classify/classify", status == 200 and data.get("predicted_request_type") == "ROOM_BOOKING",
           f"HTTP {status} {data.get('predicted_request_type')}", ms)

    status, _, ms = call("POST", f"{AI_BASE}/ai/classify/request", {"description": "thiếu tiêu đề"}, AUTH)
    record(group, "Missing title → 422", status == 422, f"HTTP {status}", ms)


# ---------------------------------------------------------------------------
# 3. Risk scoring (XGBoost master + finance/hr/it)
# ---------------------------------------------------------------------------
def check_risk() -> None:
    group = "3. Risk"
    cases = [
        ("Nghỉ phép thường (HR) → thấp, đủ điều kiện tự duyệt",
         {"request_type": "LEAVE", "lifecycle_template": "A", "risk_weight": 1, "department": "TECH"},
         lambda d: d["risk_score"] <= 2 and d["auto_approve_eligible"] is True and d["domain_model_used"] == "hr"),
        ("Tạm ứng vượt ngân sách còn lại → 5",
         {"request_type": "ADVANCE_LARGE", "lifecycle_template": "B", "risk_weight": 4, "department": "SALES",
          "amount_vnd": 300_000_000, "budget_remaining_vnd": 100_000_000, "has_receipt": 0},
         lambda d: d["risk_score"] == 5 and d["auto_approve_eligible"] is False and d["domain_model_used"] == "finance"),
        ("Nghi chia nhỏ khoản chi → ≥ 4",
         {"request_type": "EXPENSE_CLAIM", "lifecycle_template": "B", "risk_weight": 2, "department": "SALES",
          "amount_vnd": 9_500_000, "budget_remaining_vnd": 200_000_000, "is_split_amount_suspect": 1},
         lambda d: d["risk_score"] >= 4 and d["auto_approve_eligible"] is False),
        ("Cấp quyền production ngoài giờ (IT) → ≥ 4",
         {"request_type": "PROD_DATA_ACCESS", "lifecycle_template": "C", "risk_weight": 4, "department": "TECH",
          "is_off_hours": 1, "user_tenure_months": 1},
         lambda d: d["risk_score"] >= 4 and d["domain_model_used"] == "it"),
        ("Đặt phòng họp → thấp",
         {"request_type": "ROOM_BOOKING", "lifecycle_template": "A", "risk_weight": 1, "department": "TECH"},
         lambda d: d["risk_score"] <= 2),
        ("Mã cũ leave_annual vẫn được hiểu (→ LEAVE, HR)",
         {"request_type": "leave_annual", "lifecycle_template": "A", "risk_weight": 1, "department": "TECH"},
         lambda d: d["risk_score"] <= 2 and d["domain_model_used"] == "hr"),
    ]
    for name, payload, ok in cases:
        status, data, ms = call("POST", f"{AI_BASE}/ai/risk/score", payload, AUTH)
        passed = status == 200 and not data.get("fallback_used") and ok(data)
        record(group, name, passed,
               f"HTTP {status} score={data.get('risk_score')} ({data.get('risk_label')}) "
               f"model={data.get('domain_model_used')} eligible={data.get('auto_approve_eligible')}", ms)
    status, _, ms = call("POST", f"{AI_BASE}/ai/risk/score", {"request_type": "LEAVE", "risk_weight": 9}, AUTH)
    record(group, "risk_weight ngoài 1..5 → 422", status == 422, f"HTTP {status}", ms)


# ---------------------------------------------------------------------------
# 4. Auto-approve rules (catalog v2 codes, as sent by the API)
# ---------------------------------------------------------------------------
def check_auto_approve() -> None:
    group = "4. Auto-approve"
    base = {"lifecycle_template": "A", "risk_score": 1, "requester_name": "Kiểm thử", "requester_dept": "TECH"}
    cases = [
        ("LEAVE 2 ngày, còn 10 ngày phép → tự duyệt",
         {"request_type": "LEAVE", "days_requested": 2, "leave_balance_remaining": 10}, "auto_approve"),
        ("LEAVE 2 ngày, chỉ còn 1 ngày phép → người duyệt",
         {"request_type": "LEAVE", "days_requested": 2, "leave_balance_remaining": 1}, "escalate_to_human"),
        ("LEAVE 5 ngày (≥ 3) → người duyệt",
         {"request_type": "LEAVE", "days_requested": 5, "leave_balance_remaining": 12}, "escalate_to_human"),
        ("ROOM_BOOKING phòng trống → tự duyệt",
         {"request_type": "ROOM_BOOKING", "room_available": True}, "auto_approve"),
        ("ROOM_BOOKING phòng đã có người đặt → người duyệt",
         {"request_type": "ROOM_BOOKING", "room_available": False}, "escalate_to_human"),
        ("REFUND_COMPENSATION 1,5 triệu → tự duyệt",
         {"request_type": "REFUND_COMPENSATION", "risk_score": 2, "amount": 1_500_000}, "auto_approve"),
        ("REFUND_COMPENSATION 5 triệu (> 2 triệu) → người duyệt",
         {"request_type": "REFUND_COMPENSATION", "risk_score": 2, "amount": 5_000_000}, "escalate_to_human"),
        ("Template B → người duyệt",
         {"request_type": "WFH_REQ", "lifecycle_template": "B"}, "escalate_to_human"),
        ("Rủi ro 4 → người duyệt",
         {"request_type": "WFH_REQ", "risk_score": 4}, "escalate_to_human"),
    ]
    for name, override, expected in cases:
        payload = {**base, "request_id": str(uuid.uuid4()), **override}
        status, data, ms = call("POST", f"{AI_BASE}/ai/auto-approve/evaluate", payload, AUTH)
        reasons = " | ".join(r for r in data.get("detail_reasons") or [] if "❌" in r)[:120]
        record(group, name, status == 200 and data.get("decision") == expected,
               f"HTTP {status} {data.get('decision')} {reasons}", ms)


# ---------------------------------------------------------------------------
# 5. Summary, OCR, regulation and external-system context
# ---------------------------------------------------------------------------
def check_summarize() -> None:
    payload = {
        "title": "Đề nghị tạm ứng 45 triệu tổ chức hội nghị khách hàng",
        "description": "Hội nghị 120 khách tại khách sạn, chi phí thuê hội trường, ăn uống và quà tặng. Cần chuyển khoản đặt cọc trước ngày 20.",
        "request_type": "ADVANCE_MEDIUM",
        "requester_name": "Kiểm thử",
        "risk_score": 3,
        "amount": 45_000_000,
    }
    status, data, ms = call("POST", f"{AI_BASE}/ai/summarize/request", payload, AUTH, timeout=90)
    record("5. Summarize", "Tóm tắt yêu cầu", status == 200 and bool(data.get("summary"))
           and data.get("sentiment") in {"normal", "urgent", "high_risk"},
           f"HTTP {status} sentiment={data.get('sentiment')} len={len(data.get('summary') or '')}", ms)


def _multipart(field: str, filename: str, content: bytes, mime: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode()
    return head + content + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def check_ocr() -> None:
    expected = json.loads((OCR_DIR / "expected.json").read_text(encoding="utf-8"))
    for filename, want in expected.items():
        body, content_type = _multipart("file", filename, (OCR_DIR / filename).read_bytes(), "image/png")
        status, data, ms = call("POST", f"{AI_BASE}/ai/ocr/extract", body=body,
                                headers={**AUTH, "Content-Type": content_type}, timeout=180)
        fields = data.get("extracted_fields") or {}
        amount_ok = fields.get("amount") is not None and abs(float(fields["amount"]) - want["amount"]) < 1
        date_ok = str(fields.get("invoice_date") or "")[:10] == want["invoice_date"]
        record("6. OCR", f"Hóa đơn {filename}", status == 200 and amount_ok and date_ok,
               f"HTTP {status} engine={data.get('engine')} amount={fields.get('amount')} date={fields.get('invoice_date')}", ms)
    status, _, ms = call("POST", f"{AI_BASE}/ai/ocr/extract-url", {"image_url": "http://127.0.0.1/x.png"}, AUTH)
    record("6. OCR", "URL nội bộ bị chặn (SSRF)", status in {400, 422}, f"HTTP {status}", ms)


def check_policy_and_context() -> None:
    status, data, ms = call("GET", f"{AI_BASE}/ai/policy/rules", headers=AUTH)
    record("7. Policy/Context", "GET /ai/policy/rules", status == 200 and "rules" in data,
           f"HTTP {status} version={data.get('version')} rules={len(data.get('rules') or [])}", ms)
    for path in ("leave-balance?employee=khong.ton.tai%40eas.com", "facility-status?resource=KHONG_TON_TAI"):
        status, _, ms = call("GET", f"{AI_BASE}/ai/mock/context/{path}", headers=AUTH)
        record("7. Policy/Context", f"GET {path.split('?')[0]} (không có dữ liệu → 404)", status in {200, 404},
               f"HTTP {status}", ms)


def check_api_proxy() -> None:
    status, _, ms = call("POST", f"{API_BASE}/api/v1/ai/classify", {"title": "Xin nghỉ phép"})
    record("8. API", "API core bảo vệ route AI (chưa đăng nhập)", status in {401, 403}, f"HTTP {status}", ms)


def main() -> int:
    print(f"AI service: {AI_BASE}  |  API: {API_BASE}")
    if not SECRET:
        print("Thiếu INTERNAL_API_SECRET trong .env")
        return 2
    if check_health_and_auth():
        check_classifier()
        check_risk()
        check_auto_approve()
        check_summarize()
        check_ocr()
        check_policy_and_context()
        check_api_proxy()
    width = max(len(r.name) for r in RESULTS)
    group = None
    for r in RESULTS:
        if r.group != group:
            group = r.group
            print(f"\n{group}")
        print(f"  {'ĐẠT ' if r.passed else 'TRƯỢT'} {r.name:<{width}}  {r.detail}"
              + (f"  [{r.latency_ms:.0f} ms]" if r.latency_ms else ""))
    passed = sum(r.passed for r in RESULTS)
    print(f"\nKẾT QUẢ: {passed}/{len(RESULTS)} kiểm tra đạt")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
