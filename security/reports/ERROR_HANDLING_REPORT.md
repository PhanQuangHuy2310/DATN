# Error Handling Security Report

## Status: PASS

Trạng thái trước khắc phục: **MEDIUM**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [ERROR_HANDLING_PLAN.md](../plans/ERROR_HANDLING_PLAN.md).

## Findings

- Django: `DEBUG` chỉ bật khi `EAS_ENV=development` **và** `DJANGO_DEBUG=true` (mặc định tắt). `ApiDatabaseErrorMiddleware.process_exception` trả mã lỗi chung cho `/api/v1/*`, log SQLSTATE + correlation ID. `str(exc)` trong view chỉ là mã lỗi nội bộ (`JsonBodyError`, `StorageError`).
- Route lạ trả trang HTML 404 mặc định của Django (không lộ stack, nhưng không phải JSON).
- ai_service:
  - `ocr.py:210` trả `"Cả PaddleOCR và Gemini Vision đều lỗi: {e}"` với HTTP 500; `ocr.py:331` trả `"Không tải được ảnh từ URL: {e}"`; `ocr.py:289` trả lỗi phân giải DNS. Nội dung exception lộ tên thư viện/host.
  - `/docs`, `/redoc`, `/openapi.json` bật ở mọi môi trường; `/metrics` công khai. Gateway chặn `/docs` từ ngoài, ai_service chỉ bind localhost → mức MEDIUM vì phụ thuộc lớp mạng.
- `/health/ready` công khai chạy 5 truy vấn DB (~2s) mỗi lần → khuếch đại tải.

## What's at risk

Thông điệp lỗi lộ thư viện/hạ tầng giúp dò tấn công; tài liệu API và metrics giúp lập bản đồ dịch vụ; health check đắt có thể bị gọi dồn dập.

## What's already secure

Middleware lỗi toàn cục của api_core; DEBUG tắt mặc định; log có lọc dữ liệu nhạy cảm.

## Recommendations

1. Lỗi OCR chung chung, chi tiết vào log.
2. Tắt docs/openapi và yêu cầu secret cho `/metrics` khi production.
3. JSON handler404/500.
4. Cache readiness.

## Verification results

- [x] Handler lỗi toàn cục bắt mọi exception (api_core middleware + handler500; FastAPI mặc định 500 chung)
- [x] Response chỉ có thông điệp chung
- [x] Chi tiết chỉ ghi log server
- [x] Không stack trace/SQL/đường dẫn trong response (curl 404, input sai)
- [x] DEBUG tắt ở production
- [x] Docs/OpenAPI/metrics trả 401/404 ở production (test subprocess)
