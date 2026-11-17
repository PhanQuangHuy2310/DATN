-- Dán vào Supabase SQL Editor rồi Run. Xoá file này sau khi chạy xong.
CREATE ROLE eas_mock_login LOGIN PASSWORD '683WGUDWNWHBKPonOPwjQPMTVbD2YzHJ' IN ROLE eas_mock;
SELECT rolname, rolcanlogin, pg_has_role('eas_mock_login', 'eas_mock', 'MEMBER') AS la_thanh_vien_eas_mock
FROM pg_roles WHERE rolname = 'eas_mock_login';


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
