-- =============================================================================
-- 14 — Vá bảo mật + chuẩn hoá schema eas, giai đoạn EXPAND (04/11/2026)
-- Báo cáo:  docs/KIEM_TOAN_CODE_DATA_2026-11-04.md
-- Thiết kế: docs/THIET_KE_SCHEMA_EAS_V2.md
--
-- CÁCH CHẠY: Supabase Dashboard → SQL Editor → dán TOÀN BỘ file → Run.
--   * Chạy bằng role mặc định của SQL Editor (postgres, thành viên eas_migration).
--   * Một transaction, có tự kiểm tra cuối file: sai ở đâu thì ROLLBACK toàn bộ.
--   * Chạy lại lần 2 an toàn (idempotent).
--   * Chỉ THÊM / SIẾT; không xoá dữ liệu nghiệp vụ, không xoá cột. Phần xoá
--     (CONTRACT) nằm ở 15_schema_v2_consolidate.sql, chỉ chạy
--     sau khi bản code mới đã chạy ổn định.
--   * Rollback: database/migrations/rollback/14_security_hardening_and_schema_v2_expand_rollback.sql
--
-- NỘI DUNG
--   1. S2  Xoá mọi policy RLS cấp cho anon/authenticated/public trong schema eas.
--   2. S3  Hàm SECURITY DEFINER: cố định search_path, thu hồi EXECUTE của PUBLIC.
--   3. S1  Thu hồi quyền sửa/xoá module requests_workflows của vai trò nghiệp vụ.
--   4. L1  Bỏ UNIQUE(instance_id, assignee_id) của approval_step; thay bằng trigger
--          "một người thật không giữ 2 bước trong cùng phiên" (AI hệ thống được phép).
--   5. M2  Bảng mới privacy_case_approval (duyệt kép xoá dữ liệu cá nhân).
--   6. M3  Bảng mới sla_escalation_policy (nhắc / tự chuyển / leo thang mức 2).
--   7. M4  Bảng mới work_handover (bàn giao công việc khi vắng).
--   8. M5  Bảng mới business_holiday (lịch nghỉ cho SLA giờ làm việc).
--   9. P4  Chỉ mục cho khoá ngoại được truy vấn theo người.
--  10. T*  Đánh dấu các cột / bảng di sản sẽ bỏ ở giai đoạn CONTRACT.
--  11. Tự kiểm tra.
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = 0;
SET LOCAL client_min_messages = warning;

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres). current_user=%', current_user;
  END IF;
  IF to_regclass('eas.approval_step') IS NULL OR to_regclass('eas.role_module_permission') IS NULL THEN
    RAISE EXCEPTION 'Thiếu bảng lõi eas (cần migration 11 trở lên).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;

-- ---------------------------------------------------------------------------
-- 1. S2 — policy công khai. Không role công khai nào được có policy trong eas,
--    kể cả khi hiện chưa có GRANT: một lệnh GRANT nhầm sẽ lộ password_hash.
-- ---------------------------------------------------------------------------
DO $public_policies$
DECLARE p record;
BEGIN
  FOR p IN
    SELECT schemaname, tablename, policyname
    FROM pg_policies
    WHERE schemaname = 'eas'
      AND roles && ARRAY['anon', 'authenticated', 'public']::name[]
  LOOP
    EXECUTE format('DROP POLICY %I ON %I.%I', p.policyname, p.schemaname, p.tablename);
  END LOOP;
END
$public_policies$;

-- ---------------------------------------------------------------------------
-- 2. S3 — SECURITY DEFINER không cố định search_path → cố định; bỏ EXECUTE của
--    PUBLIC trên mọi hàm SECURITY DEFINER của eas (backend vẫn giữ grant riêng).
-- ---------------------------------------------------------------------------
DO $definer$
DECLARE f record; r text;
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure AS sig,
           NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig, '{}')) c WHERE c LIKE 'search_path=%') AS no_path
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'eas' AND p.prosecdef
  LOOP
    IF f.no_path THEN
      EXECUTE format('ALTER FUNCTION %s SET search_path = pg_catalog, eas', f.sig);
    END IF;
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f.sig);
    FOR r IN SELECT rolname FROM pg_roles
             WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login') LOOP
      EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %I', f.sig, r);
    END LOOP;
  END LOOP;
END
$definer$;

