-- AI auto-approval actor. Approval decisions must reference a real app_user
-- that is the step assignee, so the worker hands low-risk steps (weight <= 2)
-- to this account before approving. The password hash is unusable: nobody
-- can sign in as this account. Matches EAS_AI_SYSTEM_USER_ID in settings.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

INSERT INTO eas.app_user(id,email,display_name,department_id,password_hash,must_change_password,is_active)
SELECT '00000002-0000-4000-8000-0000000000a1','ai.system@eas.com','EAS AI (tự động duyệt)',
       d.id,'!UNUSABLE_AI_SYSTEM',false,true
FROM eas.department d
WHERE d.code='BOD'
ON CONFLICT (id) DO NOTHING;

INSERT INTO eas.role_membership(user_id,role,scope_kind,department_id,type_scope,type_id,valid_from)
SELECT '00000002-0000-4000-8000-0000000000a1','APPROVER','GLOBAL',NULL,'ALL',NULL,statement_timestamp()
WHERE NOT EXISTS (
  SELECT 1 FROM eas.role_membership
  WHERE user_id='00000002-0000-4000-8000-0000000000a1' AND role='APPROVER' AND revoked_at IS NULL
);

UPDATE eas.security_epoch SET version=version+1,updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT u.email, u.is_active, array_agg(m.role) AS roles
FROM eas.app_user u JOIN eas.role_membership m ON m.user_id=u.id AND m.revoked_at IS NULL
WHERE u.id='00000002-0000-4000-8000-0000000000a1'
GROUP BY u.email, u.is_active;
