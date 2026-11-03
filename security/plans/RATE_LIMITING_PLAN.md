# Rate Limiting Fix Plan

Báo cáo: [RATE_LIMITING_REPORT.md](../reports/RATE_LIMITING_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `api_core/authn/views.py` — `password()`: kiểm `is_throttled` trước, ghi `register_login_failure` khi `INVALID_CURRENT_PASSWORD`, trả 429 `PASSWORD_CHANGE_RATE_LIMITED`; thành công thì xoá đếm tài khoản.
- `api_core/authn/views.py` — `password_reset_request` dùng `client_ip(request)`.
- `web_client/src/domain.js` — thông điệp tiếng Việt cho `PASSWORD_CHANGE_RATE_LIMITED`.

## New files

- Test `CredentialHardeningTests.test_wrong_current_password_is_rate_limited` (401, 401, 429; handler chỉ chạy 2 lần).

## Verification goals

- [x] Login, reset mật khẩu, đổi mật khẩu có rate limit (EAS không có đăng ký công khai)
- [x] Chặn sau N lần sai trong cửa sổ thời gian (5/15 phút theo tài khoản, 30/15 phút theo IP)
- [x] Không bypass được bằng giả `X-Forwarded-For`
- [x] Bị giới hạn trả 429

## Manual verification (for the human)

- Production phải đặt `EAS_TRUST_PROXY_HEADERS=true` khi chạy sau nginx, nếu không mọi người dùng chung một IP và bị khóa cùng nhau.
