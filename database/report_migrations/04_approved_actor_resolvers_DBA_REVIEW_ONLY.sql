-- REVIEW ONLY. Not auto-applied. Requires DBA approval and full DB backup.
-- Keep all existing security/immutability/audit guards. Expand only explicit
-- actor resolver allowlists for configured A/B/C workflows from plan.docx.
-- Does NOT enable auto approval, parallel execution, delegated signature,
-- automatically create users, grant roles, or change existing releases.
-- Verify live eas.guard_release() matches the bundled schema BEFORE applying.
BEGIN;
SET LOCAL statement_timeout = '15s';
CREATE OR REPLACE FUNCTION eas.guard_release() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
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
   IF cnt NOT BETWEEN 1 AND 3 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Route requires 1..3 approvers'; END IF;
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


CREATE OR REPLACE FUNCTION eas.guard_request() RETURNS trigger LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'eas' AS $
DECLARE origin_owner uuid; lc char(1); tcode varchar(30); allowed boolean;
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
  IF OLD.status IN ('COMPLETED','REJECTED','CANCELLED') AND NEW IS DISTINCT FROM OLD THEN
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
     OR (OLD.status='WAITING_FOR_ACCEPTANCE' AND NEW.status IN ('READY_FOR_EXECUTION','COMPLETED'));
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
END $;

CREATE OR REPLACE FUNCTION eas.guard_revision() RETURNS trigger LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'eas' AS $
DECLARE r eas.request; c eas.config_release; tcode varchar(30);
BEGIN
 PERFORM eas.lock_security(false);
 SELECT * INTO r FROM eas.request WHERE id=NEW.request_id FOR UPDATE;
 IF NOT FOUND THEN RETURN NEW; END IF;
 SELECT * INTO c FROM eas.config_release WHERE id=NEW.release_id;
 IF NOT FOUND THEN RETURN NEW; END IF;
 SELECT code INTO tcode FROM eas.request_type WHERE id=r.type_id;
 IF r.status NOT IN ('DRAFT','NEEDS_INFO') OR c.type_id<>r.type_id OR c.state<>'PUBLISHED' OR NEW.submitted_by<>r.requester_id
   OR (tcode IN ('LEAVE','ACCESS') AND NEW.amount_vnd IS NOT NULL) OR (tcode='EQUIPMENT' AND NEW.amount_vnd IS NULL) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Revision release/owner/amount invalid';
 END IF;
 IF NEW.revision_no<>(SELECT coalesce(max(revision_no),0)+1 FROM eas.request_revision WHERE request_id=NEW.request_id) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Revision numbers must be consecutive per request';
 END IF;
 RETURN NEW;
END $;

CREATE OR REPLACE FUNCTION eas.check_submission_files() RETURNS trigger LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'eas' AS $
DECLARE a eas.execution_attempt; n integer; tcode varchar(30);
BEGIN
 IF TG_TABLE_NAME='execution_attempt' THEN
  SELECT * INTO a FROM eas.execution_attempt WHERE id=NEW.id;
  IF NOT FOUND OR a.submitted_at IS NULL THEN RETURN NULL; END IF;
  SELECT count(*) INTO n FROM eas.execution_attachment WHERE attempt_id=a.id;
  IF n NOT BETWEEN 1 AND 5 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Submitted result requires 1..5 evidence files'; END IF;
 ELSE
  SELECT rt.code INTO tcode FROM eas.request_revision v JOIN eas.config_release c ON c.id=v.release_id JOIN eas.request_type rt ON rt.id=c.type_id WHERE v.id=NEW.id;
  IF NOT FOUND THEN RETURN NULL; END IF;
  SELECT count(*) INTO n FROM eas.revision_attachment WHERE revision_id=NEW.id;
  IF n>5 OR (tcode='EQUIPMENT' AND n=0) THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Equipment revision requires quote; maximum five files'; END IF;
 END IF;
 RETURN NULL;
END $;
COMMIT;
