-- =============================================================================
-- 11 — Dọn bảng trùng chức năng + tách tài khoản quản trị (2026-11-03)
-- Kế hoạch: plans/active/2026-11-03_db_cleanup_admin_split.md (EAS-PLAN-2026-11-03-01)
--
-- CÁCH CHẠY: Supabase Dashboard → SQL Editor → dán TOÀN BỘ file → Run.
--   * Chạy bằng role mặc định của SQL Editor (postgres). Toàn bộ nằm trong 1
--     transaction: nếu bất kỳ kiểm tra nào sai, KHÔNG có gì bị thay đổi.
--   * Chạy lại lần 2 an toàn (idempotent): các bước đã làm sẽ được bỏ qua.
--   * Không xoá dữ liệu: bảng trùng được CHUYỂN sang schema eas_deprecated
--     (khôi phục bằng rollback/11_cleanup_duplicates_and_admin_split_rollback.sql).
--     Xoá hẳn sau 2 tuần bằng scheduled/2026-11-17_drop_eas_deprecated_after_11.sql.
--
-- NỘI DUNG
--   1. Gom quyền sở hữu mọi object trong schema eas về eas_migration.
--   2. Thu hồi quyền của anon/authenticated trên schema eas (least privilege).
--   3. Quyền module gắn với danh tính lõi: role_module_permission (theo eas.role),
--      user_permissions/user_leave_and_trips trỏ sang eas.app_user,
--      viết lại eas.get_effective_user_permissions.
--   4. Chuyển bảng trùng sang eas_deprecated: users, departments, requests, roles,
--      role_permissions, request_templates, workflow_categories (+ view/function
--      chỉ phục vụ chúng).
--   5. Tách quản trị: app_user.account_type + bảng eas.admin_account. Chỉ
--      admin@eas.com là tài khoản quản trị; mọi tài khoản khác bị thu hồi
--      OPS_ADMIN/POLICY_ADMIN/AUDITOR (vai trò nghiệp vụ giữ nguyên).
--   6. Trigger chặn trộn vai trò quản trị và vai trò nghiệp vụ trên cùng tài khoản.
--   7. Tự kiểm tra; sai thì ROLLBACK toàn bộ.
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = 0;
SET LOCAL client_min_messages = warning;

-- ---------------------------------------------------------------------------
-- 0. Điều kiện tiên quyết
-- ---------------------------------------------------------------------------
DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres). current_user=%', current_user;
  END IF;
  IF to_regclass('eas.app_user') IS NULL OR to_regclass('eas.role_membership') IS NULL
     OR to_regclass('eas.role') IS NULL THEN
    RAISE EXCEPTION 'Thiếu bảng lõi của schema eas: sai database?';
  END IF;
END
$pre$;

-- ---------------------------------------------------------------------------
-- 1. Quyền sở hữu: mọi bảng/view/function trong eas về eas_migration
--    (owner không bị RLS chặn, nên các bước dữ liệu bên dưới thấy đủ dòng).
-- ---------------------------------------------------------------------------
DO $own$
DECLARE o record;
BEGIN
  FOR o IN
    SELECT c.oid::regclass AS obj, c.relkind
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'eas' AND c.relkind IN ('r', 'p', 'v', 'm')
      AND pg_get_userbyid(c.relowner) <> 'eas_migration'
      AND pg_has_role(current_user, c.relowner, 'MEMBER')
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO eas_migration',
                   CASE o.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW' ELSE 'TABLE' END,
                   o.obj);
  END LOOP;
  FOR o IN
    SELECT p.oid::regprocedure AS obj
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'eas' AND pg_get_userbyid(p.proowner) <> 'eas_migration'
      AND pg_has_role(current_user, p.proowner, 'MEMBER')
  LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO eas_migration', o.obj);
  END LOOP;
END
$own$;

