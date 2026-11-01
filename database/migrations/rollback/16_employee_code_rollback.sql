-- Rollback of 16_employee_code.sql: attendance matching falls back to email.
BEGIN;
SET LOCAL ROLE eas_migration;
DROP INDEX IF EXISTS eas.app_user_employee_code_key;
ALTER TABLE eas.app_user DROP COLUMN IF EXISTS employee_code;
UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
