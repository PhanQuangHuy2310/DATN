# File Uploads Fix Plan

Báo cáo: [FILE_UPLOADS_REPORT.md](../reports/FILE_UPLOADS_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `api_core/workflow/views.py` — như XSS.

## New files

- `api_core/tests/test_attachment_download_headers.py`.

## Verification goals

- [x] Kiểu tệp theo magic bytes
- [x] Đổi tên UUID phía server
- [x] Lưu ở bucket riêng
- [x] Giới hạn kích thước phía server

## Manual verification (for the human)

- Tải lên một tệp `.exe` đổi đuôi thành `.pdf`: phải nhận 422 `FILE_TYPE_NOT_ALLOWED`.
