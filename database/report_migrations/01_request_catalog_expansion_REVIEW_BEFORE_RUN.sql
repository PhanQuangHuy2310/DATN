-- EAS REPORT v1: DBA REVIEW REQUIRED - DO NOT EXECUTE WITH eas_api OR WORKER LOGIN.
-- The report asserts 16 request categories but does not list 16 canonical codes.
-- Do not seed invented codes. This migration ONLY permits future audited catalog entries.
-- Before execution: backup DB, verify UAT, verify mock integrations and audit traces.
-- Only an authorized migration role may execute. This migration is not auto-applied.
BEGIN;
ALTER TABLE eas.request_type DROP CONSTRAINT type_p0;
ALTER TABLE eas.request_type
  ADD CONSTRAINT request_type_code_syntax
  CHECK (code ~ '^[A-Z][A-Z0-9_]{1,29}$' AND lifecycle IN ('A','B','C'));
-- Baseline eas_api has SELECT/UPDATE but NOT INSERT permission on request_type.
-- New API is scoped to OPS_ADMIN GLOBAL/ALL, reason, idempotency and audit;
-- nonetheless this broadens SQL privileges and needs DBA/security sign-off.
GRANT INSERT ON eas.request_type TO eas_api;
GRANT UPDATE (response_body) ON eas.idempotency_record TO eas_api;
COMMIT;
-- With migration and backend tests complete, set EAS_ALLOW_REPORT_CATALOG_EXPANSION=true.
-- New types are NOT usable until Policy Admin publishes a validated config and
-- REQUESTER is granted valid membership for that type/department scope.
-- SLA 80% vs P0 50% and AI auto-approval require separate security review/migrations.
