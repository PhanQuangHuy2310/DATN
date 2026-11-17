-- 23: AI suy luận tình huống xấu: nâng luồng TỪNG HỒ SƠ A -> B/C, lùi hạn SLA có kiểm soát,
--     và lưu đề xuất xử lý của AI (quản lý xác nhận).
--
-- Bối cảnh (đặc tả nhóm 18/11/2026): chỉ luồng A có AI tự duyệt. Khi một hồ sơ A dính tình huống xấu
-- (vd. xin nghỉ khi đang giữ việc mai đến hạn), hệ thống phải chuyển CHÍNH hồ sơ đó sang luồng B
-- (quản lý duyệt -> bộ phận chuyên môn xử lý) hoặc C (+ nghiệm thu độc lập), mà không đổi luồng của
-- cả loại yêu cầu và không đổi 58 loại (mô hình phân loại giữ nguyên nhãn).
--
--   1. config_release.escalation: bản cấu hình "nâng cấp" của một loại A, vòng đời B hoặc C.
--      Không bao giờ là bản đang dùng (active) của loại; chỉ được gắn vào revision khi AI nâng luồng.
--   2. guard_release: cho phép bản nâng cấp có vòng đời CAO HƠN vòng đời của loại.
--   3. guard_active_release: bản nâng cấp không được làm bản đang dùng.
--   4. guard_request: kiểm tra trạng thái theo vòng đời của REVISION hiện tại (hồ sơ đã nâng lên B
--      được vào READY_FOR_EXECUTION dù loại là A). Hồ sơ chưa nâng giữ nguyên hành vi cũ.
--   5. guard_sla: hạn SLA chỉ được LÙI về sau, khi backend đặt cờ eas.sla_extend_stage_id cho đúng
--      giai đoạn đó, giai đoạn chưa đóng và chưa vi phạm (hướng xử lý "lùi hạn" do quản lý xác nhận).
--   6. Bản nâng cấp B và C cho 9 loại A (tuyến duyệt gốc + bộ phận chuyên môn xử lý; C thêm cấp duyệt
--      và nghiệm thu bởi quản lý trực tiếp).
--   7. eas.ai_remediation: đề xuất xử lý gốc rễ của AI và quyết định của quản lý (append + đổi trạng thái).
--
-- Chạy được nhiều lần (idempotent). Rollback: database/migrations/rollback/23_ai_bad_case_escalation_rollback.sql

BEGIN;
SELECT eas.lock_security(true);

-- ==== 1. Cột đánh dấu bản nâng cấp ===========================================================
ALTER TABLE eas.config_release ADD COLUMN IF NOT EXISTS escalation boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN eas.config_release.escalation IS
  'Bản cấu hình nâng cấp (B/C) của loại luồng A, chỉ gắn vào hồ sơ bị AI nâng luồng; không bao giờ là bản đang dùng.';
CREATE INDEX IF NOT EXISTS config_release_escalation
  ON eas.config_release(type_id, lifecycle) WHERE escalation AND state = 'PUBLISHED';

-- ==== 2. guard_release ===========================================================================
CREATE OR REPLACE FUNCTION eas.guard_release() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
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
 -- 23: bản nâng cấp (escalation) được phép có vòng đời CAO HƠN vòng đời của loại.
 IF FOUND AND lc<>NEW.lifecycle AND NOT (NEW.escalation AND NEW.lifecycle > lc) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Release lifecycle differs from type';
 END IF;
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
END $$;
ALTER FUNCTION eas.guard_release() OWNER TO eas_migration;

-- ==== 3. guard_active_release =====================================================================
CREATE OR REPLACE FUNCTION eas.guard_active_release() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.code<>OLD.code) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request type identity immutable';
 END IF;
 IF NEW.active_release_id IS NOT NULL AND NOT EXISTS(
   SELECT 1 FROM eas.config_release
   WHERE id=NEW.active_release_id AND type_id=NEW.id AND state='PUBLISHED' AND NOT escalation) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Active release must be a published non-escalation release for this type';
 END IF;
 RETURN NEW;
