-- REVIEW ONLY. Not auto-applied. Requires owner approval (B4), DBA review and a
-- full backup. Thesis §2.3: five retries after the first attempt = 6 attempts.
--
-- Compatible with existing data: events already DEAD at 4 attempts (legacy
-- limit) stay valid. The worker reads the new limit from this constraint
-- (api_core/worker.py outbox_max_attempts); restart workers after applying.
--
-- BEFORE RUNNING: pg_dump --schema=eas --schema-only > eas_schema_before_09.sql
-- ROLLBACK (only while no event has more than 4 attempts):
--   BEGIN;
--   SELECT count(*) FROM eas.outbox_event WHERE attempts > 4;   -- must be 0
--   ALTER TABLE eas.outbox_event DROP CONSTRAINT outbox_dead;
--   ALTER TABLE eas.outbox_event DROP CONSTRAINT outbox_event_attempts_check;
--   ALTER TABLE eas.outbox_event ADD CONSTRAINT outbox_event_attempts_check
--     CHECK (attempts >= 0 AND attempts <= 4);
--   ALTER TABLE eas.outbox_event ADD CONSTRAINT outbox_dead
--     CHECK (state <> 'DEAD' OR attempts = 4);
--   COMMIT;
--   Then restart workers so they re-read the limit.

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';

DO $pre$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'outbox_dead'
                 AND conrelid = 'eas.outbox_event'::regclass
                 AND pg_get_constraintdef(oid) LIKE '%attempts = 4%') THEN
    RAISE EXCEPTION 'outbox_dead differs from the expected legacy definition; inspect drift';
  END IF;
END
$pre$;

ALTER TABLE eas.outbox_event DROP CONSTRAINT outbox_event_attempts_check;
ALTER TABLE eas.outbox_event ADD CONSTRAINT outbox_event_attempts_check
  CHECK (attempts >= 0 AND attempts <= 6);
ALTER TABLE eas.outbox_event DROP CONSTRAINT outbox_dead;
-- 4 keeps legacy dead letters valid; new dead letters are written at 6.
ALTER TABLE eas.outbox_event ADD CONSTRAINT outbox_dead
  CHECK (state <> 'DEAD' OR (attempts >= 4 AND attempts <= 6));

DO $verify$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'outbox_dead'
                 AND pg_get_constraintdef(oid) LIKE '%attempts <= 6%') THEN
    RAISE EXCEPTION 'outbox_dead not updated';
  END IF;
END
$verify$;

COMMIT;
