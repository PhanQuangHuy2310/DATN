-- ============================================================
-- EAS catalog upgrade: lifecycle/role catalog and request types.
-- Run once after the 2.0.1 installer, as the project database owner/migration role.
-- This preserves existing EAS records; it does not reset or drop schemas.
-- ============================================================

BEGIN;
SET LOCAL timezone='UTC';
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='300s';
SET LOCAL ROLE eas_migration;

-- ============================================================
-- STEP 1: Create eas.lifecycle lookup table
-- Tách mức workflow A/B/C ra bảng riêng
-- ============================================================
CREATE TABLE eas.lifecycle (
  code          char(1) PRIMARY KEY CHECK (code IN ('A','B','C')),
  name          varchar(50)  NOT NULL CHECK (length(btrim(name))>0),
  description   varchar(500) NOT NULL CHECK (length(btrim(description))>0),
  has_execution boolean      NOT NULL DEFAULT false,
  has_acceptance boolean     NOT NULL DEFAULT false,
  CONSTRAINT lifecycle_consistency CHECK (
    (NOT has_acceptance OR has_execution)  -- acceptance requires execution
  )
);
COMMENT ON TABLE eas.lifecycle IS 'Bảng tra cứu mức workflow: A=phê duyệt, B=phê duyệt+thực hiện, C=phê duyệt+thực hiện+nghiệm thu.';

INSERT INTO eas.lifecycle (code, name, description, has_execution, has_acceptance) VALUES
  ('A', 'Phê duyệt đơn giản',              'Quy trình chỉ cần phê duyệt, không có bước thực hiện hay nghiệm thu. Phù hợp cho nghỉ phép, đặt phòng.', false, false),
  ('B', 'Phê duyệt + Thực hiện',           'Quy trình cần phê duyệt và thực hiện bởi bộ phận chuyên trách. Phù hợp cho cấp quyền IT, hỗ trợ kỹ thuật.', true, false),
  ('C', 'Phê duyệt + Thực hiện + Nghiệm thu', 'Quy trình đầy đủ: phê duyệt, thực hiện, nghiệm thu bởi người yêu cầu. Phù hợp cho mua sắm, mượn thiết bị.', true, true);

-- ============================================================
-- STEP 2: Create eas.role lookup table
-- Chuẩn hóa 7 role nghiệp vụ
-- ============================================================
CREATE TABLE eas.role (
  code        varchar(24) PRIMARY KEY CHECK (code=upper(btrim(code)) AND length(code)>0),
  name        varchar(100) NOT NULL CHECK (length(btrim(name))>0),
  description varchar(500) NOT NULL CHECK (length(btrim(description))>0),
  is_system   boolean      NOT NULL DEFAULT true
);
COMMENT ON TABLE eas.role IS 'Bảng tra cứu vai trò nghiệp vụ. role_membership tham chiếu FK đến bảng này.';

INSERT INTO eas.role (code, name, description, is_system) VALUES
  ('REQUESTER',    'Người tạo yêu cầu',     'Nhân viên tạo và theo dõi yêu cầu trong hệ thống.', true),
  ('APPROVER',     'Người phê duyệt',       'Quản lý hoặc lãnh đạo phê duyệt/từ chối yêu cầu.', true),
  ('EXECUTOR',     'Người thực hiện',        'Nhân viên IT, tài sản hoặc bộ phận chuyên trách thực hiện yêu cầu đã duyệt.', true),
  ('ACCEPTOR',     'Người nghiệm thu',       'Người xác nhận kết quả thực hiện (thường là người yêu cầu ban đầu).', true),
  ('POLICY_ADMIN', 'Quản trị chính sách',    'Quản lý cấu hình biểu mẫu, quy tắc định tuyến và SLA.', true),
  ('OPS_ADMIN',    'Quản trị vận hành',      'Giám sát hệ thống, gán lại executor, hủy/đóng yêu cầu đặc biệt.', true),
  ('AUDITOR',      'Kiểm toán viên',         'Chỉ đọc toàn bộ dữ liệu hệ thống phục vụ kiểm toán nội bộ.', true);

-- ============================================================
-- STEP 3: Modify eas.request_type
-- Thêm cột name, description, category; drop constraint cứng type_p0
-- ============================================================

