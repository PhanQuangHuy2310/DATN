-- =============================================================================
-- 15 — Schema eas v2: gộp bảng trùng, bỏ tên trùng, GIỮ NGUYÊN DỮ LIỆU (04/11/2026)
-- Thiết kế: docs/THIET_KE_SCHEMA_EAS_V2.md
--
-- ĐIỀU KIỆN TRƯỚC KHI CHẠY (file tự kiểm 1 và 3, dừng nếu thiếu):
--   1. Migration 14 đã chạy.
--   2. Bản code từ 04/11/2026 đã triển khai (code không còn đọc/ghi tên cũ).
--   3. Đã chạy: python manage.py import_legacy_changelog --apply
--      (chép 29 dòng system_versions_changelog vào admin_event, giữ chuỗi băm).
--   4. Đã sao lưu (Supabase → Database → Backups).
--
-- CÁCH CHẠY: Supabase SQL Editor → dán TOÀN BỘ file → Run. Một transaction, tự kiểm
-- tra cuối file; chạy lại an toàn. Rollback:
--   database/migrations/rollback/15_schema_v2_consolidate_rollback.sql
--
-- KHÔNG XOÁ DỮ LIỆU. Mọi thứ bỏ khỏi eas được dời sang schema eas_archive
-- (không role ứng dụng nào đọc được), giá trị cột bị bỏ được lưu ở
-- eas_archive.dropped_column_value.
--
-- NỘI DUNG
--   1. eas_deprecated (bảng cũ users/roles/requests/... của bản đầu) → đổi tên eas_archive.
--   2. Bỏ 9 VIEW trùng tên trong eas (roles, requests, departments, admins,
--      user_roles, role_permissions, request_templates, v_users_management,
--      v_request_templates_full). Chúng chỉ là bí danh của bảng thật, không có dữ liệu riêng.
--   3. Bảng trùng chức năng:
--      a. workflow_categories   → eas_archive (trùng eas.lifecycle, SLA sai quy chế).
--      b. system_versions_changelog → eas_archive (đã chép vào admin_event); bỏ trigger
--         trg_after_mock_api_toggle ghi đúp mỗi lần bật/tắt API.
--      c. work_handover → gộp vào approval_delegation (thêm scope/source/...).
--   4. Cột trùng: request/workflow_instance/config_release.risk_weight + approval_level
--      (nguồn: request_type, bản chụp: request_revision), app_user.username (= phần trước @ email).
--   5. Tự kiểm tra.
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL client_min_messages = warning;

DO $pre$
DECLARE missing int;
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('eas.sla_escalation_policy') IS NULL THEN
    RAISE EXCEPTION 'Chưa chạy migration 14.';
  END IF;
  IF to_regclass('eas.system_versions_changelog') IS NOT NULL THEN
    SELECT count(*) INTO missing FROM eas.system_versions_changelog c
    WHERE NOT EXISTS (SELECT 1 FROM eas.admin_event e
                      WHERE e.details->>'legacy_changelog_id' = c.id::text);
    IF missing > 0 THEN
      RAISE EXCEPTION '% dòng system_versions_changelog chưa chép sang admin_event. Chạy trước: python manage.py import_legacy_changelog --apply', missing;
    END IF;
  END IF;
END
$pre$;

-- ---------------------------------------------------------------------------
-- 1. Schema lưu trữ. eas_deprecated đã là kho bảng cũ → đổi tên, không xoá.
--    Chạy bằng role của SQL Editor (postgres): đổi tên/tạo schema cần quyền CREATE
--    trên database, eas_migration không có quyền này trên Supabase.
-- ---------------------------------------------------------------------------
DO $archive$
BEGIN
  IF to_regnamespace('eas_archive') IS NULL THEN
    IF to_regnamespace('eas_deprecated') IS NOT NULL THEN
      ALTER SCHEMA eas_deprecated RENAME TO eas_archive;
    ELSE
      CREATE SCHEMA eas_archive AUTHORIZATION eas_migration;
    END IF;
  END IF;
END
$archive$;

