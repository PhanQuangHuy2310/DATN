-- Request catalogue v2: 10 categories, 13 new types with published releases, IT_SUPPORT executed by IT.
-- Consolidated from the former migrations 11_request_category_regroup, 12_request_types_new, 13_it_support_executor (never applied separately).
-- One transaction: everything applies or nothing does.
-- Rollback: database/migrations/rollback/09_request_catalog_v2_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

-- ==== Part 1: 11_request_category_regroup =================================
-- Regroup request types into 10 categories, apply approved weights and
-- approval levels (= max approvers of the published route), rename, and
-- deactivate 8 duplicate types (history kept). Source: api_core/catalog/catalog_v2.json
-- Drop the category CHECK whatever its name (live: request_type_category_valid,
-- fresh installers: request_type_category_check).
DO $drop_category_check$
DECLARE c record;
BEGIN
  FOR c IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'eas.request_type'::regclass AND contype = 'c'
      AND pg_get_constraintdef(oid) ~ '\(category\)'
  LOOP
    EXECUTE format('ALTER TABLE eas.request_type DROP CONSTRAINT %I', c.conname);
  END LOOP;
END
$drop_category_check$;

-- Includes the 13 new types: a no-op on first run, and after a rollback
-- (which parks them inactive under GENERAL) it restores them before part 2.
UPDATE eas.request_type rt
SET name = v.name, category = v.category, risk_weight = v.risk_weight,
    approval_level = v.approval_level, is_active = v.is_active
