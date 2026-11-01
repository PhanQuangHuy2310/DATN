-- Rollback of 15_approval_delegation.sql. Steps already reassigned keep their
-- assignee (history); only future substitutions stop.
BEGIN;
SET LOCAL ROLE eas_migration;
DROP TABLE IF EXISTS eas.approval_delegation;
UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
