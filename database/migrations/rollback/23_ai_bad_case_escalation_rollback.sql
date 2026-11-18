-- Rollback 23: trả guard_release / guard_active_release / guard_request / guard_sla về bản trước 23.
--
-- Từ chối chạy nếu còn hồ sơ CHƯA KẾT THÚC đang gắn bản nâng cấp (escalation): sau rollback,
-- guard_request kiểm tra theo vòng đời của LOẠI (A) nên các hồ sơ đó sẽ kẹt ở bước xử lý.
-- Bản nâng cấp đã công bố và lịch sử eas.ai_remediation được GIỮ LẠI (bất biến, phục vụ kiểm toán);
-- cột escalation giữ nguyên để các bản đó không bị hiểu nhầm thành bản thường.

BEGIN;
SELECT eas.lock_security(true);

DO $guard$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'eas' AND table_name = 'config_release' AND column_name = 'escalation') THEN
    RAISE EXCEPTION 'Rollback 23: CSDL này CHƯA chạy migration 23, không có gì để gỡ. '
      'Muốn cài thì chạy database/migrations/23_ai_bad_case_escalation.sql (không phải file trong thư mục rollback).';
  END IF;
  IF EXISTS (
    SELECT 1 FROM eas.request r
    JOIN eas.request_revision v ON v.id = r.current_revision_id
    JOIN eas.config_release c ON c.id = v.release_id
    WHERE c.escalation AND r.status NOT IN ('COMPLETED', 'REJECTED', 'CANCELLED')
  ) THEN
    RAISE EXCEPTION 'Rollback 23: còn hồ sơ đang mở được AI nâng luồng; hoàn tất hoặc hủy chúng trước.';
  END IF;
END
$guard$;

CREATE OR REPLACE FUNCTION eas.guard_active_release() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.code<>OLD.code) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request type identity immutable';
 END IF;
 IF NEW.active_release_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM eas.config_release WHERE id=NEW.active_release_id AND type_id=NEW.id AND state='PUBLISHED') THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Active release must be published for this type';
 END IF;
 RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION eas.guard_sla() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
DECLARE old_instance uuid; new_instance uuid; old_closure text;
BEGIN
 IF ROW(NEW.id,NEW.request_id,NEW.kind,NEW.approval_step_id,NEW.started_at,NEW.due_at) IS DISTINCT FROM ROW(OLD.id,OLD.request_id,OLD.kind,OLD.approval_step_id,OLD.started_at,OLD.due_at)
  OR (OLD.closed_at IS NOT NULL AND NEW IS DISTINCT FROM OLD)
  OR (OLD.breached_at IS NOT NULL AND NEW.breached_at IS DISTINCT FROM OLD.breached_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA identity/deadline/closed history immutable';
 END IF;
 IF NEW.attempt_id IS DISTINCT FROM OLD.attempt_id THEN
  SELECT instance_id,closure_kind INTO old_instance,old_closure FROM eas.execution_attempt WHERE id=OLD.attempt_id;
  SELECT instance_id INTO new_instance FROM eas.execution_attempt WHERE id=NEW.attempt_id;
  IF NEW.kind<>'EXECUTION' OR old_instance IS DISTINCT FROM new_instance OR old_closure IS DISTINCT FROM 'REASSIGNED' THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA target can change only for reassigned execution in same instance';
  END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION eas.guard_request() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
DECLARE origin_owner uuid; lc char(1); tcode varchar(30); allowed boolean;
        ai_revoke boolean := false; preempt boolean := false;
BEGIN
 IF TG_OP='DELETE' THEN PERFORM eas.assert_privacy_delete(OLD.id); RETURN OLD; END IF;
 IF TG_OP='UPDATE' THEN
  IF current_user='eas_privacy' AND NEW.current_revision_id IS NULL
    AND (to_jsonb(NEW)-'current_revision_id')=(to_jsonb(OLD)-'current_revision_id') THEN
   PERFORM eas.assert_privacy_delete(OLD.id); RETURN NEW;
  END IF;
  IF ROW(NEW.id,NEW.code,NEW.requester_id,NEW.type_id,NEW.origin_request_id,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.code,OLD.requester_id,OLD.type_id,OLD.origin_request_id,OLD.created_at) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request identity/origin immutable';
  END IF;
  ai_revoke := OLD.status='COMPLETED' AND NEW.status='NEEDS_INFO' AND eas.ai_revocable(OLD.id);
  preempt := NEW.status='REJECTED'
    AND OLD.status IN ('READY_FOR_EXECUTION','IN_PROGRESS','COMPLETED')
    AND coalesce(current_setting('eas.preempt_request_id', true), '') = OLD.id::text;
  IF OLD.status IN ('COMPLETED','REJECTED','CANCELLED') AND NEW IS DISTINCT FROM OLD AND NOT ai_revoke AND NOT preempt THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Terminal request cannot be reopened or edited';
  END IF;
  IF NEW IS DISTINCT FROM OLD AND (NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_at<OLD.updated_at) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request command requires version increment exactly once and monotonic updated_at';
  END IF;
  IF NEW.status<>OLD.status THEN
   allowed:=(OLD.status IN ('DRAFT','NEEDS_INFO') AND NEW.status IN ('PENDING_APPROVAL','CANCELLED'))
     OR (OLD.status='PENDING_APPROVAL' AND NEW.status IN ('NEEDS_INFO','REJECTED','CANCELLED','COMPLETED','READY_FOR_EXECUTION'))
     OR (OLD.status='READY_FOR_EXECUTION' AND NEW.status='IN_PROGRESS')
     OR (OLD.status='IN_PROGRESS' AND NEW.status IN ('READY_FOR_EXECUTION','WAITING_FOR_ACCEPTANCE','COMPLETED'))
     OR (OLD.status='WAITING_FOR_ACCEPTANCE' AND NEW.status IN ('READY_FOR_EXECUTION','COMPLETED'))
     OR ai_revoke OR preempt;
   IF NOT allowed THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request transition not allowed'; END IF;
  END IF;
 END IF;
 IF NEW.origin_request_id IS NOT NULL THEN
  SELECT requester_id INTO origin_owner FROM eas.request WHERE id=NEW.origin_request_id;
  IF FOUND AND origin_owner<>NEW.requester_id THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Origin request must have same owner'; END IF;
 END IF;
 SELECT lifecycle, code INTO lc, tcode FROM eas.request_type WHERE id=NEW.type_id;
 IF FOUND AND ((tcode IN ('LEAVE','ACCESS') AND NEW.draft_amount_vnd IS NOT NULL) OR (lc='A' AND NEW.status IN ('READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE')) OR (lc='B' AND NEW.status='WAITING_FOR_ACCEPTANCE')) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request lifecycle/amount mismatch';
 END IF;
 IF NEW.status NOT IN ('DRAFT','CANCELLED') AND NEW.current_revision_id IS NULL THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Submitted request requires current revision';
 END IF;
 RETURN NEW;
END $$;

-- guard_release: bản trước 23 so vòng đời bản cấu hình với vòng đời loại, không ngoại lệ.
-- Giữ nguyên thân hàm của 23 nhưng bỏ ngoại lệ escalation bằng cách thay đúng điều kiện đó.
DO $rel$
DECLARE src text;
BEGIN
  SELECT pg_get_functiondef('eas.guard_release()'::regprocedure) INTO src;
  src := replace(src, 'IF FOUND AND lc<>NEW.lifecycle AND NOT (NEW.escalation AND NEW.lifecycle > lc) THEN',
                      'IF FOUND AND lc<>NEW.lifecycle THEN');
  EXECUTE src;
END
$rel$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;