FROM (VALUES
  ('ADVANCE_LARGE', 'Tạm ứng dự án lớn (>50tr)', 'FINANCE', 4, 3, true),
  ('ADVANCE_MEDIUM', 'Tạm ứng chi phí (10-50tr)', 'FINANCE', 3, 2, true),
  ('ADVANCE_SMALL', 'Tạm ứng chi phí (<10tr)', 'FINANCE', 2, 2, true),
  ('BUDGET_REALLOCATION', 'Điều chuyển & bổ sung ngân sách liên bộ phận', 'FINANCE', 5, 5, true),
  ('EQUIPMENT', 'Mua sắm thiết bị / tài sản', 'FINANCE', 3, 3, true),
  ('EXPENSE_CLAIM', 'Thanh toán chi phí', 'FINANCE', 3, 3, true),
  ('PURCHASE_REQUEST', 'Đề nghị mua sắm', 'FINANCE', 3, 3, true),
  ('REFUND_COMPENSATION', 'Hoàn tiền / Đền bù', 'FINANCE', 2, 1, true),
  ('REIMBURSEMENT', 'Quyết toán tạm ứng', 'FINANCE', 2, 2, true),
  ('SAAS_LICENSE_BUY', 'Mua bản quyền phần mềm mới', 'FINANCE', 3, 3, true),
  ('SALARY_ADVANCE', 'Ứng lương', 'FINANCE', 2, 2, true),
  ('SUPPLIER_ONBOARDING', 'Thẩm định & phê duyệt nhà cung cấp mới', 'FINANCE', 3, 3, true),
  ('TAX_INVOICE_ISSUE', 'Phát hành / điều chỉnh hóa đơn VAT', 'FINANCE', 1, 1, true),
  ('VENDOR_PAYMENT', 'Thanh toán Hợp đồng Vendor', 'FINANCE', 5, 3, true),
  ('ACCESS', 'Cấp tài khoản & quyền truy cập', 'RESOURCE', 2, 2, true),
  ('LAPTOP_PROVISION', 'Cấp máy tính / thiết bị làm việc', 'RESOURCE', 2, 1, true),
  ('OFFICE_SUPPLIES', 'Cấp văn phòng phẩm', 'RESOURCE', 1, 1, true),
  ('RESOURCE_REVOKE', 'Thu hồi tài khoản / thiết bị', 'RESOURCE', 2, 1, true),
  ('ACCESS_FACILITY', 'Cấp thẻ ra vào', 'FACILITY', 2, 2, true),
  ('EQUIPMENT_BORROW', 'Mượn thiết bị / đồ dùng', 'FACILITY', 2, 2, true),
  ('ROOM_BOOKING', 'Đặt phòng họp', 'FACILITY', 1, 1, true),
  ('VEHICLE_BOOKING', 'Mượn xe công vụ', 'FACILITY', 2, 1, true),
  ('VISITOR_SECURITY_PASS', 'Thẻ an ninh khách & đối tác ra vào', 'FACILITY', 1, 1, true),
  ('CROSS_DEPT_SUPPORT', 'Hỗ trợ liên phòng ban', 'WORK', 2, 2, true),
  ('PROJECT_INITIATION', 'Đề xuất khởi tạo dự án', 'WORK', 4, 4, true),
  ('TASK_REQUEST', 'Yêu cầu xử lý công việc', 'WORK', 1, 1, true),
  ('BUSINESS_TRIP', 'Đăng ký đi công tác', 'HR', 3, 3, true),
  ('DISCIPLINE_REQ', 'Đề xuất kỷ luật', 'HR', 4, 3, true),
  ('EMPLOYEE_ONBOARDING', 'Tiếp nhận nhân viên mới', 'HR', 3, 2, true),
  ('HR_CERTIFICATE', 'Xin giấy xác nhận công tác / thu nhập', 'HR', 1, 1, true),
  ('INTERNAL_TRANSFER', 'Điều chuyển nội bộ', 'HR', 3, 3, true),
  ('PROMOTION_REQ', 'Đề xuất thăng chức', 'HR', 4, 3, true),
  ('RECRUITMENT_REQ', 'Yêu cầu tuyển dụng nhân sự', 'HR', 4, 4, true),
  ('RESIGNATION', 'Thôi việc / Bàn giao', 'HR', 4, 3, true),
  ('REWARD_REQ', 'Đề xuất khen thưởng', 'HR', 3, 3, true),
  ('SALARY_ADJUSTMENT', 'Điều chỉnh lương', 'HR', 5, 4, true),
  ('TRAINING_COURSE', 'Đăng ký đào tạo & chứng chỉ nghề nghiệp', 'HR', 2, 2, true),
  ('ATTENDANCE_ADJUSTMENT', 'Điều chỉnh chấm công', 'TIME', 1, 1, true),
  ('LEAVE', 'Nghỉ phép', 'TIME', 1, 2, true),
  ('LEAVE_SPECIAL', 'Nghỉ phép đặc biệt', 'TIME', 2, 3, true),
  ('OVERTIME_REQ', 'Đăng ký làm thêm giờ (OT)', 'TIME', 2, 1, true),
  ('WFH_REQ', 'Làm việc từ xa (WFH)', 'TIME', 1, 1, true),
  ('DATA_UAT_EXPORT', 'Trích xuất dữ liệu / UAT', 'IT', 3, 2, true),
  ('FEATURE_RELEASE', 'Feature Request / Release', 'IT', 3, 2, true),
  ('IT_SUPPORT', 'Yêu cầu hỗ trợ IT', 'IT', 1, 1, true),
  ('PROD_DATA_ACCESS', 'Cấp quyền Dữ liệu nhạy cảm/Server', 'IT', 5, 3, true),
  ('SECURITY_INCIDENT_HOTFIX', 'Khắc phục sự cố bảo mật & Hotfix khẩn cấp', 'IT', 5, 5, true),
  ('SERVER_FIREWALL', 'Cấp Server / Firewall', 'IT', 3, 3, true),
  ('CONTRACT_APPROVAL', 'Duyệt hợp đồng', 'LEGAL', 5, 3, true),
  ('DOCUMENT_SEAL', 'Đóng dấu / ký văn bản', 'LEGAL', 2, 2, true),
  ('NDA_PRIVACY_CLEARANCE', 'Thẩm định NDA & chia sẻ dữ liệu đối tác', 'LEGAL', 2, 2, true),
  ('POLICY_ISSUANCE', 'Ban hành quy chế nội bộ', 'LEGAL', 4, 3, true),
  ('FLASH_SALE_VOUCHER', 'Flash Sale / Voucher', 'SALES', 4, 2, true),
  ('MARKETING_CAMPAIGN', 'Ngân sách chiến dịch Marketing & Sự kiện', 'SALES', 4, 4, true),
  ('SPECIAL_DISCOUNT', 'Phê duyệt chiết khấu thương mại đặc biệt', 'SALES', 3, 3, true),
  ('ASSET_DISPOSAL', 'Thanh lý & hủy tài sản cố định', 'ADMIN', 4, 4, true),
  ('FACILITY_REPAIR', 'Sửa chữa sự cố văn phòng', 'ADMIN', 2, 1, true),
  ('WAREHOUSE_TRANSFER', 'Luân chuyển kho', 'ADMIN', 3, 1, true),
  ('ASSET_PURCHASE', 'Mua sắm tài sản phòng ban', 'FINANCE', 4, 3, false),
  ('SOFTWARE_ACCESS', 'Cấp tài khoản / VPN', 'RESOURCE', 2, 2, false),
  ('ROOM_STUDIO', 'Mượn phòng họp / Studio', 'FACILITY', 1, 1, false),
  ('ROOM_VEHICLE', 'Mượn phòng họp / Xe công vụ', 'FACILITY', 1, 1, false),
  ('LEAVE_ANNUAL', 'Nghỉ phép dưới 3 ngày', 'TIME', 1, 1, false),
  ('LEAVE_LONG', 'Nghỉ phép từ 3 ngày', 'TIME', 3, 2, false),
  ('OVERTIME_APPROVAL', 'Đăng ký làm thêm giờ (OT)', 'TIME', 2, 1, false),
  ('FACILITY_MAINTENANCE', 'Sửa chữa cơ sở vật chất', 'ADMIN', 2, 1, false)
) AS v(code, name, category, risk_weight, approval_level, is_active)
WHERE rt.code = v.code;

