-- Rollback of 08_ai_auto_approval.sql.
-- Runs the former per-feature rollbacks in reverse order: 10_ai_auto_approve_revoke_rollback, 09_ai_policy_store_rollback, 14_system_account_flag_rollback, 08_ai_system_account_rollback.
BEGIN;
SET LOCAL ROLE eas_migration;

-- ==== 10_ai_auto_approve_revoke_rollback ==========================
-- Rollback of 10_ai_auto_approve_revoke.sql: restores the original
-- eas.guard_request (terminal requests fully immutable) and drops eas.ai_revocable.
CREATE OR REPLACE FUNCTION eas.guard_request()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'eas'
AS $function$
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
END $function$;
DROP FUNCTION IF EXISTS eas.ai_revocable(uuid);

-- ==== 09_ai_policy_store_rollback =================================
-- Rollback of 09_ai_policy_store.sql. Drops stored AI policy versions:
-- export them first if they must be kept (SELECT version, document FROM eas.ai_policy_version).
DROP TABLE IF EXISTS eas.ai_policy_version;

-- ==== 14_system_account_flag_rollback =============================
-- Rollback of 14_system_account_flag.sql. The API still treats the AI account
-- (EAS_AI_SYSTEM_USER_ID) as a system account without this column.
ALTER TABLE eas.app_user DROP COLUMN IF EXISTS is_system_account;

-- ==== 08_ai_system_account_rollback ===============================
-- Rollback of 08_ai_system_account.sql. Fails (FK RESTRICT) if the AI account
-- already recorded approval decisions; those are audit history and must stay.
UPDATE eas.role_membership SET revoked_at=statement_timestamp()
WHERE user_id='00000002-0000-4000-8000-0000000000a1' AND revoked_at IS NULL;
UPDATE eas.app_user SET is_active=false WHERE id='00000002-0000-4000-8000-0000000000a1';

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
