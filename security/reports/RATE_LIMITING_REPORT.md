# Rate Limiting Security Report

## Status: PASS

Trạng thái trước khắc phục: **MEDIUM**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/active/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [mục Kế hoạch khắc phục](#kế-hoạch-khắc-phục).

## Findings

- Login: throttle 2 chiều (`login_throttle.py`) — tài khoản 5 lần/15 phút trên mọi IP, IP 30 lần/15 phút; trả 429 + `Retry-After`. Chỉ tin `X-Forwarded-For` khi `EAS_TRUST_PROXY_HEADERS=true`, khi đó lấy entry **cuối** (do proxy của mình thêm).
- Reset mật khẩu: cooldown 5 phút/email, 20 lần/giờ/IP, phản hồi 202 đồng nhất (không dò được email).
- Toàn API: `ApiRateLimitMiddleware` 300 request/phút/IP. Gateway: `limit_req` login 5r/m, upload 10r/m, AI 20r/m, API 60r/m.
- Production bắt buộc `REDIS_URL` nên bộ đếm dùng chung giữa các worker.
- **MEDIUM:** `POST /auth/password` không giới hạn số lần sai `current_password` → session bị đánh cắp thành công cụ dò mật khẩu.
- **LOW:** reset-request băm `REMOTE_ADDR` thay vì `client_ip()`; sau proxy mọi người dùng chung một IP, kẻ xấu làm cạn ngân sách 20 lần/giờ thì yêu cầu reset hợp lệ bị bỏ qua.

## What's at risk

Dò mật khẩu hiện tại qua phiên bị chiếm; chặn chức năng reset mật khẩu của cả công ty sau proxy.

## What's already secure

Toàn bộ cơ chế login/reset/API/gateway nêu trên; test `test_login_rate_limit_*`, `RateLimitTests`.

## Recommendations

1. Throttle đổi mật khẩu dùng chung ngân sách account+IP của login.
2. Reset dùng `client_ip()`.

## Verification results

- [x] Login, reset mật khẩu, đổi mật khẩu có rate limit (EAS không có đăng ký công khai)
- [x] Chặn sau N lần sai trong cửa sổ thời gian (5/15 phút theo tài khoản, 30/15 phút theo IP)
- [x] Không bypass được bằng giả `X-Forwarded-For`
- [x] Bị giới hạn trả 429

## Kế hoạch khắc phục

### Changes

- `api_core/authn/views.py` — `password()`: kiểm `is_throttled` trước, ghi `register_login_failure` khi `INVALID_CURRENT_PASSWORD`, trả 429 `PASSWORD_CHANGE_RATE_LIMITED`; thành công thì xoá đếm tài khoản.
- `api_core/authn/views.py` — `password_reset_request` dùng `client_ip(request)`.
- `web_client/src/domain.js` — thông điệp tiếng Việt cho `PASSWORD_CHANGE_RATE_LIMITED`.

### New files

- Test `CredentialHardeningTests.test_wrong_current_password_is_rate_limited` (401, 401, 429; handler chỉ chạy 2 lần).

### Verification goals

- [x] Login, reset mật khẩu, đổi mật khẩu có rate limit (EAS không có đăng ký công khai)
- [x] Chặn sau N lần sai trong cửa sổ thời gian (5/15 phút theo tài khoản, 30/15 phút theo IP)
- [x] Không bypass được bằng giả `X-Forwarded-For`
- [x] Bị giới hạn trả 429

### Manual verification (for the human)

- Production phải đặt `EAS_TRUST_PROXY_HEADERS=true` khi chạy sau nginx, nếu không mọi người dùng chung một IP và bị khóa cùng nhau.
