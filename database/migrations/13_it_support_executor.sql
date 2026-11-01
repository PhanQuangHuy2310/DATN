-- IT_SUPPORT: work is executed by IT (EXECUTOR_IT) instead of Administration.
-- Published releases are immutable, so a new version is published and made
-- active; bindings are re-merged from active releases (same rule as 12).
-- Rollback: database/migrations/rollback/13_it_support_executor_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

DO $migration$
DECLARE
  current_release eas.config_release;
  bindings jsonb;
  new_route jsonb;
  release_id uuid;
  author uuid := '00000002-0000-4000-8000-000000000001';
BEGIN
  SELECT cr.* INTO current_release
  FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
  WHERE rt.code = 'IT_SUPPORT';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'IT_SUPPORT has no active release; nothing changed.';
  END IF;
  IF current_release.route_rules->>'executor' = 'EXECUTOR_IT' THEN
    RAISE NOTICE 'IT_SUPPORT already executed by IT; nothing changed.';
    RETURN;
  END IF;

  SELECT jsonb_build_object('schema_version', 1, 'departments', jsonb_object_agg(dept, slots))
  INTO bindings
  FROM (
    SELECT dept, jsonb_object_agg(slot, val) AS slots
    FROM (
      SELECT DISTINCT ON (d.key, s.key) d.key AS dept, s.key AS slot, s.value AS val
      FROM eas.config_release cr
      JOIN eas.request_type rt ON rt.active_release_id = cr.id
      CROSS JOIN LATERAL jsonb_each(cr.actor_bindings->'departments') d
      CROSS JOIN LATERAL jsonb_each(d.value) s
      ORDER BY d.key, s.key, cr.published_at DESC NULLS LAST
    ) slot_rows
    GROUP BY dept
  ) dept_rows;

  new_route := jsonb_set(current_release.route_rules, '{executor}', '"EXECUTOR_IT"');
  INSERT INTO eas.config_release(
    type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
    created_by, published_by, published_at, content_sha256, risk_weight, approval_level)
  VALUES (
    current_release.type_id,
    (SELECT max(version) + 1 FROM eas.config_release WHERE type_id = current_release.type_id),
    'PUBLISHED', current_release.lifecycle, current_release.form_schema, new_route, bindings,
    current_release.sla_profile, author, author, statement_timestamp(),
    encode(sha256(convert_to(jsonb_build_object(
      'form_schema', current_release.form_schema, 'route_rules', new_route,
      'actor_bindings', bindings, 'sla_profile', current_release.sla_profile,
      'lifecycle', current_release.lifecycle)::text, 'UTF8')), 'hex'),
    current_release.risk_weight, current_release.approval_level)
  RETURNING id INTO release_id;
  UPDATE eas.request_type SET active_release_id = release_id WHERE id = current_release.type_id;
END
$migration$;

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT cr.version, cr.route_rules->>'executor' AS executor
FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
WHERE rt.code = 'IT_SUPPORT';
