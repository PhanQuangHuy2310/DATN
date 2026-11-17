-- EAS 2.1.0 -> current authentication schema.
-- Preserves accounts and business data; does not reset or drop schemas.
-- Run once as postgres/schema owner after catalog migration 04.

BEGIN;
SET LOCAL timezone='UTC';
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='300s';
SET LOCAL ROLE eas_migration;
SET CONSTRAINTS ALL IMMEDIATE;

DO $migration$
DECLARE
  has_username boolean;
  has_email boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='eas' AND table_name='app_user' AND column_name='username'
  ) INTO has_username;
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='eas' AND table_name='app_user' AND column_name='email'
  ) INTO has_email;

  IF has_username AND has_email THEN
    RAISE EXCEPTION 'Both username and email exist on eas.app_user; inspect schema drift before migrating.';
  ELSIF NOT has_username AND NOT has_email THEN
    RAISE EXCEPTION 'Neither username nor email exists on eas.app_user.';
  ELSIF has_username THEN
    IF EXISTS (
      SELECT 1 FROM eas.app_user
      GROUP BY lower(btrim(split_part(username, '@', 1)))
      HAVING count(*) > 1
    ) THEN
      RAISE EXCEPTION 'Email migration would create duplicate @eas.com addresses.';
    END IF;

    IF EXISTS (
      SELECT 1 FROM eas.app_user
      WHERE btrim(split_part(username, '@', 1)) = ''
         OR btrim(split_part(username, '@', 1)) ~ '[[:space:]]'
         OR length(btrim(split_part(username, '@', 1))) > 64
    ) THEN
      RAISE EXCEPTION 'Email migration found a username that cannot form a valid @eas.com address.';
    END IF;

    ALTER TABLE eas.app_user RENAME COLUMN username TO email;
    ALTER TABLE eas.app_user ALTER COLUMN email TYPE varchar(254);
    ALTER TABLE eas.app_user DROP CONSTRAINT IF EXISTS app_user_username_check;
    ALTER TABLE eas.app_user
      RENAME CONSTRAINT app_user_username_key TO app_user_email_key;
    UPDATE eas.app_user
    SET email=lower(btrim(split_part(email, '@', 1))) || '@eas.com',
        auth_version=auth_version+1;
  ELSE
    IF EXISTS (
      SELECT 1 FROM eas.app_user
      WHERE email !~ '^[^@[:space:]]+@eas[.]com$'
    ) THEN
      RAISE EXCEPTION 'Existing employee emails do not meet the @eas.com policy.';
    END IF;
  END IF;
END
$migration$;

SET CONSTRAINTS ALL IMMEDIATE;
DO $email_policy$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='eas.app_user'::regclass
      AND contype='c'
      AND pg_get_constraintdef(oid) LIKE '%@eas%'
  ) THEN
    ALTER TABLE eas.app_user
      ADD CONSTRAINT app_user_email_policy
      CHECK (email=lower(btrim(email)) AND email ~ '^[^@[:space:]]+@eas[.]com$');
  END IF;
END
$email_policy$;

CREATE TABLE eas.password_reset_request (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  requested_email varchar(254) NOT NULL,
  status varchar(10) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING','APPROVED','EXPIRED')),
  requested_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  expires_at timestamptz NOT NULL,
  resolved_at timestamptz,
  resolved_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  resolution_reason varchar(2000),
  CHECK (expires_at > requested_at),
  CHECK (
    (status='PENDING' AND resolved_at IS NULL AND resolved_by IS NULL)
    OR (status<>'PENDING' AND resolved_at IS NOT NULL)
  )
);
CREATE UNIQUE INDEX password_reset_one_pending_per_user
  ON eas.password_reset_request(user_id) WHERE status='PENDING';
CREATE INDEX password_reset_pending_queue
  ON eas.password_reset_request(requested_at,id) WHERE status='PENDING';
GRANT SELECT, INSERT, UPDATE ON eas.password_reset_request TO eas_api;
ALTER TABLE eas.password_reset_request ENABLE ROW LEVEL SECURITY;
CREATE POLICY trusted_backend ON eas.password_reset_request
  FOR ALL TO eas_api USING (true) WITH CHECK (true);

UPDATE eas.security_epoch
SET version=version+1, updated_at=statement_timestamp()
WHERE id=1;

COMMENT ON SCHEMA eas IS 'EAS current schema; email login; admin-approved password reset; backend-only';

COMMIT;

SELECT 'EAS email login and password reset upgrade complete' AS result,
       (SELECT count(*) FROM eas.app_user) AS accounts,
       (SELECT count(*) FROM eas.password_reset_request) AS reset_requests;
