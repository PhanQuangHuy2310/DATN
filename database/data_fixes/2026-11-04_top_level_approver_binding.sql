-- =============================================================================
-- Data fix 2026-11-04 — Khai báo người duyệt thay cho lãnh đạo cao nhất
-- Thiết kế: docs/THIET_KE_SCHEMA_EAS_V2.md §5
--
-- Lãnh đạo cao nhất không có quản lý trực tiếp. Bước DIRECT_MANAGER của họ được
-- chuyển cho người khai báo ở slot TOP_LEVEL_APPROVER của phòng ban. Không khai báo
-- thì bước bị bỏ; nếu tuyến rỗng thì đơn bị từ chối (ROUTE_CONFIGURATION_INVALID).
--
-- CÁCH CHẠY: sửa 2 giá trị ở khối "THAM SỐ" bên dưới, dán toàn bộ vào Supabase SQL Editor → Run.
--   * Một transaction; chạy lại an toàn (loại đã có đúng khai báo thì bỏ qua).
--   * Chỉ thêm bản phát hành MỚI cho từng loại yêu cầu có dùng DIRECT_MANAGER
--     (bản PUBLISHED cũ bất biến, hồ sơ đã gửi giữ nguyên cấu hình cũ).
--   * Hoàn tác: chạy lại với approver_email của người khác, hoặc trỏ
--     request_type.active_release_id về bản trước.
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $fix$
DECLARE
  -- THAM SỐ ---------------------------------------------------------------
  dept_code      text := 'BOD';                    -- phòng ban của lãnh đạo cao nhất
  approver_email text := 'CHANGE_ME@eas.com';      -- người duyệt thay (vd thành viên HĐQT)
  -- -----------------------------------------------------------------------
  dept_key text;
  approver uuid;
  author   uuid;
  cur      record;
  bindings jsonb;
  changed  integer := 0;
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  -- actor_bindings.departments được khoá theo id phòng ban (uuid dạng text), không theo mã.
  SELECT id::text INTO dept_key FROM eas.department WHERE code = dept_code;
  IF dept_key IS NULL THEN
    RAISE EXCEPTION 'Không có phòng ban %', dept_code;
  END IF;

  SELECT u.id INTO approver FROM eas.app_user u
   WHERE lower(u.email) = lower(approver_email) AND u.is_active AND NOT u.is_system_account;
  IF approver IS NULL THEN
    RAISE EXCEPTION 'Không có người dùng đang hoạt động với email %', approver_email;
  END IF;
  -- Người duyệt thay không được là chính lãnh đạo cần duyệt (tách biệt nhiệm vụ).
  IF EXISTS (SELECT 1 FROM eas.app_user u JOIN eas.department d ON d.id = u.department_id
              WHERE u.id = approver AND d.code = dept_code AND u.manager_id IS NULL) THEN
    RAISE EXCEPTION 'Người duyệt thay không được là lãnh đạo cao nhất của chính phòng %', dept_code;
  END IF;

  SELECT u.id INTO author FROM eas.app_user u
   WHERE u.account_type = 'ADMIN' AND u.is_active ORDER BY u.created_at LIMIT 1;
  IF author IS NULL THEN
    RAISE EXCEPTION 'Không tìm thấy tài khoản ADMIN làm người phát hành';
  END IF;

  SET LOCAL ROLE eas_migration;
  FOR cur IN
    SELECT cr.* FROM eas.request_type rt
      JOIN eas.config_release cr ON cr.id = rt.active_release_id
     WHERE rt.is_active
       AND (cr.route_rules::text LIKE '%"DIRECT_MANAGER"%')
       AND (cr.actor_bindings #>> ARRAY['departments', dept_key, 'TOP_LEVEL_APPROVER'])
           IS DISTINCT FROM approver::text
  LOOP
    bindings := jsonb_set(
      jsonb_set(cur.actor_bindings, '{departments}', coalesce(cur.actor_bindings->'departments', '{}'::jsonb)),
      ARRAY['departments', dept_key],
      coalesce(cur.actor_bindings #> ARRAY['departments', dept_key], '{}'::jsonb)
        || jsonb_build_object('TOP_LEVEL_APPROVER', approver::text));

    INSERT INTO eas.config_release(
      type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
      created_by, published_by, published_at, content_sha256)
    VALUES (
      cur.type_id,
      (SELECT max(version) + 1 FROM eas.config_release WHERE type_id = cur.type_id),
      'PUBLISHED', cur.lifecycle, cur.form_schema, cur.route_rules, bindings, cur.sla_profile,
      author, author, statement_timestamp(),
      encode(sha256(convert_to(jsonb_build_object(
        'form_schema', cur.form_schema, 'route_rules', cur.route_rules,
        'actor_bindings', bindings, 'sla_profile', cur.sla_profile,
        'lifecycle', cur.lifecycle)::text, 'UTF8')), 'hex'))
    RETURNING id INTO cur.id;
    UPDATE eas.request_type SET active_release_id = cur.id WHERE id = cur.type_id;
    changed := changed + 1;
  END LOOP;
  RESET ROLE;

  RAISE NOTICE 'Đã phát hành bản mới cho % loại yêu cầu (phòng %, người duyệt thay %).',
    changed, dept_code, approver_email;
END
$fix$;

COMMIT;
