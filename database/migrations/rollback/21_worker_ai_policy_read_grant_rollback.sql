-- Rollback của database/migrations/21_worker_ai_policy_read_grant.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Chạy lại an toàn.
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

DROP POLICY IF EXISTS worker_read ON eas.ai_policy_version;
REVOKE SELECT ON eas.ai_policy_version FROM eas_worker, eas_worker_login;

RESET ROLE;
COMMIT;

SELECT 'rollback 21 OK' AS status;
