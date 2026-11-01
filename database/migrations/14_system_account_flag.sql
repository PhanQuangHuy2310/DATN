-- Flag non-human accounts (EAS AI). The admin API hides them by default and
-- refuses to edit, disable or re-permission them (SYSTEM_ACCOUNT_LOCKED).
-- Rollback: database/migrations/rollback/14_system_account_flag_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

ALTER TABLE eas.app_user ADD COLUMN IF NOT EXISTS is_system_account boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN eas.app_user.is_system_account IS 'Tài khoản hệ thống (không đăng nhập, không sửa qua UI/API quản trị).';
UPDATE eas.app_user SET is_system_account = true WHERE id = '00000002-0000-4000-8000-0000000000a1';

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT email, is_system_account FROM eas.app_user WHERE is_system_account;
