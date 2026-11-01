-- TEST DATA ONLY: map EAS accounts to distinct Gmail plus-addresses in one inbox.
-- Deploy the API first with EAS_LOGIN_EMAIL_DOMAIN=gmail.com and working Gmail SMTP.
-- Replace the mailbox placeholder before running; do not use with real accounts.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

DO $migration$
DECLARE
  mailbox text := 'REPLACE_WITH_YOUR_GMAIL_ADDRESS';
BEGIN
  IF mailbox !~ '^[A-Za-z0-9.]+@gmail[.]com$'
     OR position('+' in split_part(mailbox, '@', 1)) > 0 THEN
    RAISE EXCEPTION 'Replace mailbox with one Gmail address without a plus tag.';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='eas.app_user'::regclass
      AND conname='app_user_email_policy'
  ) THEN
    RAISE EXCEPTION 'Expected app_user_email_policy; inspect schema before migrating.';
  END IF;

  IF EXISTS (
    SELECT 1 FROM eas.app_user
    WHERE email !~ '^[^@[:space:]]+@eas[.]com$'
  ) THEN
    RAISE EXCEPTION 'Expected all current test accounts to use @eas.com; no rows changed.';
  END IF;

  ALTER TABLE eas.app_user DROP CONSTRAINT app_user_email_policy;

  UPDATE eas.app_user
  SET email=split_part(mailbox, '@', 1) || '+' || replace(id::text, '-', '') || '@gmail.com',
      auth_version=auth_version+1;

  UPDATE eas.password_reset_request pr
  SET requested_email=u.email
  FROM eas.app_user u
  WHERE pr.user_id=u.id AND pr.status='PENDING';

  SET CONSTRAINTS ALL IMMEDIATE;

  ALTER TABLE eas.app_user
    ADD CONSTRAINT app_user_email_policy
    CHECK (email=lower(btrim(email)) AND email ~ '^[^@[:space:]]+@gmail[.]com$');

  UPDATE eas.security_epoch
  SET version=version+1,updated_at=statement_timestamp()
  WHERE id=1;
END
$migration$;

COMMIT;

SELECT count(*) AS account_count,
       count(*) FILTER (WHERE email ~ '^[^@[:space:]]+@gmail[.]com$') AS gmail_alias_count,
       count(*) FILTER (WHERE email ~ '^[^@[:space:]]+@eas[.]com$') AS eas_email_count
FROM eas.app_user;
