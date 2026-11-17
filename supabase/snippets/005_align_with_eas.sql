-- =============================================================================
-- Mock systems 005 — căn dữ liệu HRM giả lập theo tổ chức thật của EAS (04/11/2026)
-- Tài liệu: docs/TICH_HOP_HE_THONG_NGOAI.md §4.1
--
-- Vấn đề: 55 nhân viên mock (@example.test) không khớp tài khoản EAS nào (0/136),
-- mã phòng ban lệch (HQ/IT/SALES so với BOD/TECH/BIZ), nên quỹ phép, ngân sách
-- phòng ban… không tra cứu được.
--
-- Đây là bước CẤP DỮ LIỆU MỘT LẦN cho hệ thống giả lập (giống nhập hồ sơ nhân sự
-- vào HRM); lúc chạy, các hệ thống vẫn chỉ nói chuyện với nhau qua API.
--
--   1. Bảng ghi nhận lời gọi ghi từ EAS (chống trùng theo source_request_id):
--      mock_hr.leave_usage, mock_finance.budget_commitment.
--   2. Phòng ban: HQ→BOD, IT→TECH, SALES→BIZ; tên theo EAS.
--   3. Nhân viên: mỗi tài khoản nhân sự EAS (136) có hồ sơ HRM, email @eas.com,
--      mã NV0001…, đúng quản lý trực tiếp. 55 hồ sơ mẫu cũ chuyển TERMINATED
--      (không xoá: phiếu mượn, quyền IT, khách hàng cũ vẫn tham chiếu được).
--   4. Quỹ phép năm hiện tại: ANNUAL 12, SICK 30, PARENTAL 180 ngày.
--
-- CÁCH CHẠY: Supabase SQL Editor → dán TOÀN BỘ file → Run. Chạy lại an toàn.
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('mock_hr.employee') IS NULL OR to_regclass('eas.app_user') IS NULL THEN
    RAISE EXCEPTION 'Cần schema mock_hr và eas.';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;

