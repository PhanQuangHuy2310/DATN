-- Rollback 27: trả cách đánh số cũ (thêm/gỡ tăng số đầu, sửa tăng số sau), xoá bảng quyết định giữ/bỏ và hai cột
-- lần đăng nhập. Không khôi phục số phiên bản trước khi đưa về v1.0 (lịch sử phiên bản vẫn còn trong
-- eas.regulation_versions).

BEGIN;
SELECT eas.lock_security(true);

CREATE OR REPLACE FUNCTION eas.fn_before_regulation_versioning()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_cur_major INT;
    v_cur_minor INT;
BEGIN
    SELECT COALESCE(global_major_version, 1), COALESCE(global_minor_version, 0)
    INTO v_cur_major, v_cur_minor
    FROM eas.ai_system_state
    WHERE id = 1;

    IF TG_OP = 'INSERT' THEN
        v_cur_major := v_cur_major + 1;
        v_cur_minor := 0;
        NEW.major_version := v_cur_major;
        NEW.minor_version := v_cur_minor;
        NEW.version_string := v_cur_major || '.' || v_cur_minor;
        NEW.updated_at := now();
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF COALESCE(OLD.is_deleted, false) = false AND COALESCE(NEW.is_deleted, false) = true THEN
            v_cur_major := v_cur_major + 1;
            v_cur_minor := 0;
            NEW.major_version := v_cur_major;
            NEW.minor_version := v_cur_minor;
            NEW.version_string := v_cur_major || '.' || v_cur_minor;
            NEW.updated_at := now();
        ELSIF NEW.content IS DISTINCT FROM OLD.content OR NEW.title IS DISTINCT FROM OLD.title OR NEW.category IS DISTINCT FROM OLD.category THEN
            v_cur_minor := v_cur_minor + 1;
            NEW.major_version := v_cur_major;
            NEW.minor_version := v_cur_minor;
            NEW.version_string := v_cur_major || '.' || v_cur_minor;
            NEW.updated_at := now();
        END IF;
        RETURN NEW;
    END IF;
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

  UPDATE eas.ai_system_state
  SET global_major_version = v_major, global_minor_version = v_minor,
      target_regulation_version = v_ver, updated_at = now()
  WHERE id = 1;
  RETURN COALESCE(NEW, OLD);
END
$function$;

DROP TABLE IF EXISTS eas.regulation_keep_decision;
ALTER TABLE eas.app_user DROP COLUMN IF EXISTS last_login_at;
ALTER TABLE eas.app_user DROP COLUMN IF EXISTS previous_login_at;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;
