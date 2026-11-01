-- Rollback of 004_hrm_attendance.sql: removes the mock attendance feed. The
-- workflow then treats everyone as present (no substitution).
BEGIN;
SET LOCAL ROLE eas_migration;
DROP TABLE IF EXISTS mock_hr.attendance;
DELETE FROM mock_hr.schema_migration WHERE version='004';
COMMIT;
