-- Rollback of 12_request_types_new.sql. Published releases are immutable and
-- may already be referenced by requests, so the 13 types are deactivated
-- (hidden from menus, history kept) instead of deleted.
BEGIN;
SET LOCAL ROLE eas_migration;
UPDATE eas.request_type SET is_active = false WHERE code IN ('SALARY_ADVANCE', 'RESOURCE_REVOKE', 'VEHICLE_BOOKING', 'CROSS_DEPT_SUPPORT', 'PROJECT_INITIATION', 'TASK_REQUEST', 'DISCIPLINE_REQ', 'HR_CERTIFICATE', 'PROMOTION_REQ', 'REWARD_REQ', 'SALARY_ADJUSTMENT', 'DOCUMENT_SEAL', 'POLICY_ISSUANCE');
UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
