-- Rollback của database/migrations/18_role_module_permission_write_grant.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Chạy lại an toàn.
-- Sau rollback, admin lại không sửa được ma trận quyền theo vai trò (lỗi H1).
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

REVOKE INSERT, UPDATE ON eas.role_module_permission FROM eas_api;

RESET ROLE;
COMMIT;

SELECT 'rollback 18 OK' AS status;
