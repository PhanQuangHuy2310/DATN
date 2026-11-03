-- Rollback 13 — chỉ hoàn tác phần có thể cần hoàn tác: security_invoker của view.
-- Cố ý KHÔNG cấp lại quyền cho anon/authenticated và KHÔNG tắt RLS: đó là lỗ hổng
-- (AGENTS.md). Chủ sở hữu object giữ eas_migration.
BEGIN;
SET LOCAL ROLE eas_migration;

DO $views$
DECLARE v text;
BEGIN
  FOR v IN
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'eas' AND c.relkind = 'v'
      AND c.relname IN ('admins', 'departments', 'request_templates', 'requests', 'role_permissions',
                        'roles', 'user_roles', 'v_request_templates_full', 'v_users_management')
  LOOP
    EXECUTE format('ALTER VIEW eas.%I RESET (security_invoker)', v);
  END LOOP;
END
$views$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;

COMMIT;
