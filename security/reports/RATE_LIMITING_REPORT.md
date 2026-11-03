# Rate Limiting Security Report

## Status: PASS

Trạng thái trước khắc phục: **MEDIUM**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [RATE_LIMITING_PLAN.md](../plans/RATE_LIMITING_PLAN.md).

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