-- ---------------------------------------------------------------------------
-- 3. S1 — cấu hình loại yêu cầu là việc của POLICY_ADMIN. Vai trò nghiệp vụ chỉ
--    xem và tạo hồ sơ trên module requests_workflows (code cũng chặn ở máy chủ).
-- ---------------------------------------------------------------------------
UPDATE eas.role_module_permission
SET can_update = false, can_delete = false, updated_at = now()
WHERE module_code = 'requests_workflows'
  AND role_code IN ('REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR')
  AND (can_update OR can_delete);

UPDATE eas.user_permissions up
SET can_update = false, can_delete = false, updated_at = now()
WHERE up.module_code = 'requests_workflows'
  AND (up.can_update OR up.can_delete)
  AND NOT EXISTS (
    SELECT 1 FROM eas.role_membership m
    WHERE m.user_id = up.user_id AND m.role = 'POLICY_ADMIN' AND m.revoked_at IS NULL
  );

-- ---------------------------------------------------------------------------
-- 4. L1 — AI hệ thống tiếp quản lần lượt nhiều bước của một phiên (quyết định D5),
--    nên UNIQUE(instance_id, assignee_id) phải bỏ. Thay bằng trigger chỉ áp cho
--    người thật: một người không giữ 2 bước trong cùng phiên (tách nhiệm).
-- ---------------------------------------------------------------------------
ALTER TABLE eas.approval_step DROP CONSTRAINT IF EXISTS approval_step_instance_id_assignee_id_key;

