-- ========================================================================================
-- VERIFY SCRIPT: verify_eas_core_schema.sql
-- Kiểm thử xác thực schema 'eas' và 30 bảng vật lý
-- ========================================================================================

DO $$
DECLARE
    tbl text;
    tbls text[] := ARRAY[
        'security_epoch', 'department', 'app_user', 'role_membership', 'request_type',
        'config_release', 'request', 'request_revision', 'workflow_instance', 'request_participant',
        'approval_step', 'approval_decision', 'execution_attempt', 'acceptance_decision', 'execution_issue',
        'attachment', 'draft_attachment', 'revision_attachment', 'execution_attachment', 'sla_stage',
        'sla_alert', 'audit_event', 'admin_event', 'audit_head', 'audit_checkpoint',
        'outbox_event', 'notification', 'idempotency_record', 'privacy_case', 'retention_hold'
    ];
    cnt int;
BEGIN
    FOREACH tbl IN ARRAY tbls LOOP
        SELECT count(*) INTO cnt
        FROM information_schema.tables
        WHERE table_schema = 'eas' AND table_name = tbl;

        IF cnt = 0 THEN
            RAISE EXCEPTION 'Kiểm thử thất bại: Bảng eas.% không tồn tại!', tbl;
        END IF;
    END LOOP;

    -- Kiểm tra bản ghi bootstrap
    SELECT count(*) INTO cnt FROM eas.security_epoch WHERE id = 1;
    IF cnt = 0 THEN
        RAISE EXCEPTION 'Thiếu dữ liệu bootstrap trong eas.security_epoch!';
    END IF;

    SELECT count(*) INTO cnt FROM eas.audit_head WHERE scope_key = 'ADMIN';
    IF cnt = 0 THEN
        RAISE EXCEPTION 'Thiếu dữ liệu bootstrap trong eas.audit_head!';
    END IF;

    RAISE NOTICE 'Xác thực thành công toàn bộ 30 bảng và bootstrap data cho schema eas!';
END $$;
