# CORS Fix Plan

Báo cáo: [CORS_REPORT.md](../reports/CORS_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `ai_service/main.py` — `allow_credentials=False`, `allow_headers=["Content-Type", "X-Internal-Secret", "X-Correlation-ID"]`.

## New files

- `tests/test_ai_service_exposure.py` kiểm tra preflight không trả `Access-Control-Allow-Credentials`.

## Verification goals

- [x] Origin là allowlist tường minh
- [x] Không wildcard trong mã và trong header thực tế
- [x] Không phản chiếu Origin ngoài allowlist
- [x] Không có credentials (đã tắt)
- [x] Method chỉ gồm những gì API dùng

## Manual verification (for the human)

- Không có.
