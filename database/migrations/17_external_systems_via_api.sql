-- =============================================================================
-- 17 — Hệ thống ngoài chỉ qua API + phân loại yêu cầu theo nhóm (04/11/2026)
-- Tài liệu: docs/TICH_HOP_HE_THONG_NGOAI.md, docs/PHAN_LOAI_YEU_CAU.md
-- Chạy SAU database/mock_enterprise_sql/migrations/005_align_with_eas.sql.
--
--   1. Role eas_mock (NOLOGIN): role DUY NHẤT đọc/ghi schema mock_*; dùng cho dịch
--      vụ Mock Systems API. eas_api / eas_worker bị thu hồi mọi quyền trên mock_*.
--   2. guard_request: đường "thu hồi ưu tiên" của Ban Giám đốc
--      (READY_FOR_EXECUTION | IN_PROGRESS | COMPLETED → REJECTED) khi backend đặt
--      cờ giao dịch eas.preempt_request_id = id đơn bị thu hồi.
--   3. Biểu mẫu (bản phát hành mới): mã lấy từ hệ thống ngoài thay danh sách cứng —
--      ROOM_BOOKING.room_code, VEHICLE_BOOKING.vehicle_code,
--      EQUIPMENT_BORROW.asset_category, ACCESS.app_code/requested_role,
--      EXPENSE_CLAIM.expense_category; LEAVE thêm leave_kind (có lương / không lương).
--   4. Phân loại: eas.request_group (12 nhóm), eas.request_menu_item (61 loại nhỏ),
--      request_type.category → khoá ngoại tới request_group.
--
-- Sau khi chạy: tạo role đăng nhập cho dịch vụ mock (KHÔNG ghi mật khẩu vào file):
--   CREATE ROLE eas_mock_login LOGIN PASSWORD '<mật khẩu mạnh>' IN ROLE eas_mock;
--
-- CÁCH CHẠY: Supabase SQL Editor → dán TOÀN BỘ file → Run. Chạy lại an toàn.
-- Rollback: database/migrations/rollback/17_external_systems_via_api_rollback.sql
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('mock_hr.leave_usage') IS NULL THEN
    RAISE EXCEPTION 'Chạy trước database/mock_enterprise_sql/migrations/005_align_with_eas.sql';
  END IF;
END
$pre$;

-- Tạo role cần quyền CREATEROLE của postgres (chạy trước khi đổi sang eas_migration).
DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_mock') THEN
    CREATE ROLE eas_mock NOLOGIN;
  END IF;
END
$role$;
-- Hàm tạm dựng biểu mẫu (tạo bằng role của SQL Editor: cần quyền TEMP).
CREATE OR REPLACE FUNCTION pg_temp.form_set(form jsonb, field text, spec jsonb, drop_field text DEFAULT NULL)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
  SELECT jsonb_set(
           jsonb_set(form, '{properties}',
             ((form->'properties') - coalesce(drop_field, '')) || jsonb_build_object(field, spec)),
           '{required}',
           (SELECT coalesce(jsonb_agg(DISTINCT x), '[]'::jsonb) FROM (
              SELECT CASE WHEN r = drop_field THEN field ELSE r END AS x
              FROM jsonb_array_elements_text(form->'required') r
              UNION SELECT field) q))
$$;

SET LOCAL ROLE eas_migration;

