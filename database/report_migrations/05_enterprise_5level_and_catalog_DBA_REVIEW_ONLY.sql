-- =============================================================================
-- Migration 05: Enterprise 5-Level Risk/Approval Architecture & 12 Missing Types
-- Target Project: Live Supabase (emnusiybdkpibtqsplta)
-- Scope:
--   1. Upgrade approval route & step constraints from 1..3 to 1..5 levels (5 cấp).
--   2. Add 5-level columns (risk_weight 1..5, approval_level 1..5, tier_level 1..5,
--      resolver_code) across all 6 core workflow tables:
--      - eas.request_type
--      - eas.config_release
--      - eas.request
--      - eas.request_revision
--      - eas.workflow_instance
--      - eas.approval_step
--   3. Register 12 missing Enterprise Request Types across all 5 levels and
--      8 company departments/domains.
-- =============================================================================

BEGIN;

-- 1. Upgrade 5-Level Constraints on workflow_instance and approval_step
ALTER TABLE eas.approval_step DROP CONSTRAINT IF EXISTS approval_step_step_no_check;
ALTER TABLE eas.approval_step ADD CONSTRAINT approval_step_step_no_check CHECK (step_no >= 1 AND step_no <= 5);

ALTER TABLE eas.workflow_instance DROP CONSTRAINT IF EXISTS workflow_instance_resolved_route_check;
ALTER TABLE eas.workflow_instance ADD CONSTRAINT workflow_instance_resolved_route_check CHECK (
  jsonb_typeof(resolved_route) = 'array'
  AND jsonb_array_length(resolved_route) >= 1
  AND jsonb_array_length(resolved_route) <= 5
);

-- 2. Add 5-Level Columns to all 6 related tables
ALTER TABLE eas.request_type
  ADD COLUMN IF NOT EXISTS risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5),
  ADD COLUMN IF NOT EXISTS approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5);

ALTER TABLE eas.config_release
  ADD COLUMN IF NOT EXISTS risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5),
  ADD COLUMN IF NOT EXISTS approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5);

ALTER TABLE eas.request
  ADD COLUMN IF NOT EXISTS risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5),
  ADD COLUMN IF NOT EXISTS approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5);

ALTER TABLE eas.request_revision
  ADD COLUMN IF NOT EXISTS risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5),
  ADD COLUMN IF NOT EXISTS approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5);

ALTER TABLE eas.workflow_instance
  ADD COLUMN IF NOT EXISTS risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5),
  ADD COLUMN IF NOT EXISTS approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5);

ALTER TABLE eas.approval_step
  ADD COLUMN IF NOT EXISTS tier_level smallint NOT NULL DEFAULT 1 CHECK (tier_level BETWEEN 1 AND 5),
  ADD COLUMN IF NOT EXISTS resolver_code character varying(40);

