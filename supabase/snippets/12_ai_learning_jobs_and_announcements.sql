-- 12 — Học quy định AI bằng job có lease + thông báo cập nhật cho người dùng (2026-11-03)
-- Kế hoạch: plans/active/2026-11-03_ai_learning_and_admin_remediation.md (EAS-PLAN-2026-11-03-02)
-- Chạy SAU migration 11. Dán toàn bộ vào Supabase SQL Editor → Run. Một transaction; chạy lại an toàn.
-- Rollback: database/migrations/rollback/12_ai_learning_jobs_and_announcements_rollback.sql
--
-- Vì sao: khoá đăng nhập trước đây là một cờ boolean do thread trong Django hoặc
-- trigger DB bật lên; tiến trình chết là cờ kẹt mãi. Từ bản này:
--   * Mỗi lần quy định/bộ luật AI đổi, ứng dụng xếp một job vào eas.ai_learning_job.
--   * Khoá đăng nhập = đang có job QUEUED/RUNNING. Job có lease: tiến trình chết thì
--     tiến trình khác nhận lại; hết số lần thử thì FAILED (giữ bộ luật cũ, mở khoá).
--   * Chỉ khi AI đã nạp và xác nhận bộ luật mới, job mới chuyển APPLIED, ghi bộ luật
--     hiệu lực, tạo thông báo cho người dùng, rồi khoá tự hết.
--   * Trigger quy định chỉ còn tính số phiên bản và ghi lịch sử (không bật khoá,
--     không ghi changelog trùng với ứng dụng).
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = '60s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('eas.ai_system_state') IS NULL OR to_regclass('eas.company_regulations') IS NULL THEN
    RAISE EXCEPTION 'Thiếu eas.ai_system_state / eas.company_regulations: chạy migration nền tảng quản trị trước.';
  END IF;
  IF to_regclass('eas.admin_account') IS NULL THEN
    RAISE EXCEPTION 'Chạy migration 11 trước (thiếu eas.admin_account).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;

-- ---------------------------------------------------------------------------
-- 1. Job học quy định
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.ai_learning_job (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_version  varchar(20) NOT NULL,
  base_version    varchar(20),
  reason          text NOT NULL DEFAULT '',
  status          varchar(16) NOT NULL DEFAULT 'QUEUED'
                  CHECK (status IN ('QUEUED', 'RUNNING', 'APPLIED', 'FAILED')),
  step            smallint NOT NULL DEFAULT 0 CHECK (step BETWEEN 0 AND 4),
  step_label      text NOT NULL DEFAULT 'Đang chờ xử lý',
  progress        smallint NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  attempts        smallint NOT NULL DEFAULT 0,
  max_attempts    smallint NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
  rerun_requested boolean NOT NULL DEFAULT false,
  not_before      timestamptz NOT NULL DEFAULT statement_timestamp(),
  lease_owner     text,
  lease_until     timestamptz,
  requested_by    uuid REFERENCES eas.app_user(id) ON DELETE SET NULL,
  snapshot        jsonb,
  compiled_policy jsonb,
  diff            jsonb,
  error           text,
  created_at      timestamptz NOT NULL DEFAULT statement_timestamp(),
  started_at      timestamptz,
  finished_at     timestamptz,
  updated_at      timestamptz NOT NULL DEFAULT statement_timestamp()
);
COMMENT ON TABLE eas.ai_learning_job IS
  'Job học/áp dụng quy định cho AI. Đang có job QUEUED/RUNNING = khoá đăng nhập cổng nhân viên.';
-- Tối đa một job mở; thay đổi mới trong lúc chạy đặt rerun_requested.
CREATE UNIQUE INDEX IF NOT EXISTS ai_learning_job_single_open
  ON eas.ai_learning_job ((true)) WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX IF NOT EXISTS ai_learning_job_created ON eas.ai_learning_job (created_at DESC);

