-- HRM employee code on accounts: attendance is matched by employee code first,
-- email only as a fallback. Filled by: python manage.py sync_employee_codes --apply
-- Rollback: database/migrations/rollback/16_employee_code_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

ALTER TABLE eas.app_user ADD COLUMN IF NOT EXISTS employee_code varchar(30);
CREATE UNIQUE INDEX IF NOT EXISTS app_user_employee_code_key
  ON eas.app_user(employee_code) WHERE employee_code IS NOT NULL;
COMMENT ON COLUMN eas.app_user.employee_code IS 'Mã nhân viên HRM (khớp chấm công); NULL nếu chưa đồng bộ.';

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
