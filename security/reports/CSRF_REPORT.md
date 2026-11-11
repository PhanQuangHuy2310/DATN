# Cross-Site Request Forgery Security Report

## Status: PASS

Trạng thái trước khắc phục: **CRITICAL (code chết)**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [CSRF_PLAN.md](../plans/CSRF_PLAN.md).

## Findings

- `CsrfViewMiddleware` bật; SPA gửi `X-CSRFToken` từ cookie `csrftoken` (`web_client/src/api.js:44`).
- Cookie session `eas_session`: `HttpOnly`, `SameSite=Lax`, `Secure` khi production. Cookie `csrftoken`: `SameSite=Lax`, `Secure` khi production (không HttpOnly — cần thiết để SPA đọc).
- Thử nghiệm: `POST /api/v1/auth/logout` với `Origin: https://evil.example` và không token → 403.
- Route GET không đổi trạng thái nghiệp vụ. `GET /attachments/{id}/download` chỉ ghi nhật ký audit (append-only).
- `@csrf_exempt` chỉ xuất hiện ở `policy_views.py` (code chết, xem AUTH_MIDDLEWARE).

## What's at risk

Như AUTH_MIDDLEWARE: nếu file chết được nối route, form cross-site có thể bật bảo trì hoặc nạp quy chế.

## What's already secure

Middleware CSRF toàn cục, cookie SameSite=Lax, POST cross-origin bị từ chối, test `test_login_requires_csrf_in_real_client_mode`.

## Recommendations

Xoá code `csrf_exempt` chết.

## Verification results

- [x] Cookie session có SameSite=Lax
- [x] Endpoint đổi trạng thái kiểm tra CSRF token
- [x] Không route GET nào đổi trạng thái nghiệp vụ
- [x] Mọi cookie phiên có HttpOnly + SameSite; Secure ở production
- [x] POST cross-origin bị từ chối (curl → 403)
