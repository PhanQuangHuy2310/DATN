-- =============================================================================
-- EAS — BOOTSTRAP ROLES & PREREQUISITES FOR FRESH OR EXISTING SUPABASE DB ([M1])
-- =============================================================================
-- CÁCH CHẠY:
--   1. Trên Supabase Dashboard → SQL Editor: Dán TOÀN BỘ nội dung file này → Run.
--      (Hoàn toàn tương thích chuẩn SQL của Supabase SQL Editor, không dùng
--       các meta-command \set, \echo, \ir của psql).
--   2. Script chạy trong 1 transaction và idempotent (chạy nhiều lần an toàn):
--      - Tạo đầy đủ các database roles bắt buộc (eas_migration, eas_api,
--        eas_worker, eas_privacy, eas_backup, eas_mock, anon, authenticated,
--        service_role) nếu chưa tồn tại.
--      - Gán quyền thành viên eas_migration cho user hiện tại (postgres) để
--        thỏa điều kiện tiên quyết của các bản nâng cấp Migration 11 -> 18.
--      - Nếu các bảng lõi eas.department và eas.app_user đã được tạo (sau khi
--        chạy 00_eas_supabase_schema.sql + 04 + 05), tự động đảm bảo phòng ban
--        BOD và tài khoản quản trị gốc admin@eas.com tồn tại trước khi chạy
--        Migration 11.
--
-- THỨ TỰ CHẠY CÁC FILE KHI DỰNG DATABASE MỚI TỪ ĐẦU TRÊN SUPABASE SQL EDITOR:
--   Bước 1: Chạy file này (database/install_fresh_db.sql) để tạo Roles.
--   Bước 2: database/EAS_Supabase_SQL/00_eas_supabase_schema.sql
--   Bước 3: database/migrations/04_current_schema_upgrade.sql
--           database/migrations/05_email_login_and_password_reset.sql
--           database/migrations/08_ai_auto_approval.sql
--   Bước 4: supabase/migrations/20261103_admin_full_upgrade.sql
--   Bước 5: Chạy lại file này (database/install_fresh_db.sql) để seed tối thiểu
--           admin@eas.com (hoặc chạy 01_demo_seed_DEV_ONLY.sql cho môi trường dev).
--   Bước 6: Chạy lần lượt database/migrations/09_*.sql -> 10 -> 11 -> 12 ->
--           13 -> 14 -> 15 -> 16_*.sql
--   Bước 7: database/mock_enterprise_sql/00_mock_enterprise_schemas.sql
--           database/mock_enterprise_sql/01_mock_seed_DEV_ONLY.sql
--           database/mock_enterprise_sql/migrations/001_*.sql -> 005_*.sql
--   Bước 8: database/migrations/17_external_systems_via_api.sql
--           database/migrations/18_role_module_permission_write_grant.sql
--           database/migrations/repair_stuck_requests.sql
-- =============================================================================

BEGIN;

-- 1. Khởi tạo các database roles bắt buộc (nếu chưa có) và gán eas_migration
DO $roles$
DECLARE
  r text;
BEGIN
  FOREACH r IN ARRAY ARRAY[
    'anon',
    'authenticated',
    'service_role',
    'eas_migration',
    'eas_api',
    'eas_worker',
    'eas_privacy',
    'eas_backup',
    'eas_mock'
  ]
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN', r);
    END IF;
  END LOOP;

  EXECUTE format('GRANT eas_migration TO %I', current_user);
END
$roles$;

-- 2. Nếu bảng eas.department và eas.app_user đã tồn tại, đảm bảo tài khoản
--    quản trị gốc admin@eas.com tồn tại để vượt qua kiểm tra của Migration 11
DO $seed_admin$
DECLARE
  v_dept_id uuid;
  v_admin_id uuid;
  v_has_email boolean;
  v_has_account_type boolean;
BEGIN
  IF to_regclass('eas.department') IS NULL OR to_regclass('eas.app_user') IS NULL THEN
    RAISE NOTICE 'Schema eas chưa được tạo. Hãy chạy 00_eas_supabase_schema.sql tiếp theo.';
    RETURN;
  END IF;

  SELECT id INTO v_dept_id FROM eas.department WHERE code = 'BOD' LIMIT 1;
  IF v_dept_id IS NULL THEN
    SELECT id INTO v_dept_id FROM eas.department ORDER BY created_at ASC LIMIT 1;
  END IF;
  IF v_dept_id IS NULL THEN
    INSERT INTO eas.department (code, name, is_active)
    VALUES ('BOD', 'Ban Giám Đốc & Quản Trị Hệ Thống', true)
    RETURNING id INTO v_dept_id;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'eas' AND table_name = 'app_user' AND column_name = 'email'
  ) INTO v_has_email;

  IF NOT v_has_email THEN
    RAISE NOTICE 'Bảng eas.app_user chưa chạy migration 05 (chưa có cột email). Bỏ qua bước seed admin@eas.com.';
    RETURN;
  END IF;

  SELECT id INTO v_admin_id FROM eas.app_user WHERE lower(email) = 'admin@eas.com' LIMIT 1;
  IF v_admin_id IS NULL THEN
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'eas' AND table_name = 'app_user' AND column_name = 'account_type'
    ) INTO v_has_account_type;

    IF v_has_account_type THEN
      INSERT INTO eas.app_user (
        email,
        display_name,
        department_id,
        password_hash,
        is_active,
        must_change_password,
        auth_version,
        account_type
      )
      VALUES (
        'admin@eas.com',
        'System Administrator',
        v_dept_id,
        'pbkdf2_sha256$720000$freshdbinstall$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        true,
        true,
        1,
        'ADMIN'
      )
      RETURNING id INTO v_admin_id;
    ELSE
      INSERT INTO eas.app_user (
        email,
        display_name,
        department_id,
        password_hash,
        is_active,
        must_change_password,
        auth_version
      )
      VALUES (
        'admin@eas.com',
        'System Administrator',
        v_dept_id,
        'pbkdf2_sha256$720000$freshdbinstall$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        true,
        true,
        1
      )
      RETURNING id INTO v_admin_id;
    END IF;
  END IF;

  IF to_regclass('eas.admin_account') IS NOT NULL THEN
    INSERT INTO eas.admin_account (user_id)
    VALUES (v_admin_id)
    ON CONFLICT (user_id) DO NOTHING;
  END IF;

  IF to_regclass('eas.role_membership') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM eas.role_membership
      WHERE user_id = v_admin_id AND role = 'OPS_ADMIN' AND revoked_at IS NULL
    ) THEN
      INSERT INTO eas.role_membership (user_id, role, dept_id, granted_by)
      VALUES (v_admin_id, 'OPS_ADMIN', NULL, v_admin_id);
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM eas.role_membership
      WHERE user_id = v_admin_id AND role = 'POLICY_ADMIN' AND revoked_at IS NULL
    ) THEN
      INSERT INTO eas.role_membership (user_id, role, dept_id, granted_by)
      VALUES (v_admin_id, 'POLICY_ADMIN', NULL, v_admin_id);
    END IF;
  END IF;

  RAISE NOTICE 'Hoàn tất kiểm tra/khởi tạo roles và tài khoản admin@eas.com (id=%).', v_admin_id;
END
$seed_admin$;

COMMIT;