END;
$$;
ALTER FUNCTION eas.guard_active_release() OWNER TO eas_migration;

-- ==== 4. guard_request: vòng đời theo revision hiện tại ==========================================
CREATE OR REPLACE FUNCTION eas.guard_request() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
DECLARE origin_owner uuid; lc char(1); rlc char(1); tcode varchar(30); allowed boolean;
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
 -- 23: hồ sơ được AI nâng luồng mang vòng đời của bản cấu hình gắn với revision hiện tại.
 IF NEW.current_revision_id IS NOT NULL THEN
  SELECT c.lifecycle INTO rlc FROM eas.request_revision v JOIN eas.config_release c ON c.id=v.release_id
  WHERE v.id=NEW.current_revision_id;
  IF rlc IS NOT NULL THEN lc := rlc; END IF;
 END IF;
 IF tcode IS NOT NULL AND ((tcode IN ('LEAVE','ACCESS') AND NEW.draft_amount_vnd IS NOT NULL) OR (lc='A' AND NEW.status IN ('READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE')) OR (lc='B' AND NEW.status='WAITING_FOR_ACCEPTANCE')) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request lifecycle/amount mismatch';
 END IF;
 IF NEW.status NOT IN ('DRAFT','CANCELLED') AND NEW.current_revision_id IS NULL THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Submitted request requires current revision';
 END IF;
 RETURN NEW;
END $$;
ALTER FUNCTION eas.guard_request() OWNER TO eas_migration;

-- ==== 5. guard_sla: lùi hạn có kiểm soát =======================================================
CREATE OR REPLACE FUNCTION eas.guard_sla() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
DECLARE old_instance uuid; new_instance uuid; old_closure text; extend boolean;
BEGIN
 -- 23: chỉ LÙI hạn, chỉ khi backend đặt cờ cho đúng giai đoạn này, giai đoạn chưa đóng/chưa vi phạm.
 extend := coalesce(current_setting('eas.sla_extend_stage_id', true), '') = OLD.id::text
   AND NEW.due_at > OLD.due_at AND OLD.closed_at IS NULL AND OLD.breached_at IS NULL;
 IF ROW(NEW.id,NEW.request_id,NEW.kind,NEW.approval_step_id,NEW.started_at) IS DISTINCT FROM ROW(OLD.id,OLD.request_id,OLD.kind,OLD.approval_step_id,OLD.started_at)
  OR (NEW.due_at IS DISTINCT FROM OLD.due_at AND NOT extend)
  OR (OLD.closed_at IS NOT NULL AND NEW IS DISTINCT FROM OLD)
  OR (OLD.breached_at IS NOT NULL AND NEW.breached_at IS DISTINCT FROM OLD.breached_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA identity/deadline/closed history immutable';
 END IF;
 IF NEW.attempt_id IS DISTINCT FROM OLD.attempt_id THEN
  SELECT instance_id,closure_kind INTO old_instance,old_closure FROM eas.execution_attempt WHERE id=OLD.attempt_id;
  SELECT instance_id INTO new_instance FROM eas.execution_attempt WHERE id=NEW.attempt_id;
  IF NEW.kind<>'EXECUTION' OR old_instance IS DISTINCT FROM new_instance OR old_closure IS DISTINCT FROM 'REASSIGNED' THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA target can change only for reassigned execution in same instance';
  END IF;
 END IF;
 RETURN NEW;
END $$;
ALTER FUNCTION eas.guard_sla() OWNER TO eas_migration;

-- ==== 6. Bản nâng cấp B và C cho 9 loại luồng A ================================================
DO $esc$
DECLARE
  -- loại -> (bộ phận xử lý, cấp duyệt thêm ở B, cấp duyệt thêm ở C)
  plan constant jsonb := '{
    "LEAVE":                 ["EXECUTOR_HR",       [],          ["HR_MANAGER"]],
    "LEAVE_SPECIAL":         ["EXECUTOR_HR",       [],          ["HR_MANAGER"]],
    "ATTENDANCE_ADJUSTMENT": ["EXECUTOR_HR",       [],          ["HR_MANAGER"]],
    "WFH_REQ":               ["EXECUTOR_HR",       [],          ["HR_MANAGER"]],
    "EXPENSE_CLAIM":         ["EXECUTOR_FINANCE",  ["FINANCE"], ["FINANCE", "DIRECTOR"]],
    "REFUND_COMPENSATION":   ["EXECUTOR_FINANCE",  ["FINANCE"], ["FINANCE", "DIRECTOR"]],
    "SPECIAL_DISCOUNT":      ["EXECUTOR_FINANCE",  ["FINANCE"], ["FINANCE", "DIRECTOR"]],
    "ROOM_BOOKING":          ["EXECUTOR_FACILITY", [],          []],
    "VISITOR_SECURITY_PASS": ["EXECUTOR_ADMIN",    [],          ["SECURITY"]]
  }';
  author uuid;
  t record;
  lc text;
  extra jsonb;
  new_rules jsonb;
  route jsonb;
  sla jsonb;
  rule jsonb;
  approvers jsonb;
  a text;