-- The 2.0.1 baseline already includes these metadata columns.
-- Normalize existing rows before relaxing the fixed three-type constraint.
UPDATE eas.request_type SET
  name = 'Nghỉ phép thường niên',
  description = 'Yêu cầu nghỉ phép năm, nghỉ phép cá nhân theo quy chế lao động.',
  category = 'HR'
WHERE code = 'LEAVE';

UPDATE eas.request_type SET
  name = 'Cấp quyền truy cập hệ thống',
  description = 'Yêu cầu cấp/thay đổi quyền truy cập ứng dụng, hệ thống nội bộ.',
  category = 'IT'
WHERE code = 'ACCESS';

UPDATE eas.request_type SET
  name = 'Mua sắm thiết bị',
  description = 'Yêu cầu mua sắm thiết bị văn phòng, công nghệ hoặc vật tư.',
  category = 'PROCUREMENT'
WHERE code = 'EQUIPMENT';

-- Drop the baseline constraint that only permits the original three types.
ALTER TABLE eas.request_type DROP CONSTRAINT type_p0;

-- 3d. Thêm FK lifecycle -> lifecycle(code)
ALTER TABLE eas.request_type
  ADD CONSTRAINT request_type_lifecycle_fk
    FOREIGN KEY (lifecycle) REFERENCES eas.lifecycle(code) ON DELETE RESTRICT;

-- Keep the metadata required for newly registered request types.
ALTER TABLE eas.request_type
  ALTER COLUMN description DROP DEFAULT,
  ALTER COLUMN category DROP DEFAULT;

ALTER TABLE eas.request_type
  ADD CONSTRAINT request_type_name_not_empty CHECK (length(btrim(name))>0);

-- 3f. Thêm các loại yêu cầu mới
INSERT INTO eas.request_type (id, code, name, description, lifecycle, category, is_active) VALUES
  ('00000000-0000-4000-8000-000000000004', 'LEAVE_SPECIAL',     'Nghỉ phép đặc biệt',          'Nghỉ tang, nghỉ cưới, nghỉ thai sản hoặc các trường hợp đặc biệt khác.',    'A', 'HR',          true),
  ('00000000-0000-4000-8000-000000000005', 'ROOM_BOOKING',      'Đặt phòng họp',                'Đặt trước phòng họp, phòng hội nghị hoặc không gian làm việc chung.',        'A', 'FACILITY',    true),
  ('00000000-0000-4000-8000-000000000006', 'EXPENSE_CLAIM',     'Thanh toán chi phí',           'Yêu cầu hoàn ứng, thanh toán chi phí công tác, tiếp khách, taxi.',           'A', 'FINANCE',     true),
  ('00000000-0000-4000-8000-000000000007', 'ACCESS_FACILITY',   'Cấp quyền ra vào',            'Đăng ký thẻ ra vào tòa nhà, phòng server hoặc khu vực hạn chế.',            'B', 'FACILITY',    true),
  ('00000000-0000-4000-8000-000000000008', 'BUSINESS_TRIP',     'Công tác',                     'Đăng ký công tác trong/ngoài nước, bao gồm lịch trình và kinh phí.',         'B', 'HR',          true),
  ('00000000-0000-4000-8000-000000000009', 'IT_SUPPORT',        'Yêu cầu hỗ trợ IT',           'Yêu cầu hỗ trợ kỹ thuật: cài đặt phần mềm, sửa chữa thiết bị, troubleshoot.','B', 'IT',          true),
  ('00000000-0000-4000-8000-000000000010', 'EQUIPMENT_BORROW',  'Mượn thiết bị',               'Mượn laptop, projector, thiết bị demo hoặc công cụ chuyên dụng có thời hạn.','C', 'ASSET',       true);

-- ============================================================
-- STEP 4: Add FK from role_membership.role -> eas.role(code)
-- ============================================================

-- 4a. Drop old CHECK constraint on role column
-- The CHECK is inline, need to find its name first
DO $$ 
DECLARE constraint_name text;
BEGIN
  SELECT c.conname INTO constraint_name
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE n.nspname = 'eas'
    AND t.relname = 'role_membership'
    AND c.contype = 'c'
    AND pg_get_constraintdef(c.oid) LIKE '%REQUESTER%APPROVER%';
  
  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE eas.role_membership DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

