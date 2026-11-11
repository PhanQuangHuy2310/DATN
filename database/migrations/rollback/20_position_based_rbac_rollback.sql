-- =============================================================================
-- Rollback 20: Position-Based RBAC
-- =============================================================================

BEGIN;

SELECT eas.lock_security(true);

-- Restore default UI module permissions for workflow roles
UPDATE eas.role_module_permission
SET can_view = true,
    can_create = (module_code = 'requests_workflows'),
    updated_at = now()
WHERE role_code IN ('REQUESTER', 'ACCEPTOR', 'EXECUTOR', 'APPROVER')
  AND module_code IN ('dashboard', 'requests_workflows', 'org_chart', 'regulations');

-- Revoke position memberships
UPDATE eas.role_membership
SET revoked_at = statement_timestamp()
WHERE role IN ('STAFF', 'TEAM_LEAD', 'MANAGER', 'VICE_DIRECTOR', 'DIRECTOR')
  AND revoked_at IS NULL;

DELETE FROM eas.role_module_permission
WHERE role_code IN ('STAFF', 'TEAM_LEAD', 'MANAGER', 'VICE_DIRECTOR', 'DIRECTOR');

UPDATE eas.security_epoch
SET version = version + 1, updated_at = statement_timestamp()
WHERE id = 1;

COMMIT;