-- ---------------------------------------------------------------------------
-- 1. Quyền: mock_* chỉ cho eas_mock (và eas_backup đọc để sao lưu).
-- ---------------------------------------------------------------------------
DO $mock_grants$
DECLARE s text; r text; t record; p record;
BEGIN
  FOREACH s IN ARRAY ARRAY['mock_hr','mock_assets','mock_facilities','mock_crm',
                           'mock_procurement','mock_it','mock_finance','mock_travel'] LOOP
    CONTINUE WHEN to_regnamespace(s) IS NULL;
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO eas_mock', s);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA %I TO eas_mock', s);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA %I
                    GRANT SELECT, INSERT, UPDATE ON TABLES TO eas_mock', s);
    FOR r IN SELECT rolname FROM pg_roles
             WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login') LOOP
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM %I', s, r);
      EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', s, r);
    END LOOP;
  END LOOP;
  -- RLS: mỗi bảng mock chỉ có policy cho eas_mock (và eas_backup đọc); bỏ policy
  -- cũ cấp cho eas_api.
  FOR t IN SELECT c.oid::regclass AS rel FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname LIKE 'mock\_%' AND c.relkind = 'r' LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', t.rel);
    FOR p IN SELECT polname FROM pg_policy
             WHERE polrelid = t.rel AND polroles && (SELECT array_agg(oid) FROM pg_roles
                   WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login')) LOOP
      EXECUTE format('DROP POLICY %I ON %s', p.polname, t.rel);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = t.rel AND polname = 'mock_service') THEN
      EXECUTE format('CREATE POLICY mock_service ON %s FOR ALL TO eas_mock USING (true) WITH CHECK (true)', t.rel);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_backup')
       AND NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = t.rel AND polname = 'backup_read') THEN
      EXECUTE format('CREATE POLICY backup_read ON %s FOR SELECT TO eas_backup USING (true)', t.rel);
      EXECUTE format('GRANT SELECT ON %s TO eas_backup', t.rel);
    END IF;
  END LOOP;
END
$mock_grants$;

-- ---------------------------------------------------------------------------
-- 2. guard_request: thêm đường thu hồi ưu tiên (giữ nguyên mọi quy tắc cũ).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION eas.guard_request() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, eas AS $f$
DECLARE origin_owner uuid; lc char(1); tcode varchar(30); allowed boolean;
        ai_revoke boolean := false; preempt boolean := false;
BEGIN
 IF TG_OP='DELETE' THEN PERFORM eas.assert_privacy_delete(OLD.id); RETURN OLD; END IF;
 IF TG_OP='UPDATE' THEN
  IF current_user='eas_privacy' AND NEW.current_revision_id IS NULL
    AND (to_jsonb(NEW)-'current_revision_id')=(to_jsonb(OLD)-'current_revision_id') THEN
   PERFORM eas.assert_privacy_delete(OLD.id); RETURN NEW;
  END IF;
  IF ROW(NEW.id,NEW.code,NEW.requester_id,NEW.type_id,NEW.origin_request_id,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.code,OLD.requester_id,OLD.type_id,OLD.origin_request_id,OLD.created_at) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request identity/origin immutable';
  END IF;
  ai_revoke := OLD.status='COMPLETED' AND NEW.status='NEEDS_INFO' AND eas.ai_revocable(OLD.id);
  -- Thu hồi ưu tiên (migration 17): chỉ khi backend đặt cờ cho đúng đơn này.
  preempt := NEW.status='REJECTED'
    AND OLD.status IN ('READY_FOR_EXECUTION','IN_PROGRESS','COMPLETED')
    AND coalesce(current_setting('eas.preempt_request_id', true), '') = OLD.id::text;
  IF OLD.status IN ('COMPLETED','REJECTED','CANCELLED') AND NEW IS DISTINCT FROM OLD AND NOT ai_revoke AND NOT preempt THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Terminal request cannot be reopened or edited';
  END IF;
  IF NEW IS DISTINCT FROM OLD AND (NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_at<OLD.updated_at) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request command requires version increment exactly once and monotonic updated_at';
  END IF;
  IF NEW.status<>OLD.status THEN
   allowed:=(OLD.status IN ('DRAFT','NEEDS_INFO') AND NEW.status IN ('PENDING_APPROVAL','CANCELLED'))
     OR (OLD.status='PENDING_APPROVAL' AND NEW.status IN ('NEEDS_INFO','REJECTED','CANCELLED','COMPLETED','READY_FOR_EXECUTION'))
     OR (OLD.status='READY_FOR_EXECUTION' AND NEW.status='IN_PROGRESS')
     OR (OLD.status='IN_PROGRESS' AND NEW.status IN ('READY_FOR_EXECUTION','WAITING_FOR_ACCEPTANCE','COMPLETED'))
     OR (OLD.status='WAITING_FOR_ACCEPTANCE' AND NEW.status IN ('READY_FOR_EXECUTION','COMPLETED'))
     OR ai_revoke OR preempt;
   IF NOT allowed THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request transition not allowed'; END IF;
  END IF;
 END IF;
 IF NEW.origin_request_id IS NOT NULL THEN
  SELECT requester_id INTO origin_owner FROM eas.request WHERE id=NEW.origin_request_id;
  IF FOUND AND origin_owner<>NEW.requester_id THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Origin request must have same owner'; END IF;
 END IF;
 SELECT lifecycle, code INTO lc, tcode FROM eas.request_type WHERE id=NEW.type_id;
 IF FOUND AND ((tcode IN ('LEAVE','ACCESS') AND NEW.draft_amount_vnd IS NOT NULL) OR (lc='A' AND NEW.status IN ('READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE')) OR (lc='B' AND NEW.status='WAITING_FOR_ACCEPTANCE')) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request lifecycle/amount mismatch';
 END IF;
 IF NEW.status NOT IN ('DRAFT','CANCELLED') AND NEW.current_revision_id IS NULL THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Submitted request requires current revision';
 END IF;
 RETURN NEW;
