-- Rollback của database/migrations/14_security_hardening_and_schema_v2_expand.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Một transaction; chạy lại an toàn.
--
-- CỐ Ý KHÔNG KHÔI PHỤC các phần vá bảo mật (đó là lỗ hổng, không phải tính năng):
--   * 16 policy anon_auth_read_* (S2), EXECUTE của PUBLIC trên hàm SECURITY DEFINER (S3),
--   * quyền sửa cấu hình loại yêu cầu của vai trò nghiệp vụ (S1).
-- Chỉ hoàn tác phần schema:
--   * khôi phục UNIQUE(instance_id, assignee_id) nếu dữ liệu cho phép;
--   * dời 4 bảng mới sang schema eas_rollback_14_<thời điểm> (không xoá dữ liệu).
-- Nếu báo "permission denied for database": chạy trước GRANT CREATE ON DATABASE postgres TO eas_migration;
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

DROP TRIGGER IF EXISTS approval_step_distinct_human ON eas.approval_step;
DROP FUNCTION IF EXISTS eas.guard_step_distinct_human();
DROP INDEX IF EXISTS eas.ix_approval_step_instance_assignee;

DO $unique$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'approval_step_instance_id_assignee_id_key') THEN
    RETURN;
  END IF;
  IF EXISTS (SELECT 1 FROM eas.approval_step GROUP BY instance_id, assignee_id HAVING count(*) > 1) THEN
    RAISE EXCEPTION 'Đã có phiên do AI duyệt nhiều bước: không thể khôi phục UNIQUE(instance_id, assignee_id). Giữ trạng thái hiện tại.';
  END IF;
  ALTER TABLE eas.approval_step
    ADD CONSTRAINT approval_step_instance_id_assignee_id_key UNIQUE (instance_id, assignee_id);
END
$unique$;

DO $move$
DECLARE
  t text;
  target text := 'eas_rollback_14_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSUS');
BEGIN
  IF to_regclass('eas.work_handover') IS NULL AND to_regclass('eas.privacy_case_approval') IS NULL
     AND to_regclass('eas.sla_escalation_policy') IS NULL AND to_regclass('eas.business_holiday') IS NULL THEN
    RETURN;
  END IF;
  EXECUTE format('CREATE SCHEMA %I AUTHORIZATION eas_migration', target);
  EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', target);
  FOREACH t IN ARRAY ARRAY['privacy_case_approval', 'sla_escalation_policy', 'work_handover', 'business_holiday'] LOOP
    IF to_regclass('eas.' || t) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE eas.%I SET SCHEMA %I', t, target);
    END IF;
  END LOOP;
END
$move$;

DROP FUNCTION IF EXISTS eas.guard_work_handover_overlap() CASCADE;
DROP FUNCTION IF EXISTS eas.guard_privacy_approval_append_only() CASCADE;

RESET ROLE;
COMMIT;
