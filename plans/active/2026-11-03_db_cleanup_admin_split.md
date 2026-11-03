# Kế hoạch: Dọn bảng trùng chức năng và tách tài khoản quản trị (Supabase)

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-11-03-01 |
| Ngày mở | 03/11/2026 |
| Trạng thái | ACTIVE — bản đầu đã chạy trên Supabase; chờ chạy lại bản cập nhật (chỉ một tài khoản quản trị) |
| Migration | `database/migrations/11_cleanup_duplicates_and_admin_split.sql` |
| Rollback | `database/migrations/rollback/11_cleanup_duplicates_and_admin_split_rollback.sql` |
| Xoá hẳn (sau 14 ngày) | `database/migrations/scheduled/2026-11-17_drop_eas_deprecated_after_11.sql` |

## 1. Hiện trạng (khảo sát chỉ đọc trên DB live, 03/11/2026)

- Schema `eas` có 2 bộ bảng song song. Bộ lõi (owner `eas_migration`, tạo trước) chứa dữ liệu thật, có 26 khóa ngoại trỏ tới `app_user` và chuỗi băm audit; toàn bộ `api_core` dùng bộ này. Bộ thứ hai (owner `postgres`, tạo sau) gần như không được code dùng:

| Bảng tạo sau | Trùng chức năng với | Code dùng |
|---|---|---|
| `users` | `app_user` | Chỉ `/me` tra quyền module |
| `departments` | `department` | Không |
| `requests` | `request` | Không |
| `roles`, `role_permissions` | `role`, `role_membership` | Qua hàm quyền module |
| `request_templates`, `workflow_categories` | `request_type`, `config_release` | Không |

- Không có tài khoản quản trị thuần: cả 5 người có vai trò OPS_ADMIN/POLICY_ADMIN/AUDITOR đều kiêm vai trò nhân viên.
- Bảo mật: `anon`/`authenticated` có USAGE schema `eas`, quyền trên cả 48 bảng (kể cả TRUNCATE) và EXECUTE trên 37 function; default privilege của `postgres` tự cấp cho mọi object mới. RLS vẫn chặn đọc dòng, nhưng đây là lỗ hổng cấu hình.

## 2. Quyết định (data engineering)

1. Giữ bảng theo **mức sử dụng** (dữ liệu, khóa ngoại, code, audit), không theo ngày tạo. Giữ "bảng tạo sau" sẽ phải xoá `app_user`/`request`/`department` và mất toàn bộ dữ liệu.
2. Không `DROP` ngay: chuyển bảng trùng sang schema `eas_deprecated`, xoá sau 14 ngày.
3. Tách quản trị bằng mô hình supertype/subtype: `app_user` vẫn là danh tính chung (bảo toàn khóa ngoại và audit), thêm `account_type` và bảng `eas.admin_account`.
4. Cập nhật 03/11/2026 theo yêu cầu chủ dự án: **chỉ `admin@eas.com` là tài khoản quản trị**. Mọi tài khoản khác bị thu hồi OPS_ADMIN/POLICY_ADMIN/AUDITOR (giữ vai trò nghiệp vụ). Các tài khoản `<tên>+admin@eas.com` do bản đầu tạo bị thu hồi vai trò và khoá (không xoá vì có thể đã có nhật ký audit).
5. Một transaction, idempotent, tự kiểm tra; sai thì rollback toàn bộ. Mỗi lần chạy ghi một dấu thời gian ở `eas_deprecated.migration_marker` để rollback khôi phục đúng.

## 3. Work breakdown

| # | Hạng mục | Trạng thái |
|---|---|---|
| 1 | Khảo sát chỉ đọc: bảng, khóa ngoại, view, function, quyền, dữ liệu | DONE |
| 2 | Dựng bản sao (DDL + dữ liệu live) trong PGlite, giả lập SQL Editor không superuser | DONE |
| 3 | Viết migration 11 + rollback + script xoá theo lịch | DONE |
| 4 | Kiểm thử trên bản sao: migrate → rollback → migrate → migrate (idempotent) → drop sớm (bỏ qua) → drop sau 14 ngày → drop lần 2 | DONE |
| 5 | Backend: `/me` lấy quyền module theo id `app_user`, dự phòng theo vai trò; test `api_core/tests/test_actor_permissions.py` | DONE |
| 6 | Chạy migration 11 (bản đầu) trên Supabase | DONE (chủ dự án) |
| 6b | Chạy lại migration 11 bản cập nhật: chỉ giữ `admin@eas.com` | TODO (chủ dự án) |
| 7 | Sau 14 ngày: chạy script xoá `eas_deprecated` | TODO (từ 17/11/2026) |
| 8 | Bổ sung trường `account_type` vào API quản trị người dùng (tạo tài khoản quản trị từ giao diện) | TODO |

## 4. Kết quả kiểm thử trên bản sao (dữ liệu live 03/11/2026)

- Chạy dưới role không superuser, không `BYPASSRLS` (giống SQL Editor): PASS.
- Sau migration: 43 bảng trong `eas`, 0 quyền của `anon` trên bảng, `anon` mất USAGE schema; 5 tài khoản ADMIN, 41 EMPLOYEE; số request, audit_event không đổi; số quyền quản trị đang hiệu lực không đổi.
- Trigger chặn gán vai trò nghiệp vụ cho ADMIN và vai trò quản trị cho EMPLOYEE.
- Hàm quyền module: nhân viên 4 module xem được, admin OPS 9 module, khớp logic dự phòng của backend.
- Backend: 426 test PASS.

## 5. Lưu ý vận hành

- 4 dòng `user_leave_and_trips` thuộc người không có trong `app_user` (dữ liệu mẫu) được lưu ở `eas_deprecated.user_leave_and_trips_unmapped`.
- `PUBLIC` vẫn có EXECUTE trên function `eas` (mặc định Postgres) nhưng `anon`/`authenticated` không còn USAGE schema nên không gọi được.
- Sau bản cập nhật: không ai còn vai trò AUDITOR (trước đây do hung.nguyen, tri.tran giữ); POLICY_ADMIN và OPS_ADMIN chỉ còn ở `admin@eas.com`. Cấp lại AUDITOR cần tạo tài khoản ADMIN mới (TODO #8).
