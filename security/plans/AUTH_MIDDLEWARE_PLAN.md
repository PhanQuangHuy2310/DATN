# Auth Middleware Fix Plan

Báo cáo: [AUTH_MIDDLEWARE_REPORT.md](../reports/AUTH_MIDDLEWARE_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- Xoá `api_core/workflow/policy_views.py`, `api_core/workflow/maintenance.py`.
- `api_core/workflow/views.py` — `admin_events_view` dùng `@require_actor("AUDITOR", "POLICY_ADMIN", "OPS_ADMIN")`.
- `api_core/workflow/reporting.py` — `list_admin_events` bỏ truy vấn `EXISTS` trùng (dùng `actor.roles`, cùng vị từ hiệu lực), vẫn giữ lọc phạm vi bản ghi trong SQL.

## New files

- Test `AdminEventsRoleGateTests` (`api_core/tests/test_role_scope_alignment.py`).

## Verification goals

- [x] Mọi route trả/sửa dữ liệu người dùng có xác thực
- [x] Xác thực chạy trong decorator trước handler
- [x] Request không xác thực → 401 (test hiện có trong `test_authn.py`, `test_workflow_api.py`)
- [x] Non-admin gọi route admin → 403 (thêm test admin-events, handler không bị gọi)
- [x] Không còn view `csrf_exempt` không xác thực trong mã nguồn (`git grep csrf_exempt` = 0)

## Manual verification (for the human)

- Đăng nhập bằng tài khoản REQUESTER, mở `/api/v1/admin-events` và `/api/v1/admin/users` trên trình duyệt: phải nhận 403.
