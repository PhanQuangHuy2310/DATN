# Biên bản kiểm chứng Supabase EAS

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-DOC-09 |
| Ngày chạy | 09/10/2026 |
| Project ref | `emnusiybdkpibtqsplta` |
| Phương thức | Kết nối PostgreSQL TLS, ép session read-only |
| Script | `database/EAS_Supabase_SQL/02_verify_installation_READ_ONLY.sql` |
| Phạm vi | Metadata/schema/invariant cài đặt; không đọc nội dung hồ sơ nghiệp vụ |

## 1. Kiểm soát an toàn khi chạy

- Không in URL kết nối, password, API key hoặc token vào biên bản.
- Session đặt `default_transaction_read_only=on` và `statement_timeout=15s`.
- Không chạy `01_demo_seed_DEV_ONLY.sql` hoặc `03_database_regression_DEV_ONLY.sql`.
- Không INSERT/UPDATE/DELETE/DDL và không thay đổi dữ liệu project.
- Script verification tự mở `BEGIN TRANSACTION READ ONLY`.

## 2. Kết quả quan sát

| Kiểm tra | Actual result | Trạng thái |
|---|---|---|
| Kết nối TLS đến database | Thành công | PASS |
| PostgreSQL server | 17.6 | PASS |
| Session read-only | `on` | PASS |
| Bảng trong schema `eas` | 30 | PASS |
| Routine trong schema `eas` | 27 | PASS |
| RLS policy trong schema `eas` | 60 | PASS |
| Verification script | Hoàn thành không lỗi | PASS |

## 3. Phát hiện bảo mật liên quan

| ID | Phát hiện | Mức | Xử lý |
|---|---|---|---|
| SEC-01 | Các file `.env` đã xuất hiện trong Git history | Critical | Rotate mọi credential liên quan; không coi `.gitignore` là đủ |
| SEC-02 | DSN kiểm tra đang dùng vai trò quản trị `postgres` | Critical với runtime | Chỉ dùng cho migration có kiểm soát; tạo login runtime thuộc đúng một nhóm `eas_api`/`eas_worker` |
| SEC-03 | Password có ký tự đặc biệt nhưng DSN chưa percent-encode | High | Tạo DSN chuẩn bằng URL encoding hoặc truyền qua secret manager/structured config |
| SEC-04 | Frontend có Supabase anon key dù kiến trúc quy định client gọi Django | Medium | Bỏ direct Supabase config khỏi frontend P0; chỉ giữ `VITE_API_BASE_URL` |

Không ghi giá trị credential vào issue, screenshot, CI log hay luận văn. Sau rotate, xác minh credential cũ bị từ chối và cập nhật secret qua kênh riêng.

## 4. Giới hạn bằng chứng

PASS trên không chứng minh:

- API, authentication, authorization theo end-user hoặc workflow chạy đúng.
- Concurrency/locking đa phiên và idempotency ở tầng ứng dụng.
- Storage, virus scanner, worker, notification hoặc audit canonicalization của backend.
- Backup/restore, RPO/RTO, performance, UAT hoặc production readiness.
- 100 test case trong tài liệu 04 đã PASS.

Trạng thái 100 test case ứng dụng vẫn là `NOT RUN` cho đến khi có release, môi trường, actual result và evidence tương ứng.
