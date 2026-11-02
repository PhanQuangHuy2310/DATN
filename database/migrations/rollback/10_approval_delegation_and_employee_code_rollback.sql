-- Rollback of 10_approval_delegation_and_employee_code.sql.
-- Runs the former per-feature rollbacks in reverse order: 16_employee_code_rollback, 15_approval_delegation_rollback.
BEGIN;
SET LOCAL ROLE eas_migration;

-- ==== 16_employee_code_rollback ===================================
-- Rollback of 16_employee_code.sql: attendance matching falls back to email.
DROP INDEX IF EXISTS eas.app_user_employee_code_key;
ALTER TABLE eas.app_user DROP COLUMN IF EXISTS employee_code;

-- ==== 15_approval_delegation_rollback =============================
-- Rollback of 15_approval_delegation.sql. Steps already reassigned keep their
-- assignee (history); only future substitutions stop.
DROP TABLE IF EXISTS eas.approval_delegation;

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