-- 1. Ghi nhận lời gọi ghi từ EAS ---------------------------------------------
CREATE TABLE IF NOT EXISTS mock_hr.leave_usage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id uuid NOT NULL REFERENCES mock_hr.employee(id),
  leave_type text NOT NULL CHECK (leave_type IN ('ANNUAL', 'SICK', 'UNPAID', 'PARENTAL')),
  year smallint NOT NULL CHECK (year BETWEEN 2020 AND 2100),
  days numeric(6,2) NOT NULL CHECK (days > 0),
  source_request_id uuid NOT NULL UNIQUE,
  recorded_at timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE TABLE IF NOT EXISTS mock_finance.budget_commitment (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cost_center varchar(30) NOT NULL,
  fiscal_year smallint NOT NULL,
  amount_minor bigint NOT NULL CHECK (amount_minor > 0),
  source_request_id uuid NOT NULL UNIQUE,
  committed_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

-- 2. Phòng ban -----------------------------------------------------------------
UPDATE mock_hr.department d
   SET code = m.new_code, updated_at = statement_timestamp()
  FROM (VALUES ('HQ', 'BOD'), ('IT', 'TECH'), ('SALES', 'BIZ')) AS m(old_code, new_code)
 WHERE d.code = m.old_code
   AND NOT EXISTS (SELECT 1 FROM mock_hr.department x WHERE x.code = m.new_code);
UPDATE mock_hr.department d
   SET name = e.name, updated_at = statement_timestamp()
  FROM eas.department e
 WHERE e.code = d.code AND d.name IS DISTINCT FROM e.name;
DO $dept$
DECLARE missing text;
BEGIN
  SELECT string_agg(e.code, ', ') INTO missing FROM eas.department e
  WHERE NOT EXISTS (SELECT 1 FROM mock_hr.department d WHERE d.code = e.code);
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'Phòng ban EAS chưa có trong HRM: %', missing;
  END IF;
END
$dept$;

-- 3. Nhân viên -----------------------------------------------------------------
UPDATE mock_hr.employee
   SET employment_status = 'TERMINATED', ended_on = greatest(hired_on, current_date),
       updated_at = statement_timestamp()
 WHERE work_email LIKE '%@example.test' AND employment_status <> 'TERMINATED';

WITH src AS (
  SELECT lower(u.email) AS email, u.display_name, d.code AS dept, u.is_active,
         u.employee_code,
         row_number() OVER (ORDER BY lower(u.email)) AS rn,
         CASE
           WHEN u.manager_id IS NULL THEN 'Giám đốc'
           WHEN EXISTS (SELECT 1 FROM eas.app_user r WHERE r.manager_id = u.id) THEN 'Quản lý'
           ELSE 'Nhân viên'
         END AS title
  FROM eas.app_user u JOIN eas.department d ON d.id = u.department_id
  WHERE NOT u.is_system_account AND u.account_type <> 'ADMIN'
)
INSERT INTO mock_hr.employee(id, employee_code, display_name, work_email, department_id,
                             job_title, employment_status, hired_on, ended_on)
SELECT gen_random_uuid(),
       coalesce(src.employee_code, 'NV' || lpad(src.rn::text, 4, '0')),
       src.display_name, src.email, hd.id, src.title,
       CASE WHEN src.is_active THEN 'ACTIVE' ELSE 'TERMINATED' END,
       date '2024-01-02',
       CASE WHEN src.is_active THEN NULL ELSE current_date END
FROM src JOIN mock_hr.department hd ON hd.code = src.dept
ON CONFLICT (work_email) DO UPDATE
   SET display_name = EXCLUDED.display_name,
       department_id = EXCLUDED.department_id,
       job_title = EXCLUDED.job_title,
       employment_status = EXCLUDED.employment_status,
       ended_on = EXCLUDED.ended_on,
       updated_at = statement_timestamp();

UPDATE mock_hr.employee e
   SET manager_id = m.id, updated_at = statement_timestamp()
  FROM eas.app_user u
  JOIN eas.app_user mu ON mu.id = u.manager_id
  JOIN mock_hr.employee m ON m.work_email = lower(mu.email)
 WHERE e.work_email = lower(u.email) AND e.manager_id IS DISTINCT FROM m.id;

-- 4. Quỹ phép năm hiện tại -------------------------------------------------------
INSERT INTO mock_hr.leave_balance(id, employee_id, leave_type, year, entitled_days, used_days)
SELECT gen_random_uuid(), e.id, q.leave_type,
       extract(year FROM statement_timestamp() AT TIME ZONE 'Asia/Ho_Chi_Minh')::smallint,
       q.days, 0
FROM mock_hr.employee e
CROSS JOIN (VALUES ('ANNUAL', 12), ('SICK', 30), ('PARENTAL', 180)) AS q(leave_type, days)
WHERE e.work_email LIKE '%@eas.com' AND e.employment_status = 'ACTIVE'
ON CONFLICT (employee_id, leave_type, year) DO NOTHING;

INSERT INTO mock_hr.schema_migration(version, description)
VALUES ('005', 'Align simulated HRM with EAS organisation; write-back ledgers')
ON CONFLICT (version) DO NOTHING;

-- Tự kiểm tra ------------------------------------------------------------------------
DO $check$
DECLARE unmatched int;
BEGIN
  SELECT count(*) INTO unmatched FROM eas.app_user u
  WHERE NOT u.is_system_account AND u.account_type <> 'ADMIN'
    AND NOT EXISTS (SELECT 1 FROM mock_hr.employee e WHERE e.work_email = lower(u.email));
  IF unmatched > 0 THEN
    RAISE EXCEPTION '% tài khoản EAS chưa có hồ sơ HRM', unmatched;
  END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'mock 005 OK' AS status,
       (SELECT count(*) FROM mock_hr.employee WHERE employment_status = 'ACTIVE') AS active_employees,
       (SELECT count(*) FROM mock_hr.leave_balance) AS leave_balances;
