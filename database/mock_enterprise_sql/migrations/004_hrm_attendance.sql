-- Upgrade 1.3.0 -> 1.4.0. HRM attendance feed (mock timekeeping module).
-- The workflow reads today's status when it hands work to an executor or an
-- approver: ABSENT/LEAVE people are replaced (see api_core service). Rows are
-- matched by HRM employee code; employee_email is the fallback key when an
-- account has no code yet. No row for a day means PRESENT.
-- (Consolidated with the former 005_attendance_employee_code; never applied separately.)
-- Rollback: database/mock_enterprise_sql/migrations/rollback/004_hrm_attendance_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

CREATE TABLE mock_hr.attendance (
  employee_code varchar(30),
  employee_email varchar(254) CHECK (employee_email = lower(btrim(employee_email))),
  work_date date NOT NULL,
  status text NOT NULL CHECK (status IN ('PRESENT','ABSENT','LEAVE')),
  source text NOT NULL DEFAULT 'TIMEKEEPING' CHECK (source IN ('TIMEKEEPING','LEAVE_SYSTEM','MANUAL')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CONSTRAINT attendance_has_key CHECK (employee_code IS NOT NULL OR employee_email IS NOT NULL)
);
CREATE UNIQUE INDEX attendance_code_day ON mock_hr.attendance(employee_code, work_date)
  WHERE employee_code IS NOT NULL;
CREATE UNIQUE INDEX attendance_email_day ON mock_hr.attendance(employee_email, work_date)
  WHERE employee_code IS NULL;
COMMENT ON TABLE mock_hr.attendance IS 'Mock HRM chấm công: trạng thái có mặt theo ngày (khớp theo mã nhân viên, email dự phòng).';

REVOKE ALL ON mock_hr.attendance FROM PUBLIC;
GRANT SELECT ON mock_hr.attendance TO eas_api, eas_backup;

-- Demo data for the day the migration runs: two TECH executors are away
-- (keyed by email because the demo accounts have no HRM code yet).
INSERT INTO mock_hr.attendance(employee_email,work_date,status,source) VALUES
  ('huy.do@eas.com', CURRENT_DATE, 'ABSENT', 'TIMEKEEPING'),
  ('khoi.dang@eas.com', CURRENT_DATE, 'LEAVE', 'LEAVE_SYSTEM');

INSERT INTO mock_hr.schema_migration(version,description)
VALUES ('004','HRM attendance feed (employee code, email fallback)');
COMMIT;

SELECT employee_code, employee_email, work_date, status FROM mock_hr.attendance ORDER BY work_date DESC, employee_email;