BEGIN
  SELECT u.id INTO author FROM eas.app_user u WHERE u.account_type = 'ADMIN' AND u.is_active
  ORDER BY u.created_at LIMIT 1;
  FOR t IN
    SELECT rt.id AS type_id, rt.code, cr.*
    FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
    WHERE rt.code IN (SELECT jsonb_object_keys(plan)) AND rt.lifecycle = 'A' AND cr.lifecycle = 'A'
  LOOP
    FOREACH lc IN ARRAY ARRAY['B', 'C'] LOOP
      CONTINUE WHEN EXISTS (
        SELECT 1 FROM eas.config_release e
        WHERE e.type_id = t.type_id AND e.escalation AND e.lifecycle = lc AND e.state = 'PUBLISHED');
      extra := plan->t.code->(CASE WHEN lc = 'B' THEN 1 ELSE 2 END);
      new_rules := '[]'::jsonb;
      FOR rule IN SELECT value FROM jsonb_array_elements(t.route_rules->'rules') LOOP
        approvers := rule->'approvers';
        FOR a IN SELECT jsonb_array_elements_text(extra) LOOP
          IF NOT approvers ? a AND jsonb_array_length(approvers) < 5 THEN
            approvers := approvers || to_jsonb(a);
          END IF;
        END LOOP;
        new_rules := new_rules || jsonb_build_array(jsonb_set(rule, '{approvers}', approvers));
      END LOOP;
      route := jsonb_build_object(
        'schema_version', 1,
        'rules', new_rules,
        'executor', plan->t.code->>0,
        'acceptor', CASE WHEN lc = 'C' THEN to_jsonb('DIRECT_MANAGER'::text) ELSE 'null'::jsonb END);
      sla := t.sla_profile
        || jsonb_build_object('execution_hours', 24)
        || jsonb_build_object('acceptance_hours', CASE WHEN lc = 'C' THEN to_jsonb(24) ELSE 'null'::jsonb END);
      INSERT INTO eas.config_release(
        type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
        created_by, published_by, published_at, content_sha256, escalation)
      VALUES (
        t.type_id, (SELECT max(version) + 1 FROM eas.config_release WHERE type_id = t.type_id),
        'PUBLISHED', lc, t.form_schema, route, t.actor_bindings, sla,
        coalesce(author, t.created_by), coalesce(author, t.created_by), statement_timestamp(),
        encode(sha256(convert_to(jsonb_build_object(
          'form_schema', t.form_schema, 'route_rules', route, 'actor_bindings', t.actor_bindings,
          'sla_profile', sla, 'lifecycle', lc, 'escalation', true)::text, 'UTF8')), 'hex'),
        true);
    END LOOP;
  END LOOP;
END
$esc$;

