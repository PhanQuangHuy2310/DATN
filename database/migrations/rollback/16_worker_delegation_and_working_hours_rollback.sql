-- Rollback của database/migrations/16_worker_delegation_and_working_hours.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Chạy lại an toàn.
-- Không trả lại EXECUTE cho PUBLIC (không cần: backend gọi bằng role riêng).
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

DROP POLICY IF EXISTS worker_read ON eas.approval_delegation;
DO $revoke$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_worker') THEN
    REVOKE SELECT ON eas.approval_delegation FROM eas_worker;
  END IF;
END
$revoke$;

-- Bản trước migration 16 (luôn "Đang làm" khi không có đơn).
CREATE OR REPLACE FUNCTION eas.get_user_working_status(
  p_user_id uuid,
  p_check_time timestamptz DEFAULT now()
) RETURNS TABLE(status_code text, status_label text, detail_reason text)
LANGUAGE plpgsql STABLE
SET search_path = pg_catalog, eas
AS $f$
DECLARE
  v_leave record;
  v_vn_time timestamp;
  v_dow int;
  v_time time;
BEGIN
  SELECT type, title INTO v_leave
  FROM eas.user_leave_and_trips
  WHERE user_id = p_user_id
    AND approval_status = 'APPROVED'
    AND p_check_time BETWEEN start_time AND end_time
  ORDER BY CASE WHEN type = 'BUSINESS_TRIP' THEN 1 ELSE 2 END, created_at DESC
  LIMIT 1;

  IF FOUND THEN
    IF v_leave.type = 'BUSINESS_TRIP' THEN
      RETURN QUERY SELECT 'CONG_TAC'::text, 'Công tác'::text, v_leave.title::text;
    ELSE
      RETURN QUERY SELECT 'NGHI_LAM'::text, 'Nghỉ làm'::text, v_leave.title::text;
    END IF;
    RETURN;
  END IF;

  v_vn_time := p_check_time AT TIME ZONE 'Asia/Ho_Chi_Minh';
  v_dow := extract(isodow FROM v_vn_time);
  v_time := v_vn_time::time;
  IF v_dow BETWEEN 1 AND 5 AND v_time BETWEEN time '08:00' AND time '17:30' THEN
    RETURN QUERY SELECT 'DANG_LAM'::text, 'Đang làm'::text, 'Trong giờ hành chính (08:00 - 17:30, T2-T6)'::text;
  ELSIF v_dow IN (6, 7) THEN
    RETURN QUERY SELECT 'DANG_LAM'::text, 'Đang làm'::text, 'Mặc định đi làm (Hôm nay cuối tuần T7/CN)'::text;
  ELSE
    RETURN QUERY SELECT 'DANG_LAM'::text, 'Đang làm'::text, 'Mặc định đi làm (Ngoài khung 08:00 - 17:30)'::text;
  END IF;
END
$f$;

RESET ROLE;
COMMIT;