-- ---------------------------------------------------------------------------
-- 2. Least privilege: anon/authenticated không được chạm vào schema eas
--    (frontend/mobile không gọi Supabase trực tiếp; mọi truy cập qua api_core).
-- ---------------------------------------------------------------------------
DO $sec$
DECLARE
  orig text := current_user;
  o record;
  d text;
  r text;
  skipped int := 0;
BEGIN
  -- Từng object mà anon/authenticated đang có quyền; thu hồi dưới danh nghĩa
  -- đúng grantor. Object ngoài tầm (grantor không với tới) chỉ cảnh báo.
  FOR o IN
    SELECT 'TABLE' AS kind, c.oid::regclass::text AS obj, pg_get_userbyid(a.grantor) AS grantor,
           pg_get_userbyid(a.grantee) AS grantee
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, LATERAL aclexplode(c.relacl) a
    WHERE n.nspname = 'eas' AND c.relkind IN ('r', 'p', 'v', 'm')
      AND pg_get_userbyid(a.grantee) IN ('anon', 'authenticated')
    UNION
    SELECT 'SEQUENCE', c.oid::regclass::text, pg_get_userbyid(a.grantor), pg_get_userbyid(a.grantee)
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, LATERAL aclexplode(c.relacl) a
    WHERE n.nspname = 'eas' AND c.relkind = 'S'
      AND pg_get_userbyid(a.grantee) IN ('anon', 'authenticated')
    UNION
    SELECT 'FUNCTION', p.oid::regprocedure::text, pg_get_userbyid(a.grantor), pg_get_userbyid(a.grantee)
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace, LATERAL aclexplode(p.proacl) a
    WHERE n.nspname = 'eas' AND pg_get_userbyid(a.grantee) IN ('anon', 'authenticated')
    UNION
    SELECT 'SCHEMA', 'eas', pg_get_userbyid(a.grantor), pg_get_userbyid(a.grantee)
    FROM pg_namespace n, LATERAL aclexplode(n.nspacl) a
    WHERE n.nspname = 'eas' AND pg_get_userbyid(a.grantee) IN ('anon', 'authenticated')
  LOOP
    IF NOT pg_has_role(current_user, o.grantor, 'MEMBER') THEN
      skipped := skipped + 1;
      CONTINUE;
    END IF;
    BEGIN
      EXECUTE format('SET LOCAL ROLE %I', o.grantor);
      EXECUTE format('REVOKE ALL ON %s %s FROM %I', o.kind, o.obj, o.grantee);
      EXECUTE format('SET LOCAL ROLE %I', orig);
    EXCEPTION WHEN insufficient_privilege THEN
      EXECUTE format('SET LOCAL ROLE %I', orig);
      skipped := skipped + 1;
    END;
  END LOOP;

  -- Không để object tạo sau tự cấp quyền cho anon/authenticated nữa.
  FOR d IN
    SELECT DISTINCT pg_get_userbyid(a.defaclrole)
    FROM pg_default_acl a JOIN pg_namespace n ON n.oid = a.defaclnamespace
    WHERE n.nspname = 'eas'
  LOOP
    CONTINUE WHEN NOT pg_has_role(current_user, d, 'MEMBER');
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
      CONTINUE WHEN NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA eas REVOKE ALL ON TABLES FROM %I', d, r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA eas REVOKE ALL ON SEQUENCES FROM %I', d, r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA eas REVOKE ALL ON FUNCTIONS FROM %I', d, r);
    END LOOP;
  END LOOP;

  IF skipped > 0 THEN
    RAISE WARNING '% quyền của anon/authenticated không thu hồi được từ SQL Editor (grantor ngoài tầm). RLS vẫn chặn dữ liệu.', skipped;
  END IF;
END
$sec$;

