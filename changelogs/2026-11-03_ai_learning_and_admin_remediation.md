# Changelog 03/11/2026 — AI học quy định có kiểm chứng, thông báo cập nhật, khắc phục phase 0–7

Kế hoạch: [EAS-PLAN-2026-11-03-02](../plans/active/2026-11-03_ai_learning_and_admin_remediation.md)

## Database (migration 12, chạy thủ công trên Supabase SQL Editor)

- `eas.ai_learning_job` (QUEUED → RUNNING → APPLIED | FAILED, có lease, tối đa 3 lần thử). Khoá đăng nhập suy ra từ job đang mở, không còn cờ boolean có thể kẹt.
- `eas.system_announcement` + `eas.announcement_receipt`: thông báo "Hệ thống đã cập nhật" kèm thay đổi và hướng dẫn thao tác.
- `ai_system_state`: thêm `applied_policy`, `applied_snapshot`, `applied_at`, `applied_job_id`; chuẩn hoá bộ đếm phiên bản theo phiên bản lớn nhất thực có (live đang có target "2.1" nhưng bộ đếm 1.0 → trước đây lần sửa tiếp theo bị lùi số).
- Trigger `fn_after_regulation_versioning` chỉ ghi lịch sử và phiên bản; bỏ tự bật khoá.
- Gỡ khoá đang kẹt trên live (APPLYING 75%) bằng một job học lại.
- Rollback: `database/migrations/rollback/12_ai_learning_jobs_and_announcements_rollback.sql`.

## Backend

- `api_core/workflow/ai_learning.py`: trích luật tất định từ văn bản quy định tiếng Việt (ngưỡng tiền, số ngày, "bắt buộc duyệt thủ công", phạm vi loại yêu cầu), đẩy sang ai_service, đọc lại xác nhận phiên bản và chạy ca kiểm thử vàng; chỉ khi AI áp dụng đúng mới mở khoá và gửi thông báo. AI lỗi → thử lại 15s/45s/120s → giữ luật cũ, mở khoá, chỉ báo quản trị viên.
- API mới: `GET /api/v1/announcements`, `POST /api/v1/announcements/<id>/read`, `POST /api/v1/admin/ai-engine/test` (hỏi AI thật với loại yêu cầu/số tiền/số ngày).
- Module quản trị viết lại trên bảng lõi (`org_users_rbac.py`, `workflows.py`, `analytics.py`): tạo/sửa/khoá người dùng qua kiểm tra chung, mật khẩu Argon2, idempotency, audit `admin_event`; AUDITOR chỉ đọc; analytics bỏ số liệu giả.
- Circuit breaker API tích hợp: chặn tạo/gửi yêu cầu phía server (`409 INTEGRATION_UNAVAILABLE`), ánh xạ theo nhóm catalog v2 thật (trước đây 4/8 API không khoá gì), bật/tắt có transaction + audit.
- Sửa lỗi có sẵn: tạo nháp không tiêu đề → 500 (NULL vào cột NOT NULL); `service.SELECT_BY_ID_SQL` đọc cột không tồn tại/sai thứ tự (500 khi sửa phòng ban, loại yêu cầu, vai trò).
- `supabase/migrations/20261103_admin_full_upgrade.sql`: bỏ `GRANT ALL` cho `anon`/`authenticated` (live đã sạch).

## AI service (không đổi chi phí)

- Endpoint CPU/mạng chạy trong threadpool thay vì chặn event loop (`classify`, `risk`, `summarize` — Gemini trước đây chặn toàn service vài giây mỗi lần gọi).
- Nạp sẵn model NLP + 4 model rủi ro khi khởi động.
- Cache tóm tắt Gemini theo nội dung (LRU 512): yêu cầu giống hệt không gọi Gemini lần nữa, giảm chi phí.

## Frontend

- Hộp "Hệ thống đã cập nhật quy định vX" sau đăng nhập (thay đổi + hướng dẫn), xem lại ở Thông báo.
- Overlay khoá chỉ theo khoá thật (trước đây trạng thái ERROR khoá nhân viên vĩnh viễn).
- Khôi phục menu bị mất sau redesign: Theo dõi vận hành, Thông báo SLA, Báo cáo phòng ban, Nhật ký kiểm toán; thêm Danh tính & phạm vi quyền, Phiên bản cấu hình quy trình, Luật AI thủ công. Nhân viên có lại "Quy trình AI", trưởng phòng có lại "Nhân viên phòng ban".
- Mobile: sidebar không còn che toàn màn hình (không mở/đóng được menu); dashboard admin không tràn ngang ở 1024px.
- Trang Quản trị AI gọi AI thật, hiện lịch sử các lượt học. ESLint 89 → 0 lỗi.