-- 3. Upgrade eas.guard_release() to support 1..5 approval levels
CREATE OR REPLACE FUNCTION eas.guard_release()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'eas'
AS $function$
DECLARE lc char(1); j jsonb; r jsonb; defaults integer; cnt integer; h numeric;
BEGIN
 IF TG_OP IN ('UPDATE','DELETE') AND OLD.state='PUBLISHED' THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Published release is immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.type_id<>OLD.type_id OR NEW.version<>OLD.version OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Release identity is immutable';
 END IF;
 SELECT lifecycle INTO lc FROM eas.request_type WHERE id=NEW.type_id;
 IF FOUND AND lc<>NEW.lifecycle THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Release lifecycle differs from type'; END IF;
 IF NEW.state='PUBLISHED' THEN
  FOREACH j IN ARRAY ARRAY[NEW.form_schema,NEW.route_rules,NEW.actor_bindings,NEW.sla_profile] LOOP
   IF j->'schema_version' IS DISTINCT FROM '1'::jsonb THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Published JSON requires schema_version 1'; END IF;
  END LOOP;
  IF NEW.form_schema->>'type' IS DISTINCT FROM 'object' OR NEW.form_schema->'additionalProperties' IS DISTINCT FROM 'false'::jsonb
     OR jsonb_typeof(NEW.form_schema->'properties') IS DISTINCT FROM 'object'
     OR jsonb_typeof(NEW.form_schema->'required') IS DISTINCT FROM 'array'
     OR jsonb_typeof(NEW.actor_bindings->'departments') IS DISTINCT FROM 'object'
     OR jsonb_typeof(NEW.route_rules->'rules') IS DISTINCT FROM 'array' THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Published configuration shape invalid';
  END IF;
  defaults:=0;
  FOR r IN SELECT value FROM jsonb_array_elements(NEW.route_rules->'rules') LOOP
   IF coalesce(r->>'id','')='' OR jsonb_typeof(r->'approvers') IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Route id/approvers missing';
   END IF;
   cnt:=jsonb_array_length(r->'approvers');
   IF cnt NOT BETWEEN 1 AND 5 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Route requires 1..5 approvers'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(r->'approvers') v WHERE v NOT IN ('CISO', 'CTO', 'DIRECTOR', 'DIRECT_MANAGER', 'FINANCE', 'HR_MANAGER', 'IT_MANAGER', 'LEGAL', 'MARKETING_MANAGER', 'OPERATIONS_MANAGER', 'PROCUREMENT_MANAGER', 'PROJECT_MANAGER', 'SECURITY', 'WAREHOUSE_MANAGER')) THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Unknown approver resolver';
   END IF;
   IF r->'default'='true'::jsonb THEN defaults:=defaults+1;
    IF r ? 'when' OR r ? 'priority' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Default rule has no condition/priority'; END IF;
   ELSE
    IF jsonb_typeof(r->'priority') IS DISTINCT FROM 'number' OR (r->>'priority')::numeric<>trunc((r->>'priority')::numeric)
       OR jsonb_typeof(r->'when') IS DISTINCT FROM 'object' OR r->'when'='{}'::jsonb THEN
     RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Conditional rule requires integer priority and condition';
    END IF;
    IF EXISTS(SELECT 1 FROM jsonb_each(r->'when') v WHERE v.key NOT IN ('amount_gt','amount_gte','days_gt','app_code_in') OR (v.key IN ('amount_gt','amount_gte','days_gt') AND jsonb_typeof(v.value)<>'number') OR (v.key='app_code_in' AND (jsonb_typeof(v.value)<>'array' OR jsonb_array_length(v.value)=0))) THEN
     RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Unknown condition/operator';
    END IF;
   END IF;
  END LOOP;
  IF defaults<>1 OR (NEW.route_rules->'rules'->-1->'default') IS DISTINCT FROM 'true'::jsonb THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Exactly one final default rule required';
  END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.route_rules->'rules') AS routes(item) GROUP BY item->>'id' HAVING count(*)>1)
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.route_rules->'rules') AS routes(item) WHERE item ? 'priority' GROUP BY item->>'priority' HAVING count(*)>1) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Duplicate route id or priority';
  END IF;
  IF NEW.sla_profile->>'clock' IS DISTINCT FROM 'CALENDAR_UTC' OR NEW.sla_profile->'reminder_fraction' IS DISTINCT FROM '0.5'::jsonb THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Unsupported SLA clock/reminder';
  END IF;
  FOREACH j IN ARRAY ARRAY[NEW.sla_profile->'approval_hours',NEW.sla_profile->'execution_hours',NEW.sla_profile->'acceptance_hours'] LOOP
   IF j IS NOT NULL AND j<>'null'::jsonb THEN
    IF jsonb_typeof(j)<>'number' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA hours must be numeric'; END IF;
    h:=j::text::numeric;
    IF h<=0 OR h>720 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA hours out of range'; END IF;
   END IF;
  END LOOP;
  IF jsonb_typeof(NEW.sla_profile->'approval_hours') IS DISTINCT FROM 'number'
   OR (NEW.lifecycle='A' AND (NEW.sla_profile->'execution_hours' IS DISTINCT FROM 'null'::jsonb OR NEW.sla_profile->'acceptance_hours' IS DISTINCT FROM 'null'::jsonb OR NEW.route_rules->'executor' IS DISTINCT FROM 'null'::jsonb OR NEW.route_rules->'acceptor' IS DISTINCT FROM 'null'::jsonb))
   OR (NEW.lifecycle='B' AND (jsonb_typeof(NEW.sla_profile->'execution_hours') IS DISTINCT FROM 'number' OR NEW.sla_profile->'acceptance_hours' IS DISTINCT FROM 'null'::jsonb OR COALESCE(NEW.route_rules->>'executor','') NOT IN ('EXECUTOR_ADMIN', 'EXECUTOR_ASSET', 'EXECUTOR_FACILITY', 'EXECUTOR_FINANCE', 'EXECUTOR_HR', 'EXECUTOR_IT', 'EXECUTOR_LEGAL', 'EXECUTOR_MARKETING', 'EXECUTOR_PROCUREMENT', 'EXECUTOR_TECH', 'EXECUTOR_WAREHOUSE') OR NEW.route_rules->'acceptor' IS DISTINCT FROM 'null'::jsonb))
   OR (NEW.lifecycle='C' AND (jsonb_typeof(NEW.sla_profile->'execution_hours') IS DISTINCT FROM 'number' OR jsonb_typeof(NEW.sla_profile->'acceptance_hours') IS DISTINCT FROM 'number' OR COALESCE(NEW.route_rules->>'executor','') NOT IN ('EXECUTOR_ADMIN', 'EXECUTOR_ASSET', 'EXECUTOR_FACILITY', 'EXECUTOR_FINANCE', 'EXECUTOR_HR', 'EXECUTOR_IT', 'EXECUTOR_LEGAL', 'EXECUTOR_MARKETING', 'EXECUTOR_PROCUREMENT', 'EXECUTOR_TECH', 'EXECUTOR_WAREHOUSE') OR COALESCE(NEW.route_rules->>'acceptor','') NOT IN ('CTO', 'DIRECT_MANAGER', 'LEGAL', 'PROJECT_MANAGER', 'REQUESTER'))) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Lifecycle/SLA/resolver mismatch';
  END IF;
 END IF;
 RETURN NEW;