-- Schema cách ly cho bảng trùng (không ai ngoài owner truy cập).
CREATE SCHEMA IF NOT EXISTS eas_deprecated AUTHORIZATION eas_migration;
REVOKE ALL ON SCHEMA eas_deprecated FROM PUBLIC;
CREATE TABLE IF NOT EXISTS eas_deprecated.migration_marker (
  name       text PRIMARY KEY,
  applied_at timestamptz NOT NULL
);
ALTER TABLE eas_deprecated.migration_marker OWNER TO eas_migration;
-- now() = thời điểm transaction: rollback dùng để nhận ra đúng các dòng migration đã thu hồi.
-- Mỗi lần chạy ghi một dấu riêng (2026-11-03_01#<thời điểm>).
INSERT INTO eas_deprecated.migration_marker(name, applied_at)
VALUES ('2026-11-03_01#' || to_char(now() AT TIME ZONE 'UTC', 'YYYYMMDD"T"HH24MISSUS'), now())
ON CONFLICT (name) DO NOTHING;

COMMENT ON SCHEMA eas_deprecated IS
  'EAS 2026-11-03: bảng trùng chức năng được cách ly; xoá sau 2 tuần (scheduled/2026-11-17_drop_eas_deprecated_after_11.sql).';

-- Mọi bước còn lại chạy dưới quyền owner của schema eas.
SET LOCAL ROLE eas_migration;
SELECT eas.lock_security(true);

-- Ảnh chụp số liệu để tự kiểm tra cuối migration (bước 1–2 chưa đổi dữ liệu).
CREATE TEMP TABLE _mig_before ON COMMIT DROP AS
SELECT (SELECT count(*) FROM eas.request) AS requests,
       (SELECT count(*) FROM eas.role_membership) AS memberships,
       (SELECT count(*) FROM eas.audit_event) AS audit_events;


-- ---------------------------------------------------------------------------
-- 3. Quyền module gắn với danh tính lõi
-- ---------------------------------------------------------------------------
DO $perm$
BEGIN
  IF to_regclass('eas.modules') IS NULL THEN
    RAISE NOTICE 'Không có eas.modules: bỏ qua bước quyền module.';
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS eas.role_module_permission (
    role_code   varchar(24) NOT NULL REFERENCES eas.role(code) ON DELETE CASCADE,
    module_code text        NOT NULL REFERENCES eas.modules(code) ON DELETE CASCADE,
    can_view    boolean     NOT NULL DEFAULT false,
    can_create  boolean     NOT NULL DEFAULT false,
    can_update  boolean     NOT NULL DEFAULT false,
    can_delete  boolean     NOT NULL DEFAULT false,
    updated_at  timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (role_code, module_code)
  );
  COMMENT ON TABLE eas.role_module_permission IS
    'Quyền mặc định theo vai trò lõi (eas.role) trên từng module giao diện; thay thế eas.roles/eas.role_permissions.';

  -- Ma trận mặc định = đúng logic dự phòng đang chạy trong api_core (authn/views.py).
  INSERT INTO eas.role_module_permission(role_code, module_code, can_view, can_create, can_update, can_delete)
  SELECT r.code, m.code,
         CASE m.code
           WHEN 'dashboard' THEN true
           WHEN 'requests_workflows' THEN true
           WHEN 'org_chart' THEN true
           WHEN 'regulations' THEN true
           WHEN 'ai_engine' THEN adm
           WHEN 'system_versions' THEN adm OR r.code = 'AUDITOR'
           ELSE adm END,
         CASE m.code
           WHEN 'requests_workflows' THEN true
           ELSE adm END,
         CASE m.code
           WHEN 'requests_workflows' THEN adm OR r.code = 'APPROVER'
           ELSE adm END,
         adm
  FROM (SELECT code, code IN ('OPS_ADMIN', 'POLICY_ADMIN') AS adm FROM eas.role) r
  CROSS JOIN eas.modules m
  ON CONFLICT (role_code, module_code) DO NOTHING;

  ALTER TABLE eas.role_module_permission ENABLE ROW LEVEL SECURITY;
END
$perm$;

-- user_permissions / user_leave_and_trips: chuyển user_id từ eas.users sang eas.app_user
-- (ghép theo email). Dòng không ghép được được lưu ở eas_deprecated.*_unmapped.
DO $repoint$
DECLARE t text; fk text;
BEGIN
  FOREACH t IN ARRAY ARRAY['user_permissions', 'user_leave_and_trips'] LOOP
    CONTINUE WHEN to_regclass('eas.' || t) IS NULL;
    FOR fk IN
      SELECT conname FROM pg_constraint
      WHERE conrelid = ('eas.' || t)::regclass AND contype = 'f'
        AND confrelid <> 'eas.app_user'::regclass
        AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = ('eas.' || t)::regclass AND attname = 'user_id')]
    LOOP
      EXECUTE format('ALTER TABLE eas.%I DROP CONSTRAINT %I', t, fk);
    END LOOP;

    IF to_regclass('eas.users') IS NOT NULL THEN
      IF t = 'user_permissions' THEN
        -- Bỏ qua dòng sẽ trùng (user_id, module_code) sau khi ghép.
        UPDATE eas.user_permissions p SET user_id = a.id
        FROM eas.users u JOIN eas.app_user a ON a.email = lower(btrim(u.email))
        WHERE p.user_id = u.id AND p.user_id <> a.id
          AND NOT EXISTS (SELECT 1 FROM eas.user_permissions x WHERE x.user_id = a.id AND x.module_code = p.module_code);
      ELSE
        UPDATE eas.user_leave_and_trips l SET user_id = a.id
        FROM eas.users u JOIN eas.app_user a ON a.email = lower(btrim(u.email))
        WHERE l.user_id = u.id AND l.user_id <> a.id;
      END IF;
    END IF;

    EXECUTE format('CREATE TABLE IF NOT EXISTS eas_deprecated.%I (LIKE eas.%I INCLUDING DEFAULTS)', t || '_unmapped', t);
    EXECUTE format(
      'INSERT INTO eas_deprecated.%I SELECT s.* FROM eas.%I s WHERE NOT EXISTS (SELECT 1 FROM eas.app_user a WHERE a.id = s.user_id)',
      t || '_unmapped', t);
    EXECUTE format('DELETE FROM eas.%I s WHERE NOT EXISTS (SELECT 1 FROM eas.app_user a WHERE a.id = s.user_id)', t);

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = ('eas.' || t)::regclass AND conname = t || '_app_user_fk') THEN
      EXECUTE format(
        'ALTER TABLE eas.%I ADD CONSTRAINT %I FOREIGN KEY (user_id) REFERENCES eas.app_user(id) ON DELETE CASCADE',
        t, t || '_app_user_fk');
    END IF;
  END LOOP;
