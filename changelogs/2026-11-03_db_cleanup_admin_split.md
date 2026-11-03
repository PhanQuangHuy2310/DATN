# Changelog 03/11/2026 — Dọn bảng trùng chức năng và tách tài khoản quản trị

Kế hoạch: [EAS-PLAN-2026-11-03-01](../plans/active/2026-11-03_db_cleanup_admin_split.md)

## Database (migration 11, chạy thủ công trên Supabase SQL Editor)

- Chuyển 7 bảng trùng chức năng (`users`, `departments`, `requests`, `roles`, `role_permissions`, `request_templates`, `workflow_categories`), 2 view và 4 function chỉ phục vụ chúng sang schema cách ly `eas_deprecated`. Dữ liệu giữ nguyên; xoá hẳn sau 14 ngày.
- Quyền module gắn với danh tính lõi: bảng mới `eas.role_module_permission` (theo `eas.role`); `user_permissions`, `user_leave_and_trips` trỏ khóa ngoại sang `eas.app_user`; viết lại `eas.get_effective_user_permissions`.
- Tách quản trị: cột `app_user.account_type` (`EMPLOYEE` | `ADMIN`), bảng `eas.admin_account`. **Chỉ `admin@eas.com` là tài khoản quản trị**; mọi tài khoản khác bị thu hồi OPS_ADMIN/POLICY_ADMIN/AUDITOR. Tài khoản `<tên>+admin@eas.com` do bản đầu tạo bị thu hồi vai trò và khoá.
- Trigger `b_account_role_type`, `b_account_type_change` chặn trộn vai trò quản trị và nghiệp vụ trên cùng tài khoản (SQLSTATE 23514).
- Bảo mật: thu hồi mọi quyền của `anon`/`authenticated` trên schema `eas` và default privilege tương ứng; mọi object trong `eas` thuộc `eas_migration`.

## Backend

- `api_core/authn/views.py`: `/me` lấy quyền module bằng id `app_user` (bỏ tra cứu `eas.users`); nếu DB chưa cấp quyền xem nào hoặc lỗi DB thì dùng ma trận theo vai trò. Chỉ bắt `DatabaseError`.
- Test mới: `api_core/tests/test_actor_permissions.py` (3 test). Toàn bộ 426 test PASS.

## Cách chạy

1. Supabase Dashboard → Database → Backups: tạo bản sao lưu.
2. SQL Editor → dán toàn bộ `database/migrations/11_cleanup_duplicates_and_admin_split.sql` → Run. Kết quả cuối là danh sách tài khoản quản trị.
3. Quay lại nếu cần: `database/migrations/rollback/11_cleanup_duplicates_and_admin_split_rollback.sql`.
4. Từ 17/11/2026: `database/migrations/scheduled/2026-11-17_drop_eas_deprecated_after_11.sql`.

## Data fix (sau migration 11)

- `database/data_fixes/2026-11-03_delete_plus_admin_accounts.sql`: xoá hẳn 4 tài khoản `hung.nguyen`/`thang.ngo`/`tri.tran`/`tuan.pham` `+admin@eas.com` (đã khoá, chỉ có dòng `role_membership` đã thu hồi và `admin_account`; không có request/audit). Script dừng nếu phát hiện tham chiếu khác. Sau khi chạy, `eas.admin_account` chỉ còn `admin@eas.com`.

- `database/data_fixes/2026-11-03_org_structure_and_passwords.sql`: bổ sung cơ cấu tổ chức (BOD: giám đốc `hung.nguyen`, phó giám đốc `ngoc.tran`; 7 phòng ban x 1 trưởng phòng + 3 trưởng nhóm + 15 nhân viên), giữ người đã có và chỉ tạo phần thiếu; trưởng nhóm có APPROVER phạm vi phòng (luồng DIRECT_MANAGER), nhân viên mới có EXECUTOR phạm vi phòng. Đặt mật khẩu theo yêu cầu chủ dự án cho admin@eas.com và mọi tài khoản còn lại (Argon2, đăng xuất phiên cũ). Kiểm thử trên bản sao live: 137 tài khoản hoạt động, chạy lại không tạo thêm.
