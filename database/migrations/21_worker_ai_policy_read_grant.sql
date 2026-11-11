-- =============================================================================
-- 21 — Worker đọc eas.ai_policy_version khi chạy ai_learning_job
--
-- Lỗi: run_outbox_worker (kết nối bằng eas_worker) gọi run_learning_jobs()
--   để lấy quy định ACTIVE từ eas.ai_policy_version, nhưng migration 08 chỉ cấp
--   quyền + policy RLS cho eas_api. Khi worker giành trước API thread sẽ lỗi
--   ProgrammingError: permission denied for table ai_policy_version.
-- Sửa: cấp SELECT (chỉ đọc) + RLS policy FOR SELECT TO eas_worker, eas_worker_login.
--
-- CÁCH CHẠY: Supabase SQL Editor → dán TOÀN BỘ file → Run. Chạy lại an toàn.
-- Rollback: database/migrations/rollback/21_worker_ai_policy_read_grant_rollback.sql
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('eas.ai_policy_version') IS NULL THEN
    RAISE EXCEPTION 'Thiếu bảng eas.ai_policy_version (chạy migration 08 trước).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;

GRANT SELECT ON eas.ai_policy_version TO eas_worker, eas_worker_login;

DO $pol$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'eas' AND tablename = 'ai_policy_version' AND policyname = 'worker_read'
  ) THEN
    CREATE POLICY worker_read ON eas.ai_policy_version
      FOR SELECT TO eas_worker, eas_worker_login USING (true);
  END IF;
END
$pol$;

DO $check$
BEGIN
  IF NOT has_table_privilege('eas_worker', 'eas.ai_policy_version', 'SELECT') THEN
    RAISE EXCEPTION 'eas_worker vẫn chưa có SELECT trên eas.ai_policy_version';
  END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'migration 21 OK' AS status;
