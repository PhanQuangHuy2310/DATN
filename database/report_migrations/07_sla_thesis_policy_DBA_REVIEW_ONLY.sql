-- REVIEW ONLY. Not auto-applied. Requires owner approval (B3), DBA review and a
-- full backup. Implements thesis Table 2.9 (80% reminder, 100% L1, >150% L2).
--
-- What it changes (and nothing else):
--   1. eas.sla_alert.kind accepts 'ESCALATE' (L2) besides REMINDER / BREACH (L1).
--      'ESCALATE' fits the existing varchar(8); no column rewrite.
--   2. eas.guard_release() accepts reminder_fraction 0.8 as well as 0.5.
--      Published releases stay immutable: existing releases keep 0.5 until a
--      Policy Admin publishes new versions with 0.8 (separate approval).
-- What it does NOT do: change published releases, open/close SLA stages,
-- send notifications, or grant read access to escalation recipients.
--
-- Enable in the application only AFTER this has been applied:
--   EAS_SLA_ESCALATION_LEVELS=1   (api_core/worker.py; default off)
--
-- BEFORE RUNNING (backup):
--   pg_dump --schema=eas --schema-only > eas_schema_before_07.sql
--   SELECT pg_get_functiondef('eas.guard_release()'::regprocedure);  -- save output
--   SELECT pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conname='sla_alert_kind_check';                            -- save output
--
-- ROLLBACK (only while no 'ESCALATE' rows exist and no release uses 0.8):
--   BEGIN;
--   SELECT count(*) FROM eas.sla_alert WHERE kind='ESCALATE';               -- must be 0
--   SELECT count(*) FROM eas.config_release
--    WHERE sla_profile->'reminder_fraction' = '0.8'::jsonb;                  -- must be 0
--   ALTER TABLE eas.sla_alert DROP CONSTRAINT sla_alert_kind_check;
--   ALTER TABLE eas.sla_alert ADD CONSTRAINT sla_alert_kind_check
--     CHECK (kind IN ('REMINDER','BREACH'));
--   -- restore the saved guard_release() definition, then:
--   COMMIT;
--   Unset EAS_SLA_ESCALATION_LEVELS before rolling back.

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';

ALTER TABLE eas.sla_alert DROP CONSTRAINT sla_alert_kind_check;
ALTER TABLE eas.sla_alert ADD CONSTRAINT sla_alert_kind_check
  CHECK (kind IN ('REMINDER', 'BREACH', 'ESCALATE'));
COMMENT ON TABLE eas.sla_alert IS
  'DB21 — Khử trùng cảnh báo theo stage: REMINDER (80%/quy chế), BREACH (L1, 100%), ESCALATE (L2, >150%).';

-- Patch exactly one predicate inside the live guard_release(); abort if the
-- live definition drifted from the bundled schema.
DO $patch$
DECLARE
  def text := pg_get_functiondef('eas.guard_release()'::regprocedure);
  old_predicate constant text :=
    'NEW.sla_profile->''reminder_fraction'' IS DISTINCT FROM ''0.5''::jsonb';
  new_predicate constant text :=
    'NOT (COALESCE(NEW.sla_profile->''reminder_fraction'',''null''::jsonb) IN (''0.5''::jsonb,''0.8''::jsonb))';
BEGIN
  IF (length(def) - length(replace(def, old_predicate, ''))) / length(old_predicate) <> 1 THEN
    RAISE EXCEPTION 'guard_release() does not contain the expected reminder predicate exactly once; inspect drift before migrating';
  END IF;
  EXECUTE replace(def, old_predicate, new_predicate);
END
$patch$;

-- Verification (must all hold before COMMIT)
DO $verify$
BEGIN
  IF position('''0.8''::jsonb' IN pg_get_functiondef('eas.guard_release()'::regprocedure)) = 0 THEN
    RAISE EXCEPTION 'guard_release() patch not applied';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sla_alert_kind_check'
                 AND pg_get_constraintdef(oid) LIKE '%ESCALATE%') THEN
    RAISE EXCEPTION 'sla_alert kind constraint not updated';
  END IF;
END
$verify$;

COMMIT;
