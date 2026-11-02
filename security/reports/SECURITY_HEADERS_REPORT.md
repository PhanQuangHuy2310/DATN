# Security Headers Security Report

## Status: PASS

Trạng thái trước khắc phục: **MEDIUM**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [SECURITY_HEADERS_PLAN.md](../plans/SECURITY_HEADERS_PLAN.md).

## Findings

Live scan (`check.py`) trên nginx cấu hình production + Django:

- **FAIL — CSP thiếu `object-src 'none'`** (`web_client/nginx.conf`).
- **WARN — lộ phiên bản** `Server: nginx/1.31.6`.
- Django `ApiSecurityHeadersMiddleware` (trước sửa):
  ```
  default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;
  connect-src 'self' http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:*;
  frame-ancestors 'none'; form-action 'self';
  ```
  Thiếu `object-src`, `base-uri`; mở `connect-src` tới localhost ở mọi môi trường.
- nginx (web, gateway) không gửi HSTS; HSTS của Django chỉ có khi production và request là HTTPS.
- Gateway (`api_gateway/nginx.conf`) không có CSP.

## What's at risk

Thiếu `object-src`/`base-uri` làm CSP yếu đi trước XSS (plugin, `<base>` hijack). Lộ phiên bản giúp dò lỗ hổng theo phiên bản. Thiếu HSTS cho phép hạ cấp HTTPS ở lần truy cập đầu.

## What's already secure

`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy` (Django), `Cross-Origin-Opener-Policy`; `script-src 'self'` không `unsafe-inline`; `add_header ... always` ở cấp server nên áp dụng cả file tĩnh.

## Recommendations

1. CSP đủ directive ở nginx.
2. CSP khóa chặt cho API JSON.
3. HSTS + ẩn phiên bản.

## Verification results

- [x] Đủ 5 header trên mọi response kể cả asset tĩnh (curl `/` và `/assets/*.js`)
- [x] Header đặt global (middleware Django + `add_header` cấp server nginx)
- [x] CSP có `default-src`, `script-src`, `object-src 'none'`, `base-uri`, `form-action`, `frame-ancestors`
- [x] `script-src` không `unsafe-inline`/`unsafe-eval`/`*`
- [x] HSTS `max-age>=31536000; includeSubDomains`
- [x] Scan lại: 0 FAIL, 0 WARN trên nginx
- [ ] Không lỗi CSP trong console trên các trang chính — cần kiểm tra thủ công
