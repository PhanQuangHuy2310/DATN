-- TEST DATA ONLY: undo 06_dev_gmail_aliases and give every account its own
-- @eas.com login. Reset mail is redirected to one inbox by EAS_EMAIL_TEST_RECIPIENT,
-- so no Gmail aliases are needed. Deploy with EAS_LOGIN_EMAIL_DOMAIN=eas.com.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

DO $migration$
BEGIN
  IF EXISTS (
    SELECT 1 FROM eas.app_user
    WHERE email !~ '^[^@[:space:]]+@gmail[.]com$'
  ) THEN
    RAISE EXCEPTION 'Expected all current test accounts to use Gmail aliases; no rows changed.';
  END IF;

  CREATE TEMP TABLE eas_email_map(id uuid PRIMARY KEY, email varchar(254) UNIQUE NOT NULL) ON COMMIT DROP;
  INSERT INTO eas_email_map(id,email) VALUES
    ('00000002-0000-4000-8000-000000000001'::uuid,'admin@eas.com'),
    ('00000002-0000-4000-8000-000000000002'::uuid,'hung.nguyen@eas.com'),
    ('00000002-0000-4000-8000-000000000003'::uuid,'ngoc.tran@eas.com'),
    ('00000002-0000-4000-8000-000000000004'::uuid,'long.le@eas.com'),
    ('00000002-0000-4000-8000-000000000005'::uuid,'tuan.pham@eas.com'),
    ('00000002-0000-4000-8000-000000000006'::uuid,'huy.do@eas.com'),
    ('00000002-0000-4000-8000-000000000007'::uuid,'lan.ngo@eas.com'),
    ('00000002-0000-4000-8000-000000000008'::uuid,'anh.vu@eas.com'),
    ('00000002-0000-4000-8000-000000000009'::uuid,'nam.hoang@eas.com'),
    ('00000002-0000-4000-8000-000000000010'::uuid,'khoi.dang@eas.com'),
    ('00000002-0000-4000-8000-000000000011'::uuid,'phuc.vo@eas.com'),
    ('00000002-0000-4000-8000-000000000012'::uuid,'chau.nguyen@eas.com'),
    ('00000002-0000-4000-8000-000000000013'::uuid,'linh.doan@eas.com'),
    ('00000002-0000-4000-8000-000000000014'::uuid,'ha.bui@eas.com'),
    ('00000002-0000-4000-8000-000000000015'::uuid,'phuc.dang@eas.com'),
    ('00000002-0000-4000-8000-000000000016'::uuid,'ngoc.trinh@eas.com'),
    ('00000002-0000-4000-8000-000000000017'::uuid,'duc.ly@eas.com'),
    ('00000002-0000-4000-8000-000000000018'::uuid,'yen.hoang@eas.com'),
    ('00000002-0000-4000-8000-000000000019'::uuid,'thang.ngo@eas.com'),
    ('00000002-0000-4000-8000-000000000020'::uuid,'yen.phan@eas.com'),
    ('00000002-0000-4000-8000-000000000021'::uuid,'kien.duong@eas.com'),
    ('00000002-0000-4000-8000-000000000022'::uuid,'ha.luong@eas.com'),
    ('00000002-0000-4000-8000-000000000023'::uuid,'trang.vu@eas.com'),
    ('00000002-0000-4000-8000-000000000024'::uuid,'thao.le@eas.com'),
    ('00000002-0000-4000-8000-000000000025'::uuid,'bao.hoang@eas.com'),
    ('00000002-0000-4000-8000-000000000026'::uuid,'dung.nguyen@eas.com'),
    ('00000002-0000-4000-8000-000000000027'::uuid,'trong.tran@eas.com'),
    ('00000002-0000-4000-8000-000000000028'::uuid,'hai.le@eas.com'),
    ('00000002-0000-4000-8000-000000000029'::uuid,'huyen.pham@eas.com'),
    ('00000002-0000-4000-8000-000000000030'::uuid,'thao.vu@eas.com'),
    ('00000002-0000-4000-8000-000000000031'::uuid,'vy.pham@eas.com'),
    ('00000002-0000-4000-8000-000000000032'::uuid,'tuan.dang@eas.com'),
    ('00000002-0000-4000-8000-000000000033'::uuid,'nga.trinh@eas.com'),
    ('00000002-0000-4000-8000-000000000034'::uuid,'cuong.dinh@eas.com'),
    ('00000002-0000-4000-8000-000000000035'::uuid,'phuong.to@eas.com'),
    ('00000002-0000-4000-8000-000000000036'::uuid,'dat.ha@eas.com'),
    ('00000002-0000-4000-8000-000000000037'::uuid,'uyen.lam@eas.com'),
    ('00000002-0000-4000-8000-000000000038'::uuid,'khoi.vo@eas.com'),
    ('00000002-0000-4000-8000-000000000039'::uuid,'dieu.mai@eas.com'),
    ('00000002-0000-4000-8000-000000000040'::uuid,'tuan.phan@eas.com'),
    ('00000002-0000-4000-8000-000000000041'::uuid,'tri.tran@eas.com'),
    ('00000002-0000-4000-8000-000000000042'::uuid,'anh.mai@eas.com');

  IF (SELECT count(*) FROM eas.app_user u LEFT JOIN eas_email_map m USING (id) WHERE m.id IS NULL) > 0 THEN
    RAISE EXCEPTION 'Some accounts have no @eas.com mapping; no rows changed.';
  END IF;

  ALTER TABLE eas.app_user DROP CONSTRAINT app_user_email_policy;

  UPDATE eas.app_user u
  SET email=m.email,
      auth_version=u.auth_version+1
  FROM eas_email_map m
  WHERE u.id=m.id;

  UPDATE eas.password_reset_request pr
  SET requested_email=u.email
  FROM eas.app_user u
  WHERE pr.user_id=u.id AND pr.status='PENDING';

  SET CONSTRAINTS ALL IMMEDIATE;

  ALTER TABLE eas.app_user
    ADD CONSTRAINT app_user_email_policy
    CHECK (email=lower(btrim(email)) AND email ~ '^[^@[:space:]]+@eas[.]com$');

  UPDATE eas.security_epoch
  SET version=version+1,updated_at=statement_timestamp()
  WHERE id=1;
END
$migration$;

COMMIT;

SELECT count(*) AS account_count,
       count(*) FILTER (WHERE email ~ '^[^@[:space:]]+@eas[.]com$') AS eas_email_count
FROM eas.app_user;
