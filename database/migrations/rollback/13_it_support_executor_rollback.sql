-- Rollback of 13_it_support_executor.sql: re-activate the previous IT_SUPPORT
-- release (executor EXECUTOR_ADMIN). The newer release stays as history.
BEGIN;
SET LOCAL ROLE eas_migration;
UPDATE eas.request_type rt
SET active_release_id = prev.id
FROM (
  SELECT cr.id, cr.type_id FROM eas.config_release cr
  JOIN eas.request_type t ON t.id = cr.type_id AND t.code = 'IT_SUPPORT'
  WHERE cr.state = 'PUBLISHED' AND cr.route_rules->>'executor' <> 'EXECUTOR_IT'
  ORDER BY cr.version DESC LIMIT 1
) prev
WHERE rt.id = prev.type_id;
UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
