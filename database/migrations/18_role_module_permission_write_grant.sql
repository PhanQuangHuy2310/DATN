-- =============================================================================
-- 18 — Admin sửa ma trận quyền theo vai trò (07/11/2026, lỗi H1)
--
-- Lỗi: PUT /api/v1/admin/rbac/role-permission trả 500 DATABASE_QUERY_FAILED.
--   api_core/administration/org_users_rbac.py ghi bằng
--   INSERT … ON CONFLICT (role_code, module_code) DO UPDATE, nhưng eas_api chỉ
--   có SELECT trên eas.role_module_permission (đã kiểm trên live 07/11/2026).
--   Policy RLS trusted_backend (FOR ALL TO eas_api, …) đã có sẵn, nên chỉ
--   thiếu quyền bảng.
-- Sửa: cấp INSERT, UPDATE cho eas_api. Không cấp DELETE (không có code xoá),
--   không cấp cho eas_worker (worker chỉ đọc ma trận quyền).
--
-- CÁCH CHẠY: Supabase SQL Editor → dán TOÀN BỘ file → Run. Chạy lại an toàn.
-- Rollback: database/migrations/rollback/18_role_module_permission_write_grant_rollback.sql
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('eas.role_module_permission') IS NULL THEN
    RAISE EXCEPTION 'Thiếu bảng eas.role_module_permission (chạy migration 11 trước).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;

GRANT INSERT, UPDATE ON eas.role_module_permission TO eas_api;

-- Quyền thay đổi: các tiến trình nạp lại trạng thái bảo mật.
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- Kiểm tra: eas_api ghi được, và policy RLS cho phép ghi vẫn còn.
DO $check$
BEGIN
  IF NOT (has_table_privilege('eas_api', 'eas.role_module_permission', 'INSERT')
          AND has_table_privilege('eas_api', 'eas.role_module_permission', 'UPDATE')) THEN
    RAISE EXCEPTION 'eas_api vẫn chưa có INSERT/UPDATE trên eas.role_module_permission';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'eas' AND tablename = 'role_module_permission'
      AND cmd IN ('ALL', 'INSERT') AND 'eas_api' = ANY (roles)
  ) THEN
    RAISE EXCEPTION 'Thiếu policy RLS cho phép eas_api ghi eas.role_module_permission';
  END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'migration 18 OK' AS status;
