-- Rollback của database/migrations/19_employee_auditor_role.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Chạy lại an toàn.
-- Thu hồi AUDITOR đang cấp cho tài khoản EMPLOYEE trước, rồi khôi phục ràng buộc cũ
-- (EMPLOYEE không được giữ AUDITOR). Giữ bản sửa "= ANY" của guard_account_type_change.
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

SELECT eas.lock_security(true);
UPDATE eas.role_membership m SET revoked_at = statement_timestamp()
FROM eas.app_user u
WHERE u.id = m.user_id AND u.account_type = 'EMPLOYEE'
  AND m.role = 'AUDITOR' AND m.revoked_at IS NULL;

CREATE OR REPLACE FUNCTION eas.enforce_account_role_type()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, eas
AS $f$
DECLARE kind text;
BEGIN
  IF NEW.revoked_at IS NOT NULL OR (NEW.valid_to IS NOT NULL AND NEW.valid_to <= statement_timestamp()) THEN
    RETURN NEW;
  END IF;
  SELECT account_type INTO kind FROM eas.app_user WHERE id = NEW.user_id;
  IF kind = 'ADMIN' AND NEW.role IN ('REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR') THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'ADMIN_ACCOUNT_CANNOT_HOLD_OPERATIONAL_ROLE';
  END IF;
  IF kind = 'EMPLOYEE' AND NEW.role IN ('OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR') THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'EMPLOYEE_ACCOUNT_CANNOT_HOLD_ADMIN_ROLE';
  END IF;
  RETURN NEW;
END
$f$;

CREATE OR REPLACE FUNCTION eas.guard_account_type_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, eas
AS $f$
BEGIN
  IF NEW.account_type IS DISTINCT FROM OLD.account_type AND EXISTS (
    SELECT 1 FROM eas.role_membership m
    WHERE m.user_id = NEW.id AND m.revoked_at IS NULL
      AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
      AND m.role = ANY (CASE WHEN NEW.account_type = 'ADMIN'
                             THEN ARRAY['REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR']
                             ELSE ARRAY['OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR'] END)
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'ACCOUNT_TYPE_CONFLICTS_WITH_ACTIVE_ROLES';
  END IF;
  RETURN NEW;
END
$f$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

RESET ROLE;
COMMIT;

SELECT 'rollback 19 OK' AS status;
