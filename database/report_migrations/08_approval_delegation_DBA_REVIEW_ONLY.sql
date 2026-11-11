-- REVIEW ONLY. Not auto-applied. Requires owner approval (C3), DBA review and a
-- full backup. Adds time-limited approval delegation (thesis §2.3.4
-- "Temporary Delegation", Appendix SD-22).
--
-- Why a new table (role_membership is not enough):
--   role_membership can grant a deputy a time-boxed APPROVER role, but routing
--   assigns *specific people* (requester's manager, slot bindings). A grant has
--   no "on behalf of whom", so the deputy would never receive the delegator's
--   work, and the grant cannot record who delegated, who revoked, or why.
--
-- Additive only: new table, indexes, RLS policies, grants. No existing row,
-- constraint, trigger or published release is changed.
--
-- Enable in the application only AFTER this has been applied:
--   EAS_APPROVAL_DELEGATION=1   (api_core/workflow/service.py; default off)
--
-- BEFORE RUNNING: pg_dump --schema=eas --schema-only > eas_schema_before_08.sql
-- ROLLBACK (no data loss only while the table is empty):
--   BEGIN;
--   SELECT count(*) FROM eas.approval_delegation;   -- review/export rows first
--   DROP TABLE eas.approval_delegation;
--   COMMIT;
--   Unset EAS_APPROVAL_DELEGATION before rolling back.

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';

CREATE TABLE eas.approval_delegation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delegator_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  delegate_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  -- Optional narrowing; NULL means every department / type the delegator approves.
  department_id uuid REFERENCES eas.department(id) ON DELETE RESTRICT,
  type_id uuid REFERENCES eas.request_type(id) ON DELETE RESTRICT,
  valid_from timestamptz NOT NULL,
  -- Time-limited by definition: an open-ended delegation is not allowed.
  valid_to timestamptz NOT NULL,
  reason varchar(500) NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 500),
  created_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  revoked_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  CONSTRAINT delegation_not_self CHECK (delegator_id <> delegate_id),
  CONSTRAINT delegation_interval CHECK (valid_to > valid_from),
  CONSTRAINT delegation_revocation CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
  CONSTRAINT delegation_revoked_after_create CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);
COMMENT ON TABLE eas.approval_delegation IS
  'Ủy quyền phê duyệt tạm thời có thời hạn (valid_from/valid_to/revoked_at); áp dụng khi định tuyến lúc gửi, không bắc cầu.';

CREATE INDEX ix_approval_delegation_active
  ON eas.approval_delegation (delegator_id, valid_from, valid_to)
  WHERE revoked_at IS NULL;
CREATE INDEX ix_approval_delegation_delegate ON eas.approval_delegation (delegate_id);

ALTER TABLE eas.approval_delegation ENABLE ROW LEVEL SECURITY;
CREATE POLICY trusted_backend ON eas.approval_delegation
  FOR ALL TO eas_api, eas_worker, eas_privacy USING (true) WITH CHECK (true);
CREATE POLICY backup_read ON eas.approval_delegation FOR SELECT TO eas_backup USING (true);

GRANT SELECT ON eas.approval_delegation TO eas_api, eas_worker, eas_backup;
GRANT INSERT ON eas.approval_delegation TO eas_api;
-- Only revocation may change a row after creation.
GRANT UPDATE (revoked_at, revoked_by) ON eas.approval_delegation TO eas_api;

DO $verify$
BEGIN
  IF to_regclass('eas.approval_delegation') IS NULL THEN
    RAISE EXCEPTION 'approval_delegation not created';
  END IF;
END
$verify$;

COMMIT;
