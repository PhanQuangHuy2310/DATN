# Cơ sở dữ liệu EAS

Thư mục database có các gói riêng cho schema phê duyệt EAS và các schema nguồn doanh nghiệp giả lập. Giữ installer, migration, seed và script kiểm tra tách biệt vì mục đích và độ an toàn khi triển khai khác nhau.

## Schema EAS

Xem [gói SQL EAS Supabase](./EAS_Supabase_SQL/README_VI.md) để biết installer baseline, kiểm tra chỉ đọc, seed/regression development, database role và cách chạy SQL validation local.

- `EAS_Supabase_SQL/00_eas_supabase_schema.sql` cài baseline mới, không phải script nâng cấp.
- `migrations/04_current_schema_upgrade.sql` nâng baseline 2.0.1 lên catalog 2.1.0 (lifecycle, role và loại yêu cầu).
- `migrations/05_email_login_and_password_reset.sql` chuyển username cũ sang email `@eas.com`, tăng `auth_version` để vô hiệu hóa session cũ và tạo bảng yêu cầu reset mật khẩu. Chạy sau catalog migration 04; transaction sẽ rollback toàn bộ nếu không tương thích.
- `EAS_Supabase_SQL/02_verify_installation_READ_ONLY.sql` kiểm tra schema core sau các migration mà không ghi dữ liệu.
- `EAS_Supabase_SQL/03_database_regression_DEV_ONLY.sql` và `01_demo_seed_DEV_ONLY.sql` chỉ dùng trên database development cô lập. Chạy regression trên baseline; chỉ chạy demo seed sau migration 05.

Project Supabase DATN hiện đã có catalog 2.1.0 và migration 05. Đã xác minh chỉ đọc: 33 bảng EAS, 42 tài khoản giữ nguyên, email hợp lệ cho toàn bộ tài khoản, `password_reset_request` có RLS/grants/policy và verifier trả `PASS`. Session cũ đã bị vô hiệu hóa qua `auth_version`. Các địa chỉ `@eas.com` chưa được chứng minh là mailbox nhận thư; cần domain mail hoạt động và SMTP provider. Không chạy lại migration 04/05, không reset/drop schema hoặc chạy demo seed trên production.

`migrations/06_dev_gmail_aliases.sql` là migration **chỉ dành cho dữ liệu tài khoản thử nghiệm**. Nó chuyển email `@eas.com` sang alias Gmail duy nhất cho cùng một inbox, tăng `auth_version` để đăng xuất phiên cũ và cập nhật yêu cầu reset đang chờ. Trên Supabase DATN, migration đã áp dụng cho 42 tài khoản sau khi API tương thích được triển khai và SMTP Gmail hoạt động; kiểm tra sau migration xác nhận 42/42 alias duy nhất, không còn email `@eas.com`, và không có reset request chờ. Không chạy lại trên DATN. Với một DB thử nghiệm khác, triển khai backend `EAS_LOGIN_EMAIL_DOMAIN=gmail.com` trước; thay placeholder mailbox trong SQL rồi chạy một lần. Không chạy nếu có tài khoản thật hoặc không muốn tất cả thư cùng vào một inbox.

Với một project mới cài baseline 2.0.1, chạy migration 04 rồi 05. Để xác minh project hiện tại, chỉ chạy script read-only `EAS_Supabase_SQL/02_verify_installation_READ_ONLY.sql`.

`report_migrations/` chứa SQL riêng cho tính năng/catalog, có kiểm thử database contract và yêu cầu DBA review. Giữ các script đó tách biệt khỏi installer baseline và review từng file trước khi triển khai.

Baseline chính thức nằm trong `EAS_Supabase_SQL/`; không dùng các bản sao schema/seed cấp cao cũ hoặc bản export database làm installer.

## Schema nguồn giả lập

[Mock enterprise SQL](./mock_enterprise_sql/README.md) là gói tùy chọn cho dữ liệu integration/demo. Đây không phải master data production và không được trộn vào schema nghiệp vụ `eas`.

## An toàn khi thay đổi

Backup và review mọi migration production. Giữ installer baseline bất biến với hệ thống đã có dữ liệu, kiểm tra nâng cấp trên bản restore thử nghiệm và chạy verify chỉ đọc sau triển khai. Không dùng seed/regression dành cho development trên production.