-- ---------------------------------------------------------------------------
-- 2. Bộ luật đang hiệu lực (kết quả job APPLIED gần nhất)
-- ---------------------------------------------------------------------------
ALTER TABLE eas.ai_system_state ADD COLUMN IF NOT EXISTS applied_policy jsonb;
ALTER TABLE eas.ai_system_state ADD COLUMN IF NOT EXISTS applied_snapshot jsonb;
ALTER TABLE eas.ai_system_state ADD COLUMN IF NOT EXISTS applied_at timestamptz;
ALTER TABLE eas.ai_system_state ADD COLUMN IF NOT EXISTS applied_job_id uuid;

-- ---------------------------------------------------------------------------
-- 3. Thông báo cập nhật cho người dùng
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.system_announcement (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id      uuid UNIQUE REFERENCES eas.ai_learning_job(id) ON DELETE SET NULL,
  kind        varchar(32) NOT NULL DEFAULT 'REGULATION_UPDATE',
  audience    varchar(16) NOT NULL DEFAULT 'ALL' CHECK (audience IN ('ALL', 'ADMIN')),
  version     varchar(20) NOT NULL,
  title       text NOT NULL,
  summary     text NOT NULL,
  changes     jsonb NOT NULL DEFAULT '[]'::jsonb,
  guidance    jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX IF NOT EXISTS system_announcement_created ON eas.system_announcement (created_at DESC);

CREATE TABLE IF NOT EXISTS eas.announcement_receipt (
  announcement_id uuid NOT NULL REFERENCES eas.system_announcement(id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE CASCADE,
  read_at         timestamptz NOT NULL DEFAULT statement_timestamp(),
  PRIMARY KEY (announcement_id, user_id)
);

-- RLS + quyền cho backend theo cùng mẫu với các bảng lõi.
DO $grants$
DECLARE t text; r text; backend text[];
BEGIN
  SELECT array_agg(rolname ORDER BY rolname) INTO backend
  FROM pg_roles WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login', 'eas_privacy');
  FOREACH t IN ARRAY ARRAY['ai_learning_job', 'system_announcement', 'announcement_receipt'] LOOP
    EXECUTE format('ALTER TABLE eas.%I ENABLE ROW LEVEL SECURITY', t);
    FOREACH r IN ARRAY backend LOOP
      EXECUTE format('GRANT SELECT, INSERT, UPDATE ON eas.%I TO %I', t, r);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = ('eas.' || t)::regclass AND polname = 'trusted_backend') THEN
      EXECUTE format('CREATE POLICY trusted_backend ON eas.%I FOR ALL TO %s USING (true) WITH CHECK (true)',
                     t, (SELECT string_agg(quote_ident(x), ', ') FROM unnest(backend) x));
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_backup')
       AND NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = ('eas.' || t)::regclass AND polname = 'backup_read') THEN
      EXECUTE format('CREATE POLICY backup_read ON eas.%I FOR SELECT TO eas_backup USING (true)', t);
      EXECUTE format('GRANT SELECT ON eas.%I TO eas_backup', t);
    END IF;
  END LOOP;
END
$grants$;
-- ai_system_state được job cập nhật.
DO $state_grants$
DECLARE r text;
BEGIN
  FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login') LOOP
    EXECUTE format('GRANT SELECT, UPDATE ON eas.ai_system_state TO %I', r);
  END LOOP;
END
$state_grants$;

