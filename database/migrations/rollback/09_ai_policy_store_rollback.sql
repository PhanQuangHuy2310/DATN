-- Rollback of 09_ai_policy_store.sql. Drops stored AI policy versions:
-- export them first if they must be kept (SELECT version, document FROM eas.ai_policy_version).
BEGIN;
SET LOCAL ROLE eas_migration;
DROP TABLE IF EXISTS eas.ai_policy_version;
COMMIT;