END $f$;

-- ---------------------------------------------------------------------------
-- 3. Biểu mẫu: mã do hệ thống ngoài cấp (chuỗi; máy chủ kiểm tra qua API).
-- ---------------------------------------------------------------------------

DO $forms$
DECLARE
  code_spec constant jsonb := '{"type":"string","minLength":2,"maxLength":40}';
  author uuid;
  t record;
  new_form jsonb;
  new_route jsonb;
  new_id uuid;
BEGIN
  SELECT u.id INTO author FROM eas.app_user u WHERE u.account_type = 'ADMIN' AND u.is_active
  ORDER BY u.created_at LIMIT 1;
  FOR t IN
    SELECT rt.id AS type_id, rt.code AS type_code, cr.*
    FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
    WHERE rt.code IN ('ROOM_BOOKING', 'VEHICLE_BOOKING', 'EQUIPMENT_BORROW', 'ACCESS',
                      'EXPENSE_CLAIM', 'LEAVE')
  LOOP
    new_route := t.route_rules;
    new_form := CASE t.type_code
      WHEN 'ROOM_BOOKING' THEN pg_temp.form_set(t.form_schema, 'room_code', code_spec, 'room_name')
      WHEN 'VEHICLE_BOOKING' THEN pg_temp.form_set(t.form_schema, 'vehicle_code', code_spec)
      WHEN 'EQUIPMENT_BORROW' THEN pg_temp.form_set(
        jsonb_set(t.form_schema, '{required}', (t.form_schema->'required') - 'item_name'),
        'asset_category', code_spec)
      WHEN 'ACCESS' THEN pg_temp.form_set(pg_temp.form_set(t.form_schema, 'app_code', code_spec),
                                         'requested_role', code_spec)
      WHEN 'EXPENSE_CLAIM' THEN pg_temp.form_set(t.form_schema, 'expense_category', code_spec)
      ELSE pg_temp.form_set(t.form_schema, 'leave_kind',
                            '{"type":"string","enum":["CO_LUONG","KHONG_LUONG"]}')
    END;
    IF t.type_code = 'ROOM_BOOKING' THEN
      new_form := jsonb_set(new_form, '{properties,attendees_count,minimum}', '1');
    END IF;
    IF t.type_code = 'ACCESS' THEN
      -- Ứng dụng ITSM xếp loại RESTRICTED cần thêm Giám đốc duyệt.
      new_route := jsonb_set(new_route, '{rules}', (
        SELECT jsonb_agg(CASE WHEN r ? 'when' AND r->'when' ? 'app_code_in'
                              THEN jsonb_set(r, '{when,app_code_in}', '["AWS","ERP","FAST_ACC","HRMS","VAULT"]')
                              ELSE r END ORDER BY ord)
        FROM jsonb_array_elements(new_route->'rules') WITH ORDINALITY AS x(r, ord)));
    END IF;
    CONTINUE WHEN t.form_schema = new_form AND t.route_rules = new_route;
    INSERT INTO eas.config_release(
      type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
      created_by, published_by, published_at, content_sha256)
    VALUES (
      t.type_id, (SELECT max(version) + 1 FROM eas.config_release WHERE type_id = t.type_id),
      'PUBLISHED', t.lifecycle, new_form, new_route, t.actor_bindings, t.sla_profile,
      coalesce(author, t.created_by), coalesce(author, t.created_by), statement_timestamp(),
      encode(sha256(convert_to(jsonb_build_object(
        'form_schema', new_form, 'route_rules', new_route, 'actor_bindings', t.actor_bindings,
        'sla_profile', t.sla_profile, 'lifecycle', t.lifecycle)::text, 'UTF8')), 'hex'))
    RETURNING id INTO new_id;
    UPDATE eas.request_type SET active_release_id = new_id WHERE id = t.type_id;
  END LOOP;
