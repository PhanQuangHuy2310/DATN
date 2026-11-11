-- 13 — Đóng lại quyền anon/authenticated và chuẩn hoá các object batch1 (2026-11-03)
-- Kế hoạch: plans/active/2026-11-03_ai_learning_and_admin_remediation.md (EAS-PLAN-2026-11-03-02)
-- Dán toàn bộ vào Supabase SQL Editor → Run. Một transaction; chạy lại an toàn.
-- Rollback: database/migrations/rollback/13_lock_client_roles_and_batch1_objects_rollback.sql
--
-- Vì sao: một script nâng cấp (batch1) chạy trực tiếp trên live đã
--   * cấp lại USAGE schema eas cho anon/authenticated và default privilege để mọi
--     bảng/function tạo sau này bằng postgres tự cấp SELECT/EXECUTE cho anon;
--   * tạo lại eas.workflow_categories không bật RLS, 9 view và 3 function thuộc postgres.
-- AGENTS.md (mục Project notes): trình duyệt và app di động không bao giờ gọi Supabase;
-- anon/authenticated không có quyền gì trên eas. Bản này khôi phục đúng trạng thái đó:
-- mọi object eas thuộc eas_migration, view chạy với quyền người gọi (security_invoker),
-- bảng nào cũng bật RLS, anon/authenticated không còn quyền và không tự được cấp nữa.
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = '60s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres).';
  END IF;
END
$pre$;

-- 1. Chuyển object do role khác tạo về eas_migration (phải làm bằng role chủ sở hữu).
DO $owner$
DECLARE o record;
BEGIN
  FOR o IN
    SELECT c.oid, c.relname, c.relkind, pg_get_userbyid(c.relowner) AS owner
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'eas' AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
      AND pg_get_userbyid(c.relowner) <> 'eas_migration'
  LOOP
    IF NOT pg_has_role(current_user, o.owner, 'MEMBER') THEN
      RAISE EXCEPTION 'eas.% thuộc %: chạy migration bằng role đó (postgres).', o.relname, o.owner;
    END IF;
    EXECUTE format('ALTER %s eas.%I OWNER TO eas_migration',
      CASE o.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                     WHEN 'S' THEN 'SEQUENCE' ELSE 'TABLE' END, o.relname);
  END LOOP;
  FOR o IN
    SELECT p.oid, pg_get_userbyid(p.proowner) AS owner
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'eas' AND pg_get_userbyid(p.proowner) <> 'eas_migration'
  LOOP
    IF NOT pg_has_role(current_user, o.owner, 'MEMBER') THEN
      RAISE EXCEPTION 'Function % thuộc %: chạy migration bằng role đó (postgres).', o.oid::regprocedure, o.owner;
    END IF;
    EXECUTE format('ALTER ROUTINE %s OWNER TO eas_migration', o.oid::regprocedure);
  END LOOP;
END
$owner$;

-- 2. Không để role client tự nhận quyền trên object tạo sau này.
DO $defaults$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['postgres', 'eas_migration'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) AND pg_has_role(current_user, r, 'MEMBER')
       AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
       AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA eas REVOKE ALL ON TABLES FROM anon, authenticated', r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA eas REVOKE ALL ON SEQUENCES FROM anon, authenticated', r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA eas REVOKE ALL ON ROUTINES FROM anon, authenticated', r);
    END IF;
  END LOOP;
END
$defaults$;

SET LOCAL ROLE eas_migration;

-- 3. Thu hồi mọi quyền hiện có của anon/authenticated trên eas.
DO $revoke$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
     AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON ALL TABLES IN SCHEMA eas FROM anon, authenticated;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA eas FROM anon, authenticated;
    REVOKE ALL ON ALL ROUTINES IN SCHEMA eas FROM anon, authenticated;
    REVOKE ALL ON SCHEMA eas FROM anon, authenticated;
  END IF;
END
$revoke$;

-- 4. View đọc dữ liệu theo quyền người gọi (không mượn quyền chủ sở hữu để vượt RLS).
DO $views$
DECLARE v text;
BEGIN
  FOR v IN
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'eas' AND c.relkind = 'v'
      AND NOT COALESCE(c.reloptions @> ARRAY['security_invoker=true'], false)
  LOOP
    EXECUTE format('ALTER VIEW eas.%I SET (security_invoker = true)', v);
  END LOOP;
END
$views$;

-- 5. Bảng nào trong eas cũng bật RLS; bảng thiếu policy nhận policy backend chuẩn.
DO $rls$
DECLARE t text; r text; backend text[];
BEGIN
  SELECT array_agg(rolname ORDER BY rolname) INTO backend
  FROM pg_roles WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login', 'eas_privacy');
  FOR t IN
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'eas' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
  LOOP
    EXECUTE format('ALTER TABLE eas.%I ENABLE ROW LEVEL SECURITY', t);
    FOREACH r IN ARRAY backend LOOP
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON eas.%I TO %I', t, r);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = ('eas.' || quote_ident(t))::regclass AND polname = 'trusted_backend') THEN
      EXECUTE format('CREATE POLICY trusted_backend ON eas.%I FOR ALL TO %s USING (true) WITH CHECK (true)',
                     t, (SELECT string_agg(quote_ident(x), ', ') FROM unnest(backend) x));
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_backup')
       AND NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = ('eas.' || quote_ident(t))::regclass AND polname = 'backup_read') THEN
      EXECUTE format('CREATE POLICY backup_read ON eas.%I FOR SELECT TO eas_backup USING (true)', t);
      EXECUTE format('GRANT SELECT ON eas.%I TO eas_backup', t);
    END IF;
  END LOOP;
END
$rls$;

-- 6. Kiểm tra sau cùng: sai một điều là huỷ toàn bộ.
DO $post$
DECLARE n int;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    IF has_schema_privilege('anon', 'eas', 'USAGE') OR has_schema_privilege('authenticated', 'eas', 'USAGE') THEN
      RAISE EXCEPTION 'anon/authenticated vẫn còn USAGE trên schema eas (cấp qua PUBLIC?)';
    END IF;
  END IF;
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace n2 ON n2.oid = c.relnamespace
  WHERE n2.nspname = 'eas' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity;
  IF n > 0 THEN RAISE EXCEPTION 'Còn % bảng eas chưa bật RLS', n; END IF;
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace n2 ON n2.oid = c.relnamespace
  WHERE n2.nspname = 'eas' AND c.relkind IN ('r', 'p', 'v', 'm', 'S') AND pg_get_userbyid(c.relowner) <> 'eas_migration';
  IF n > 0 THEN RAISE EXCEPTION 'Còn % object eas không thuộc eas_migration', n; END IF;
END
$post$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

COMMIT;

SELECT 'OK: anon/authenticated không còn quyền trên eas; mọi bảng bật RLS; object thuộc eas_migration' AS result;
