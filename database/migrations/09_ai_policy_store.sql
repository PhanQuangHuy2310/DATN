-- AI policy rules are stored here (source of truth). The AI service keeps only
-- a cached copy: the API pushes each activated version, and an AI container
-- that starts without a cache pulls the active version from the API.
-- Existing file-based policy: python manage.py import_ai_policy_file <path>
-- Rollback: database/migrations/rollback/09_ai_policy_store_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

CREATE TABLE eas.ai_policy_version (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version varchar(50) NOT NULL UNIQUE CHECK (length(btrim(version)) > 0),
  document jsonb NOT NULL CHECK (jsonb_typeof(document->'rules') = 'array'),
  state varchar(8) NOT NULL DEFAULT 'INACTIVE' CHECK (state IN ('ACTIVE','INACTIVE')),
  created_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  activated_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  activated_at timestamptz,
  CHECK (state = 'INACTIVE' OR activated_at IS NOT NULL)
);
CREATE UNIQUE INDEX ai_policy_one_active ON eas.ai_policy_version(state) WHERE state = 'ACTIVE';
CREATE INDEX ai_policy_created ON eas.ai_policy_version(created_at DESC);
COMMENT ON TABLE eas.ai_policy_version IS 'Bộ luật quy định AI theo phiên bản; đúng một phiên bản ACTIVE.';

GRANT SELECT, INSERT, UPDATE ON eas.ai_policy_version TO eas_api;
ALTER TABLE eas.ai_policy_version ENABLE ROW LEVEL SECURITY;
CREATE POLICY trusted_backend ON eas.ai_policy_version
  FOR ALL TO eas_api USING (true) WITH CHECK (true);

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT to_regclass('eas.ai_policy_version') AS created;
