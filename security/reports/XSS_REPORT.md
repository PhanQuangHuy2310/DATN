# Cross-Site Scripting Security Report

## Status: PASS

Trạng thái trước khắc phục: **LOW**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [XSS_PLAN.md](../plans/XSS_PLAN.md).

## Findings

- Frontend React: không `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function`, URL `javascript:`. `href` động chỉ ghép UUID từ server (`/api/v1/attachments/{id}/download`) hoặc ảnh tĩnh.
- Django không render template; mọi response là JSON.
- **LOW:** `attachment_download` dựng `Content-Disposition` bằng f-string: tên file chứa `"` phá vỡ trích dẫn; tên tiếng Việt bị mã hoá MIME mà trình duyệt không hiểu.
- Tệp tải xuống: `text/html`, `application/xhtml+xml`, `text/xml` bị hạ về `application/octet-stream`, nhưng **`image/svg+xml` chưa có** trong danh sách.

## What's at risk

Thấp: magic bytes chỉ cho PDF/PNG/JPEG nên SVG thực tế không lọt vào kho; header vẫn được củng cố cho lớp phòng thủ thứ hai.

## What's already secure

React escape mặc định; response tải xuống có `Content-Security-Policy: default-src 'none'`, `nosniff`, `attachment`.

## Recommendations

Dùng `content_disposition_header()` của Django; thêm SVG vào danh sách hạ cấp.

## Verification results

- [x] Không có sink HTML với dữ liệu người dùng
- [x] Không cần DOMPurify (không render HTML thô)
- [x] Server không render template (JSON) — autoescape không áp dụng
- [x] `Content-Disposition` mã hoá đúng tên tiếng Việt và ký tự `"`
