# File Uploads Security Report

## Status: PASS

Trạng thái trước khắc phục: **LOW**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [FILE_UPLOADS_PLAN.md](../plans/FILE_UPLOADS_PLAN.md).

## Findings

- `POST /requests/{id}/attachments`, `/execution/attachments`: đọc tối đa `10MB + 1` byte (`uploaded.read(10 * 1024 * 1024 + 1)`) rồi từ chối nếu vượt; nginx `client_max_body_size 10m`.
- Kiểu tệp theo **magic bytes** (`storage.sniff_allowed_mime`): chỉ `%PDF-`, PNG, JPEG.
- Tên lưu `requests/{request_id}/{uuid4}.{ext}`; tên gốc chỉ lưu metadata, cấm `/`, `\`, `..`, tối đa 150 ký tự.
- Lưu ở bucket Supabase private `eas-private` (khác origin ứng dụng), tải qua backend có kiểm quyền.
- ClamAV `INSTREAM`; lỗi kết nối → `MALWARE_SCANNER_UNAVAILABLE` (fail-closed), chỉ bỏ qua khi `development` **và** `EAS_REQUIRE_STORAGE=false`. Tải xuống yêu cầu `scan_state='CLEAN'`.
- LOW: SVG chưa có trong danh sách hạ kiểu khi tải (xem XSS).

## What's at risk

Thấp.

## What's already secure

Toàn bộ nêu trên.

## Recommendations

Hạ `image/svg+xml` về octet-stream khi tải (đã làm cùng XSS).

## Verification results

- [x] Kiểu tệp theo magic bytes
- [x] Đổi tên UUID phía server
- [x] Lưu ở bucket riêng
- [x] Giới hạn kích thước phía server