-- ---------------------------------------------------------------------------
-- 4. Trigger quy định: chỉ tính phiên bản + ghi lịch sử (bỏ bật khoá, bỏ changelog trùng)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION eas.fn_after_regulation_versioning()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, eas
AS $f$
DECLARE
  v_action text; v_summary text; v_major int; v_minor int; v_ver text; v_reg uuid; v_title text; v_content text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_action := 'CREATE'; v_reg := NEW.id; v_title := NEW.title; v_content := NEW.content;
    v_major := NEW.major_version; v_minor := NEW.minor_version; v_ver := NEW.version_string;
    v_summary := 'Thêm mới quy định "' || NEW.title || '"';
  ELSIF TG_OP = 'UPDATE' THEN
    IF COALESCE(OLD.is_deleted, false) = false AND COALESCE(NEW.is_deleted, false) = true THEN
      v_action := 'DELETE_MAJOR';
      v_summary := 'Gỡ bỏ quy định "' || NEW.title || '"';
    ELSIF NEW.version_string IS DISTINCT FROM OLD.version_string THEN
      v_action := 'UPDATE_MINOR';
      v_summary := 'Cập nhật quy định "' || NEW.title || '"';
    ELSE
      RETURN NEW;
    END IF;
    v_reg := NEW.id; v_title := NEW.title; v_content := NEW.content;
    v_major := NEW.major_version; v_minor := NEW.minor_version; v_ver := NEW.version_string;
  ELSE
    SELECT COALESCE(global_major_version, 1) + 1, 0 INTO v_major, v_minor FROM eas.ai_system_state WHERE id = 1;
    v_ver := v_major || '.' || v_minor;
    v_action := 'DELETE_MAJOR'; v_reg := NULL; v_title := OLD.title; v_content := OLD.content;
    v_summary := 'Gỡ bỏ quy định "' || OLD.title || '"';
  END IF;

  INSERT INTO eas.regulation_versions (regulation_id, version_string, major_version, minor_version,
                                       action_type, title, content, change_summary, created_by)
  VALUES (v_reg, v_ver, v_major, v_minor, v_action, v_title, v_content, v_summary,
          COALESCE(CASE WHEN TG_OP = 'DELETE' THEN OLD.updated_by ELSE NEW.updated_by END, 'Admin'));

  -- Chỉ cấp số phiên bản mới; việc học/khoá/thông báo do eas.ai_learning_job đảm nhận.
  UPDATE eas.ai_system_state
  SET global_major_version = v_major, global_minor_version = v_minor,
      target_regulation_version = v_ver, updated_at = now()
  WHERE id = 1;
  RETURN COALESCE(NEW, OLD);
END
$f$;

-- ---------------------------------------------------------------------------
-- 5. Gỡ khoá kẹt cũ: cờ boolean không còn quyết định khoá. Nếu đang kẹt hoặc chưa
--    từng áp dụng bộ luật nào, xếp một job để AI học bộ quy định hiện hành thật sự.
-- ---------------------------------------------------------------------------
-- Pipeline cũ có thể ghi target_regulation_version không khớp bộ đếm (vd "2.1"
-- trong khi quy định mới ở 1.0): chuẩn hoá theo phiên bản lớn nhất thực có.
UPDATE eas.ai_system_state s
SET global_major_version = v.maj, global_minor_version = v.mnr,
    target_regulation_version = v.maj || '.' || v.mnr
FROM (
  SELECT maj, mnr FROM (
    SELECT COALESCE(global_major_version, 1) AS maj, COALESCE(global_minor_version, 0) AS mnr
    FROM eas.ai_system_state WHERE id = 1
    UNION ALL
    SELECT major_version, minor_version FROM eas.company_regulations
  ) x
  ORDER BY maj DESC, mnr DESC
  LIMIT 1
) v
WHERE s.id = 1;

INSERT INTO eas.ai_learning_job (target_version, base_version, reason, step_label)
SELECT COALESCE(NULLIF(s.target_regulation_version, ''), s.active_regulation_version, '1.0'),
       s.active_regulation_version,
       CASE WHEN s.client_maintenance_lock THEN 'Hoàn tất lượt học bị gián đoạn trước migration 12'
            ELSE 'Học bộ quy định hiện hành lần đầu' END,
       'Đang chờ xử lý'
FROM eas.ai_system_state s
WHERE s.id = 1
  AND (s.client_maintenance_lock OR s.applied_policy IS NULL)
  AND NOT EXISTS (SELECT 1 FROM eas.ai_learning_job j WHERE j.status IN ('QUEUED', 'RUNNING'));

UPDATE eas.ai_system_state
SET client_maintenance_lock = false,
    sync_status = 'SYNCING',
    current_step_index = 1,
    progress_percent = 0,
    current_step_label = 'Đang chờ AI học quy định',
    updated_at = now()
WHERE id = 1 AND EXISTS (SELECT 1 FROM eas.ai_learning_job WHERE status = 'QUEUED');

-- Phiên đang mở nạp lại trạng thái ở request kế tiếp.
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

RESET ROLE;
COMMIT;

SELECT j.status, j.target_version, j.reason, j.created_at
FROM eas.ai_learning_job j ORDER BY j.created_at DESC LIMIT 3;
