-- AI auto-approval: system account (+ is_system_account flag), AI policy store, 24h revoke.
-- Consolidated from the former migrations 08_ai_system_account, 14_system_account_flag, 09_ai_policy_store, 10_ai_auto_approve_revoke (never applied separately).
-- One transaction: everything applies or nothing does. Schema changes (DDL) run
-- before data changes: app_user has deferred constraint triggers, and an ALTER
-- after an INSERT in the same transaction fails with "pending trigger events".
-- Rollback: database/migrations/rollback/08_ai_auto_approval_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

-- ==== Part 1: 14_system_account_flag ======================================
-- Flag non-human accounts (EAS AI). The admin API hides them by default and
-- refuses to edit, disable or re-permission them (SYSTEM_ACCOUNT_LOCKED).
ALTER TABLE eas.app_user ADD COLUMN IF NOT EXISTS is_system_account boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN eas.app_user.is_system_account IS 'Tài khoản hệ thống (không đăng nhập, không sửa qua UI/API quản trị).';

-- ==== Part 2: 09_ai_policy_store ==========================================
-- AI policy rules are stored here (source of truth). The AI service keeps only
-- a cached copy: the API pushes each activated version, and an AI container
-- that starts without a cache pulls the active version from the API.
-- Existing file-based policy: python manage.py import_ai_policy_file <path>
CREATE TABLE eas.ai_policy_version (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version varchar(50) NOT NULL UNIQUE CHECK (length(btrim(version)) > 0),
  document jsonb NOT NULL CHECK (jsonb_typeof(document->'rules') = 'array'),
  state varchar(8) NOT NULL DEFAULT 'INACTIVE' CHECK (state IN ('ACTIVE','INACTIVE')),
  created_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  activated_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  activated_at timestamptz,
  CHECK (state = 'INACTIVE' OR activated_at IS NOT NULL)
);
CREATE UNIQUE INDEX ai_policy_one_active ON eas.ai_policy_version(state) WHERE state = 'ACTIVE';
CREATE INDEX ai_policy_created ON eas.ai_policy_version(created_at DESC);
COMMENT ON TABLE eas.ai_policy_version IS 'Bộ luật quy định AI theo phiên bản; đúng một phiên bản ACTIVE.';

GRANT SELECT, INSERT, UPDATE ON eas.ai_policy_version TO eas_api;
ALTER TABLE eas.ai_policy_version ENABLE ROW LEVEL SECURITY;
CREATE POLICY trusted_backend ON eas.ai_policy_version
  FOR ALL TO eas_api USING (true) WITH CHECK (true);

-- ==== Part 3: 10_ai_auto_approve_revoke ===================================
-- Allow an approver to revoke an AI auto-approval within 24 hours.
-- Terminal requests stay immutable except for exactly one transition:
-- COMPLETED -> NEEDS_INFO, and only while the latest approval decision on the
-- current revision was made by the AI system account (migration 08) less than
-- 24 hours ago. The API then re-submits the same content for manual approval.
-- The AI account id must match EAS_AI_SYSTEM_USER_ID.
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

-- ==== Part 4: 08_ai_system_account ========================================
-- AI auto-approval actor. Approval decisions must reference a real app_user
-- that is the step assignee, so the worker hands low-risk steps (weight <= 2)
-- to this account before approving. The password hash is unusable: nobody
-- can sign in as this account. Matches EAS_AI_SYSTEM_USER_ID in settings.
INSERT INTO eas.app_user(id,email,display_name,department_id,password_hash,must_change_password,is_active,is_system_account)
SELECT '00000002-0000-4000-8000-0000000000a1','ai.system@eas.com','EAS AI (tự động duyệt)',
       d.id,'!UNUSABLE_AI_SYSTEM',false,true,true
FROM eas.department d
-- Board department when it exists, otherwise the first department (demo DBs).
ORDER BY (d.code = 'BOD') DESC, d.code
LIMIT 1
ON CONFLICT (id) DO NOTHING;

INSERT INTO eas.role_membership(user_id,role,scope_kind,department_id,type_scope,type_id,valid_from)
SELECT '00000002-0000-4000-8000-0000000000a1','APPROVER','GLOBAL',NULL,'ALL',NULL,statement_timestamp()
WHERE NOT EXISTS (
  SELECT 1 FROM eas.role_membership
  WHERE user_id='00000002-0000-4000-8000-0000000000a1' AND role='APPROVER' AND revoked_at IS NULL
);


-- Re-run safety: the account may already exist (e.g. deactivated by the
-- rollback, which keeps it because decisions reference it).
UPDATE eas.app_user SET is_system_account = true, is_active = true
WHERE id = '00000002-0000-4000-8000-0000000000a1'
  AND (NOT is_system_account OR NOT is_active);

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

-- Verification (read-only)
SELECT u.email, u.is_active, array_agg(m.role) AS roles
FROM eas.app_user u JOIN eas.role_membership m ON m.user_id=u.id AND m.revoked_at IS NULL
WHERE u.id='00000002-0000-4000-8000-0000000000a1'
GROUP BY u.email, u.is_active;
SELECT email, is_system_account FROM eas.app_user WHERE is_system_account;
SELECT to_regclass('eas.ai_policy_version') AS created;
SELECT 'ai_revocable' AS installed, to_regprocedure('eas.ai_revocable(uuid)') IS NOT NULL AS ok;