## Kiểm thử

- Django 444 OK; `tests/run_tests.py` 153 OK; `npm test` 64 OK; Playwright portal 15/15; ruff, ESLint, secret, docs, env gate PASS; build client + admin OK.
- E2E API phase 0–7 trên stack cục bộ (Postgres bản sao live + Django + ai_service): 45/45 (`%TEMP%/claude/e2e_all.py`).
- Trình duyệt thật: `web_client/e2e/live_stack_walk.mjs` (mọi trang 2 cổng, không lỗi 5xx/console ngoài `/health/ready` do bản sao thiếu schema `mock_hr`), `web_client/e2e/live_maintenance_lock.mjs` (khoá → tự đăng xuất → chặn đăng nhập → AI lỗi → mở khoá sau 62s, nhân viên không thấy cảnh báo lỗi).
- Có từ trước phase 0–5, chưa sửa: `e2e/ui.spec.js` (17/18 fail) và `e2e/smoke.spec.js` (1/3 fail) đã lỗi thời từ commit `86172e9`.

## Chạy trên live (thứ tự)

1. Supabase → Backups: tạo bản sao lưu.
2. SQL Editor lần lượt: `08_ai_auto_approval.sql` → `09_request_catalog_v2.sql` → `10_approval_delegation_and_employee_code.sql` → `12_ai_learning_jobs_and_announcements.sql`.
3. Khởi động ai_service, backend và worker (`start_worker_local.cmd`); job học lại sẽ chạy và mở khoá.

## Bổ sung sau khi chạy 08 → 12 trên live

- Live đã chạy 08, 09, 10, 12: job học lại APPLIED (v1.0), mở khoá; test API trên live 48/48, đi qua mọi trang 2 cổng không lỗi.
- Migration 13 `database/migrations/13_lock_client_roles_and_batch1_objects.sql` (+ rollback): script batch1 chạy trực tiếp trên live đã cấp lại `USAGE` schema `eas` và default privilege cho `anon`/`authenticated`, tạo `eas.workflow_categories` không RLS, 9 view và 3 function thuộc `postgres`. Bản 13 chuyển mọi object về `eas_migration`, view chạy `security_invoker`, bật RLS + policy backend, thu hồi quyền và default privilege của `anon`/`authenticated`, kiểm tra sau cùng rồi mới commit. Đã kiểm thử trên bản sao: chạy 2 lần, rollback, chạy lại đều sạch; bảng tạo sau đó `anon` không đọc được.
- Frontend: đăng nhập không còn gọi RPC Supabase từ trình duyệt (backend đã chặn sai cổng); `web_client/src/supabase.js` bỏ key ghi cứng và không được import; `@supabase/supabase-js` ghim `2.118.0`. Cổng nhân viên chặn lại mọi tài khoản có vai trò quản trị (không chỉ `admin@eas.com`).
- Test: `e2e/batch1_audit.test.mjs` đổi tên `batch1_audit.spec.js` (là test Playwright, `npm test` chạy nhầm); `portal.spec.js` theo menu admin 9 mục và quy tắc chỉ `admin@eas.com` vào cổng admin. Playwright portal 15/15, batch1 4/4, `npm test` 64, Django 444 OK.

## Kiểm tra tách quyền quản trị (live)

- DB live: chỉ `admin@eas.com` có OPS_ADMIN/POLICY_ADMIN, `account_type = ADMIN` và dòng `eas.admin_account`; vai trò nhân viên không có quyền module quản trị; không có quyền riêng.
- Kiểm thử từng tài khoản trên live (`%TEMP%/claude/e2e_admin_isolation.py`): admin vào cổng admin, bị từ chối ở cổng nhân viên, không gửi được yêu cầu nghiệp vụ; 136/136 tài khoản còn lại vào được cổng nhân viên, bị từ chối ở cổng admin, `/auth/me` không có vai trò/module quản trị, 11 API quản trị (đọc) và 2 API ghi đều 403.
- Chặn thêm: không thể cấp module chỉ-dành-cho-admin (`users`, `permissions`, `ai_engine`, `api_management`, `system_versions`) cho vai trò nhân viên hay quyền riêng của nhân viên (`422 ADMIN_MODULE_NOT_GRANTABLE`); trang Phân quyền khoá các công tắc đó.
