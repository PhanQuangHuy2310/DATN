-- Upgrade 1.4.0 -> 1.5.0. Attendance rows carry the HRM employee code; the
-- email becomes an optional fallback key. Requires 004_hrm_attendance.sql.
-- Rollback: database/mock_enterprise_sql/migrations/rollback/005_attendance_employee_code_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

ALTER TABLE mock_hr.attendance ADD COLUMN IF NOT EXISTS employee_code varchar(30);
ALTER TABLE mock_hr.attendance DROP CONSTRAINT IF EXISTS attendance_pkey;
ALTER TABLE mock_hr.attendance ALTER COLUMN employee_email DROP NOT NULL;
ALTER TABLE mock_hr.attendance ADD CONSTRAINT attendance_has_key
  CHECK (employee_code IS NOT NULL OR employee_email IS NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS attendance_code_day ON mock_hr.attendance(employee_code, work_date)
  WHERE employee_code IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS attendance_email_day ON mock_hr.attendance(employee_email, work_date)
  WHERE employee_code IS NULL;

INSERT INTO mock_hr.schema_migration(version,description)
VALUES ('005','Attendance matched by employee code (email fallback)');
COMMIT;
