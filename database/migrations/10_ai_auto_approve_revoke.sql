-- Allow an approver to revoke an AI auto-approval within 24 hours.
-- Terminal requests stay immutable except for exactly one transition:
-- COMPLETED -> NEEDS_INFO, and only while the latest approval decision on the
-- current revision was made by the AI system account (migration 08) less than
-- 24 hours ago. The API then re-submits the same content for manual approval.
-- The AI account id must match EAS_AI_SYSTEM_USER_ID.
-- Rollback: database/migrations/rollback/10_ai_auto_approve_revoke_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

CREATE OR REPLACE FUNCTION eas.ai_revocable(p_request uuid)
 RETURNS boolean
 LANGUAGE sql STABLE
 SET search_path TO 'pg_catalog', 'eas'
AS $function$
  SELECT COALESCE((
    SELECT d.actor_id = '00000002-0000-4000-8000-0000000000a1'::uuid
       AND d.decided_at > statement_timestamp() - interval '24 hours'
    FROM eas.approval_decision d
    JOIN eas.approval_step s ON s.id = d.step_id
    JOIN eas.workflow_instance i ON i.id = s.instance_id
    JOIN eas.request r ON r.id = d.request_id AND r.current_revision_id = i.revision_id
    WHERE d.request_id = p_request
    ORDER BY d.decided_at DESC
    LIMIT 1
  ), false)
$function$;
REVOKE ALL ON FUNCTION eas.ai_revocable(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eas.ai_revocable(uuid) TO eas_api;

CREATE OR REPLACE FUNCTION eas.guard_request()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'eas'
AS $function$
DECLARE origin_owner uuid; lc char(1); tcode varchar(30); allowed boolean; ai_revoke boolean := false;
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
  IF OLD.status IN ('COMPLETED','REJECTED','CANCELLED') AND NEW IS DISTINCT FROM OLD AND NOT ai_revoke THEN
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
     OR ai_revoke;
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
END $function$;

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT 'ai_revocable' AS installed, to_regprocedure('eas.ai_revocable(uuid)') IS NOT NULL AS ok;
