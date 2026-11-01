-- Approval delegation: an approver hands their approval steps to a colleague
-- for a time window. When a step is activated the workflow uses the active
-- delegate; with no delegate and the approver absent (HRM attendance) it
-- escalates to the approver's direct manager.
-- Rollback: database/migrations/rollback/15_approval_delegation_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

CREATE TABLE eas.approval_delegation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delegator_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  delegate_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  reason varchar(500) NOT NULL CHECK (length(btrim(reason)) BETWEEN 5 AND 500),
  created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  revoked_at timestamptz,
  CHECK (delegator_id <> delegate_id),
  CHECK (ends_at > starts_at AND ends_at <= starts_at + interval '90 days')
);
CREATE INDEX approval_delegation_active
  ON eas.approval_delegation(delegator_id, starts_at, ends_at) WHERE revoked_at IS NULL;
COMMENT ON TABLE eas.approval_delegation IS 'Ủy quyền duyệt theo khoảng thời gian; thu hồi bằng revoked_at, không xóa.';

GRANT SELECT, INSERT, UPDATE ON eas.approval_delegation TO eas_api;
ALTER TABLE eas.approval_delegation ENABLE ROW LEVEL SECURITY;
CREATE POLICY trusted_backend ON eas.approval_delegation
  FOR ALL TO eas_api USING (true) WITH CHECK (true);

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT to_regclass('eas.approval_delegation') AS created;
