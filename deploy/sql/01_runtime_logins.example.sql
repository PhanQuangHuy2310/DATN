-- TEMPLATE ONLY. Copy outside the repository, replace the two placeholders with
-- independently generated passwords, execute once as project postgres, then
-- securely delete the populated copy. Never commit the populated SQL.
--
-- Rotate credentials if this statement appears in SQL history or logs.

BEGIN;

DO $$
BEGIN
  IF '__GENERATE_UNIQUE_API_PASSWORD__' LIKE '__GENERATE_%'
     OR '__GENERATE_UNIQUE_WORKER_PASSWORD__' LIKE '__GENERATE_%' THEN
    RAISE EXCEPTION 'Replace both password placeholders in every occurrence before execution';
  END IF;
END $$;

CREATE ROLE eas_backend_login LOGIN INHERIT NOBYPASSRLS
  PASSWORD '__GENERATE_UNIQUE_API_PASSWORD__';
GRANT eas_api TO eas_backend_login;
ALTER ROLE eas_backend_login SET search_path = pg_catalog, eas;
ALTER ROLE eas_backend_login SET statement_timeout = '30s';
ALTER ROLE eas_backend_login SET lock_timeout = '5s';

CREATE ROLE eas_worker_login LOGIN INHERIT NOBYPASSRLS
  PASSWORD '__GENERATE_UNIQUE_WORKER_PASSWORD__';
GRANT eas_worker TO eas_worker_login;
ALTER ROLE eas_worker_login SET search_path = pg_catalog, eas;
ALTER ROLE eas_worker_login SET statement_timeout = '30s';
ALTER ROLE eas_worker_login SET lock_timeout = '5s';

-- Fail if a login accidentally received both runtime groups or an admin bit.
DO $$
BEGIN
  IF pg_has_role('eas_backend_login', 'eas_worker', 'member')
     OR pg_has_role('eas_worker_login', 'eas_api', 'member') THEN
    RAISE EXCEPTION 'Runtime roles must remain separated';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname IN ('eas_backend_login', 'eas_worker_login')
      AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls)
  ) THEN
    RAISE EXCEPTION 'Runtime login has forbidden PostgreSQL privilege';
  END IF;
END $$;

COMMIT;
