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
    IF EXISTS(SELECT 1 FROM jsonb_each(r->'when') v WHERE v.key NOT IN ('amount_gt','amount_gte') OR jsonb_typeof(v.value)<>'number') THEN
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
COMMIT;
