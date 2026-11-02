# Cross-Site Request Forgery Fix Plan

Báo cáo: [CSRF_REPORT.md](../reports/CSRF_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- Xoá `api_core/workflow/policy_views.py`, `api_core/workflow/maintenance.py`.

## New files

- Không có.

## Verification goals

- [x] Cookie session có SameSite=Lax
- [x] Endpoint đổi trạng thái kiểm tra CSRF token
- [x] Không route GET nào đổi trạng thái nghiệp vụ
- [x] Mọi cookie phiên có HttpOnly + SameSite; Secure ở production
- [x] POST cross-origin bị từ chối (curl → 403)

## Manual verification (for the human)

- Trên môi trường HTTPS production: DevTools → Application → Cookies, xác nhận `eas_session` có `Secure`, `HttpOnly`, `SameSite=Lax`.