END
$forms$;

-- ---------------------------------------------------------------------------
-- 4. Phân loại: nhóm lớn → loại nhỏ (docs/PHAN_LOAI_YEU_CAU.md §3).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.request_group (
  code        varchar(20) PRIMARY KEY CHECK (code ~ '^[A-Z][A-Z_]{1,19}$'),
  name        varchar(80) NOT NULL CHECK (length(btrim(name)) > 0),
  description varchar(300) NOT NULL,
  sort_order  smallint NOT NULL
);
CREATE TABLE IF NOT EXISTS eas.request_menu_item (
  code        varchar(40) PRIMARY KEY CHECK (code ~ '^[A-Z][A-Z0-9_]{1,39}$'),
  group_code  varchar(20) NOT NULL REFERENCES eas.request_group(code) ON DELETE RESTRICT,
  type_code   varchar(30) NOT NULL REFERENCES eas.request_type(code) ON DELETE RESTRICT,
  label       varchar(120) NOT NULL CHECK (length(btrim(label)) > 0),
  preset      jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(preset) = 'object'),
  sort_order  smallint NOT NULL,
  is_active   boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS ix_request_menu_item_group ON eas.request_menu_item (group_code, sort_order);
COMMENT ON TABLE eas.request_group IS 'Nhóm lớn hiển thị cho người gửi, theo bản chất yêu cầu (docs/PHAN_LOAI_YEU_CAU.md).';
COMMENT ON TABLE eas.request_menu_item IS 'Loại yêu cầu nhỏ trên menu; preset = trường điền sẵn (vd Đi muộn = ATTENDANCE_ADJUSTMENT + change_type).';

