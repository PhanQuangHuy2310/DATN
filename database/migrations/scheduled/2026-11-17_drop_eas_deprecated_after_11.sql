-- =============================================================================
-- Lịch 2026-11-17 — XOÁ HẲN schema eas_deprecated (không hoàn tác được)
-- Chỉ chạy khi hệ thống đã chạy ổn định ít nhất 14 ngày sau migration 11_cleanup_duplicates_and_admin_split.sql.
-- Dán toàn bộ vào Supabase SQL Editor → Run. Chạy sớm hơn 14 ngày: script tự bỏ qua.
-- Nên backup trước: Supabase Dashboard → Database → Backups.
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $drop$
DECLARE applied timestamptz; deps bigint;
BEGIN
  IF to_regnamespace('eas_deprecated') IS NULL THEN
    RAISE NOTICE 'Không có schema eas_deprecated: đã xoá trước đó, không làm gì.';
    RETURN;
  END IF;
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres).';
  END IF;

  SELECT max(applied_at) INTO applied FROM eas_deprecated.migration_marker WHERE name LIKE '2026-11-03\_01%';
  IF applied IS NULL THEN
    RAISE NOTICE 'Không thấy dấu migration 11: không làm gì.';
    RETURN;
  END IF;
  IF applied > now() - interval '14 days' THEN
    RAISE NOTICE 'Chưa đủ 14 ngày (áp dụng lúc %). Không làm gì; chạy lại sau %.', applied, applied + interval '14 days';
    RETURN;
  END IF;

  -- An toàn: không object nào ngoài eas_deprecated còn phụ thuộc vào nó.
  SELECT count(*) INTO deps
  FROM pg_depend d
  JOIN pg_class rc ON rc.oid = d.refobjid AND d.refclassid = 'pg_class'::regclass
  JOIN pg_namespace rn ON rn.oid = rc.relnamespace AND rn.nspname = 'eas_deprecated'
  LEFT JOIN pg_class oc ON oc.oid = d.objid AND d.classid = 'pg_class'::regclass
  LEFT JOIN pg_namespace onn ON onn.oid = oc.relnamespace
  LEFT JOIN pg_constraint con ON con.oid = d.objid AND d.classid = 'pg_constraint'::regclass
  LEFT JOIN pg_class cc ON cc.oid = con.conrelid
  LEFT JOIN pg_namespace cn ON cn.oid = cc.relnamespace
  LEFT JOIN pg_rewrite rw ON rw.oid = d.objid AND d.classid = 'pg_rewrite'::regclass
  LEFT JOIN pg_class vc ON vc.oid = rw.ev_class
  LEFT JOIN pg_namespace vn ON vn.oid = vc.relnamespace
  WHERE d.deptype NOT IN ('i', 'a')
    AND COALESCE(onn.nspname, cn.nspname, vn.nspname) IS NOT NULL
    AND COALESCE(onn.nspname, cn.nspname, vn.nspname) NOT IN ('eas_deprecated', 'pg_toast');
  IF deps > 0 THEN
    RAISE EXCEPTION 'Còn % object ngoài eas_deprecated phụ thuộc vào nó: không xoá.', deps;
  END IF;

  EXECUTE 'SET LOCAL ROLE eas_migration';
  EXECUTE 'DROP SCHEMA eas_deprecated CASCADE';
  RAISE NOTICE 'Đã xoá schema eas_deprecated.';
END
$drop$;

RESET ROLE;
COMMIT;

SELECT to_regnamespace('eas_deprecated') IS NULL AS eas_deprecated_dropped;