SET LOCAL ROLE eas_migration;
REVOKE ALL ON SCHEMA eas_archive FROM PUBLIC;
DO $archive_grants$
DECLARE r text;
BEGIN
  FOR r IN SELECT rolname FROM pg_roles
           WHERE rolname IN ('anon', 'authenticated', 'eas_api', 'eas_backend_login',
                             'eas_worker', 'eas_worker_login', 'eas_privacy') LOOP
    EXECUTE format('REVOKE ALL ON SCHEMA eas_archive FROM %I', r);
    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA eas_archive FROM %I', r);
  END LOOP;
END
$archive_grants$;
COMMENT ON SCHEMA eas_archive IS
  'Kho lưu trữ chỉ-đọc cho DBA: bảng/cột bị gộp hoặc bỏ khỏi eas (migration 11 và 15). Ứng dụng không truy cập.';

CREATE TABLE IF NOT EXISTS eas_archive.dropped_column_value (
  table_name  text NOT NULL,
  row_id      text NOT NULL,
  column_name text NOT NULL,
  value       jsonb,
  archived_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  PRIMARY KEY (table_name, row_id, column_name)
);

-- ---------------------------------------------------------------------------
-- 2. View trùng tên (bí danh của bảng thật).
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS eas.v_users_management;
DROP VIEW IF EXISTS eas.v_request_templates_full;
DROP VIEW IF EXISTS eas.user_roles;
DROP VIEW IF EXISTS eas.admins;
DROP VIEW IF EXISTS eas.role_permissions;
DROP VIEW IF EXISTS eas.request_templates;
DROP VIEW IF EXISTS eas.requests;
DROP VIEW IF EXISTS eas.roles;
DROP VIEW IF EXISTS eas.departments;

-- ---------------------------------------------------------------------------
-- 3a. workflow_categories → kho (trùng eas.lifecycle).
-- ---------------------------------------------------------------------------
-- Bảng cùng tên đã có trong kho (bản của migration 11) → đổi tên bảng và chỉ mục trước khi dời.
DO $wc$
DECLARE i record;
BEGIN
  IF to_regclass('eas.workflow_categories') IS NOT NULL THEN
    FOR i IN SELECT c.relname
             FROM pg_index x JOIN pg_class c ON c.oid = x.indexrelid
             WHERE x.indrelid = 'eas.workflow_categories'::regclass LOOP
      EXECUTE format('ALTER INDEX eas.%I RENAME TO %I', i.relname, i.relname || '_eas');
    END LOOP;
    ALTER TABLE eas.workflow_categories RENAME TO workflow_categories_eas;
    ALTER TABLE eas.workflow_categories_eas SET SCHEMA eas_archive;
  END IF;
END
$wc$;

-- ---------------------------------------------------------------------------
-- 3b. system_versions_changelog → kho (đã chép vào admin_event); bỏ trigger ghi đúp.
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_after_mock_api_toggle ON eas.mock_apis;
DROP FUNCTION IF EXISTS eas.fn_log_mock_api_toggle();
DO $cl$
BEGIN
  IF to_regclass('eas.system_versions_changelog') IS NOT NULL THEN
    ALTER TABLE eas.system_versions_changelog SET SCHEMA eas_archive;
  END IF;
END
$cl$;

-- ---------------------------------------------------------------------------
-- 3c. work_handover gộp vào approval_delegation (cùng ý nghĩa: giao việc cho người
--     khác trong một khoảng thời gian). approval_delegation có dữ liệu và code dùng.
-- ---------------------------------------------------------------------------
ALTER TABLE eas.approval_delegation
  ADD COLUMN IF NOT EXISTS scope varchar(10) NOT NULL DEFAULT 'APPROVAL',
  ADD COLUMN IF NOT EXISTS source varchar(14) NOT NULL DEFAULT 'MANUAL',
  ADD COLUMN IF NOT EXISTS source_request_id uuid NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS created_by uuid NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT;
