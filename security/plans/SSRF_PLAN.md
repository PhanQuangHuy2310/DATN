# Server-Side Request Forgery Fix Plan

Báo cáo: [SSRF_REPORT.md](../reports/SSRF_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `ai_service/routers/ocr.py` — `if not ip.is_global or ip.is_multicast: reject` (bao gồm private, loopback, link-local/metadata, CGNAT, unspecified, IPv4-mapped).

## New files

- Thêm 4 URL vào `tests/integration/test_ai_service.py::test_anti_ssrf_validation`: `100.64.0.1`, `0.0.0.0`, `[::ffff:127.0.0.1]`, `[::1]`.

## Verification goals

- [x] Mọi URL người dùng được kiểm tra trước khi tải
- [x] Chặn 127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1 (và thêm CGNAT, mapped IPv6)
- [x] Chỉ cho http/https
- [x] Phân giải hostname và kiểm tra IP trước khi gọi
- [ ] Chống DNS rebinding bằng ghim IP — chưa làm, ghi nhận rủi ro còn lại

## Manual verification (for the human)

- Không cần thao tác thủ công trừ khi `/ai/ocr/extract-url` được mở cho người dùng cuối; khi đó phải ghim kết nối vào IP đã kiểm tra.