DO $check$
BEGIN
  IF EXISTS (SELECT 1 FROM eas.request_type WHERE category <> ALL(ARRAY['FINANCE', 'RESOURCE', 'FACILITY', 'WORK', 'HR', 'TIME', 'IT', 'LEGAL', 'SALES', 'ADMIN'])) THEN
    RAISE EXCEPTION 'Some request types were not mapped to the 10 new categories';
  END IF;
END
$check$;

ALTER TABLE eas.request_type ADD CONSTRAINT request_type_category_valid
  CHECK (((category)::text = ANY ((ARRAY['FINANCE'::character varying, 'RESOURCE'::character varying, 'FACILITY'::character varying, 'WORK'::character varying, 'HR'::character varying, 'TIME'::character varying, 'IT'::character varying, 'LEGAL'::character varying, 'SALES'::character varying, 'ADMIN'::character varying])::text[])));

-- ==== Part 2: 12_request_types_new ========================================
-- 13 new request types, each with a PUBLISHED release (form, route, SLA).
-- actor_bindings reuse the per-department assignees already configured in the
-- active releases of existing types (merged at migration time; newest wins).
-- Uses the categories created in part 1. Idempotent per code.
DO $migration$
DECLARE
  bindings jsonb;
  author uuid := '00000002-0000-4000-8000-000000000001';
  t record;
  type_id uuid;
  release_id uuid;
