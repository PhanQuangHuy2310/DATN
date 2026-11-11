-- Rollback của database/migrations/12_ai_learning_jobs_and_announcements.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Một transaction; chạy lại an toàn.
-- Không xoá dữ liệu: bảng job/thông báo được dời sang schema eas_deprecated
-- (kèm hậu tố thời gian nếu đã có bản cũ ở đó). Trigger quy định giữ hành vi chỉ ghi
-- lịch sử (không khôi phục phần tự bật khoá vì chính nó gây khoá kẹt).
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

DO $move$
DECLARE
  t text;
  target text := 'eas_rollback_12_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSUS');
BEGIN
  IF to_regclass('eas.ai_learning_job') IS NULL THEN
    RETURN;
  END IF;
  -- Schema riêng cho mỗi lần rollback: không đụng tên index/constraint của lần trước.
  EXECUTE format('CREATE SCHEMA %I AUTHORIZATION eas_migration', target);
  EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', target);
  FOREACH t IN ARRAY ARRAY['announcement_receipt', 'system_announcement', 'ai_learning_job'] LOOP
    CONTINUE WHEN to_regclass('eas.' || t) IS NULL;
    EXECUTE format('ALTER TABLE eas.%I SET SCHEMA %I', t, target);
  END LOOP;
END
$move$;

ALTER TABLE eas.ai_system_state DROP COLUMN IF EXISTS applied_job_id;
ALTER TABLE eas.ai_system_state DROP COLUMN IF EXISTS applied_at;
ALTER TABLE eas.ai_system_state DROP COLUMN IF EXISTS applied_snapshot;
ALTER TABLE eas.ai_system_state DROP COLUMN IF EXISTS applied_policy;

UPDATE eas.ai_system_state
SET client_maintenance_lock = false, sync_status = 'COMPLETED', progress_percent = 100,
    current_step_index = 4, updated_at = now()
WHERE id = 1;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
RESET ROLE;
COMMIT;
