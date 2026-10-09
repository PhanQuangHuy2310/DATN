-- READ ONLY. Run as project postgres after provisioning runtime logins.
BEGIN TRANSACTION READ ONLY;

DO $$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['eas_backend_login', 'eas_worker_login'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name AND rolcanlogin) THEN
      RAISE EXCEPTION 'Missing LOGIN role: %', role_name;
    END IF;
  END LOOP;

  IF NOT pg_has_role('eas_backend_login', 'eas_api', 'member')
     OR pg_has_role('eas_backend_login', 'eas_worker', 'member') THEN
    RAISE EXCEPTION 'eas_backend_login membership is invalid';
  END IF;

  IF NOT pg_has_role('eas_worker_login', 'eas_worker', 'member')
     OR pg_has_role('eas_worker_login', 'eas_api', 'member') THEN
    RAISE EXCEPTION 'eas_worker_login membership is invalid';
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