-- 4b. Add FK to role table
ALTER TABLE eas.role_membership
  ADD CONSTRAINT role_membership_role_fk
    FOREIGN KEY (role) REFERENCES eas.role(code) ON DELETE RESTRICT;

-- ============================================================
-- STEP 5: Add FK from config_release.lifecycle -> lifecycle(code)
-- ============================================================
-- Drop old CHECK constraint on lifecycle column in config_release
DO $$ 
DECLARE constraint_name text;
BEGIN
  SELECT c.conname INTO constraint_name
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE n.nspname = 'eas'
    AND t.relname = 'config_release'
    AND c.contype = 'c'
    AND pg_get_constraintdef(c.oid) LIKE '%lifecycle%IN%';
  
  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE eas.config_release DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

ALTER TABLE eas.config_release
  ADD CONSTRAINT config_release_lifecycle_fk
    FOREIGN KEY (lifecycle) REFERENCES eas.lifecycle(code) ON DELETE RESTRICT;

-- ============================================================
-- STEP 6: Add FK from workflow_instance.lifecycle -> lifecycle(code)
-- ============================================================
DO $$ 
DECLARE constraint_name text;
BEGIN
  SELECT c.conname INTO constraint_name
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE n.nspname = 'eas'
    AND t.relname = 'workflow_instance'
    AND c.contype = 'c'
    AND pg_get_constraintdef(c.oid) LIKE '%lifecycle%IN%';
  
  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE eas.workflow_instance DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

ALTER TABLE eas.workflow_instance
  ADD CONSTRAINT workflow_instance_lifecycle_fk
    FOREIGN KEY (lifecycle) REFERENCES eas.lifecycle(code) ON DELETE RESTRICT;

-- ============================================================
-- STEP 7: Update guard_active_release trigger
-- Remove immutable lifecycle check (lifecycle is now FK-protected)
-- ============================================================
CREATE OR REPLACE FUNCTION eas.guard_active_release() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.code<>OLD.code OR NEW.lifecycle<>OLD.lifecycle) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request type identity/lifecycle immutable';
 END IF;
 IF NEW.active_release_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM eas.config_release WHERE id=NEW.active_release_id AND type_id=NEW.id AND state='PUBLISHED') THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Active release must be published for this type';
 END IF;
 RETURN NEW;
END $$;

-- ============================================================
-- STEP 8: Add new indexes
-- ============================================================
CREATE INDEX ix_request_type_category ON eas.request_type(category);
CREATE INDEX ix_request_type_lifecycle ON eas.request_type(lifecycle);

-- ============================================================
-- STEP 9: Grant permissions for new tables
-- ============================================================
GRANT SELECT ON eas.lifecycle TO eas_api,eas_worker,eas_backup,eas_privacy;
GRANT SELECT ON eas.role TO eas_api,eas_worker,eas_backup,eas_privacy;

-- Enable RLS on new tables
ALTER TABLE eas.lifecycle ENABLE ROW LEVEL SECURITY;
ALTER TABLE eas.role ENABLE ROW LEVEL SECURITY;
CREATE POLICY trusted_backend ON eas.lifecycle FOR ALL TO eas_api,eas_worker,eas_privacy USING (true) WITH CHECK (true);
CREATE POLICY backup_read ON eas.lifecycle FOR SELECT TO eas_backup USING (true);
CREATE POLICY trusted_backend ON eas.role FOR ALL TO eas_api,eas_worker,eas_privacy USING (true) WITH CHECK (true);
CREATE POLICY backup_read ON eas.role FOR SELECT TO eas_backup USING (true);

-- ============================================================
-- STEP 10: Update schema comment
-- ============================================================
COMMENT ON SCHEMA eas IS 'EAS schema migration 2.1.0; 32 domain tables; normalized lifecycle+role; backend-only';

COMMIT;

SELECT 'EAS 2.1.0 catalog upgrade complete' AS result,
       (SELECT count(*) FROM eas.request_type) AS request_types,
       (SELECT count(*) FROM eas.lifecycle) AS lifecycles,
       (SELECT count(*) FROM eas.role) AS roles;
