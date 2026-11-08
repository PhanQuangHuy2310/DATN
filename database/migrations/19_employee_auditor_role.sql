-- =============================================================================
-- 19 — Nhân viên được giữ vai trò AUDITOR (07/11/2026, lỗi M3, chủ dự án chọn A)
--
-- Trước đây (migration 11) AUDITOR bị coi là vai trò quản trị: tài khoản
-- EMPLOYEE không được giữ (EMPLOYEE_ACCOUNT_CANNOT_HOLD_ADMIN_ROLE). Nay AUDITOR
-- là nghiệp vụ của nhân viên: tra cứu kiểm toán chỉ-đọc trên Cổng Nhân viên.
--   * EMPLOYEE: được AUDITOR; vẫn KHÔNG được OPS_ADMIN, POLICY_ADMIN.
--   * ADMIN: giữ nguyên (không được REQUESTER/APPROVER/EXECUTOR/ACCEPTOR).
-- Ai được cấp AUDITOR: chỉ quản trị viên (kiểm ở api_core, org_users_rbac
-- _validated_role → AUDITOR_ROLE_ADMIN_ONLY).
-- Kèm sửa guard_account_type_change: "role IN (ARRAY[...])" so text với mảng
-- (lỗi kiểu khi chạy) → "role = ANY(ARRAY[...])".
--
-- CÁCH CHẠY: Supabase SQL Editor → dán TOÀN BỘ file → Run. Chạy lại an toàn.
-- Rollback: database/migrations/rollback/19_employee_auditor_role_rollback.sql
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regprocedure('eas.enforce_account_role_type()') IS NULL THEN
    RAISE EXCEPTION 'Thiếu eas.enforce_account_role_type (chạy migration 11 trước).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;

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
  IF kind = 'EMPLOYEE' AND NEW.role IN ('OPS_ADMIN', 'POLICY_ADMIN') THEN
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
                             ELSE ARRAY['OPS_ADMIN', 'POLICY_ADMIN'] END)
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'ACCOUNT_TYPE_CONFLICTS_WITH_ACTIVE_ROLES';
  END IF;
  RETURN NEW;
END
$f$;

REVOKE ALL ON FUNCTION eas.enforce_account_role_type() FROM PUBLIC;
REVOKE ALL ON FUNCTION eas.guard_account_type_change() FROM PUBLIC;

-- Vai trò đổi nghĩa: các tiến trình nạp lại trạng thái bảo mật.
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- Tự kiểm tra: EMPLOYEE nhận AUDITOR được, vẫn bị chặn OPS_ADMIN (thử rồi huỷ).
DO $check$
DECLARE u uuid; blocked boolean := false;
BEGIN
  SELECT id INTO u FROM eas.app_user
  WHERE account_type = 'EMPLOYEE' AND is_active AND NOT is_system_account LIMIT 1;
  IF u IS NULL THEN RETURN; END IF;
  PERFORM eas.lock_security(true);
  BEGIN
    INSERT INTO eas.role_membership(user_id, role, scope_kind, type_scope)
    VALUES (u, 'AUDITOR', 'GLOBAL', 'ALL');
    RAISE EXCEPTION 'probe_rollback';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM <> 'probe_rollback' THEN RAISE; END IF;
  END;
  BEGIN
    INSERT INTO eas.role_membership(user_id, role, scope_kind, type_scope)
    VALUES (u, 'OPS_ADMIN', 'GLOBAL', 'ALL');
  EXCEPTION WHEN check_violation THEN
    blocked := SQLERRM = 'EMPLOYEE_ACCOUNT_CANNOT_HOLD_ADMIN_ROLE';
  END;
  IF NOT blocked THEN
    RAISE EXCEPTION 'EMPLOYEE vẫn nhận được OPS_ADMIN: ràng buộc bị hỏng';
  END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'migration 19 OK' AS status;
