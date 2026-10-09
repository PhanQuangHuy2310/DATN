# Synthetic Enterprise Source Systems 1.3.0

Gói này tạo dữ liệu nguồn giả lập cho EAS trong cùng PostgreSQL/Supabase nhưng tách khỏi schema nghiệp vụ `eas`. Mục đích là demo và integration test; không phải hệ thống master-data dùng trong production.

## Thành phần

- `00_mock_enterprise_schemas.sql`: installer một lần, không ghi đè schema đã có.
- `01_mock_seed_DEV_ONLY.sql`: fixture tổng hợp, dùng miền `example.test`, không chứa PII thật.
- `02_verify_READ_ONLY.sql`: truy vấn kiểm tra chỉ đọc; mỗi dòng trả về là một defect.
- `migrations/001..003`: temporal concurrency guard, least-privilege defaults và readiness contract.
- `validation/reproduce.mjs`: tái lập trên PostgreSQL WASM.

## Miền dữ liệu

| Schema | Hệ thống mô phỏng | Bảng chính |
|---|---|---|
| `mock_hr` | HRIS | department, employee, leave_balance |
| `mock_assets` | Asset Management | asset_category, asset, asset_loan |
| `mock_facilities` | Facility Booking | site, resource, reservation |
| `mock_crm` | CRM | customer, contract, support_case |
| `mock_procurement` | Procurement/ERP | supplier, catalog_item, purchase_order |
| `mock_it` | IAM/ITSM | application, access_role, user_access, service_catalog |
| `mock_finance` | Finance | cost_center_budget, expense_category |
| `mock_travel` | Travel Management | travel_policy, travel_option |

## Quyền và an toàn

- `PUBLIC` không có quyền `USAGE` schema hay đọc bảng.
- Runtime role `eas_api` chỉ có `SELECT` trên các bảng/view được đưa vào hợp đồng API; không có quyền sửa mock master data.
- `eas_backup` được đọc toàn bộ để phục vụ backup.
- API chỉ xuất directory-safe fields; không có lương, tài khoản ngân hàng, giấy tờ định danh hay dữ liệu liên hệ cá nhân.
- Tiền dùng số nguyên đơn vị nhỏ nhất (`*_minor`) kèm ISO 4217 currency; thời gian dùng `timestamptz`.

## Cài đặt

Chạy theo thứ tự bằng tài khoản migration/admin trên project development:

```text
00_mock_enterprise_schemas.sql
01_mock_seed_DEV_ONLY.sql
02_verify_READ_ONLY.sql
```

Không chạy seed trên production. Installer cố ý không dùng `IF NOT EXISTS`: nếu schema đã tồn tại, deployment phải dừng để tránh che khuất schema drift.

## Bằng chứng 09/10/2026

- PostgreSQL WASM: PASS; 8 schema, fixture và invariant “một open loan trên mỗi tài sản”.
- Supabase project được người dùng chỉ định: PASS; PostgreSQL 17.6, 8 schema, 23 bảng, 6 view, migration 001–003.
- Multi-session facility concurrency: PASS; overlap bị từ chối `23P01`, khoảng thời gian kề nhau hợp lệ.
- Privilege/readiness: PASS; `eas_api` chỉ đọc, `PUBLIC` không có schema/function access, 17/17 relation khả dụng.
- Chưa có bằng chứng load test hoặc backup/restore cho gói mock.
