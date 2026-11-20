-- 27: Nạp quy định — đánh số phiên bản mới, quyết định giữ/bỏ điều cũ, thông báo một lần kể từ lần đăng nhập trước.
--     (yêu cầu người dùng 20/11)
--
-- 1. Đánh số: mọi thay đổi quy định (thêm, sửa, gỡ) chỉ tăng số sau dấu chấm (1.0 -> 1.1 -> 1.2 ...). Chỉ "cập nhật
--    lớn" mới tăng số đầu (2.0): API đặt  SET LOCAL eas.version_bump = 'major'  trong giao dịch trước khi ghi.
--    eas.version_bump = 'none' (chỉ dùng trong migration) ghi mà không tăng số và không thêm lịch sử.
-- 2. Đưa hệ thống về v1.0: các quy định đang hiệu lực mang phiên bản 1.0; lịch sử phiên bản cũ vẫn giữ để tra cứu.
-- 3. eas.regulation_keep_decision: khi văn bản mới đè lên điều của văn bản cũ, AI đề xuất giữ hay bỏ điều cũ, admin có
--    thể đổi; cặp (văn bản mới, câu cũ) được GIỮ thì lượt học không thay thế câu cũ đó.
-- 4. app_user.last_login_at / previous_login_at: thông báo quy định chỉ hiện các bản tạo sau lần đăng nhập trước, mỗi
--    bản một lần.
--
-- Chạy được nhiều lần. Rollback: database/migrations/rollback/27_regulation_versioning_keep_login_rollback.sql

BEGIN;
SELECT eas.lock_security(true);

-- 1. Đánh số phiên bản -------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION eas.fn_before_regulation_versioning()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_cur_major INT;
    v_cur_minor INT;
    v_mode TEXT := COALESCE(current_setting('eas.version_bump', true), '');
BEGIN
    IF v_mode = 'none' THEN
        RETURN NEW;
    END IF;
    SELECT COALESCE(global_major_version, 1), COALESCE(global_minor_version, 0)
    INTO v_cur_major, v_cur_minor
    FROM eas.ai_system_state
    WHERE id = 1;

    IF TG_OP = 'UPDATE'
       AND NOT (COALESCE(OLD.is_deleted, false) = false AND COALESCE(NEW.is_deleted, false) = true)
       AND NEW.content IS NOT DISTINCT FROM OLD.content
       AND NEW.title IS NOT DISTINCT FROM OLD.title
       AND NEW.category IS NOT DISTINCT FROM OLD.category
       AND COALESCE(OLD.is_deleted, false) = COALESCE(NEW.is_deleted, false) THEN
        RETURN NEW;  -- không đổi nội dung: không cấp số mới
    END IF;

    IF v_mode = 'major' THEN
        v_cur_major := v_cur_major + 1;
        v_cur_minor := 0;
    ELSE
        v_cur_minor := v_cur_minor + 1;
    END IF;
    NEW.major_version := v_cur_major;
    NEW.minor_version := v_cur_minor;
    NEW.version_string := v_cur_major || '.' || v_cur_minor;
    NEW.updated_at := now();
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION eas.fn_after_regulation_versioning()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'eas'
AS $function$
DECLARE
  v_action text; v_summary text; v_major int; v_minor int; v_ver text; v_reg uuid; v_title text; v_content text;
  v_mode text := COALESCE(current_setting('eas.version_bump', true), '');
BEGIN
  IF v_mode = 'none' THEN
    RETURN COALESCE(NEW, OLD);
  END IF;
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
    SELECT COALESCE(global_major_version, 1), COALESCE(global_minor_version, 0) INTO v_major, v_minor
      FROM eas.ai_system_state WHERE id = 1;
    IF v_mode = 'major' THEN v_major := v_major + 1; v_minor := 0; ELSE v_minor := v_minor + 1; END IF;
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
$function$;

-- 2. Đưa về v1.0 (chỉ làm một lần: đánh dấu bằng bảng 3 chưa tồn tại) ------------------------------------------
DO $reset$
BEGIN
  IF to_regclass('eas.regulation_keep_decision') IS NULL THEN
    PERFORM set_config('eas.version_bump', 'none', true);
    UPDATE eas.company_regulations SET version_string = '1.0', major_version = 1, minor_version = 0
      WHERE NOT is_deleted;
    UPDATE eas.ai_system_state
      SET global_major_version = 1, global_minor_version = 0,
          active_regulation_version = '1.0', target_regulation_version = '1.0',
          applied_policy = CASE WHEN applied_policy IS NULL THEN NULL
                                ELSE jsonb_set(applied_policy, '{version}', '"v1.0"') END,
          updated_at = now()
      WHERE id = 1;
    PERFORM set_config('eas.version_bump', '', true);
  END IF;
END
$reset$;

-- 3. Quyết định giữ / bỏ điều cũ ---------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.regulation_keep_decision (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  new_code text NOT NULL CHECK (length(btrim(new_code)) BETWEEN 1 AND 30),
  old_code text NOT NULL CHECK (length(btrim(old_code)) BETWEEN 1 AND 30),
  old_sha char(64) NOT NULL CHECK (old_sha ~ '^[0-9a-f]{64}$'),
  old_text text,
  decided_by varchar(5) NOT NULL CHECK (decided_by IN ('AI', 'ADMIN')),
  reason text,
  created_by uuid REFERENCES eas.app_user(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (new_code, old_sha)
);
REVOKE ALL ON eas.regulation_keep_decision FROM PUBLIC;
GRANT SELECT, INSERT, DELETE ON eas.regulation_keep_decision TO eas_api;
GRANT SELECT ON eas.regulation_keep_decision TO eas_worker, eas_backup;
ALTER TABLE eas.regulation_keep_decision ENABLE ROW LEVEL SECURITY;
DO $pol$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='eas' AND tablename='regulation_keep_decision'
                 AND policyname='backend_read') THEN
    CREATE POLICY backend_read ON eas.regulation_keep_decision FOR SELECT TO eas_api, eas_worker USING (true);
    CREATE POLICY backend_insert ON eas.regulation_keep_decision FOR INSERT TO eas_api WITH CHECK (true);
    CREATE POLICY backend_delete ON eas.regulation_keep_decision FOR DELETE TO eas_api USING (true);
    CREATE POLICY backup_read ON eas.regulation_keep_decision FOR SELECT TO eas_backup USING (true);
  END IF;
END
$pol$;

-- 4. Lần đăng nhập ------------------------------------------------------------------------------------------------
ALTER TABLE eas.app_user ADD COLUMN IF NOT EXISTS last_login_at timestamptz;
ALTER TABLE eas.app_user ADD COLUMN IF NOT EXISTS previous_login_at timestamptz;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;

SELECT to_regclass('eas.regulation_keep_decision') AS regulation_keep_decision,
       (SELECT global_major_version || '.' || global_minor_version FROM eas.ai_system_state WHERE id = 1) AS version;