CREATE OR REPLACE FUNCTION eas.guard_step_distinct_human() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, eas AS $f$
BEGIN
  IF EXISTS (SELECT 1 FROM eas.app_user u WHERE u.id = NEW.assignee_id AND u.is_system_account) THEN
    RETURN NEW;
  END IF;
  IF EXISTS (
    SELECT 1 FROM eas.approval_step s
    WHERE s.instance_id = NEW.instance_id AND s.assignee_id = NEW.assignee_id AND s.id <> NEW.id
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'Approver already holds another step of this instance';
  END IF;
  RETURN NEW;
END
$f$;

DROP TRIGGER IF EXISTS approval_step_distinct_human ON eas.approval_step;
CREATE TRIGGER approval_step_distinct_human
  BEFORE INSERT OR UPDATE OF assignee_id ON eas.approval_step
  FOR EACH ROW EXECUTE FUNCTION eas.guard_step_distinct_human();

CREATE INDEX IF NOT EXISTS ix_approval_step_instance_assignee
  ON eas.approval_step (instance_id, assignee_id);

-- ---------------------------------------------------------------------------
-- 5. M2 — duyệt kép xoá dữ liệu cá nhân: 2 người khác nhau, khác người thao tác,
--    cùng xác nhận đúng một danh sách xoá (manifest_sha256).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.privacy_case_approval (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id         uuid NOT NULL REFERENCES eas.privacy_case(id) ON DELETE RESTRICT,
  approver_id     uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  manifest_sha256 char(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  decision        varchar(8) NOT NULL CHECK (decision IN ('APPROVE', 'REJECT')),
  reason          text NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 2000),
  decided_at      timestamptz NOT NULL DEFAULT statement_timestamp(),
  UNIQUE (case_id, approver_id)
);
COMMENT ON TABLE eas.privacy_case_approval IS
  'Duyệt kép xoá dữ liệu cá nhân (ND 13/2023): execute-erase cần 2 APPROVE khác người, khác owner, cùng manifest_sha256. Append-only.';

-- ---------------------------------------------------------------------------
-- 6. M3 — chính sách leo thang SLA. type_id NULL = mặc định toàn hệ thống.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.sla_escalation_policy (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type_id            uuid NULL REFERENCES eas.request_type(id) ON DELETE CASCADE,
  stage_kind         varchar(10) NOT NULL CHECK (stage_kind IN ('APPROVAL', 'EXECUTION', 'ACCEPTANCE')),
  reminder_percent   smallint NOT NULL DEFAULT 50 CHECK (reminder_percent BETWEEN 10 AND 95),
  on_breach          varchar(13) NOT NULL DEFAULT 'REMIND' CHECK (on_breach IN ('REMIND', 'AUTO_REASSIGN')),
  notify_manager     boolean NOT NULL DEFAULT true,
  level2_percent     smallint NULL CHECK (level2_percent IS NULL OR level2_percent BETWEEN 101 AND 500),
  updated_by         uuid NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  updated_at         timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE UNIQUE INDEX IF NOT EXISTS sla_escalation_policy_scope
  ON eas.sla_escalation_policy (COALESCE(type_id, '00000000-0000-0000-0000-000000000000'::uuid), stage_kind);
COMMENT ON TABLE eas.sla_escalation_policy IS
  'Quyết định D3: admin chọn nhắc hay tự chuyển khi quá hạn; mức 2 (mặc định 150%) báo OPS. Bản ghi type_id NULL là mặc định.';

INSERT INTO eas.sla_escalation_policy (type_id, stage_kind, reminder_percent, on_breach, notify_manager, level2_percent)
SELECT NULL, k, 50, 'REMIND', true, 150
FROM unnest(ARRAY['APPROVAL', 'EXECUTION', 'ACCEPTANCE']) AS k
WHERE NOT EXISTS (
  SELECT 1 FROM eas.sla_escalation_policy p WHERE p.type_id IS NULL AND p.stage_kind = k
);

-- ---------------------------------------------------------------------------
-- 7. M4 — bàn giao công việc (quyết định D4): tự động từ đơn nghỉ đã duyệt hoặc
--    do người dùng tự tạo. Không chồng lấn cho cùng một người bàn giao.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.work_handover (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  from_user_id      uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  to_user_id        uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  scope             varchar(9) NOT NULL DEFAULT 'ALL' CHECK (scope IN ('ALL', 'APPROVAL', 'EXECUTION', 'ACCEPTANCE')),
  starts_at         timestamptz NOT NULL,
  ends_at           timestamptz NOT NULL,
  source            varchar(14) NOT NULL CHECK (source IN ('LEAVE_REQUEST', 'MANUAL')),
  source_request_id uuid NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
  reason            text NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 2000),
  created_by        uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  created_at        timestamptz NOT NULL DEFAULT statement_timestamp(),
  revoked_at        timestamptz NULL,
  CHECK (from_user_id <> to_user_id),
  CHECK (ends_at > starts_at AND ends_at <= starts_at + interval '90 days'),
  CHECK (source <> 'LEAVE_REQUEST' OR source_request_id IS NOT NULL)
);
-- Không chồng lấn bàn giao còn hiệu lực của cùng người, cùng phạm vi (trigger thay
-- cho EXCLUDE … gist để không cần extension btree_gist).
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
DROP TRIGGER IF EXISTS work_handover_no_overlap ON eas.work_handover;
CREATE TRIGGER work_handover_no_overlap
  BEFORE INSERT OR UPDATE ON eas.work_handover
  FOR EACH ROW EXECUTE FUNCTION eas.guard_work_handover_overlap();
CREATE INDEX IF NOT EXISTS ix_work_handover_from_user ON eas.work_handover (from_user_id, starts_at);
CREATE INDEX IF NOT EXISTS ix_work_handover_to_user ON eas.work_handover (to_user_id);
COMMENT ON TABLE eas.work_handover IS
  'Quyết định D4: bàn giao việc khi vắng. Khác approval_delegation (chỉ quyền duyệt): áp cho cả thực hiện và nghiệm thu.';

-- ---------------------------------------------------------------------------
-- 8. M5 — ngày nghỉ cho SLA tính theo giờ làm việc.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.business_holiday (
  holiday_date date PRIMARY KEY,
  name         varchar(150) NOT NULL CHECK (length(btrim(name)) > 0),
  created_by   uuid NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  created_at   timestamptz NOT NULL DEFAULT statement_timestamp()
);
COMMENT ON TABLE eas.business_holiday IS 'Lịch nghỉ lễ của công ty; dùng khi bật SLA theo giờ làm việc.';

-- RLS + grant cho 4 bảng mới, theo đúng mẫu các bảng lõi (policy chỉ cho role backend).
DO $grants$
DECLARE t text; r text; backend text[];
BEGIN
  SELECT array_agg(rolname ORDER BY rolname) INTO backend
  FROM pg_roles WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login', 'eas_privacy');
  FOREACH t IN ARRAY ARRAY['privacy_case_approval', 'sla_escalation_policy', 'work_handover', 'business_holiday'] LOOP
    EXECUTE format('ALTER TABLE eas.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON eas.%I FROM PUBLIC', t);
    FOREACH r IN ARRAY backend LOOP
      EXECUTE format('GRANT SELECT, INSERT, UPDATE ON eas.%I TO %I', t, r);
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

-- privacy_case_approval là bằng chứng: không sửa, không xoá.
CREATE OR REPLACE FUNCTION eas.guard_privacy_approval_append_only() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, eas AS $f$
BEGIN
  RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'privacy_case_approval is append-only';
END
$f$;
DROP TRIGGER IF EXISTS privacy_case_approval_append_only ON eas.privacy_case_approval;
CREATE TRIGGER privacy_case_approval_append_only
  BEFORE UPDATE OR DELETE ON eas.privacy_case_approval
  FOR EACH ROW EXECUTE FUNCTION eas.guard_privacy_approval_append_only();

-- ---------------------------------------------------------------------------
-- 9. P4 — chỉ mục khoá ngoại được tra theo người.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_approval_delegation_delegate ON eas.approval_delegation (delegate_id);
CREATE INDEX IF NOT EXISTS ix_user_leave_and_trips_user_time ON eas.user_leave_and_trips (user_id, start_time, end_time);
CREATE INDEX IF NOT EXISTS ix_announcement_receipt_user ON eas.announcement_receipt (user_id);
CREATE INDEX IF NOT EXISTS ix_regulation_versions_regulation ON eas.regulation_versions (regulation_id);

-- ---------------------------------------------------------------------------
-- 10. Đánh dấu di sản (sẽ bỏ ở migration 15 CONTRACT).
-- ---------------------------------------------------------------------------
COMMENT ON COLUMN eas.request_type.risk_weight IS
  'NGUỒN DUY NHẤT của trọng số rủi ro (chỉ POLICY_ADMIN sửa). Được chụp vào request_revision khi gửi.';
COMMENT ON COLUMN eas.request_revision.risk_weight IS 'Bản chụp bất biến trọng số rủi ro tại thời điểm gửi.';
DO $deprecated$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'eas' AND table_name = 'config_release' AND column_name = 'risk_weight') THEN
    COMMENT ON COLUMN eas.config_release.risk_weight IS 'DEPRECATED (14): không dùng; bỏ ở migration 15.';
    COMMENT ON COLUMN eas.config_release.approval_level IS 'DEPRECATED (14): số cấp suy ra từ route_rules; bỏ ở migration 15.';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'eas' AND table_name = 'app_user' AND column_name = 'username') THEN
    COMMENT ON COLUMN eas.app_user.username IS 'DEPRECATED (05): thay bằng email; bỏ ở migration 15.';
  END IF;
  IF to_regclass('eas.workflow_categories') IS NOT NULL THEN
    COMMENT ON TABLE eas.workflow_categories IS
      'DEPRECATED (14): SLA mâu thuẫn với config_release.sla_profile; thay bằng eas.lifecycle + quy chế. Bỏ ở migration 15.';
  END IF;