BEGIN
  SELECT jsonb_build_object('schema_version', 1, 'departments', jsonb_object_agg(dept, slots))
  INTO bindings
  FROM (
    SELECT dept, jsonb_object_agg(slot, val) AS slots
    FROM (
      SELECT DISTINCT ON (d.key, s.key) d.key AS dept, s.key AS slot, s.value AS val
      FROM eas.config_release cr
      JOIN eas.request_type rt ON rt.active_release_id = cr.id
      CROSS JOIN LATERAL jsonb_each(cr.actor_bindings->'departments') d
      CROSS JOIN LATERAL jsonb_each(d.value) s
      ORDER BY d.key, s.key, cr.published_at DESC NULLS LAST
    ) slot_rows
    GROUP BY dept
  ) dept_rows;
  IF bindings IS NULL OR bindings->'departments' IS NULL THEN
    RAISE EXCEPTION 'No department bindings found in active releases; nothing changed.';
  END IF;

  FOR t IN
    SELECT * FROM (VALUES
    ('SALARY_ADVANCE', 'Ứng lương', 'QL trực tiếp → Kế toán ⇒ thực hiện: FINANCE', 'FINANCE', 'B', 2, 2, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"amount_vnd":{"type":"integer","minimum":1,"maximum":100000000},"reason":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","amount_vnd","reason"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","FINANCE"]}],"executor":"EXECUTOR_FINANCE","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb),
    ('RESOURCE_REVOKE', 'Thu hồi tài khoản / thiết bị', 'QL trực tiếp ⇒ thực hiện: IT ⇒ nghiệm thu: QL trực tiếp', 'RESOURCE', 'C', 2, 1, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"employee_name":{"type":"string","minLength":2,"maxLength":150},"resources":{"type":"string","minLength":3,"maxLength":1000},"effective_date":{"type":"string","format":"date"},"reason":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","employee_name","resources","effective_date","reason"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER"]}],"executor":"EXECUTOR_IT","acceptor":"DIRECT_MANAGER"}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":24}'::jsonb),
    ('VEHICLE_BOOKING', 'Mượn xe công vụ', 'QL trực tiếp ⇒ thực hiện: ADMIN ⇒ nghiệm thu: Người tạo', 'FACILITY', 'C', 2, 1, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"destination":{"type":"string","minLength":2,"maxLength":200},"start_date":{"type":"string","format":"date"},"end_date":{"type":"string","format":"date"},"passengers":{"type":"integer","minimum":1,"maximum":50},"reason":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","destination","start_date","end_date","passengers","reason"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER"]}],"executor":"EXECUTOR_ADMIN","acceptor":"REQUESTER"}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":24}'::jsonb),
    ('CROSS_DEPT_SUPPORT', 'Hỗ trợ liên phòng ban', 'QL trực tiếp → Vận hành ⇒ thực hiện: ADMIN ⇒ nghiệm thu: Người tạo', 'WORK', 'C', 2, 2, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"target_department":{"type":"string","minLength":2,"maxLength":150},"description":{"type":"string","minLength":10,"maxLength":4000},"due_date":{"type":"string","format":"date"}},"required":["title","target_department","description","due_date"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","OPERATIONS_MANAGER"]}],"executor":"EXECUTOR_ADMIN","acceptor":"REQUESTER"}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":24}'::jsonb),
    ('PROJECT_INITIATION', 'Đề xuất khởi tạo dự án', 'QL trực tiếp → PM → Kế toán → Giám đốc ⇒ thực hiện: TECH ⇒ nghiệm thu: PM', 'WORK', 'C', 4, 4, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"objective":{"type":"string","minLength":10,"maxLength":4000},"amount_vnd":{"type":"integer","minimum":1,"maximum":10000000000},"start_date":{"type":"string","format":"date"},"end_date":{"type":"string","format":"date"}},"required":["title","objective","amount_vnd","start_date","end_date"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","PROJECT_MANAGER","FINANCE","DIRECTOR"]}],"executor":"EXECUTOR_TECH","acceptor":"PROJECT_MANAGER"}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":24}'::jsonb),
    ('TASK_REQUEST', 'Yêu cầu xử lý công việc', 'QL trực tiếp ⇒ thực hiện: ADMIN ⇒ nghiệm thu: Người tạo', 'WORK', 'C', 1, 1, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"description":{"type":"string","minLength":10,"maxLength":4000},"due_date":{"type":"string","format":"date"}},"required":["title","description","due_date"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER"]}],"executor":"EXECUTOR_ADMIN","acceptor":"REQUESTER"}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":24}'::jsonb),
    ('DISCIPLINE_REQ', 'Đề xuất kỷ luật', 'QL trực tiếp → HR → Giám đốc ⇒ thực hiện: HR', 'HR', 'B', 4, 3, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"employee_name":{"type":"string","minLength":2,"maxLength":150},"violation":{"type":"string","minLength":10,"maxLength":4000},"proposed_action":{"type":"string","minLength":5,"maxLength":500}},"required":["title","employee_name","violation","proposed_action"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","HR_MANAGER","DIRECTOR"]}],"executor":"EXECUTOR_HR","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb),
    ('HR_CERTIFICATE', 'Xin giấy xác nhận công tác / thu nhập', 'HR ⇒ thực hiện: HR', 'HR', 'B', 1, 1, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"certificate_kind":{"type":"string","enum":["CONG_TAC","THU_NHAP","KHAC"]},"purpose":{"type":"string","minLength":5,"maxLength":500}},"required":["title","certificate_kind","purpose"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["HR_MANAGER"]}],"executor":"EXECUTOR_HR","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb),
    ('PROMOTION_REQ', 'Đề xuất thăng chức', 'QL trực tiếp → HR → Giám đốc ⇒ thực hiện: HR', 'HR', 'B', 4, 3, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"employee_name":{"type":"string","minLength":2,"maxLength":150},"current_position":{"type":"string","minLength":2,"maxLength":150},"proposed_position":{"type":"string","minLength":2,"maxLength":150},"effective_date":{"type":"string","format":"date"},"reason":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","employee_name","current_position","proposed_position","effective_date","reason"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","HR_MANAGER","DIRECTOR"]}],"executor":"EXECUTOR_HR","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb),
    ('REWARD_REQ', 'Đề xuất khen thưởng', 'QL trực tiếp → HR (khi amount_gt 10000000: QL trực tiếp → HR → Giám đốc) ⇒ thực hiện: FINANCE', 'HR', 'B', 3, 3, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"employee_name":{"type":"string","minLength":2,"maxLength":150},"amount_vnd":{"type":"integer","minimum":1,"maximum":500000000},"reason":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","employee_name","amount_vnd","reason"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"REWARD_LARGE","priority":10,"when":{"amount_gt":10000000},"approvers":["DIRECT_MANAGER","HR_MANAGER","DIRECTOR"]},{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","HR_MANAGER"]}],"executor":"EXECUTOR_FINANCE","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb),
    ('SALARY_ADJUSTMENT', 'Điều chỉnh lương', 'QL trực tiếp → HR → Kế toán → Giám đốc ⇒ thực hiện: HR', 'HR', 'B', 5, 4, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"employee_name":{"type":"string","minLength":2,"maxLength":150},"amount_vnd":{"type":"integer","minimum":1,"maximum":1000000000},"effective_date":{"type":"string","format":"date"},"reason":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","employee_name","amount_vnd","effective_date","reason"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","HR_MANAGER","FINANCE","DIRECTOR"]}],"executor":"EXECUTOR_HR","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb),
    ('DOCUMENT_SEAL', 'Đóng dấu / ký văn bản', 'QL trực tiếp → Pháp chế ⇒ thực hiện: ADMIN', 'LEGAL', 'B', 2, 2, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"document_name":{"type":"string","minLength":3,"maxLength":200},"copies":{"type":"integer","minimum":1,"maximum":100},"reason":{"type":"string","minLength":10,"maxLength":2000}},"required":["title","document_name","copies","reason"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","LEGAL"]}],"executor":"EXECUTOR_ADMIN","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb),
    ('POLICY_ISSUANCE', 'Ban hành quy chế nội bộ', 'QL trực tiếp → Pháp chế → Giám đốc ⇒ thực hiện: LEGAL', 'LEGAL', 'B', 4, 3, '{"schema_version":1,"type":"object","additionalProperties":false,"properties":{"title":{"type":"string","minLength":5,"maxLength":150},"policy_title":{"type":"string","minLength":5,"maxLength":200},"scope":{"type":"string","minLength":5,"maxLength":500},"effective_date":{"type":"string","format":"date"},"summary":{"type":"string","minLength":10,"maxLength":4000}},"required":["title","policy_title","scope","effective_date","summary"]}'::jsonb, '{"schema_version":1,"rules":[{"id":"DEFAULT","default":true,"approvers":["DIRECT_MANAGER","LEGAL","DIRECTOR"]}],"executor":"EXECUTOR_LEGAL","acceptor":null}'::jsonb, '{"schema_version":1,"clock":"CALENDAR_UTC","reminder_fraction":0.5,"approval_hours":24,"execution_hours":48,"acceptance_hours":null}'::jsonb)
    ) AS v(code, name, description, category, lifecycle, risk_weight, approval_level, form_schema, route_rules, sla_profile)
  LOOP
    CONTINUE WHEN EXISTS (SELECT 1 FROM eas.request_type WHERE code = t.code);
    INSERT INTO eas.request_type(code, lifecycle, is_active, name, description, category, risk_weight, approval_level)
    VALUES (t.code, t.lifecycle, true, t.name, t.description, t.category, t.risk_weight, t.approval_level)
    RETURNING id INTO type_id;
    INSERT INTO eas.config_release(
      type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
      created_by, published_by, published_at, content_sha256, risk_weight, approval_level)
    VALUES (
      type_id, 1, 'PUBLISHED', t.lifecycle, t.form_schema, t.route_rules, bindings, t.sla_profile,
      author, author, statement_timestamp(),
      encode(sha256(convert_to(jsonb_build_object(
        'form_schema', t.form_schema, 'route_rules', t.route_rules,
        'actor_bindings', bindings, 'sla_profile', t.sla_profile, 'lifecycle', t.lifecycle)::text, 'UTF8')), 'hex'),
      t.risk_weight, t.approval_level)
    RETURNING id INTO release_id;
    UPDATE eas.request_type SET active_release_id = release_id WHERE id = type_id;
  END LOOP;
