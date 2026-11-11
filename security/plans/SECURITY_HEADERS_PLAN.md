# Security Headers Fix Plan

Báo cáo: [SECURITY_HEADERS_REPORT.md](../reports/SECURITY_HEADERS_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `web_client/nginx.conf` — `server_tokens off`; HSTS `max-age=31536000; includeSubDomains`; `Permissions-Policy`; CSP `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`.
- `api_core/middleware.py` — CSP API `default-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`.
- `api_gateway/nginx.conf` — CSP JSON tương tự + HSTS.

## New files

- Cập nhật `api_core/tests/test_security_middleware.py` (kiểm tra 5 directive, không còn `127.0.0.1`).

## Verification goals

- [x] Đủ 5 header trên mọi response kể cả asset tĩnh (curl `/` và `/assets/*.js`)
- [x] Header đặt global (middleware Django + `add_header` cấp server nginx)
- [x] CSP có `default-src`, `script-src`, `object-src 'none'`, `base-uri`, `form-action`, `frame-ancestors`
- [x] `script-src` không `unsafe-inline`/`unsafe-eval`/`*`
- [x] HSTS `max-age>=31536000; includeSubDomains`
- [x] Scan lại: 0 FAIL, 0 WARN trên nginx
- [ ] Không lỗi CSP trong console trên các trang chính — cần kiểm tra thủ công

## Manual verification (for the human)

- Mở web_client qua nginx (`docker compose up web`), duyệt đăng nhập, danh sách, chi tiết, sơ đồ quy trình; DevTools Console không có lỗi `Content-Security-Policy`.
- Sau khi có domain HTTPS: chạy `check.py https://<domain>` để xác nhận HSTS (scanner bỏ qua HSTS với localhost). `preload` chỉ thêm khi mọi subdomain đều HTTPS.
