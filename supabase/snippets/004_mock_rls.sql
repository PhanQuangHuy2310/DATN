-- Upgrade 1.3.0 -> 1.4.0. Defense in depth (vibe-check DATABASE_ACCESS):
-- every mock_* table gets row level security with read-only policies for the
-- roles that already hold SELECT grants. anon/authenticated still have no
-- grants and no schema USAGE; the owner (eas_migration) keeps seeding rights.
BEGIN;
SET LOCAL ROLE eas_migration;
DO $rls$
DECLARE t record;
BEGIN
  FOR t IN
    SELECT schemaname, tablename FROM pg_tables
    WHERE schemaname IN ('mock_hr','mock_assets','mock_facilities','mock_crm',
                         'mock_procurement','mock_it','mock_finance','mock_travel')
  LOOP
    EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', t.schemaname, t.tablename);
    EXECUTE format('DROP POLICY IF EXISTS api_read ON %I.%I', t.schemaname, t.tablename);
    EXECUTE format('DROP POLICY IF EXISTS backup_read ON %I.%I', t.schemaname, t.tablename);
    EXECUTE format('CREATE POLICY api_read ON %I.%I FOR SELECT TO eas_api USING (true)', t.schemaname, t.tablename);
    EXECUTE format('CREATE POLICY backup_read ON %I.%I FOR SELECT TO eas_backup USING (true)', t.schemaname, t.tablename);
  END LOOP;
END
$rls$;
INSERT INTO mock_hr.schema_migration(version,description)
VALUES ('004','Row level security on mock source tables');
COMMIT;