END
$migration$;

-- ==== Part 3: 13_it_support_executor ======================================
-- IT_SUPPORT: work is executed by IT (EXECUTOR_IT) instead of Administration.
-- Published releases are immutable, so a new version is published and made
-- active; bindings are re-merged from active releases (same rule as 12).
DO $migration$
DECLARE
  current_release eas.config_release;
  bindings jsonb;
  new_route jsonb;
  release_id uuid;
  author uuid := '00000002-0000-4000-8000-000000000001';
BEGIN
  SELECT cr.* INTO current_release
  FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
  WHERE rt.code = 'IT_SUPPORT';
  IF NOT FOUND THEN
    -- Part of a larger migration: skip this part instead of aborting it.
    RAISE NOTICE 'IT_SUPPORT has no active release; executor change skipped.';
    RETURN;
  END IF;
  IF current_release.route_rules->>'executor' = 'EXECUTOR_IT' THEN
    RAISE NOTICE 'IT_SUPPORT already executed by IT; nothing changed.';
    RETURN;
  END IF;

  SELECT jsonb_build_object('schema_version', 1, 'departments', jsonb_object_agg(dept, slots))
  INTO bindings
  FROM (
    SELECT dept, jsonb_object_agg(slot, val) AS slots
    FROM (
      SELECT DISTINCT ON (d.key, s.key) d.key AS dept, s.key AS slot, s.value AS val
      FROM eas.config_release cr
      JOIN eas.request_type rt ON rt.active_release_id = cr.id
      CROSS JOIN LATERAL jsonb_each(cr.actor_bindings->'departments') d
      CROSS JOIN LATERAL jsonb_each(d.value) s
      ORDER BY d.key, s.key, cr.published_at DESC NULLS LAST
    ) slot_rows
    GROUP BY dept
  ) dept_rows;

  new_route := jsonb_set(current_release.route_rules, '{executor}', '"EXECUTOR_IT"');
  INSERT INTO eas.config_release(
    type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
    created_by, published_by, published_at, content_sha256, risk_weight, approval_level)
  VALUES (
    current_release.type_id,
    (SELECT max(version) + 1 FROM eas.config_release WHERE type_id = current_release.type_id),
    'PUBLISHED', current_release.lifecycle, current_release.form_schema, new_route, bindings,
    current_release.sla_profile, author, author, statement_timestamp(),
    encode(sha256(convert_to(jsonb_build_object(
      'form_schema', current_release.form_schema, 'route_rules', new_route,
      'actor_bindings', bindings, 'sla_profile', current_release.sla_profile,
      'lifecycle', current_release.lifecycle)::text, 'UTF8')), 'hex'),
    current_release.risk_weight, current_release.approval_level)
  RETURNING id INTO release_id;
  UPDATE eas.request_type SET active_release_id = release_id WHERE id = current_release.type_id;
END
$migration$;

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

-- Verification (read-only)
SELECT category, count(*) FILTER (WHERE is_active) AS active, count(*) FILTER (WHERE NOT is_active) AS inactive
FROM eas.request_type GROUP BY category ORDER BY category;
SELECT rt.code, rt.category, rt.risk_weight, rt.approval_level, cr.state
FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
WHERE rt.code IN ('SALARY_ADVANCE', 'RESOURCE_REVOKE', 'VEHICLE_BOOKING', 'CROSS_DEPT_SUPPORT', 'PROJECT_INITIATION', 'TASK_REQUEST', 'DISCIPLINE_REQ', 'HR_CERTIFICATE', 'PROMOTION_REQ', 'REWARD_REQ', 'SALARY_ADJUSTMENT', 'DOCUMENT_SEAL', 'POLICY_ISSUANCE') ORDER BY rt.category, rt.code;
SELECT cr.version, cr.route_rules->>'executor' AS executor
FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
WHERE rt.code = 'IT_SUPPORT';
