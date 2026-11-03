# Database Access Fix Plan

Báo cáo: [DATABASE_ACCESS_REPORT.md](../reports/DATABASE_ACCESS_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `database/mock_enterprise_sql/migrations/004_mock_rls.sql` — `ENABLE ROW LEVEL SECURITY` + policy `api_read` (SELECT TO `eas_api`) và `backup_read` (SELECT TO `eas_backup`) cho mọi bảng `mock_*`, ghi `schema_migration '004'`.
- `database/mock_enterprise_sql/00_mock_enterprise_schemas.sql` — cài mới có sẵn khối RLS và bản ghi `004`.
- `database/mock_enterprise_sql/validation/reproduce.mjs` — kiểm tra mọi bảng `mock_*` có RLS và policy.

## New files

- `database/mock_enterprise_sql/migrations/004_mock_rls.sql`

## Verification goals

- [x] Mọi bảng `eas` bật RLS (live: 33/33)
- [x] Mọi bảng có policy tường minh (`eas` live 33/33; `mock_*` trong bản cài mới qua PGlite)
- [x] Không policy nào `USING (true)` cấp cho `PUBLIC`/`anon`/`authenticated`
- [x] Không có quyền `anon`/`authenticated` trên bảng, schema, function (live)
- [ ] Bảng `mock_*` trên DB live bật RLS — **chờ áp dụng migration 004**

## Manual verification (for the human)

- DBA chạy `database/mock_enterprise_sql/migrations/004_mock_rls.sql` trên Supabase bằng role sở hữu (`eas_migration`), sau đó chạy `02_verify_READ_ONLY.sql`.
- Sau khi áp dụng: nâng `api_core/health/views.py:84` thành `{"001","002","003","004"}`.
- Thử `curl` PostgREST bằng anon key tới `/rest/v1/` với schema `eas`/`mock_hr`: phải nhận lỗi quyền hoặc rỗng.