END
$repoint$;

-- Quyền hiệu lực = OR quyền của mọi vai trò đang hiệu lực + ghi đè theo người dùng.
DO $fn$
BEGIN
  IF to_regclass('eas.modules') IS NULL OR to_regclass('eas.user_permissions') IS NULL THEN
    RETURN;
  END IF;
  EXECUTE $body$
    CREATE OR REPLACE FUNCTION eas.get_effective_user_permissions(p_user_id uuid)
    RETURNS TABLE(module_code text, module_name text, group_name text, route_path text,
                  icon_name text, target_app text, can_view boolean, can_create boolean,
                  can_update boolean, can_delete boolean, show_on_sidebar boolean,
                  permission_source text)
    LANGUAGE sql STABLE
    SET search_path = pg_catalog, eas
    AS $q$
      WITH rp AS (
        SELECT p.module_code,
               bool_or(p.can_view) AS v, bool_or(p.can_create) AS c,
               bool_or(p.can_update) AS u, bool_or(p.can_delete) AS d
        FROM eas.role_membership m
        JOIN eas.role_module_permission p ON p.role_code = m.role
        WHERE m.user_id = p_user_id AND m.revoked_at IS NULL
          AND m.valid_from <= statement_timestamp()
          AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
        GROUP BY p.module_code
      )
      SELECT m.code, m.name, m.group_name, m.route_path, m.icon_name, m.target_app,
             COALESCE(up.can_view, rp.v, false),
             COALESCE(up.can_create, rp.c, false),
             COALESCE(up.can_update, rp.u, false),
             COALESCE(up.can_delete, rp.d, false),
             COALESCE(up.can_view, rp.v, false) OR COALESCE(up.can_create, rp.c, false)
               OR COALESCE(up.can_update, rp.u, false) OR COALESCE(up.can_delete, rp.d, false),
             CASE WHEN up.id IS NOT NULL THEN 'USER_OVERRIDE' ELSE 'ROLE_DEFAULT' END
      FROM eas.modules m
      LEFT JOIN rp ON rp.module_code = m.code
      LEFT JOIN eas.user_permissions up ON up.user_id = p_user_id AND up.module_code = m.code
      ORDER BY m.sort_order, m.code
    $q$
  $body$;
