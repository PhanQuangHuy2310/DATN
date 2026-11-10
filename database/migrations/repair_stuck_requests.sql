-- =============================================================================
-- Migration: Repair Stuck PENDING_APPROVAL Requests & Orphan SLA Stages ([M2])
-- =============================================================================
-- CÁCH CHẠY:
--   Supabase Dashboard → SQL Editor → dán TOÀN BỘ file → Run.
--   (Hoặc chạy qua CLI: python manage.py repair_workflow_consistency --apply)
--
-- MỤC ĐÍCH:
--   1. Xử lý các hồ sơ đang ở trạng thái PENDING_APPROVAL (điển hình:
--      REQ-2026-0002, REQ-2026-0009, REQ-2026-0026) nhưng workflow_instance
--      đang ACTIVE lại không có bước approval_step nào ở trạng thái ACTIVE:
--      - Kích hoạt bước WAITING kế tiếp có step_no nhỏ nhất sang ACTIVE.
--      - Đóng các sla_stage cũ bị treo (nếu có) và mở sla_stage APPROVAL mới
--        khớp với hạn xử lý của bước vừa kích hoạt.
--   2. Xử lý các hồ sơ đã ở trạng thái kết thúc (COMPLETED, REJECTED, CANCELLED,
--      điển hình: REQ-2026-0011) nhưng vẫn còn sla_stage mở (closed_at IS NULL),
--      approval_step đang ACTIVE/WAITING, hoặc workflow_instance đang ACTIVE:
--      - Đóng toàn bộ sla_stage còn mở.
--      - Chuyển các bước approval_step còn ACTIVE/WAITING sang SKIPPED.
--      - Đóng workflow_instance còn ACTIVE.
--
-- Script hoàn toàn idempotent (chạy lại nhiều lần an toàn trong 1 transaction).
-- =============================================================================

BEGIN;

DO $repair$
DECLARE
  rec record;
  v_now timestamptz := statement_timestamp();
  v_due timestamptz;
BEGIN
  -- 1. Khôi phục các hồ sơ PENDING_APPROVAL bị thiếu bước ACTIVE (REQ-2026-0002, 0009, 0026...)
  FOR rec IN
    SELECT
      r.id AS request_id,
      r.code AS request_code,
      i.id AS instance_id,
      s.id AS next_step_id,
      s.step_no,
      COALESCE(
        NULLIF(cr.sla_profile->>'approval_hours', '')::int,
        24
      ) AS approval_hours
    FROM eas.request r
    JOIN eas.request_revision v ON v.id = r.current_revision_id
    JOIN eas.config_release cr ON cr.id = v.release_id
    JOIN eas.workflow_instance i
      ON i.revision_id = v.id
     AND i.state = 'ACTIVE'
    JOIN LATERAL (
      SELECT s1.id, s1.step_no
      FROM eas.approval_step s1
      WHERE s1.instance_id = i.id
        AND s1.state = 'WAITING'
      ORDER BY s1.step_no ASC
      LIMIT 1
    ) s ON TRUE
    WHERE r.status = 'PENDING_APPROVAL'
      AND NOT EXISTS (
        SELECT 1
        FROM eas.approval_step sa
        WHERE sa.instance_id = i.id
          AND sa.state = 'ACTIVE'
      )
    ORDER BY r.code
  LOOP
    v_due := v_now + make_interval(hours => rec.approval_hours);

    UPDATE eas.approval_step
       SET state = 'ACTIVE',
           activated_at = v_now
     WHERE id = rec.next_step_id;

    UPDATE eas.sla_stage
       SET closed_at = v_now
     WHERE request_id = rec.request_id
       AND closed_at IS NULL;

    INSERT INTO eas.sla_stage (
      request_id,
      kind,
      approval_step_id,
      started_at,
      due_at
    )
    VALUES (
      rec.request_id,
      'APPROVAL',
      rec.next_step_id,
      v_now,
      v_due
    );

    RAISE NOTICE '[M2] Activated WAITING step % for stuck request %', rec.step_no, rec.request_code;
  END LOOP;

  -- 2. Đóng sla_stage, approval_step và workflow_instance mồ côi của các hồ sơ đã kết thúc (REQ-2026-0011...)
  FOR rec IN
    SELECT
      r.id AS request_id,
      r.code AS request_code,
      r.status AS request_status
    FROM eas.request r
    WHERE r.status IN ('COMPLETED', 'REJECTED', 'CANCELLED')
      AND (
        EXISTS (
          SELECT 1 FROM eas.sla_stage ss
          WHERE ss.request_id = r.id AND ss.closed_at IS NULL
        )
        OR EXISTS (
          SELECT 1 FROM eas.approval_step s
          WHERE s.request_id = r.id AND s.state IN ('ACTIVE', 'WAITING')
        )
        OR EXISTS (
          SELECT 1 FROM eas.workflow_instance i
          WHERE i.request_id = r.id AND i.state = 'ACTIVE'
        )
      )
    ORDER BY r.code
  LOOP
    UPDATE eas.approval_step
       SET state = 'SKIPPED',
           closed_at = COALESCE(closed_at, v_now)
     WHERE request_id = rec.request_id
       AND state IN ('ACTIVE', 'WAITING');

    UPDATE eas.workflow_instance
       SET state = rec.request_status,
           closed_at = COALESCE(closed_at, v_now)
     WHERE request_id = rec.request_id
       AND state = 'ACTIVE';

    UPDATE eas.sla_stage
       SET closed_at = v_now
     WHERE request_id = rec.request_id
       AND closed_at IS NULL;

    RAISE NOTICE '[M2] Closed orphan workflow/SLA records for terminal request % (%)',
      rec.request_code, rec.request_status;
  END LOOP;
END
$repair$;

COMMIT;
