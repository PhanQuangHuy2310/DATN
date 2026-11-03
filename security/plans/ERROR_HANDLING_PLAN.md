# Error Handling Fix Plan

Báo cáo: [ERROR_HANDLING_REPORT.md](../reports/ERROR_HANDLING_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `ai_service/routers/ocr.py` — 502 `"Không bóc tách được nội dung ảnh."`, 400 `"Không tải được ảnh từ URL."`, 400 `"Không thể phân giải tên miền của URL."`; chi tiết ghi log.
- `ai_service/main.py` — `IS_PRODUCTION`: `docs_url`, `redoc_url`, `openapi_url` = `None`; public path production chỉ `/health`, `/`.
- `api_core/config/urls.py` — `handler404`/`handler500` trả `api_error` JSON (`RESOURCE_NOT_FOUND`, `INTERNAL_SERVER_ERROR`).
- `api_core/health/views.py` — cache kết quả ready 5 giây (chỉ khi ready, tắt khi `test`).

## New files

- `tests/test_ai_service_exposure.py` (mới); `JsonErrorHandlerTests` trong `api_core/tests/test_health.py`.

## Verification goals

- [x] Handler lỗi toàn cục bắt mọi exception (api_core middleware + handler500; FastAPI mặc định 500 chung)
- [x] Response chỉ có thông điệp chung
- [x] Chi tiết chỉ ghi log server
- [x] Không stack trace/SQL/đường dẫn trong response (curl 404, input sai)
- [x] DEBUG tắt ở production
- [x] Docs/OpenAPI/metrics trả 401/404 ở production (test subprocess)

## Manual verification (for the human)

- Không có.
