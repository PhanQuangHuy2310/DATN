# Database Access Security Report

## Status: PASS

Trạng thái trước khắc phục: **LOW**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [DATABASE_ACCESS_PLAN.md](../plans/DATABASE_ACCESS_PLAN.md).

## Findings

Kiểm tra bằng truy vấn catalog chỉ đọc trên DB Supabase live (01/11/2026):

| Schema | Bảng | Tắt RLS | Không policy | Quyền `anon` | Quyền `authenticated` | `USAGE` schema |
|---|---|---|---|---|---|---|
| `eas` | 33 | 0 | 0 | 0 | 0 | không |
| `mock_*` (8 schema) | 24 | **24** | **24** | 0 | 0 | không |

- Không có function `eas`/`mock_*` nào cho `anon`/`authenticated` EXECUTE; function `SECURITY DEFINER` đều `SET search_path=pg_catalog,eas`.
- **LOW:** 24 bảng `mock_*` không bật RLS, chỉ được bảo vệ bằng GRANT (`database/mock_enterprise_sql/00_mock_enterprise_schemas.sql:384-397`).
- Client (web_client, web_admin, mobile_app) không gọi Supabase trực tiếp; không có anon key ở frontend.

## What's at risk

Hiện chưa khai thác được vì `anon`/`authenticated` không có GRANT. Rủi ro là phòng thủ một lớp: một lệnh `GRANT SELECT ... TO authenticated` nhầm sẽ mở toàn bộ dữ liệu mock (danh bạ nhân viên, hợp đồng, ngân sách) qua PostgREST.

## What's already secure

- `eas`: RLS bật trên mọi bảng, policy chỉ cấp cho role backend (`eas_api`, `eas_worker`, `eas_privacy`, `eas_backup`); thu hồi toàn bộ quyền của `anon`, `authenticated`, `service_role`, `PUBLIC` (`00_eas_supabase_schema.sql:1200-1221`).
- Backend kết nối bằng login role riêng (`eas_backend_login`, `eas_worker_login`), không dùng service key.
- Health check `runtime_role_is_non_admin`, `runtime_role_is_api_only` xác nhận role runtime không có quyền quản trị.

## Recommendations

1. Bật RLS + policy chỉ đọc cho mọi bảng `mock_*` (migration 004).
2. Áp dụng migration trên Supabase sau khi DBA duyệt; sau đó nâng readiness lên yêu cầu `004`.

Ngoại lệ có lý do (ghi trong `AGENTS.md`): policy `USING (true)` của EAS gắn `TO` role backend, không phải `PUBLIC`. EAS không dùng Supabase Auth nên không có `auth.uid()`; phân quyền theo người dùng nằm ở `api_core` (`require_actor` + vị từ sở hữu trong SQL).

## Verification results

- [x] Mọi bảng `eas` bật RLS (live: 33/33)
- [x] Mọi bảng có policy tường minh (`eas` live 33/33; `mock_*` trong bản cài mới qua PGlite)
- [x] Không policy nào `USING (true)` cấp cho `PUBLIC`/`anon`/`authenticated`
- [x] Không có quyền `anon`/`authenticated` trên bảng, schema, function (live)
- [ ] Bảng `mock_*` trên DB live bật RLS — **chờ áp dụng migration 004**
