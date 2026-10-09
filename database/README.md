# Database EAS

Nguồn database hiện hành là [gói SQL EAS 2.0.1](EAS_Supabase_SQL/README_VI.md). Các thư mục `migrations/`, `functions/`, `verify/` ở cấp này chỉ là skeleton cũ và không được coi là migration framework đã triển khai.

Gói [mock enterprise sources 1.0.0](mock_enterprise_sql/README.md) tạo 8 schema dữ liệu tổng hợp cho integration/demo. Đây là hệ thống nguồn giả lập tách khỏi `eas`, không phải dữ liệu production hay phần mở rộng tùy tiện của approval domain.

## Baseline hiện có

- `00_eas_supabase_schema.sql`: cài mới schema `eas`, 30 bảng, role group, guard, RLS và reference data tối thiểu.
- `02_verify_installation_READ_ONLY.sql`: kiểm tra an toàn trên database đã cài.
- `03_database_regression_DEV_ONLY.sql`: regression có fixture và rollback; chỉ chạy trên database development riêng.
- `01_demo_seed_DEV_ONLY.sql`: demo identity/config; không chạy trên production hoặc project chưa xác định môi trường.
- `DATA_DICTIONARY.md` và catalog JSON: từ điển vật lý/truy nguyên.

## Bằng chứng hiện tại

- PGlite/PostgreSQL WASM: PASS, 86 SQL assertions.
- Supabase project thật: read-only installation verification PASS; xem [biên bản](../docs/09_Bien_ban_kiem_chung_Supabase.md).
- Chưa có bằng chứng concurrency đa session, load, backup/restore hoặc acceptance API.

## Quy tắc thay đổi

`00_eas_supabase_schema.sql` là installer cho database mới, không phải công cụ upgrade production. Mọi thay đổi sau khi có dữ liệu phải là migration tăng dần, review riêng, có:

- ID/version và checksum bất biến.
- Expand/contract tương thích N/N-1.
- Precondition, forward verification và rollback/roll-forward plan.
- Test trên bản restore production đã khử dữ liệu nhạy cảm.
- Lock/time estimate và abort threshold.

Không dùng `CREATE TABLE IF NOT EXISTS` để che schema drift. Không sửa migration đã phát hành. Không chạy file `DEV_ONLY` trên project thật nếu chưa có xác nhận đó là môi trường development trống.
