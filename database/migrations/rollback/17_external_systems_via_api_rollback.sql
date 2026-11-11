-- Rollback của database/migrations/17_external_systems_via_api.sql
-- Dán toàn bộ vào Supabase SQL Editor → Run. Chạy lại an toàn.
--
-- Trả lại: biểu mẫu cũ, guard_request cũ, nhóm cũ (10 mã) của request_type, quyền đọc
-- mock_* của eas_api (bản code trước 04/11 đọc thẳng các bảng này).
-- Giữ lại (không xoá dữ liệu): bảng request_group / request_menu_item (bỏ khoá
-- ngoại), role eas_mock.
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL ROLE eas_migration;

-- Biểu mẫu: trỏ về bản phát hành ngay trước bản của migration 17.
UPDATE eas.request_type rt
   SET active_release_id = prev.id
  FROM eas.config_release cur, LATERAL (
         SELECT p.id FROM eas.config_release p
         WHERE p.type_id = cur.type_id AND p.state = 'PUBLISHED' AND p.version < cur.version
         ORDER BY p.version DESC LIMIT 1) prev
 WHERE cur.id = rt.active_release_id
   AND rt.code IN ('ROOM_BOOKING', 'VEHICLE_BOOKING', 'EQUIPMENT_BORROW', 'ACCESS', 'EXPENSE_CLAIM', 'LEAVE')
   AND (cur.form_schema->'properties' ?| ARRAY['room_code', 'vehicle_code', 'asset_category', 'leave_kind', 'requested_role']);

-- Nhóm cũ.
ALTER TABLE eas.request_type DROP CONSTRAINT IF EXISTS request_type_category_fk;
UPDATE eas.request_type rt SET category = a.value #>> '{}'
  FROM eas_archive.dropped_column_value a
 WHERE a.table_name = 'request_type' AND a.column_name = 'category_before_17'
   AND a.row_id = rt.id::text;
DO $chk$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'request_type_category_valid') THEN
    ALTER TABLE eas.request_type ADD CONSTRAINT request_type_category_valid
      CHECK (category IN ('FINANCE','RESOURCE','FACILITY','WORK','HR','TIME','IT','LEGAL','SALES','ADMIN'));
  END IF;
END
$chk$;

-- guard_request như trước migration 17.
CREATE OR REPLACE FUNCTION eas.guard_request() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, eas AS $f$
DECLARE origin_owner uuid; lc char(1); tcode varchar(30); allowed boolean; ai_revoke boolean := false;
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
  IF OLD.status IN ('COMPLETED','REJECTED','CANCELLED') AND NEW IS DISTINCT FROM OLD AND NOT ai_revoke THEN
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
     OR ai_revoke;
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
END $f$;

-- Quyền đọc mock_* của bản code cũ (chỉ các bảng/view trong hợp đồng cũ).
DO $grants$
DECLARE s text; t record;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eas_api') THEN
    FOREACH s IN ARRAY ARRAY['mock_hr','mock_assets','mock_facilities','mock_crm',
                             'mock_procurement','mock_it','mock_finance','mock_travel'] LOOP
      EXECUTE format('GRANT USAGE ON SCHEMA %I TO eas_api', s);
    END LOOP;
    GRANT SELECT ON mock_hr.department, mock_hr.employee_directory, mock_hr.leave_balance,
      mock_hr.schema_migration, mock_assets.asset_catalog, mock_assets.asset_loan,
      mock_facilities.resource_catalog, mock_crm.customer_directory, mock_crm.contract,
      mock_procurement.supplier_directory, mock_procurement.catalog_item,
      mock_it.application_catalog, mock_it.access_role, mock_it.service_catalog,
      mock_finance.cost_center_budget, mock_finance.expense_category,
      mock_travel.travel_policy, mock_travel.travel_option TO eas_api;
    -- Bảng có RLS: trả policy đọc cho eas_api.
    FOR t IN SELECT c.oid::regclass AS rel FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname LIKE 'mock' || chr(92) || '_%' AND c.relkind = 'r' AND c.relrowsecurity LOOP
      IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = t.rel AND polname = 'api_read') THEN
        EXECUTE format('CREATE POLICY api_read ON %s FOR SELECT TO eas_api USING (true)', t.rel);
      END IF;
    END LOOP;
  END IF;
END
$grants$;

RESET ROLE;
COMMIT;
