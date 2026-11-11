# Auth Middleware Security Report

## Status: PASS

Trạng thái trước khắc phục: **CRITICAL (code chết)**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [AUTH_MIDDLEWARE_PLAN.md](../plans/AUTH_MIDDLEWARE_PLAN.md).

## Findings

Đã liệt kê toàn bộ 93 route Django qua URL resolver và decorator của từng view.

- Route nghiệp vụ (`/api/v1/requests*`, `/attachments*`, `/notifications*`, `/reports*`, `/ai/*`, `/meta/*` trừ `request-types`, `/mock/*`) đều có `@require_actor(...)` chạy trước handler. Dispatcher không decorator (`request_detail_or_patch`, `config_releases_view`, `config_release_detail_view`) đều ủy quyền cho hàm con đã có decorator.
- Admin: `/api/v1/admin/*` yêu cầu `OPS_ADMIN` rồi `authorize()` kiểm tra `scope_kind='GLOBAL' AND type_scope='ALL'`; `/config-releases*` yêu cầu `POLICY_ADMIN`; `/ops/*` yêu cầu `OPS_ADMIN`; `/password-reset/requests*` yêu cầu `OPS_ADMIN` GLOBAL.
- Công khai có chủ đích: `/`, `/health/live`, `/health/ready` (chỉ boolean), `/auth/csrf`, `/auth/login`, `/auth/password-reset/request` (phản hồi đồng nhất), `/request-types`, `/system/maintenance`.
- **CRITICAL tiềm ẩn (code chết):** `api_core/workflow/policy_views.py` có `toggle_maintenance` và `ingest_policy` được đánh dấu `@csrf_exempt`. `ingest_policy` **không xác thực**, bật chế độ bảo trì (từ chối người dùng thường), ghi file vào `ai_service/data/` và chạy `subprocess` huấn luyện lại model. `toggle_maintenance` cấp quyền theo tiền tố email (`admin`, `director`). File không được route nên hiện chưa khai thác được, nhưng chỉ cần một dòng `path(...)` là thành lỗ hổng nghiêm trọng.
- **LOW:** `admin_events_view` chỉ dùng `@require_actor()`, kiểm tra role bên trong service.
- ai_service: middleware `verify_internal_secret` (so sánh `hmac.compare_digest`) chạy trước mọi router; nhưng `/docs`, `/redoc`, `/openapi.json`, `/metrics` công khai ở mọi môi trường (xem ERROR_HANDLING).

## What's at risk

Nếu `policy_views.py` được nối route: bất kỳ ai trên Internet cũng có thể đặt hệ thống vào bảo trì liên tục (DoS) và kích hoạt tiến trình huấn luyện tốn tài nguyên với dữ liệu tùy ý.

## What's already secure

- `require_actor` kiểm tra session đã ký, marker phiên trong cache (thu hồi khi logout/đổi mật khẩu), idle timeout, `auth_version`, `must_change_password`, chặn tài khoản quản trị dùng API nghiệp vụ (`ADMIN_PORTAL_ONLY`), và chế độ bảo trì.
- Request không xác thực trả 401 `AUTHENTICATION_REQUIRED`; sai role trả 403.
- Tối ưu hiệu năng gần đây (dùng lại `request.actor` cho view lồng nhau) an toàn: thuộc tính này chỉ do chính decorator gán, và kiểm tra role của decorator trong vẫn chạy.

## Recommendations

1. Xoá `policy_views.py` và `workflow/maintenance.py` (chỉ dùng lẫn nhau).
2. Đưa role của admin-events lên decorator.

## Verification results

- [x] Mọi route trả/sửa dữ liệu người dùng có xác thực
- [x] Xác thực chạy trong decorator trước handler
- [x] Request không xác thực → 401 (test hiện có trong `test_authn.py`, `test_workflow_api.py`)
- [x] Non-admin gọi route admin → 403 (thêm test admin-events, handler không bị gọi)
- [x] Không còn view `csrf_exempt` không xác thực trong mã nguồn (`git grep csrf_exempt` = 0)
