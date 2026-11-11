-- =============================================================================
-- ROLLBACK của database/migrations/11_cleanup_duplicates_and_admin_split.sql
-- Chỉ dùng khi cần quay lại. Dán toàn bộ vào Supabase SQL Editor → Run.
-- Một transaction; sai bất kỳ bước nào thì không có gì thay đổi.
--
-- Khôi phục: bảng/view/function trùng về schema eas, user_id cũ của
-- user_permissions/user_leave_and_trips, hàm quyền cũ, vai trò quản trị về tài
-- khoản đã bị thu hồi. Tài khoản <tên>+admin@eas.com (nếu bản cũ từng tạo) vẫn bị
-- KHOÁ (is_active=false), không xoá, vì có thể đã phát sinh nhật ký audit.
-- KHÔNG khôi phục quyền anon/authenticated (đó là lỗ hổng, không phải tính năng).
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL client_min_messages = warning;

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('eas_deprecated.migration_marker') IS NULL
     OR NOT EXISTS (SELECT 1 FROM eas_deprecated.migration_marker WHERE name LIKE '2026-11-03\_01%') THEN
    RAISE EXCEPTION 'Không thấy dấu migration 2026-11-03_01: chưa chạy migration hoặc đã rollback.';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;
SELECT eas.lock_security(true);

-- 1. Gỡ ràng buộc loại tài khoản
DROP TRIGGER IF EXISTS b_account_role_type ON eas.role_membership;
DROP TRIGGER IF EXISTS b_account_type_change ON eas.app_user;
DROP FUNCTION IF EXISTS eas.enforce_account_role_type();
DROP FUNCTION IF EXISTS eas.guard_account_type_change();

-- 2. Trả vai trò về như trước migration
CREATE TEMP TABLE _marker ON COMMIT DROP AS
SELECT applied_at FROM eas_deprecated.migration_marker WHERE name LIKE '2026-11-03\_01%';

DO $roles$
BEGIN
  IF to_regclass('eas.admin_account') IS NULL THEN RETURN; END IF;

  -- Vai trò migration đã thu hồi (đúng thời điểm transaction của migration).
  UPDATE eas.role_membership m SET revoked_at = NULL
  FROM _marker k
  WHERE m.revoked_at = k.applied_at;  -- mọi lần chạy migration

  -- Tài khoản quản trị tạo mới: thu hồi vai trò và khoá.
  UPDATE eas.role_membership m SET revoked_at = now()
  WHERE m.revoked_at IS NULL
    AND m.user_id IN (SELECT user_id FROM eas.admin_account WHERE employee_user_id IS NOT NULL);
  UPDATE eas.app_user u SET is_active = false, auth_version = u.auth_version + 1
  WHERE u.id IN (SELECT user_id FROM eas.admin_account WHERE employee_user_id IS NOT NULL);
END
$roles$;

-- Kiểm tra ngay các ràng buộc deferred (manager_acyclic) trước khi đổi cấu trúc app_user.
SET CONSTRAINTS ALL IMMEDIATE;
DROP TABLE IF EXISTS eas.admin_account;
ALTER TABLE eas.app_user DROP CONSTRAINT IF EXISTS app_user_account_type_check;
ALTER TABLE eas.app_user DROP COLUMN IF EXISTS account_type;

-- 3. Đưa bảng/view/function trùng về schema eas
DO $back$
DECLARE o text; f regprocedure;
BEGIN
  FOREACH o IN ARRAY ARRAY['departments', 'roles', 'users', 'role_permissions',
                           'workflow_categories', 'request_templates', 'requests'] LOOP
    IF to_regclass('eas_deprecated.' || o) IS NOT NULL AND to_regclass('eas.' || o) IS NULL THEN
      EXECUTE format('ALTER TABLE eas_deprecated.%I SET SCHEMA eas', o);
    END IF;
  END LOOP;
  FOREACH o IN ARRAY ARRAY['v_users_management', 'v_request_templates_full'] LOOP
    IF to_regclass('eas_deprecated.' || o) IS NOT NULL AND to_regclass('eas.' || o) IS NULL THEN
      EXECUTE format('ALTER VIEW eas_deprecated.%I SET SCHEMA eas', o);
    END IF;
  END LOOP;
  FOR f IN
    SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'eas_deprecated'
  LOOP
    EXECUTE format('ALTER FUNCTION %s SET SCHEMA eas', f);
  END LOOP;
