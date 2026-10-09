-- Read-only installation verification. Any returned row is a defect.

SELECT 'missing_schema' AS defect, required.name AS detail
FROM (VALUES ('mock_hr'),('mock_assets'),('mock_facilities'),('mock_crm'),('mock_procurement'),('mock_it'),('mock_finance'),('mock_travel')) required(name)
LEFT JOIN information_schema.schemata s ON s.schema_name=required.name
WHERE s.schema_name IS NULL;

SELECT 'unexpected_public_schema_privilege' AS defect, n.nspname AS detail
FROM pg_namespace n
WHERE n.nspname LIKE 'mock_%' AND has_schema_privilege('public',n.oid,'USAGE');

SELECT 'open_asset_loan_conflict' AS defect, asset_id::text AS detail
FROM mock_assets.asset_loan
WHERE status IN ('RESERVED','ACTIVE','OVERDUE')
GROUP BY asset_id HAVING count(*) > 1;

SELECT 'active_access_conflict' AS defect, employee_id::text || ':' || access_role_id::text AS detail
FROM mock_it.user_access
WHERE status='ACTIVE'
GROUP BY employee_id,access_role_id HAVING count(*) > 1;

SELECT 'asset_state_mismatch' AS defect, id::text AS detail
FROM mock_assets.asset
WHERE condition='RETIRED' AND availability_status<>'RETIRED';

SELECT 'terminated_employee_without_end_date' AS defect, id::text AS detail
FROM mock_hr.employee
WHERE employment_status='TERMINATED' AND ended_on IS NULL;

SELECT 'missing_integrity_trigger' AS defect, required.name AS detail
FROM (VALUES ('trg_asset_loan_overlap'),('trg_facility_reservation_overlap')) required(name)
LEFT JOIN pg_trigger t ON t.tgname=required.name AND NOT t.tgisinternal
WHERE t.oid IS NULL;

SELECT 'missing_migration' AS defect, '001' AS detail
WHERE NOT EXISTS (SELECT 1 FROM mock_hr.schema_migration WHERE version='001');

SELECT 'missing_migration' AS defect, '002' AS detail
WHERE NOT EXISTS (SELECT 1 FROM mock_hr.schema_migration WHERE version='002');

SELECT 'missing_migration' AS defect, '003' AS detail
WHERE NOT EXISTS (SELECT 1 FROM mock_hr.schema_migration WHERE version='003');

SELECT 'public_function_execute' AS defect, n.nspname || '.' || p.proname AS detail
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname LIKE 'mock_%' AND has_function_privilege('public',p.oid,'EXECUTE');
