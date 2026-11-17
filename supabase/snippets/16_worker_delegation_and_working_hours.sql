-- =============================================================================
-- 16 — Worker đọc uỷ quyền + quy tắc giờ làm việc (04/11/2026)
--
-- 1. Lỗi: role eas_worker không có SELECT/policy trên eas.approval_delegation.
--    Khi worker (AI tự duyệt) kích hoạt bước kế tiếp, uỷ quyền bị bỏ qua.
--    Sửa: cấp SELECT + policy chỉ-đọc cho eas_worker. Không cấp ghi.
-- 2. Quy tắc chấm công (chủ dự án chốt 04/11/2026; dữ liệu chấm công là dữ liệu ảo):
--    * có đơn nghỉ / công tác ĐÃ DUYỆT trùng thời điểm → Nghỉ làm / Công tác;
--    * không có đơn → mặc định đi làm, T2–T6:
--        08:00–12:00 và 13:30–17:30  → DANG_LAM  "Đang làm"
--        12:00–13:30                  → NGOAI_GIO "Nghỉ trưa"
--        ngoài khung / T7, CN         → NGOAI_GIO "Ngoài giờ làm việc"
--    Thay eas.get_user_working_status (trước đây báo "Đang làm" cả giờ trưa,
--    buổi tối và cuối tuần).
--
-- CÁCH CHẠY: Supabase SQL Editor → dán TOÀN BỘ file → Run. Chạy lại an toàn.
-- Rollback: database/migrations/rollback/16_worker_delegation_and_working_hours_rollback.sql
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role thành viên eas_migration (SQL Editor mặc định: postgres).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;

-- ---------------------------------------------------------------------------
-- 1. Worker đọc uỷ quyền.
-- ---------------------------------------------------------------------------
DO $grant$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_worker') THEN
    GRANT SELECT ON eas.approval_delegation TO eas_worker;
    IF NOT EXISTS (SELECT 1 FROM pg_policy
                   WHERE polrelid = 'eas.approval_delegation'::regclass AND polname = 'worker_read') THEN
      CREATE POLICY worker_read ON eas.approval_delegation FOR SELECT TO eas_worker USING (true);
    END IF;
  END IF;
END
$grant$;

-- ---------------------------------------------------------------------------
-- 2. Trạng thái làm việc theo đơn đã duyệt + giờ hành chính.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION eas.get_user_working_status(
  p_user_id uuid,
  p_check_time timestamptz DEFAULT now()
) RETURNS TABLE(status_code text, status_label text, detail_reason text)
LANGUAGE plpgsql STABLE
SET search_path = pg_catalog, eas
AS $f$
DECLARE
  v_leave record;
  v_local timestamp := p_check_time AT TIME ZONE 'Asia/Ho_Chi_Minh';
  v_dow int := extract(isodow FROM v_local);
  v_time time := v_local::time;
BEGIN
  SELECT l.type, l.title INTO v_leave
  FROM eas.user_leave_and_trips l
  WHERE l.user_id = p_user_id
    AND l.approval_status = 'APPROVED'
    AND p_check_time >= l.start_time AND p_check_time < l.end_time
  ORDER BY (l.type = 'BUSINESS_TRIP'), l.created_at DESC
  LIMIT 1;

  IF FOUND THEN
    IF v_leave.type = 'BUSINESS_TRIP' THEN
      RETURN QUERY SELECT 'CONG_TAC'::text, 'Công tác'::text, v_leave.title::text;
    ELSE
      RETURN QUERY SELECT 'NGHI_LAM'::text, 'Nghỉ làm'::text, v_leave.title::text;
    END IF;
    RETURN;
  END IF;

  IF v_dow BETWEEN 1 AND 5 THEN
    IF (v_time >= time '08:00' AND v_time < time '12:00')
       OR (v_time >= time '13:30' AND v_time < time '17:30') THEN
      RETURN QUERY SELECT 'DANG_LAM'::text, 'Đang làm'::text,
        'Giờ làm việc (08:00–12:00, 13:30–17:30, T2–T6)'::text;
      RETURN;
    END IF;
    IF v_time >= time '12:00' AND v_time < time '13:30' THEN
      RETURN QUERY SELECT 'NGOAI_GIO'::text, 'Nghỉ trưa'::text, 'Nghỉ trưa (12:00–13:30)'::text;
      RETURN;
    END IF;
  END IF;
  RETURN QUERY SELECT 'NGOAI_GIO'::text, 'Ngoài giờ làm việc'::text,
    'Ngoài giờ làm việc (08:00–12:00, 13:30–17:30, T2–T6)'::text;
END
$f$;
REVOKE EXECUTE ON FUNCTION eas.get_user_working_status(uuid, timestamptz) FROM PUBLIC;
DO $exec_grants$
DECLARE r text;
BEGIN
  FOR r IN SELECT rolname FROM pg_roles
           WHERE rolname IN ('eas_api', 'eas_backend_login', 'eas_worker', 'eas_worker_login') LOOP
    EXECUTE format('GRANT EXECUTE ON FUNCTION eas.get_user_working_status(uuid, timestamptz) TO %I', r);
  END LOOP;
END
$exec_grants$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

-- ---------------------------------------------------------------------------
-- 3. Tự kiểm tra.
-- ---------------------------------------------------------------------------
DO $check$
DECLARE
  u uuid := '00000000-0000-0000-0000-000000000000';
  c text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_worker') THEN
    IF NOT has_table_privilege('eas_worker', 'eas.approval_delegation', 'SELECT') THEN
      RAISE EXCEPTION 'eas_worker vẫn chưa đọc được approval_delegation';
    END IF;
    IF has_table_privilege('eas_worker', 'eas.approval_delegation', 'INSERT,UPDATE,DELETE') THEN
      RAISE EXCEPTION 'eas_worker không được ghi approval_delegation';
    END IF;
  END IF;
  -- Thứ Tư 05/11/2026, giờ Việt Nam.
  SELECT status_code INTO c FROM eas.get_user_working_status(u, timestamptz '2026-11-05 09:00+07');
  IF c <> 'DANG_LAM' THEN RAISE EXCEPTION '09:00 phải là DANG_LAM, nhận %', c; END IF;
  SELECT status_code INTO c FROM eas.get_user_working_status(u, timestamptz '2026-11-05 12:30+07');
  IF c <> 'NGOAI_GIO' THEN RAISE EXCEPTION '12:30 phải là NGOAI_GIO, nhận %', c; END IF;
  SELECT status_code INTO c FROM eas.get_user_working_status(u, timestamptz '2026-11-05 13:30+07');
  IF c <> 'DANG_LAM' THEN RAISE EXCEPTION '13:30 phải là DANG_LAM, nhận %', c; END IF;
  SELECT status_code INTO c FROM eas.get_user_working_status(u, timestamptz '2026-11-05 17:30+07');
  IF c <> 'NGOAI_GIO' THEN RAISE EXCEPTION '17:30 phải là NGOAI_GIO, nhận %', c; END IF;
  SELECT status_code INTO c FROM eas.get_user_working_status(u, timestamptz '2026-11-08 10:00+07');
  IF c <> 'NGOAI_GIO' THEN RAISE EXCEPTION 'Chủ nhật phải là NGOAI_GIO, nhận %', c; END IF;
END
$check$;

RESET ROLE;
COMMIT;

SELECT 'migration 16 OK' AS status;