-- ==== 7. Đề xuất xử lý của AI ==================================================================
CREATE TABLE IF NOT EXISTS eas.ai_remediation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE CASCADE,
  case_code varchar(60) NOT NULL CHECK (case_code ~ '^[A-Z][A-Z0-9_]{2,59}$'),
  state varchar(12) NOT NULL DEFAULT 'PROPOSED'
    CHECK (state IN ('PROPOSED', 'CONFIRMED', 'DISMISSED', 'FAILED')),
  proposal jsonb NOT NULL CHECK (jsonb_typeof(proposal) = 'object'),
  model_version varchar(60) NOT NULL,
  chosen jsonb,
  result jsonb,
  proposed_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  decided_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  decided_at timestamptz,
  CHECK ((state = 'PROPOSED') = (decided_at IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS ai_remediation_open
  ON eas.ai_remediation(request_id, case_code) WHERE state = 'PROPOSED';
CREATE INDEX IF NOT EXISTS ai_remediation_request ON eas.ai_remediation(request_id, proposed_at DESC);
COMMENT ON TABLE eas.ai_remediation IS
  'Hướng xử lý gốc rễ AI đề xuất cho hồ sơ dính tình huống xấu; quản lý xác nhận hoặc bỏ qua. Không xóa, chỉ đổi trạng thái một lần.';

CREATE OR REPLACE FUNCTION eas.guard_ai_remediation() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='AI remediation history is append-only';
 END IF;
 IF OLD.state <> 'PROPOSED' THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Decided AI remediation is immutable';
 END IF;
 IF ROW(NEW.id, NEW.request_id, NEW.case_code, NEW.proposal, NEW.model_version, NEW.proposed_at)
    IS DISTINCT FROM ROW(OLD.id, OLD.request_id, OLD.case_code, OLD.proposal, OLD.model_version, OLD.proposed_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='AI proposal is immutable';
 END IF;
 RETURN NEW;
END $$;
ALTER FUNCTION eas.guard_ai_remediation() OWNER TO eas_migration;
REVOKE EXECUTE ON FUNCTION eas.guard_ai_remediation() FROM PUBLIC;
DROP TRIGGER IF EXISTS ai_remediation_guard ON eas.ai_remediation;
CREATE TRIGGER ai_remediation_guard BEFORE UPDATE OR DELETE ON eas.ai_remediation
  FOR EACH ROW EXECUTE FUNCTION eas.guard_ai_remediation();

REVOKE ALL ON eas.ai_remediation FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON eas.ai_remediation TO eas_api, eas_worker;
GRANT SELECT ON eas.ai_remediation TO eas_backup;
ALTER TABLE eas.ai_remediation ENABLE ROW LEVEL SECURITY;
DO $pol$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='eas' AND tablename='ai_remediation' AND policyname='backend_read') THEN
    CREATE POLICY backend_read ON eas.ai_remediation FOR SELECT TO eas_api, eas_worker USING (true);
    CREATE POLICY backend_insert ON eas.ai_remediation FOR INSERT TO eas_api, eas_worker WITH CHECK (state = 'PROPOSED');
    CREATE POLICY backend_decide ON eas.ai_remediation FOR UPDATE TO eas_api, eas_worker
      USING (state = 'PROPOSED') WITH CHECK (state IN ('CONFIRMED', 'DISMISSED', 'FAILED'));
    CREATE POLICY backup_read ON eas.ai_remediation FOR SELECT TO eas_backup USING (true);
  END IF;
END
$pol$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- ==== Kiểm tra =================================================================================
DO $check$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM eas.config_release WHERE escalation AND state = 'PUBLISHED';
  IF n < 18 THEN RAISE EXCEPTION '23: expected 18 escalation releases, found %', n; END IF;
  IF EXISTS (SELECT 1 FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
             WHERE cr.escalation) THEN
    RAISE EXCEPTION '23: an escalation release became active';
  END IF;
END
$check$;

COMMIT;

-- Xem lại (chỉ đọc)
SELECT rt.code, cr.lifecycle, cr.version, cr.route_rules->>'executor' AS executor,
       cr.route_rules->>'acceptor' AS acceptor
FROM eas.config_release cr JOIN eas.request_type rt ON rt.id = cr.type_id
WHERE cr.escalation ORDER BY rt.code, cr.lifecycle;
