-- Upgrade 1.3.0 -> 1.4.0. HRM attendance feed (mock timekeeping module).
-- The workflow reads today's status when it hands work to an executor; an
-- ABSENT or LEAVE executor is replaced by a present colleague of the same
-- department holding the EXECUTOR role. No row for a day means PRESENT.
-- employee_email matches eas.app_user.email (a real HRM would map employee ids).
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

CREATE TABLE mock_hr.attendance (
  employee_email varchar(254) NOT NULL CHECK (employee_email = lower(btrim(employee_email))),
  work_date date NOT NULL,
  status text NOT NULL CHECK (status IN ('PRESENT','ABSENT','LEAVE')),
  source text NOT NULL DEFAULT 'TIMEKEEPING' CHECK (source IN ('TIMEKEEPING','LEAVE_SYSTEM','MANUAL')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  PRIMARY KEY (employee_email, work_date)
);
COMMENT ON TABLE mock_hr.attendance IS 'Mock HRM chấm công: trạng thái có mặt theo ngày, dùng để chuyển việc khi người thực hiện vắng.';

REVOKE ALL ON mock_hr.attendance FROM PUBLIC;
GRANT SELECT ON mock_hr.attendance TO eas_api, eas_backup;

-- Demo data for the day the migration runs: two TECH executors are away.
INSERT INTO mock_hr.attendance(employee_email,work_date,status,source) VALUES
  ('huy.do@eas.com', CURRENT_DATE, 'ABSENT', 'TIMEKEEPING'),
  ('khoi.dang@eas.com', CURRENT_DATE, 'LEAVE', 'LEAVE_SYSTEM')
ON CONFLICT (employee_email, work_date) DO NOTHING;

INSERT INTO mock_hr.schema_migration(version,description)
VALUES ('004','HRM attendance feed for absent-executor reassignment');
COMMIT;

SELECT employee_email, work_date, status FROM mock_hr.attendance ORDER BY work_date DESC, employee_email;