END
$back$;

-- 4. user_permissions / user_leave_and_trips trỏ lại eas.users
DO $repoint$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['user_permissions', 'user_leave_and_trips'] LOOP
    CONTINUE WHEN to_regclass('eas.' || t) IS NULL OR to_regclass('eas.users') IS NULL;
    EXECUTE format('ALTER TABLE eas.%I DROP CONSTRAINT IF EXISTS %I', t, t || '_app_user_fk');
    EXECUTE format(
      'UPDATE eas.%I s SET user_id = u.id FROM eas.app_user a JOIN eas.users u ON lower(btrim(u.email)) = a.email WHERE s.user_id = a.id',
      t);
    IF to_regclass('eas_deprecated.' || t || '_unmapped') IS NOT NULL THEN
      EXECUTE format('INSERT INTO eas.%I SELECT * FROM eas_deprecated.%I ON CONFLICT DO NOTHING', t, t || '_unmapped');
      EXECUTE format('DROP TABLE eas_deprecated.%I', t || '_unmapped');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = ('eas.' || t)::regclass AND conname = t || '_user_id_fkey') THEN
      EXECUTE format(
        'ALTER TABLE eas.%I ADD CONSTRAINT %I FOREIGN KEY (user_id) REFERENCES eas.users(id) ON DELETE CASCADE NOT VALID',
        t, t || '_user_id_fkey');
    END IF;
  END LOOP;
END
$repoint$;

-- 5. Hàm quyền module bản gốc (đọc eas.users/eas.roles/eas.role_permissions)
DO $fn$
BEGIN
  IF to_regclass('eas.modules') IS NULL OR to_regclass('eas.users') IS NULL THEN RETURN; END IF;
  EXECUTE $body$
    CREATE OR REPLACE FUNCTION eas.get_effective_user_permissions(p_user_id uuid)
    RETURNS TABLE(module_code text, module_name text, group_name text, route_path text,
                  icon_name text, target_app text, can_view boolean, can_create boolean,
                  can_update boolean, can_delete boolean, show_on_sidebar boolean,
                  permission_source text)
    LANGUAGE sql STABLE
    AS $q$
      SELECT m.code, m.name, m.group_name, m.route_path, m.icon_name, m.target_app,
             COALESCE(up.can_view, rp.can_view, false),
             COALESCE(up.can_create, rp.can_create, false),
             COALESCE(up.can_update, rp.can_update, false),
             COALESCE(up.can_delete, rp.can_delete, false),
             (COALESCE(up.can_view, rp.can_view, false) OR COALESCE(up.can_create, rp.can_create, false)
              OR COALESCE(up.can_update, rp.can_update, false) OR COALESCE(up.can_delete, rp.can_delete, false)),
             CASE WHEN up.id IS NOT NULL THEN 'USER_OVERRIDE' ELSE 'ROLE_DEFAULT' END
      FROM eas.modules m
      LEFT JOIN eas.users u ON u.id = p_user_id
      LEFT JOIN eas.role_permissions rp ON rp.role_id = u.role_id AND rp.module_code = m.code
      LEFT JOIN eas.user_permissions up ON up.user_id = u.id AND up.module_code = m.code
      ORDER BY m.sort_order ASC
    $q$
  $body$;
END
$fn$;
DROP TABLE IF EXISTS eas.role_module_permission;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
DELETE FROM eas_deprecated.migration_marker WHERE name LIKE '2026-11-03\_01%';

RESET ROLE;
COMMIT;

SELECT 'rollback 11 hoàn tất' AS result,
       (SELECT count(*) FROM eas.app_user WHERE is_active) AS active_users,
       to_regclass('eas.users') IS NOT NULL AS users_restored;