INSERT INTO eas.request_group(code, name, description, sort_order) VALUES
  ('ABSENCE',     'Vắng mặt',                    'Không có mặt tại nơi làm việc trong một khoảng giờ hoặc ngày', 1),
  ('WORKTIME',    'Chấm công & giờ làm',         'Sửa hoặc bổ sung giờ công, làm thêm giờ', 2),
  ('BORROW',      'Mượn & đặt chỗ',              'Dùng tạm có thời hạn, hết hạn trả lại', 3),
  ('PROVISION',   'Cấp phát & quyền truy cập',   'Được cấp hẳn tài sản hoặc quyền để làm việc, hoặc thu hồi', 4),
  ('PAYMENT',     'Tạm ứng & thanh toán',        'Tiền chi ra hoặc hoàn lại', 5),
  ('PROCUREMENT', 'Mua sắm & ngân sách',         'Mua mới hoặc thay đổi ngân sách', 6),
  ('PEOPLE',      'Nhân sự & chế độ',            'Quyết định về một nhân sự trong vòng đời làm việc', 7),
  ('SUPPORT',     'Hỗ trợ & sự cố',              'Có thứ đang hỏng hoặc gặp sự cố cần xử lý', 8),
  ('WORK',        'Công việc & dự án',           'Giao hoặc khởi tạo một đầu việc có kế hoạch', 9),
  ('LEGAL',       'Văn bản & pháp chế',          'Văn bản ràng buộc pháp lý cần thẩm định hoặc ký', 10),
  ('SALES',       'Kinh doanh & marketing',      'Chính sách bán hàng và quảng bá', 11),
  ('ASSET',       'Kho & tài sản cố định',       'Thay đổi vị trí hoặc trạng thái tài sản công ty', 12)
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description,
  sort_order = EXCLUDED.sort_order;

-- Lưu nhóm cũ để rollback trả lại đúng giá trị.
INSERT INTO eas_archive.dropped_column_value(table_name, row_id, column_name, value)
SELECT 'request_type', id::text, 'category_before_17', to_jsonb(category)
FROM eas.request_type
WHERE category IN ('FINANCE','RESOURCE','FACILITY','WORK','HR','TIME','IT','LEGAL','SALES','ADMIN')
ON CONFLICT (table_name, row_id, column_name) DO NOTHING;
ALTER TABLE eas.request_type DROP CONSTRAINT IF EXISTS request_type_category_valid;
UPDATE eas.request_type rt SET category = m.grp
FROM (VALUES
  ('ATTENDANCE_ADJUSTMENT','ABSENCE'),('LEAVE','ABSENCE'),('LEAVE_SPECIAL','ABSENCE'),
  ('BUSINESS_TRIP','ABSENCE'),('WFH_REQ','ABSENCE'),('LEAVE_ANNUAL','ABSENCE'),('LEAVE_LONG','ABSENCE'),
  ('OVERTIME_REQ','WORKTIME'),('OVERTIME_APPROVAL','WORKTIME'),
  ('ROOM_BOOKING','BORROW'),('VEHICLE_BOOKING','BORROW'),('EQUIPMENT_BORROW','BORROW'),
  ('ROOM_STUDIO','BORROW'),('ROOM_VEHICLE','BORROW'),
  ('LAPTOP_PROVISION','PROVISION'),('OFFICE_SUPPLIES','PROVISION'),('ACCESS','PROVISION'),
  ('PROD_DATA_ACCESS','PROVISION'),('SERVER_FIREWALL','PROVISION'),('ACCESS_FACILITY','PROVISION'),
  ('VISITOR_SECURITY_PASS','PROVISION'),('RESOURCE_REVOKE','PROVISION'),('SOFTWARE_ACCESS','PROVISION'),
  ('ADVANCE_SMALL','PAYMENT'),('ADVANCE_MEDIUM','PAYMENT'),('ADVANCE_LARGE','PAYMENT'),
  ('SALARY_ADVANCE','PAYMENT'),('REIMBURSEMENT','PAYMENT'),('EXPENSE_CLAIM','PAYMENT'),
  ('REFUND_COMPENSATION','PAYMENT'),('VENDOR_PAYMENT','PAYMENT'),('TAX_INVOICE_ISSUE','PAYMENT'),
  ('PURCHASE_REQUEST','PROCUREMENT'),('EQUIPMENT','PROCUREMENT'),('SAAS_LICENSE_BUY','PROCUREMENT'),
  ('SUPPLIER_ONBOARDING','PROCUREMENT'),('BUDGET_REALLOCATION','PROCUREMENT'),('ASSET_PURCHASE','PROCUREMENT'),
  ('RECRUITMENT_REQ','PEOPLE'),('EMPLOYEE_ONBOARDING','PEOPLE'),('INTERNAL_TRANSFER','PEOPLE'),
  ('PROMOTION_REQ','PEOPLE'),('SALARY_ADJUSTMENT','PEOPLE'),('REWARD_REQ','PEOPLE'),
  ('DISCIPLINE_REQ','PEOPLE'),('TRAINING_COURSE','PEOPLE'),('HR_CERTIFICATE','PEOPLE'),('RESIGNATION','PEOPLE'),
  ('IT_SUPPORT','SUPPORT'),('FACILITY_REPAIR','SUPPORT'),('SECURITY_INCIDENT_HOTFIX','SUPPORT'),
  ('FACILITY_MAINTENANCE','SUPPORT'),
  ('TASK_REQUEST','WORK'),('CROSS_DEPT_SUPPORT','WORK'),('PROJECT_INITIATION','WORK'),
  ('FEATURE_RELEASE','WORK'),('DATA_UAT_EXPORT','WORK'),
  ('CONTRACT_APPROVAL','LEGAL'),('DOCUMENT_SEAL','LEGAL'),('NDA_PRIVACY_CLEARANCE','LEGAL'),
  ('POLICY_ISSUANCE','LEGAL'),
  ('SPECIAL_DISCOUNT','SALES'),('FLASH_SALE_VOUCHER','SALES'),('MARKETING_CAMPAIGN','SALES'),
  ('WAREHOUSE_TRANSFER','ASSET'),('ASSET_DISPOSAL','ASSET')
) AS m(code, grp)
WHERE rt.code = m.code AND rt.category IS DISTINCT FROM m.grp;
DO $fk$
BEGIN
  IF EXISTS (SELECT 1 FROM eas.request_type rt
             WHERE NOT EXISTS (SELECT 1 FROM eas.request_group g WHERE g.code = rt.category)) THEN
    RAISE EXCEPTION 'Còn loại yêu cầu chưa được xếp nhóm: %',
      (SELECT string_agg(code, ', ') FROM eas.request_type rt
       WHERE NOT EXISTS (SELECT 1 FROM eas.request_group g WHERE g.code = rt.category));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'request_type_category_fk') THEN
    ALTER TABLE eas.request_type ADD CONSTRAINT request_type_category_fk
      FOREIGN KEY (category) REFERENCES eas.request_group(code) ON DELETE RESTRICT;
  END IF;
