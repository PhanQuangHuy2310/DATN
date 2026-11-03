-- =============================================================================
-- Data fix 2026-11-03 — XOÁ HẲN các tài khoản quản trị phụ (<tên>+admin@eas.com)
-- Chạy SAU migration 11. Chỉ giữ lại admin@eas.com.
-- Dán toàn bộ vào Supabase SQL Editor → Run. Một transaction; chạy lại an toàn.
-- KHÔNG hoàn tác được: chỉ xoá tài khoản ADMIN đã bị khoá và chưa từng phát sinh
-- dữ liệu nghiệp vụ/audit (nếu có, script dừng và không xoá gì).
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('eas.admin_account') IS NULL THEN
    RAISE EXCEPTION 'Chưa chạy migration 11 (thiếu eas.admin_account).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;
SELECT eas.lock_security(true);

CREATE TEMP TABLE _victim ON COMMIT DROP AS
SELECT id, email FROM eas.app_user
WHERE account_type = 'ADMIN' AND email <> 'admin@eas.com' AND NOT is_active;

-- An toàn: ngoài role_membership và admin_account, không bảng nào được tham chiếu tới.
DO $refs$
DECLARE r record; n bigint;
BEGIN
  FOR r IN
    SELECT cl.oid::regclass AS tbl, a.attname AS col
    FROM pg_constraint con
    JOIN pg_class cl ON cl.oid = con.conrelid
    JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1]
    WHERE con.contype = 'f' AND con.confrelid = 'eas.app_user'::regclass
      AND cl.oid NOT IN ('eas.role_membership'::regclass, 'eas.admin_account'::regclass)
  LOOP
    EXECUTE format('SELECT count(*) FROM %s WHERE %I IN (SELECT id FROM _victim)', r.tbl, r.col) INTO n;
    IF n > 0 THEN
      RAISE EXCEPTION 'Tài khoản cần xoá đang được tham chiếu ở %.% (% dòng): dừng, không xoá gì.', r.tbl, r.col, n;
    END IF;
  END LOOP;
END
$refs$;

DELETE FROM eas.admin_account WHERE user_id IN (SELECT id FROM _victim);
DELETE FROM eas.role_membership WHERE user_id IN (SELECT id FROM _victim);
DELETE FROM eas.app_user WHERE id IN (SELECT id FROM _victim);

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

DO $verify$
BEGIN
  IF EXISTS (SELECT 1 FROM eas.app_user WHERE account_type = 'ADMIN' AND email <> 'admin@eas.com') THEN
    RAISE EXCEPTION 'VERIFY: vẫn còn tài khoản ADMIN khác admin@eas.com (đang hoạt động?): kiểm tra tay.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM eas.admin_account a JOIN eas.app_user u ON u.id = a.user_id WHERE u.email = 'admin@eas.com') THEN
    RAISE EXCEPTION 'VERIFY: mất admin@eas.com';
  END IF;
END
$verify$;

RESET ROLE;
COMMIT;

SELECT u.email AS admin_account, u.display_name, u.is_active,
       (SELECT string_agg(DISTINCT m.role, ', ') FROM eas.role_membership m
         WHERE m.user_id = u.id AND m.revoked_at IS NULL) AS active_roles
FROM eas.admin_account a JOIN eas.app_user u ON u.id = a.user_id
ORDER BY u.email;
