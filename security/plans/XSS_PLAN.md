# Cross-Site Scripting Fix Plan

Báo cáo: [XSS_REPORT.md](../reports/XSS_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `api_core/workflow/views.py` — `content_disposition_header(True, filename)` (RFC 6266, `filename*=utf-8''...`); `image/svg+xml` → `application/octet-stream`.

## New files

- `api_core/tests/test_attachment_download_headers.py` (mới).

## Verification goals

- [x] Không có sink HTML với dữ liệu người dùng
- [x] Không cần DOMPurify (không render HTML thô)
- [x] Server không render template (JSON) — autoescape không áp dụng
- [x] `Content-Disposition` mã hoá đúng tên tiếng Việt và ký tự `"`

## Manual verification (for the human)

- Tải một tệp có tên tiếng Việt có dấu; tên lưu xuống phải giữ nguyên dấu.
