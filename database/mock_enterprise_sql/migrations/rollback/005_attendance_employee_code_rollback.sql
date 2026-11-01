-- Rollback of 005_attendance_employee_code.sql. Rows without an email are
-- removed first because the email key becomes mandatory again.
BEGIN;
SET LOCAL ROLE eas_migration;
DELETE FROM mock_hr.attendance WHERE employee_email IS NULL;
DROP INDEX IF EXISTS mock_hr.attendance_email_day;
DROP INDEX IF EXISTS mock_hr.attendance_code_day;
ALTER TABLE mock_hr.attendance DROP CONSTRAINT IF EXISTS attendance_has_key;
ALTER TABLE mock_hr.attendance ALTER COLUMN employee_email SET NOT NULL;
ALTER TABLE mock_hr.attendance ADD PRIMARY KEY (employee_email, work_date);
ALTER TABLE mock_hr.attendance DROP COLUMN IF EXISTS employee_code;
DELETE FROM mock_hr.schema_migration WHERE version='005';
COMMIT;
