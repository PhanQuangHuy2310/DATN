-- 13 new request types, each with a PUBLISHED release (form, route, SLA).
-- actor_bindings reuse the per-department assignees already configured in the
-- active releases of existing types (merged at migration time; newest wins).
-- Requires 11_request_category_regroup.sql (new categories). Idempotent per code.
-- Rollback: database/migrations/rollback/12_request_types_new_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

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

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT rt.code, rt.category, rt.risk_weight, rt.approval_level, cr.state
FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
WHERE rt.code IN ('SALARY_ADVANCE', 'RESOURCE_REVOKE', 'VEHICLE_BOOKING', 'CROSS_DEPT_SUPPORT', 'PROJECT_INITIATION', 'TASK_REQUEST', 'DISCIPLINE_REQ', 'HR_CERTIFICATE', 'PROMOTION_REQ', 'REWARD_REQ', 'SALARY_ADJUSTMENT', 'DOCUMENT_SEAL', 'POLICY_ISSUANCE') ORDER BY rt.category, rt.code;
