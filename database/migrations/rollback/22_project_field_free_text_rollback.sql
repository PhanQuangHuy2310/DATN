-- Rollback 22: re-activate the previous release of OVERTIME_REQ / ADVANCE_LARGE
-- when the active one is the free-text project_id release created by 22.
-- The 22 release row is kept (history); only the active pointer moves back.

BEGIN;

UPDATE eas.request_type rt
SET active_release_id = prev.id
FROM eas.config_release cur, LATERAL (
  SELECT p.id FROM eas.config_release p
  WHERE p.type_id = cur.type_id AND p.version < cur.version AND p.state = 'PUBLISHED'
  ORDER BY p.version DESC LIMIT 1
) prev
WHERE rt.code IN ('OVERTIME_REQ', 'ADVANCE_LARGE')
  AND cur.id = rt.active_release_id
  AND cur.form_schema->'properties'->'project_id' = '{"type":"string","minLength":2,"maxLength":120}'::jsonb;

COMMIT;
