-- Rollback của database/migrations/15_schema_v2_consolidate.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Một transaction; chạy lại an toàn.
--
-- Khôi phục đúng giá trị cũ từ eas_archive.dropped_column_value và dời bảng về eas, để
-- bản code trước 04/11/2026 chạy được. CỐ Ý KHÔNG khôi phục:
--   * 9 view bí danh (không code nào dùng);
--   * trigger trg_after_mock_api_toggle (ghi đúp nhật ký mỗi lần bật/tắt API).
-- Các dòng đã chép vào admin_event giữ nguyên (bảng chỉ-ghi-thêm, chuỗi băm).
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

DO $restore$
DECLARE
  c record;
  i record;
  col_type text;
  col_default text;
BEGIN
  IF to_regnamespace('eas_archive') IS NULL THEN
    RAISE NOTICE 'Không có eas_archive: migration 15 chưa chạy, không làm gì.';
    RETURN;
  END IF;

  -- 1. Cột đã bỏ: thêm lại hết, rồi mới điền đúng giá trị đã lưu (ALTER TABLE không chạy
  --    được sau UPDATE trên bảng có trigger ràng buộc trì hoãn).
  FOR c IN
    SELECT * FROM (VALUES
      ('request', 'risk_weight'), ('request', 'approval_level'),
      ('workflow_instance', 'risk_weight'), ('workflow_instance', 'approval_level'),
      ('config_release', 'risk_weight'), ('config_release', 'approval_level'),
      ('app_user', 'username')
    ) AS t(tbl, col)
  LOOP
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'eas' AND table_name = c.tbl AND column_name = c.col) THEN
      IF c.col = 'username' THEN
        col_type := 'varchar'; col_default := NULL;
      ELSE
        col_type := 'smallint NOT NULL CHECK (' || c.col || ' BETWEEN 1 AND 5)';
        col_default := CASE c.col WHEN 'risk_weight' THEN '3' ELSE '1' END;
      END IF;
      EXECUTE format('ALTER TABLE eas.%I ADD COLUMN %I %s %s', c.tbl, c.col, col_type,
                     CASE WHEN col_default IS NULL THEN '' ELSE 'DEFAULT ' || col_default END);
    END IF;
  END LOOP;

  ALTER TABLE eas.config_release DISABLE TRIGGER release_guard;
  ALTER TABLE eas.workflow_instance DISABLE TRIGGER instance_guard;
  ALTER TABLE eas.request DISABLE TRIGGER request_guard;
  FOR c IN
    SELECT DISTINCT table_name AS tbl, column_name AS col FROM eas_archive.dropped_column_value
  LOOP
    EXECUTE format(
      'UPDATE eas.%1$I t SET %2$I = (a.value #>> ''{}'')::%3$s
         FROM eas_archive.dropped_column_value a
        WHERE a.table_name = %1$L AND a.column_name = %2$L AND a.row_id = t.id::text
          AND a.value IS NOT NULL AND a.value <> ''null''::jsonb
          AND t.%2$I IS DISTINCT FROM (a.value #>> ''{}'')::%3$s',
      c.tbl, c.col, CASE WHEN c.col = 'username' THEN 'varchar' ELSE 'smallint' END);
  END LOOP;
  SET CONSTRAINTS ALL IMMEDIATE;
  ALTER TABLE eas.config_release ENABLE TRIGGER release_guard;
  ALTER TABLE eas.workflow_instance ENABLE TRIGGER instance_guard;
  ALTER TABLE eas.request ENABLE TRIGGER request_guard;

  -- 2. Bảng đã dời.
  IF to_regclass('eas_archive.workflow_categories_eas') IS NOT NULL AND to_regclass('eas.workflow_categories') IS NULL THEN
    ALTER TABLE eas_archive.workflow_categories_eas SET SCHEMA eas;
    ALTER TABLE eas.workflow_categories_eas RENAME TO workflow_categories;
    FOR i IN SELECT ic.relname FROM pg_index x JOIN pg_class ic ON ic.oid = x.indexrelid
             WHERE x.indrelid = 'eas.workflow_categories'::regclass AND ic.relname LIKE '%\_eas' LOOP
      EXECUTE format('ALTER INDEX eas.%I RENAME TO %I', i.relname, left(i.relname, length(i.relname) - 4));
    END LOOP;
  END IF;
  IF to_regclass('eas_archive.system_versions_changelog') IS NOT NULL AND to_regclass('eas.system_versions_changelog') IS NULL THEN
    ALTER TABLE eas_archive.system_versions_changelog SET SCHEMA eas;
  END IF;
  IF to_regclass('eas_archive.work_handover') IS NOT NULL AND to_regclass('eas.work_handover') IS NULL THEN
    DELETE FROM eas.approval_delegation d
     USING eas_archive.work_handover h WHERE h.id = d.id;
    ALTER TABLE eas_archive.work_handover SET SCHEMA eas;
  END IF;
END
$restore$;

-- 3. Trigger chống chồng lấn của work_handover (như migration 14).
CREATE OR REPLACE FUNCTION eas.guard_work_handover_overlap() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, eas AS $f$
BEGIN
  IF NEW.revoked_at IS NULL AND EXISTS (
    SELECT 1 FROM eas.work_handover h
    WHERE h.from_user_id = NEW.from_user_id AND h.id <> NEW.id AND h.revoked_at IS NULL
      AND (h.scope = NEW.scope OR h.scope = 'ALL' OR NEW.scope = 'ALL')
      AND tstzrange(h.starts_at, h.ends_at) && tstzrange(NEW.starts_at, NEW.ends_at)
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23P01', MESSAGE = 'Overlapping work handover';
  END IF;
  RETURN NEW;
END
$f$;
DO $handover_trigger$
BEGIN
  IF to_regclass('eas.work_handover') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS work_handover_no_overlap ON eas.work_handover;
    CREATE TRIGGER work_handover_no_overlap
      BEFORE INSERT OR UPDATE ON eas.work_handover
      FOR EACH ROW EXECUTE FUNCTION eas.guard_work_handover_overlap();
  END IF;
END
$handover_trigger$;

-- 4. Cột thêm vào approval_delegation.
ALTER TABLE eas.approval_delegation
  DROP CONSTRAINT IF EXISTS approval_delegation_source_check,
  DROP CONSTRAINT IF EXISTS approval_delegation_scope_check,
  DROP COLUMN IF EXISTS created_by,
  DROP COLUMN IF EXISTS source_request_id,
  DROP COLUMN IF EXISTS source,
  DROP COLUMN IF EXISTS scope;


RESET ROLE;

-- 5. Trả tên schema cũ (chạy bằng postgres: cần quyền CREATE trên database) (giữ bảng dropped_column_value bên trong để tra cứu).
DO $rename$
BEGIN
  IF to_regnamespace('eas_archive') IS NOT NULL AND to_regnamespace('eas_deprecated') IS NULL THEN
    ALTER SCHEMA eas_archive RENAME TO eas_deprecated;
  END IF;
END
$rename$;

COMMIT;