END
$fk$;

-- Loại nhỏ: mọi loại đang hoạt động có một dòng (trừ ATTENDANCE_ADJUSTMENT và LEAVE,
-- chỉ hiện qua các lựa chọn đặt sẵn).
INSERT INTO eas.request_menu_item(code, group_code, type_code, label, preset, sort_order)
SELECT * FROM (VALUES
  ('LATE_IN',          'ABSENCE',  'ATTENDANCE_ADJUSTMENT', 'Đi muộn',            '{"change_type":"Đi muộn"}'::jsonb, 1),
  ('EARLY_OUT',        'ABSENCE',  'ATTENDANCE_ADJUSTMENT', 'Về sớm',             '{"change_type":"Về sớm"}'::jsonb, 2),
  ('PAID_LEAVE',       'ABSENCE',  'LEAVE',                 'Nghỉ phép có lương', '{"leave_kind":"CO_LUONG"}'::jsonb, 3),
  ('UNPAID_LEAVE',     'ABSENCE',  'LEAVE',                 'Nghỉ không lương',   '{"leave_kind":"KHONG_LUONG"}'::jsonb, 4),
  ('MISSED_CHECK_IN',  'WORKTIME', 'ATTENDANCE_ADJUSTMENT', 'Quên chấm công',     '{"change_type":"Quên chấm công"}'::jsonb, 1)
) AS v(code, group_code, type_code, label, preset, sort_order)
WHERE EXISTS (SELECT 1 FROM eas.request_type rt WHERE rt.code = v.type_code)
ON CONFLICT (code) DO UPDATE SET group_code = EXCLUDED.group_code, type_code = EXCLUDED.type_code,
  label = EXCLUDED.label, preset = EXCLUDED.preset, sort_order = EXCLUDED.sort_order;

