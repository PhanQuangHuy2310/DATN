-- Run as project postgres/DB administrator after 00. READ ONLY; safe on an installed schema.
-- This checks schema integrity, not application readiness or go-live acceptance.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='30s';
SET LOCAL timezone='UTC';
DO $verify$
DECLARE n integer;
BEGIN
 SELECT count(*) INTO n FROM pg_tables WHERE schemaname='eas';
 IF n<>30 THEN RAISE EXCEPTION 'Expected 30 EAS domain tables, found %',n; END IF;
 SELECT count(*) INTO n FROM information_schema.columns WHERE table_schema='eas';
 IF n<>260 THEN RAISE EXCEPTION 'Expected 260 EAS columns, found %',n; END IF;
 IF EXISTS(SELECT 1 FROM unnest(ARRAY[
  'security_epoch','department','app_user','role_membership','request_type','config_release',
  'request','request_revision','workflow_instance','request_participant','approval_step',
  'approval_decision','execution_attempt','acceptance_decision','execution_issue','attachment',
  'draft_attachment','revision_attachment','execution_attachment','sla_stage','sla_alert',
  'audit_event','admin_event','audit_head','audit_checkpoint','outbox_event','notification',
  'idempotency_record','privacy_case','retention_hold']) expected(name)
  WHERE NOT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='eas' AND tablename=expected.name)) THEN
  RAISE EXCEPTION 'One or more expected EAS tables are missing';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='eas' AND c.relkind='r' AND (NOT c.relrowsecurity OR pg_get_userbyid(c.relowner)<>'eas_migration')) THEN
  RAISE EXCEPTION 'EAS table owner or RLS setup differs from baseline';
 END IF;
 SELECT count(*) INTO n FROM pg_constraint c JOIN pg_namespace s ON s.oid=c.connamespace WHERE s.nspname='eas' AND c.contype='p';
 IF n<>30 THEN RAISE EXCEPTION 'Every domain table must have a primary key'; END IF;
 SELECT count(*) INTO n FROM pg_constraint c JOIN pg_namespace s ON s.oid=c.connamespace WHERE s.nspname='eas' AND c.contype='f';
 IF n<>72 THEN RAISE EXCEPTION 'Expected 72 foreign keys, found %',n; END IF;
 SELECT count(*) INTO n FROM pg_constraint c JOIN pg_namespace s ON s.oid=c.connamespace WHERE s.nspname='eas' AND c.contype='c';
 IF n<>139 THEN RAISE EXCEPTION 'Expected 139 CHECK constraints, found %',n; END IF;
 SELECT count(*) INTO n FROM pg_policies WHERE schemaname='eas';
 IF n<>60 THEN RAISE EXCEPTION 'Expected 60 service-role RLS policies, found %',n; END IF;
 SELECT count(*) INTO n FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace s ON s.oid=c.relnamespace WHERE s.nspname='eas' AND NOT t.tgisinternal;
 IF n<>52 THEN RAISE EXCEPTION 'Expected 52 business guard triggers, found %',n; END IF;
 IF EXISTS(SELECT 1 FROM pg_constraint c JOIN pg_namespace s ON s.oid=c.connamespace
  WHERE s.nspname='eas' AND (NOT c.convalidated OR (c.contype='f' AND c.confdeltype<>'r'))) THEN
  RAISE EXCEPTION 'Unvalidated or non-RESTRICT foreign key/check found';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_constraint c JOIN pg_namespace s ON s.oid=c.connamespace
  WHERE s.nspname='eas' AND c.conname='request_current_revision_same_request' AND c.condeferrable AND c.condeferred) THEN
  RAISE EXCEPTION 'Deferred circular revision FK is missing';
 END IF;
 SELECT count(*) INTO n FROM pg_indexes WHERE schemaname='eas' AND indexname IN ('one_active_instance','one_active_step','one_current_attempt','one_open_stage');
 IF n<>4 THEN RAISE EXCEPTION 'Missing partial unique workflow indexes'; END IF;
 IF EXISTS(SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace s ON s.oid=c.relnamespace
  WHERE s.nspname='eas' AND NOT t.tgisinternal AND t.tgenabled NOT IN ('O','A')) THEN
  RAISE EXCEPTION 'A business guard trigger is disabled';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM eas.security_epoch WHERE id=1) OR NOT EXISTS(SELECT 1 FROM eas.audit_head WHERE scope_key='ADMIN') THEN
  RAISE EXCEPTION 'Required singleton or audit seed is missing';
 END IF;
 SELECT count(*) INTO n FROM eas.request_type WHERE (code,lifecycle) IN (('LEAVE','A'),('ACCESS','B'),('EQUIPMENT','C'));
 IF n<>3 THEN RAISE EXCEPTION 'Missing P0 reference types'; END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')
  AND (has_schema_privilege(oid,'eas','USAGE') OR has_table_privilege(oid,'eas.request','SELECT'))) THEN
  RAISE EXCEPTION 'Unexpected Supabase client access to private EAS data';
 END IF;
 IF has_table_privilege('eas_worker','eas.approval_decision','INSERT') OR has_table_privilege('eas_api','eas.audit_head','UPDATE') THEN
  RAISE EXCEPTION 'Service role privileges are broader than the baseline';
 END IF;
END
$verify$;
SELECT 'PASS: EAS 2.0.1 schema checks' AS result,version() AS postgres_version;
SELECT code,lifecycle,is_active,active_release_id,
 CASE WHEN active_release_id IS NULL THEN 'REQUIRES_APPROVED_CONFIG_BEFORE_USE' ELSE 'CONFIG_POINTER_PRESENT' END AS setup_status
 FROM eas.request_type ORDER BY code;
SELECT t.tablename,
 (SELECT count(*) FROM information_schema.columns c WHERE c.table_schema='eas' AND c.table_name=t.tablename) AS columns,
 (SELECT count(*) FROM pg_indexes i WHERE i.schemaname='eas' AND i.tablename=t.tablename) AS indexes
 FROM pg_tables t WHERE t.schemaname='eas' ORDER BY t.tablename;
COMMIT;