END
$fn$;

-- ---------------------------------------------------------------------------
-- 4. Cách ly bảng trùng chức năng (giữ nguyên dữ liệu, ràng buộc, index)
-- ---------------------------------------------------------------------------
DO $quarantine$
DECLARE o text; f regprocedure;
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'eas' AND p.proname IN (
      'get_user_requests_detail', 'fn_log_template_changes',
      'fn_sync_template_workflow_by_category', 'fn_propagate_category_workflow')
  LOOP
    EXECUTE format('ALTER FUNCTION %s SET SCHEMA eas_deprecated', f);
  END LOOP;

  FOREACH o IN ARRAY ARRAY['v_users_management', 'v_request_templates_full'] LOOP
    IF to_regclass('eas.' || o) IS NOT NULL THEN
      EXECUTE format('ALTER VIEW eas.%I SET SCHEMA eas_deprecated', o);
    END IF;
  END LOOP;

  FOREACH o IN ARRAY ARRAY['requests', 'request_templates', 'workflow_categories',
                           'role_permissions', 'users', 'roles', 'departments'] LOOP
    IF to_regclass('eas.' || o) IS NOT NULL THEN
      IF to_regclass('eas_deprecated.' || o) IS NOT NULL THEN
        RAISE EXCEPTION 'eas_deprecated.% đã tồn tại: kiểm tra lần chạy trước.', o;
      END IF;
      EXECUTE format('ALTER TABLE eas.%I SET SCHEMA eas_deprecated', o);
    END IF;
  END LOOP;
END
$quarantine$;

-- ---------------------------------------------------------------------------
-- 5. Tách tài khoản quản trị
-- ---------------------------------------------------------------------------
ALTER TABLE eas.app_user ADD COLUMN IF NOT EXISTS account_type varchar(16) NOT NULL DEFAULT 'EMPLOYEE';
DO $chk$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'eas.app_user'::regclass AND conname = 'app_user_account_type_check') THEN
    ALTER TABLE eas.app_user ADD CONSTRAINT app_user_account_type_check
      CHECK (account_type IN ('EMPLOYEE', 'ADMIN'));
  END IF;
END
$chk$;
COMMENT ON COLUMN eas.app_user.account_type IS
  'EMPLOYEE: chỉ vai trò nghiệp vụ (cổng nhân viên). ADMIN: chỉ vai trò quản trị (cổng quản trị), chi tiết ở eas.admin_account.';

CREATE TABLE IF NOT EXISTS eas.admin_account (
  user_id          uuid PRIMARY KEY REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  employee_user_id uuid UNIQUE REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  created_at       timestamptz NOT NULL DEFAULT statement_timestamp(),
  CONSTRAINT admin_account_not_self CHECK (employee_user_id IS NULL OR employee_user_id <> user_id)
);
COMMENT ON TABLE eas.admin_account IS
  'Tài khoản quản trị (subtype của app_user, account_type=ADMIN). employee_user_id: tài khoản nhân viên của cùng người (nếu có).';
