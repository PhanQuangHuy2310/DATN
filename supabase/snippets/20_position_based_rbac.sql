-- =============================================================================
-- Migration 20: Position-Based RBAC (5 Enterprise Positions)
-- Positions: STAFF (Nhân viên), TEAM_LEAD (Trưởng nhóm), MANAGER (Trưởng phòng),
--            VICE_DIRECTOR (Phó giám đốc), DIRECTOR (Giám đốc)
-- =============================================================================

BEGIN;

SELECT eas.lock_security(true);

-- 1. Upsert the 5 Enterprise Position roles into eas.role
INSERT INTO eas.role (code, name, description, is_system)
VALUES
    ('STAFF', 'Nhân viên', 'Nhân viên chuyên môn khởi tạo yêu cầu, thực hiện công việc và nghiệm thu kết quả.', true),
    ('TEAM_LEAD', 'Trưởng nhóm', 'Trưởng nhóm điều phối nhân sự nhóm và phê duyệt cấp 1 trong phòng ban.', true),
    ('MANAGER', 'Trưởng phòng', 'Trưởng phòng quản lý nhân sự phòng ban và phê duyệt cấp phòng.', true),
    ('VICE_DIRECTOR', 'Phó giám đốc', 'Phó giám đốc phụ trách khối nghiệp vụ và phê duyệt cấp Ban điều hành.', true),
    ('DIRECTOR', 'Giám đốc', 'Giám đốc điều hành toàn công ty và phê duyệt cấp cao nhất.', true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_system = EXCLUDED.is_system;

-- 2. Clear UI module permissions on internal workflow-step roles so bool_or()
--    in eas.get_effective_user_permissions() is driven strictly by the employee's
--    Chức vụ (Position) + per-user overrides.
INSERT INTO eas.role_module_permission (role_code, module_code, can_view, can_create, can_update, can_delete, updated_at)
SELECT r.code, m.code, false, false, false, false, now()
FROM eas.role r
CROSS JOIN eas.modules m
WHERE r.code IN ('REQUESTER', 'ACCEPTOR', 'EXECUTOR', 'APPROVER')
ON CONFLICT (role_code, module_code) DO UPDATE SET
    can_view = false,
    can_create = false,
    can_update = false,
    can_delete = false,
    updated_at = now();

-- 3. Seed default 9-module RBAC matrix for the 5 Positions
--    (4 system modules remain hard-locked false for all employee positions)
INSERT INTO eas.role_module_permission (role_code, module_code, can_view, can_create, can_update, can_delete, updated_at)
VALUES
    -- Nhân viên (STAFF)
    ('STAFF', 'dashboard',          true,  false, false, false, now()),
    ('STAFF', 'requests_workflows', true,  true,  false, false, now()),
    ('STAFF', 'org_chart',          true,  false, false, false, now()),
    ('STAFF', 'users',              false, false, false, false, now()),
    ('STAFF', 'permissions',        false, false, false, false, now()),
    ('STAFF', 'regulations',        true,  false, false, false, now()),
    ('STAFF', 'ai_engine',          false, false, false, false, now()),
    ('STAFF', 'api_management',     false, false, false, false, now()),
    ('STAFF', 'system_versions',    false, false, false, false, now()),

    -- Trưởng nhóm (TEAM_LEAD)
    ('TEAM_LEAD', 'dashboard',          true,  false, false, false, now()),
    ('TEAM_LEAD', 'requests_workflows', true,  true,  true,  false, now()),
    ('TEAM_LEAD', 'org_chart',          true,  false, false, false, now()),
    ('TEAM_LEAD', 'users',              true,  false, false, false, now()),
    ('TEAM_LEAD', 'permissions',        false, false, false, false, now()),
    ('TEAM_LEAD', 'regulations',        true,  false, false, false, now()),
    ('TEAM_LEAD', 'ai_engine',          false, false, false, false, now()),
    ('TEAM_LEAD', 'api_management',     false, false, false, false, now()),
    ('TEAM_LEAD', 'system_versions',    false, false, false, false, now()),

    -- Trưởng phòng (MANAGER)
    ('MANAGER', 'dashboard',          true,  false, false, false, now()),
    ('MANAGER', 'requests_workflows', true,  true,  true,  false, now()),
    ('MANAGER', 'org_chart',          true,  false, false, false, now()),
    ('MANAGER', 'users',              true,  false, true,  false, now()),
    ('MANAGER', 'permissions',        false, false, false, false, now()),
    ('MANAGER', 'regulations',        true,  false, false, false, now()),
    ('MANAGER', 'ai_engine',          false, false, false, false, now()),
    ('MANAGER', 'api_management',     false, false, false, false, now()),
    ('MANAGER', 'system_versions',    false, false, false, false, now()),

    -- Phó giám đốc (VICE_DIRECTOR)
    ('VICE_DIRECTOR', 'dashboard',          true,  false, false, false, now()),
    ('VICE_DIRECTOR', 'requests_workflows', true,  true,  true,  true,  now()),
    ('VICE_DIRECTOR', 'org_chart',          true,  false, false, false, now()),
    ('VICE_DIRECTOR', 'users',              true,  true,  true,  false, now()),
    ('VICE_DIRECTOR', 'permissions',        false, false, false, false, now()),
    ('VICE_DIRECTOR', 'regulations',        true,  false, true,  false, now()),
    ('VICE_DIRECTOR', 'ai_engine',          false, false, false, false, now()),
    ('VICE_DIRECTOR', 'api_management',     false, false, false, false, now()),
    ('VICE_DIRECTOR', 'system_versions',    false, false, false, false, now()),

    -- Giám đốc (DIRECTOR)
    ('DIRECTOR', 'dashboard',          true,  false, false, false, now()),
    ('DIRECTOR', 'requests_workflows', true,  true,  true,  true,  now()),
    ('DIRECTOR', 'org_chart',          true,  false, true,  false, now()),
    ('DIRECTOR', 'users',              true,  true,  true,  true,  now()),
    ('DIRECTOR', 'permissions',        false, false, false, false, now()),
    ('DIRECTOR', 'regulations',        true,  true,  true,  true,  now()),
    ('DIRECTOR', 'ai_engine',          false, false, false, false, now()),
    ('DIRECTOR', 'api_management',     false, false, false, false, now()),
    ('DIRECTOR', 'system_versions',    false, false, false, false, now())
ON CONFLICT (role_code, module_code) DO UPDATE SET
    can_view = EXCLUDED.can_view,
    can_create = EXCLUDED.can_create,
    can_update = EXCLUDED.can_update,
    can_delete = EXCLUDED.can_delete,
    updated_at = now();

-- 4. Assign each non-system EMPLOYEE account their exact Position based on org hierarchy
WITH computed_positions AS (
    SELECT
        u.id AS user_id,
        CASE
            WHEN d.code = 'BOD' AND u.manager_id IS NULL THEN 'DIRECTOR'
            WHEN d.code = 'BOD' AND u.manager_id IS NOT NULL THEN 'VICE_DIRECTOR'
            WHEN COALESCE(d.code, '') <> 'BOD'
                 AND (u.manager_id IS NULL OR mgr.department_id IS DISTINCT FROM u.department_id)
                 THEN 'MANAGER'
            WHEN COALESCE(d.code, '') <> 'BOD'
                 AND EXISTS (SELECT 1 FROM eas.app_user sub WHERE sub.manager_id = u.id)
                 THEN 'TEAM_LEAD'
            ELSE 'STAFF'
        END AS target_position
    FROM eas.app_user u
    LEFT JOIN eas.department d ON d.id = u.department_id
    LEFT JOIN eas.app_user mgr ON mgr.id = u.manager_id
    WHERE COALESCE(u.account_type, 'EMPLOYEE') = 'EMPLOYEE'
      AND u.email <> 'ai.system@eas.com'
      AND u.id <> '00000000-0000-0000-0000-000000000001'::uuid
),
revoked_mismatched AS (
    UPDATE eas.role_membership m
    SET revoked_at = statement_timestamp()
    FROM computed_positions cp
    WHERE m.user_id = cp.user_id
      AND m.role IN ('STAFF', 'TEAM_LEAD', 'MANAGER', 'VICE_DIRECTOR', 'DIRECTOR')
      AND m.role <> cp.target_position
      AND m.revoked_at IS NULL
    RETURNING m.id
)
INSERT INTO eas.role_membership (id, user_id, role, scope_kind, department_id, type_scope, type_id, valid_from)
SELECT
    gen_random_uuid(),
    cp.user_id,
    cp.target_position,
    'GLOBAL',
    NULL,
    'ALL',
    NULL,
    statement_timestamp()
FROM computed_positions cp
WHERE NOT EXISTS (
    SELECT 1
    FROM eas.role_membership m
    WHERE m.user_id = cp.user_id
      AND m.role = cp.target_position
      AND m.revoked_at IS NULL
      AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
);

UPDATE eas.security_epoch
SET version = version + 1, updated_at = statement_timestamp()
WHERE id = 1;

COMMIT;