DO $deleg_checks$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'approval_delegation_scope_check') THEN
    ALTER TABLE eas.approval_delegation ADD CONSTRAINT approval_delegation_scope_check
      CHECK (scope IN ('ALL', 'APPROVAL', 'EXECUTION', 'ACCEPTANCE'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'approval_delegation_source_check') THEN
    ALTER TABLE eas.approval_delegation ADD CONSTRAINT approval_delegation_source_check
      CHECK (source IN ('LEAVE_REQUEST', 'MANUAL') AND (source <> 'LEAVE_REQUEST' OR source_request_id IS NOT NULL));
  END IF;
END
$deleg_checks$;
COMMENT ON TABLE eas.approval_delegation IS
  'Uỷ quyền / bàn giao việc khi vắng (gộp work_handover ở migration 15). scope: APPROVAL (mặc định), EXECUTION, ACCEPTANCE, ALL.';

DO $handover$
BEGIN
  IF to_regclass('eas.work_handover') IS NOT NULL THEN
    INSERT INTO eas.approval_delegation(id, delegator_id, delegate_id, starts_at, ends_at, reason,
                                        created_at, revoked_at, scope, source, source_request_id, created_by)
    SELECT h.id, h.from_user_id, h.to_user_id, h.starts_at, h.ends_at, left(h.reason, 500),
           h.created_at, h.revoked_at, h.scope, h.source, h.source_request_id, h.created_by
    FROM eas.work_handover h
    ON CONFLICT (id) DO NOTHING;
    ALTER TABLE eas.work_handover SET SCHEMA eas_archive;
  END IF;
END
$handover$;
DROP FUNCTION IF EXISTS eas.guard_work_handover_overlap() CASCADE;

-- ---------------------------------------------------------------------------
-- 4. Cột trùng: lưu giá trị vào kho rồi bỏ.
-- ---------------------------------------------------------------------------
DO $columns$
DECLARE
  c record;
BEGIN
  FOR c IN
    SELECT * FROM (VALUES
      ('request', 'risk_weight'), ('request', 'approval_level'),
      ('workflow_instance', 'risk_weight'), ('workflow_instance', 'approval_level'),
      ('config_release', 'risk_weight'), ('config_release', 'approval_level'),
      ('app_user', 'username')
    ) AS t(tbl, col)
  LOOP
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'eas' AND table_name = c.tbl AND column_name = c.col) THEN
      EXECUTE format(
        'INSERT INTO eas_archive.dropped_column_value(table_name, row_id, column_name, value)
         SELECT %L, id::text, %L, to_jsonb(%I) FROM eas.%I
         ON CONFLICT (table_name, row_id, column_name) DO UPDATE SET value = EXCLUDED.value',
        c.tbl, c.col, c.col, c.tbl);
      EXECUTE format('ALTER TABLE eas.%I DROP COLUMN %I', c.tbl, c.col);
    END IF;
  END LOOP;
END
$columns$;

COMMENT ON COLUMN eas.request_type.risk_weight IS
  'NGUỒN DUY NHẤT của trọng số rủi ro (chỉ POLICY_ADMIN sửa). Bản chụp khi gửi: request_revision.risk_weight.';

-- Phiên đăng nhập nạp lại cấu hình.
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- ---------------------------------------------------------------------------
-- 5. Tự kiểm tra.
-- ---------------------------------------------------------------------------
DO $check$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema = 'eas') THEN
    RAISE EXCEPTION 'Còn view trong schema eas';
  END IF;
  IF to_regclass('eas.workflow_categories') IS NOT NULL OR to_regclass('eas.system_versions_changelog') IS NOT NULL
     OR to_regclass('eas.work_handover') IS NOT NULL OR to_regnamespace('eas_deprecated') IS NOT NULL THEN
    RAISE EXCEPTION 'Còn bảng/schema trùng chưa dời';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'eas'
               AND ((table_name IN ('request', 'config_release', 'workflow_instance') AND column_name IN ('risk_weight', 'approval_level'))
                 OR (table_name = 'app_user' AND column_name = 'username'))) THEN
    RAISE EXCEPTION 'Còn cột trùng chưa bỏ';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_api') THEN
    IF has_schema_privilege('eas_api', 'eas_archive', 'USAGE') THEN
      RAISE EXCEPTION 'eas_api không được đọc eas_archive';
    END IF;
  END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'migration 15 OK' AS status,
       (SELECT count(*) FROM pg_tables WHERE schemaname = 'eas') AS eas_tables,
       (SELECT count(*) FROM pg_views WHERE schemaname = 'eas') AS eas_views,
       (SELECT count(*) FROM pg_tables WHERE schemaname = 'eas_archive') AS archived_tables;
