-- Rollback of 08_ai_system_account.sql. Fails (FK RESTRICT) if the AI account
-- already recorded approval decisions; those are audit history and must stay.
BEGIN;
SET LOCAL ROLE eas_migration;
UPDATE eas.role_membership SET revoked_at=statement_timestamp()
WHERE user_id='00000002-0000-4000-8000-0000000000a1' AND revoked_at IS NULL;
UPDATE eas.app_user SET is_active=false WHERE id='00000002-0000-4000-8000-0000000000a1';
UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
