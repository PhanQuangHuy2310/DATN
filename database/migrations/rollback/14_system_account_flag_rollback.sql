-- Rollback of 14_system_account_flag.sql. The API still treats the AI account
-- (EAS_AI_SYSTEM_USER_ID) as a system account without this column.
BEGIN;
SET LOCAL ROLE eas_migration;
ALTER TABLE eas.app_user DROP COLUMN IF EXISTS is_system_account;
UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