END
$deprecated$;

-- Phiên đang mở nạp lại quyền module ở request kế tiếp.
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- ---------------------------------------------------------------------------
-- 11. Tự kiểm tra: sai là ROLLBACK cả file.
-- ---------------------------------------------------------------------------
DO $check$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM pg_policies
  WHERE schemaname = 'eas' AND roles && ARRAY['anon', 'authenticated', 'public']::name[];
  IF n <> 0 THEN RAISE EXCEPTION 'Còn % policy cho role công khai', n; END IF;

  SELECT count(*) INTO n FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace
  WHERE ns.nspname = 'eas' AND p.prosecdef
    AND (NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig, '{}')) c WHERE c LIKE 'search_path=%')
         OR has_function_privilege('public', p.oid, 'EXECUTE'));
  IF n <> 0 THEN RAISE EXCEPTION 'Còn % hàm SECURITY DEFINER chưa an toàn', n; END IF;

  SELECT count(*) INTO n FROM eas.role_module_permission
  WHERE module_code = 'requests_workflows' AND role_code IN ('REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR')
    AND (can_update OR can_delete);
  IF n <> 0 THEN RAISE EXCEPTION 'Vai trò nghiệp vụ vẫn còn quyền sửa cấu hình loại yêu cầu'; END IF;

  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'approval_step_instance_id_assignee_id_key') THEN
    RAISE EXCEPTION 'UNIQUE(instance_id, assignee_id) chưa được bỏ';
  END IF;

  SELECT count(*) INTO n FROM unnest(ARRAY['privacy_case_approval', 'sla_escalation_policy', 'work_handover', 'business_holiday']) t
  WHERE NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
                    WHERE ns.nspname = 'eas' AND c.relname = t AND c.relrowsecurity);
  IF n <> 0 THEN RAISE EXCEPTION '% bảng mới thiếu hoặc chưa bật RLS', n; END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'migration 14 OK' AS status,
       (SELECT count(*) FROM pg_policies WHERE schemaname = 'eas') AS eas_policies,
       (SELECT count(*) FROM eas.sla_escalation_policy) AS sla_policies;
