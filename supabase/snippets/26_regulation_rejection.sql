-- 26: Quy định bị trả lại (yêu cầu trưởng nhóm 18/11).
--
-- Khi văn bản quy định mới có lỗi (lỗi ký tự, mâu thuẫn giữa các điều) hoặc AI học thất bại sau mọi lần thử:
--   - HIỆU LỰC quay về bản AI đã áp dụng gần nhất: cả văn bản hiển thị (eas.company_regulations được khôi phục, có
--     phiên bản mới ghi "khôi phục") lẫn bộ luật AI. Người dùng không còn thấy văn bản khác với quy định đang áp.
--   - Bản bị trả lại được lưu ở bảng này, kèm DANH SÁCH LỖI chỉ rõ từng câu/điều, để admin sửa rồi nạp lại.
--     Admin nhận thông báo lỗi (eas.system_announcement, audience ADMIN).
-- Trạng thái: OPEN (chờ admin sửa) -> RESOLVED (admin đã nạp lại mã đó) / DISMISSED (admin bỏ qua, có ghi chú).
--
-- Chạy được nhiều lần. Rollback: database/migrations/rollback/26_regulation_rejection_rollback.sql

BEGIN;
SELECT eas.lock_security(true);

CREATE TABLE IF NOT EXISTS eas.regulation_rejection (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid REFERENCES eas.ai_learning_job(id) ON DELETE SET NULL,
  regulation_code text NOT NULL CHECK (length(btrim(regulation_code)) BETWEEN 1 AND 30),
  action varchar(10) NOT NULL CHECK (action IN ('CREATE', 'UPDATE', 'DELETE')),
  cause varchar(12) NOT NULL CHECK (cause IN ('VALIDATION', 'TECHNICAL')),
  rejected_title text,
  rejected_content text,
  rejected_version text,
  restored_version text,
  errors jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(errors) = 'array'),
  warnings jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(warnings) = 'array'),
  message text NOT NULL CHECK (length(btrim(message)) BETWEEN 5 AND 4000),
  state varchar(10) NOT NULL DEFAULT 'OPEN' CHECK (state IN ('OPEN', 'RESOLVED', 'DISMISSED')),
  resolved_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  resolved_at timestamptz,
  note varchar(500),
  created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK ((state = 'OPEN') = (resolved_at IS NULL))
);
CREATE INDEX IF NOT EXISTS regulation_rejection_open ON eas.regulation_rejection(regulation_code) WHERE state = 'OPEN';
COMMENT ON TABLE eas.regulation_rejection IS
  'Quy định bị trả lại: hiệu lực đã quay về bản cũ; lưu bản bị trả lại + danh sách lỗi từng câu để admin sửa và nạp lại.';

CREATE OR REPLACE FUNCTION eas.guard_regulation_rejection() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='regulation rejections are kept for audit';
 END IF;
 IF (to_jsonb(NEW) - ARRAY['state','resolved_by','resolved_at','note'])
    IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['state','resolved_by','resolved_at','note'])
    OR OLD.state <> 'OPEN' THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='only an OPEN rejection can be resolved or dismissed';
 END IF;
 RETURN NEW;
END $$;
ALTER FUNCTION eas.guard_regulation_rejection() OWNER TO eas_migration;
REVOKE EXECUTE ON FUNCTION eas.guard_regulation_rejection() FROM PUBLIC;
DROP TRIGGER IF EXISTS regulation_rejection_guard ON eas.regulation_rejection;
CREATE TRIGGER regulation_rejection_guard BEFORE UPDATE OR DELETE ON eas.regulation_rejection
  FOR EACH ROW EXECUTE FUNCTION eas.guard_regulation_rejection();

REVOKE ALL ON eas.regulation_rejection FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON eas.regulation_rejection TO eas_api, eas_worker;
GRANT SELECT ON eas.regulation_rejection TO eas_backup;
ALTER TABLE eas.regulation_rejection ENABLE ROW LEVEL SECURITY;
DO $pol$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='eas' AND tablename='regulation_rejection'
                 AND policyname='backend_read') THEN
    CREATE POLICY backend_read ON eas.regulation_rejection FOR SELECT TO eas_api, eas_worker USING (true);
    CREATE POLICY backend_insert ON eas.regulation_rejection FOR INSERT TO eas_api, eas_worker WITH CHECK (true);
    CREATE POLICY backend_update ON eas.regulation_rejection FOR UPDATE TO eas_api, eas_worker
      USING (true) WITH CHECK (true);
    CREATE POLICY backup_read ON eas.regulation_rejection FOR SELECT TO eas_backup USING (true);
  END IF;
END
$pol$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;

SELECT to_regclass('eas.regulation_rejection') AS regulation_rejection;