END $function$;

-- 4. Grant privileges on new columns to eas_api
GRANT SELECT, INSERT, UPDATE (risk_weight, approval_level)
  ON eas.request_type, eas.config_release, eas.request, eas.request_revision, eas.workflow_instance
  TO eas_api;

GRANT SELECT, INSERT, UPDATE (tier_level, resolver_code)
  ON eas.approval_step
  TO eas_api;

-- 5. Register 12 Enterprise 5-Level Request Types
INSERT INTO eas.request_type(code, name, description, category, lifecycle, is_active, risk_weight, approval_level)
VALUES
  ('VISITOR_SECURITY_PASS', 'Thẻ an ninh khách & đối tác ra vào', 'Đăng ký cấp thẻ an ninh ra vào tòa nhà/phòng máy cho khách và đối tác (Cấp 1 - Duyệt 1 cấp).', 'FACILITY', 'A', true, 1, 1),
  ('TAX_INVOICE_ISSUE', 'Phát hành / điều chỉnh hóa đơn VAT', 'Đề nghị kế toán thuế xuất hoặc điều chỉnh hóa đơn GTGT cho khách hàng theo hợp đồng (Cấp 1 - Duyệt 1 cấp).', 'FINANCE', 'B', true, 1, 1),
  ('TRAINING_COURSE', 'Đăng ký đào tạo & chứng chỉ nghề nghiệp', 'Đề xuất cử nhân sự tham gia khóa đào tạo chuyên môn hoặc thi chứng chỉ quốc tế (Cấp 2 - Duyệt 2 cấp).', 'HR', 'B', true, 2, 2),
  ('NDA_PRIVACY_CLEARANCE', 'Thẩm định NDA & chia sẻ dữ liệu đối tác', 'Yêu cầu thẩm định thỏa thuận bảo mật (NDA) và phạm vi chia sẻ dữ liệu với đối tác (Cấp 2 - Duyệt 2 cấp).', 'GENERAL', 'B', true, 2, 2),
  ('INTERNAL_TRANSFER', 'Điều chuyển nội bộ & bổ nhiệm nhân sự', 'Đề xuất điều chuyển phòng ban hoặc thay đổi vị trí công tác của nhân sự (Cấp 3 - Duyệt 3 cấp).', 'HR', 'B', true, 3, 3),
  ('SPECIAL_DISCOUNT', 'Phê duyệt chiết khấu thương mại đặc biệt', 'Đề xuất áp dụng mức chiết khấu vượt khung chuẩn cho hợp đồng khách hàng B2B (Cấp 3 - Duyệt 3 cấp).', 'GENERAL', 'A', true, 3, 3),
  ('SUPPLIER_ONBOARDING', 'Thẩm định & phê duyệt nhà cung cấp mới', 'Đánh giá năng lực, mã số thuế và phê duyệt đưa nhà cung cấp mới vào danh mục chuẩn (Cấp 3 - Duyệt 3 cấp).', 'PROCUREMENT', 'B', true, 3, 3),
  ('RECRUITMENT_REQ', 'Yêu cầu tuyển dụng nhân sự (Headcount)', 'Đề xuất mở định biên tuyển dụng vị trí mới kèm ngân sách lương và nghiệm thu nhân sự (Cấp 4 - Duyệt 4 cấp).', 'HR', 'C', true, 4, 4),
  ('MARKETING_CAMPAIGN', 'Ngân sách chiến dịch Marketing & Sự kiện', 'Phê duyệt ngân sách triển khai chiến dịch quảng cáo, truyền thông và nghiệm thu KPI (Cấp 4 - Duyệt 4 cấp).', 'GENERAL', 'C', true, 4, 4),
  ('ASSET_DISPOSAL', 'Thanh lý & hủy tài sản cố định', 'Đề nghị hội đồng thẩm định, thanh lý hoặc tiêu hủy tài sản cố định hết khấu hao/hư hỏng (Cấp 4 - Duyệt 4 cấp).', 'ASSET', 'C', true, 4, 4),
  ('BUDGET_REALLOCATION', 'Điều chuyển & bổ sung ngân sách liên bộ phận', 'Yêu cầu điều chuyển hạn mức ngân sách giữa các hạng mục/phòng ban vượt ngưỡng kiểm soát (Cấp 5 - Duyệt 5 cấp).', 'FINANCE', 'C', true, 5, 5),
  ('SECURITY_INCIDENT_HOTFIX', 'Khắc phục sự cố bảo mật & Hotfix khẩn cấp', 'Phê duyệt 5 cấp xử lý sự cố an ninh thông tin trọng yếu và phát hành bản vá khẩn cấp lên Production (Cấp 5 - Duyệt 5 cấp).', 'IT', 'C', true, 5, 5)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    lifecycle = EXCLUDED.lifecycle,
    is_active = EXCLUDED.is_active,
    risk_weight = EXCLUDED.risk_weight,
    approval_level = EXCLUDED.approval_level;

COMMIT;
