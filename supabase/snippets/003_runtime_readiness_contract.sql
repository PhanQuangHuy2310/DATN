-- Upgrade 1.2.0 -> 1.3.0. Read-only metadata grant for API readiness.
BEGIN;
SET LOCAL ROLE eas_migration;
GRANT SELECT ON mock_hr.schema_migration TO eas_api;
INSERT INTO mock_hr.schema_migration(version,description)
VALUES ('003','Runtime readiness contract grant');
COMMIT;