ALTER TABLE eas.admin_account ENABLE ROW LEVEL SECURITY;

-- Chỉ một tài khoản quản trị duy nhất: admin@eas.com.
DO $sole$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM eas.app_user WHERE email = 'admin@eas.com') THEN
    RAISE EXCEPTION 'Không có tài khoản admin@eas.com: dừng để không mất quyền quản trị hệ thống.';
  END IF;
END
$sole$;

-- 5a. admin@eas.com: tài khoản ADMIN, thu hồi vai trò nghiệp vụ còn sót.
UPDATE eas.role_membership m SET revoked_at = now()
FROM eas.app_user u
WHERE u.email = 'admin@eas.com' AND m.user_id = u.id AND m.revoked_at IS NULL
  AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
  AND m.role IN ('REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR');

UPDATE eas.app_user SET account_type = 'ADMIN'
WHERE email = 'admin@eas.com' AND account_type <> 'ADMIN';

INSERT INTO eas.admin_account(user_id)
SELECT id FROM eas.app_user WHERE email = 'admin@eas.com'
ON CONFLICT (user_id) DO NOTHING;

-- 5b. Mọi tài khoản khác: thu hồi vai trò quản trị (giữ nguyên vai trò nghiệp vụ).
UPDATE eas.role_membership m SET revoked_at = now()
FROM eas.app_user u
WHERE m.user_id = u.id AND u.email <> 'admin@eas.com' AND m.revoked_at IS NULL
  AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
  AND m.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR');

-- 5c. Tài khoản ADMIN khác (vd <tên>+admin@eas.com do bản migration trước tạo):
--     thu hồi mọi vai trò còn lại và khoá; không xoá vì có thể đã có nhật ký audit.
UPDATE eas.role_membership m SET revoked_at = now()
FROM eas.app_user u
WHERE m.user_id = u.id AND u.account_type = 'ADMIN' AND u.email <> 'admin@eas.com'
  AND m.revoked_at IS NULL;

UPDATE eas.app_user
SET is_active = false, auth_version = auth_version + 1
WHERE account_type = 'ADMIN' AND email <> 'admin@eas.com' AND is_active;

-- Các phiên đang mở nạp lại vai trò ngay ở request kế tiếp.
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- ---------------------------------------------------------------------------
-- 6. Ràng buộc: vai trò quản trị chỉ trên ADMIN, vai trò nghiệp vụ chỉ trên EMPLOYEE
-- ---------------------------------------------------------------------------
-- Kiểm tra ngay các ràng buộc deferred (manager_acyclic) trước khi gắn trigger lên app_user.
SET CONSTRAINTS ALL IMMEDIATE;

CREATE OR REPLACE FUNCTION eas.enforce_account_role_type()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, eas
AS $f$
DECLARE kind text;
BEGIN
  IF NEW.revoked_at IS NOT NULL OR (NEW.valid_to IS NOT NULL AND NEW.valid_to <= statement_timestamp()) THEN
    RETURN NEW;
  END IF;
  SELECT account_type INTO kind FROM eas.app_user WHERE id = NEW.user_id;
  IF kind = 'ADMIN' AND NEW.role IN ('REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR') THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'ADMIN_ACCOUNT_CANNOT_HOLD_OPERATIONAL_ROLE';
  END IF;
  IF kind = 'EMPLOYEE' AND NEW.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR') THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'EMPLOYEE_ACCOUNT_CANNOT_HOLD_ADMIN_ROLE';
  END IF;
  RETURN NEW;
END
$f$;