INSERT INTO eas.request_menu_item(code, group_code, type_code, label, sort_order)
SELECT rt.code, rt.category, rt.code, rt.name,
       10 + row_number() OVER (PARTITION BY rt.category ORDER BY rt.name)
FROM eas.request_type rt
WHERE rt.is_active AND rt.code NOT IN ('ATTENDANCE_ADJUSTMENT', 'LEAVE')
ON CONFLICT (code) DO UPDATE SET group_code = EXCLUDED.group_code, label = EXCLUDED.label;
UPDATE eas.request_menu_item SET label = 'Nghỉ chế độ (cưới, tang, thai sản, ốm dài ngày)'
WHERE code = 'LEAVE_SPECIAL';

-- RLS + quyền theo mẫu bảng lõi.
DO $rls$
DECLARE t text; r text;
BEGIN
  FOREACH t IN ARRAY ARRAY['request_group', 'request_menu_item'] LOOP
    EXECUTE format('ALTER TABLE eas.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON eas.%I FROM PUBLIC', t);
    FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('eas_api', 'eas_backend_login') LOOP
      EXECUTE format('GRANT SELECT, INSERT, UPDATE ON eas.%I TO %I', t, r);
    END LOOP;
    FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('eas_worker', 'eas_backup') LOOP
      EXECUTE format('GRANT SELECT ON eas.%I TO %I', t, r);
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = ('eas.' || t)::regclass AND polname = 'trusted_backend') THEN
      EXECUTE format('CREATE POLICY trusted_backend ON eas.%I FOR ALL TO %s USING (true) WITH CHECK (true)', t,
        (SELECT string_agg(quote_ident(rolname), ', ') FROM pg_roles
         WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker')));
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_backup')
       AND NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = ('eas.' || t)::regclass AND polname = 'backup_read') THEN
      EXECUTE format('CREATE POLICY backup_read ON eas.%I FOR SELECT TO eas_backup USING (true)', t);
    END IF;
  END LOOP;
END
$rls$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- ---------------------------------------------------------------------------
-- 5. Tự kiểm tra.
-- ---------------------------------------------------------------------------
DO $check$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_api')
     AND has_schema_privilege('eas_api', 'mock_hr', 'USAGE') THEN
    RAISE EXCEPTION 'eas_api vẫn vào được mock_hr';
  END IF;
  IF NOT has_table_privilege('eas_mock', 'mock_assets.asset_loan', 'INSERT') THEN
    RAISE EXCEPTION 'eas_mock chưa ghi được mock_assets.asset_loan';
  END IF;
  IF (SELECT count(*) FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
      WHERE (rt.code = 'ROOM_BOOKING' AND cr.form_schema->'properties' ? 'room_code')
         OR (rt.code = 'ACCESS' AND NOT (cr.form_schema->'properties'->'app_code') ? 'enum')
         OR (rt.code = 'LEAVE' AND cr.form_schema->'properties' ? 'leave_kind')) <> 3 THEN
    RAISE EXCEPTION 'Biểu mẫu mới chưa được kích hoạt đủ';
  END IF;
  IF EXISTS (SELECT 1 FROM eas.request_type rt WHERE rt.is_active AND rt.code NOT IN ('ATTENDANCE_ADJUSTMENT', 'LEAVE')
             AND NOT EXISTS (SELECT 1 FROM eas.request_menu_item m WHERE m.type_code = rt.code)) THEN
    RAISE EXCEPTION 'Còn loại yêu cầu hoạt động không có trên menu';
  END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'migration 17 OK' AS status,
       (SELECT count(*) FROM eas.request_group) AS groups,
       (SELECT count(*) FROM eas.request_menu_item WHERE is_active) AS menu_items;
