-- 22: project_id on OVERTIME_REQ / ADVANCE_LARGE is a free-text project code.
--
-- The published form demanded a UUID (format: uuid) but there is no project
-- catalogue to pick from, so the employee form showed a plain text box and every
-- submit failed with "Giá trị không hợp lệ". The field becomes a project code
-- or name (2-120 chars). Same publish pattern as migration 17: a new PUBLISHED
-- release per type, the previous release stays untouched for history.
--
-- Idempotent: a type whose active release already has the new spec is skipped.
-- Rollback: database/migrations/rollback/22_project_field_free_text_rollback.sql

BEGIN;

DO $forms$
DECLARE
  project_spec constant jsonb := '{"type":"string","minLength":2,"maxLength":120}';
  author uuid;
  t record;
  new_form jsonb;
  new_id uuid;
BEGIN
  SELECT u.id INTO author FROM eas.app_user u WHERE u.account_type = 'ADMIN' AND u.is_active
  ORDER BY u.created_at LIMIT 1;
  FOR t IN
    SELECT rt.id AS type_id, cr.*
    FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
    WHERE rt.code IN ('OVERTIME_REQ', 'ADVANCE_LARGE')
      AND cr.form_schema->'properties' ? 'project_id'
  LOOP
    new_form := jsonb_set(t.form_schema, '{properties,project_id}', project_spec);
    CONTINUE WHEN t.form_schema = new_form;
    INSERT INTO eas.config_release(
      type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
      created_by, published_by, published_at, content_sha256)
    VALUES (
      t.type_id, (SELECT max(version) + 1 FROM eas.config_release WHERE type_id = t.type_id),
      'PUBLISHED', t.lifecycle, new_form, t.route_rules, t.actor_bindings, t.sla_profile,
      coalesce(author, t.created_by), coalesce(author, t.created_by), statement_timestamp(),
      encode(sha256(convert_to(jsonb_build_object(
        'form_schema', new_form, 'route_rules', t.route_rules, 'actor_bindings', t.actor_bindings,
        'sla_profile', t.sla_profile, 'lifecycle', t.lifecycle)::text, 'UTF8')), 'hex'))
    RETURNING id INTO new_id;
    UPDATE eas.request_type SET active_release_id = new_id WHERE id = t.type_id;
  END LOOP;
END
$forms$;

DO $check$
BEGIN
  IF EXISTS (
    SELECT 1 FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
    WHERE rt.code IN ('OVERTIME_REQ', 'ADVANCE_LARGE')
      AND cr.form_schema->'properties'->'project_id'->>'format' = 'uuid'
  ) THEN
    RAISE EXCEPTION '22: project_id still requires a UUID';
  END IF;
END
$check$;

COMMIT;