CREATE OR REPLACE FUNCTION eas.guard_account_type_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, eas
AS $f$
BEGIN
  IF NEW.account_type IS DISTINCT FROM OLD.account_type AND EXISTS (
    SELECT 1 FROM eas.role_membership m
    WHERE m.user_id = NEW.id AND m.revoked_at IS NULL
      AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
      AND m.role IN (CASE WHEN NEW.account_type = 'ADMIN'
                          THEN ARRAY['REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR']
                          ELSE ARRAY['OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR'] END)
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'ACCOUNT_TYPE_CONFLICTS_WITH_ACTIVE_ROLES';
  END IF;
  RETURN NEW;
END
$f$;

REVOKE ALL ON FUNCTION eas.enforce_account_role_type() FROM PUBLIC;
REVOKE ALL ON FUNCTION eas.guard_account_type_change() FROM PUBLIC;

DROP TRIGGER IF EXISTS b_account_role_type ON eas.role_membership;
CREATE TRIGGER b_account_role_type BEFORE INSERT OR UPDATE ON eas.role_membership
  FOR EACH ROW EXECUTE FUNCTION eas.enforce_account_role_type();
DROP TRIGGER IF EXISTS b_account_type_change ON eas.app_user;
CREATE TRIGGER b_account_type_change BEFORE UPDATE OF account_type ON eas.app_user
  FOR EACH ROW EXECUTE FUNCTION eas.guard_account_type_change();

-- Quyền đọc cho backend + policy RLS cùng mẫu với các bảng lõi.
DO $grants$
DECLARE t text; r text; backend text[];
BEGIN
  SELECT array_agg(rolname ORDER BY rolname) INTO backend
  FROM pg_roles WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_privacy');
  FOREACH t IN ARRAY ARRAY['admin_account', 'role_module_permission'] LOOP
    CONTINUE WHEN to_regclass('eas.' || t) IS NULL;
    FOREACH r IN ARRAY backend LOOP
      EXECUTE format('GRANT SELECT ON eas.%I TO %I', t, r);
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

-- Nhật ký phiên bản hệ thống (nếu bảng tồn tại).
DO $log$
BEGIN
  IF to_regclass('eas.system_versions_changelog') IS NOT NULL THEN
    INSERT INTO eas.system_versions_changelog(system_version, change_type, change_scope, title, description, changed_by)
    VALUES ('db-2026.11.03', 'PERMISSION', 'MAJOR',
            'Dọn bảng trùng chức năng và tách tài khoản quản trị',
            'Cách ly users/departments/requests/roles/role_permissions/request_templates/workflow_categories sang eas_deprecated; thêm app_user.account_type, eas.admin_account (chỉ admin@eas.com), eas.role_module_permission; thu hồi quyền anon/authenticated trên schema eas.',
            'migration 11_cleanup_duplicates_and_admin_split');
  END IF;
END
$log$;

-- ---------------------------------------------------------------------------
-- 7. Tự kiểm tra — sai bất kỳ điều gì thì huỷ toàn bộ migration
-- ---------------------------------------------------------------------------
DO $verify$
DECLARE b record; n bigint; t text;
BEGIN
  SELECT * INTO b FROM _mig_before;
  IF (SELECT count(*) FROM eas.request) <> b.requests THEN RAISE EXCEPTION 'VERIFY: số request thay đổi'; END IF;
  IF (SELECT count(*) FROM eas.audit_event) <> b.audit_events THEN RAISE EXCEPTION 'VERIFY: audit_event thay đổi'; END IF;
  IF (SELECT count(*) FROM eas.role_membership) < b.memberships THEN RAISE EXCEPTION 'VERIFY: mất role_membership'; END IF;
  -- Đúng một tài khoản quản trị đang hoạt động: admin@eas.com, và nó còn vai trò quản trị.
  IF (SELECT count(*) FROM eas.app_user WHERE account_type = 'ADMIN' AND is_active) <> 1
     OR NOT EXISTS (SELECT 1 FROM eas.app_user WHERE email = 'admin@eas.com' AND account_type = 'ADMIN') THEN
    RAISE EXCEPTION 'VERIFY: phải có đúng 1 tài khoản ADMIN đang hoạt động (admin@eas.com)';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM eas.role_membership m JOIN eas.app_user u ON u.id = m.user_id
    WHERE u.email = 'admin@eas.com' AND m.revoked_at IS NULL
      AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
      AND m.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR')) THEN
    RAISE EXCEPTION 'VERIFY: admin@eas.com không còn vai trò quản trị nào';
  END IF;
  SELECT count(*) INTO n FROM eas.role_membership m JOIN eas.app_user u ON u.id = m.user_id
  WHERE u.email <> 'admin@eas.com' AND m.revoked_at IS NULL
    AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
    AND m.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR');
  IF n > 0 THEN RAISE EXCEPTION 'VERIFY: còn % vai trò quản trị ngoài admin@eas.com', n; END IF;

  FOREACH t IN ARRAY ARRAY['users', 'departments', 'requests', 'roles', 'role_permissions', 'request_templates', 'workflow_categories'] LOOP
    IF to_regclass('eas.' || t) IS NOT NULL THEN RAISE EXCEPTION 'VERIFY: eas.% vẫn còn', t; END IF;
  END LOOP;

  SELECT count(*) INTO n FROM pg_constraint c
  JOIN pg_class s ON s.oid = c.conrelid JOIN pg_namespace sn ON sn.oid = s.relnamespace
  JOIN pg_class d ON d.oid = c.confrelid JOIN pg_namespace dn ON dn.oid = d.relnamespace
  WHERE c.contype = 'f' AND sn.nspname = 'eas' AND dn.nspname = 'eas_deprecated';
  IF n > 0 THEN RAISE EXCEPTION 'VERIFY: còn % khóa ngoại từ eas sang eas_deprecated', n; END IF;

  SELECT count(*) INTO n FROM eas.role_membership m JOIN eas.app_user u ON u.id = m.user_id
  WHERE m.revoked_at IS NULL AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
    AND ((u.account_type = 'EMPLOYEE' AND m.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR'))
      OR (u.account_type = 'ADMIN' AND m.role IN ('REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR')));
  IF n > 0 THEN RAISE EXCEPTION 'VERIFY: % vai trò sai loại tài khoản', n; END IF;

  SELECT count(*) INTO n FROM eas.app_user u
  WHERE u.account_type = 'ADMIN' AND NOT EXISTS (SELECT 1 FROM eas.admin_account a WHERE a.user_id = u.id);
  IF n > 0 THEN RAISE EXCEPTION 'VERIFY: % tài khoản ADMIN thiếu admin_account', n; END IF;

  IF to_regclass('eas.modules') IS NOT NULL THEN
    PERFORM count(*) FROM eas.app_user u, LATERAL eas.get_effective_user_permissions(u.id);
  END IF;

  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
  WHERE ns.nspname = 'eas' AND c.relkind = 'r' AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
    AND has_table_privilege('anon', c.oid, 'SELECT');
  IF n > 0 THEN
    RAISE WARNING 'anon vẫn còn quyền SELECT trên % bảng eas (grantor ngoài tầm SQL Editor). RLS vẫn chặn dữ liệu; báo lại để xử lý.', n;
  END IF;
END
$verify$;

RESET ROLE;
COMMIT;

-- Báo cáo kết quả (chỉ đọc)
SELECT a.email AS admin_account, a.display_name, e.email AS linked_employee_account,
       a.must_change_password,
       (SELECT string_agg(DISTINCT m.role, ', ') FROM eas.role_membership m
         WHERE m.user_id = a.id AND m.revoked_at IS NULL) AS active_roles
FROM eas.admin_account x
JOIN eas.app_user a ON a.id = x.user_id
LEFT JOIN eas.app_user e ON e.id = x.employee_user_id
ORDER BY a.email;
