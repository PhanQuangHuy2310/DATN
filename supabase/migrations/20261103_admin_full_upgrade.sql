-- ============================================================================
-- SUPABASE SQL MIGRATION: FULL ADMIN & CLIENT SYSTEM (FIXED 100% FK & TRIGGERS)
-- Schema: eas (Enterprise Automation System)
-- ============================================================================

BEGIN;

-- 0. KHỞI TẠO SCHEMA & EXTENSION
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE SCHEMA IF NOT EXISTS eas;
SET search_path TO eas, public;

-- ============================================================================
-- 1. DỌN DẸP CÁC TRIGGER LỖI DO MODEL 3.8 TẠO RA TRƯỚC ĐÓ (NẾU CÓ)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'eas' AND table_name = 'company_regulations') THEN
        DROP TRIGGER IF EXISTS trg_handle_regulation_versioning ON eas.company_regulations;
        DROP TRIGGER IF EXISTS trg_regulation_versioning ON eas.company_regulations;
        DROP TRIGGER IF EXISTS handle_regulation_versioning ON eas.company_regulations;
        DROP TRIGGER IF EXISTS trg_before_regulation_versioning ON eas.company_regulations;
        DROP TRIGGER IF EXISTS trg_after_regulation_versioning ON eas.company_regulations;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'eas' AND table_name = 'request_templates') THEN
        DROP TRIGGER IF EXISTS trg_sync_template_workflow ON eas.request_templates;
        DROP TRIGGER IF EXISTS trg_after_template_workflow_log ON eas.request_templates;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'eas' AND table_name = 'workflow_categories') THEN
        DROP TRIGGER IF EXISTS trg_propagate_category_workflow ON eas.workflow_categories;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'eas' AND table_name = 'mock_apis') THEN
        DROP TRIGGER IF EXISTS trg_after_mock_api_toggle ON eas.mock_apis;
    END IF;
END $$;

DROP FUNCTION IF EXISTS eas.handle_regulation_versioning() CASCADE;

-- ============================================================================
-- 2. BẢNG PHÒNG BAN & SƠ ĐỒ CÔNG TY (departments)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eas.departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    parent_id UUID REFERENCES eas.departments(id) ON DELETE SET NULL,
    manager_name TEXT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 3. BẢNG VAI TRÒ & CHỨC NĂNG PHÂN QUYỀN RBAC (roles, modules, permissions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eas.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eas.modules (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    route_path TEXT NOT NULL,
    icon_name TEXT NOT NULL DEFAULT 'LayoutGrid',
    sort_order INT NOT NULL DEFAULT 0,
    target_app TEXT NOT NULL DEFAULT 'BOTH' CHECK (target_app IN ('ADMIN', 'CLIENT', 'BOTH')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eas.role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES eas.roles(id) ON DELETE CASCADE,
    module_code TEXT NOT NULL REFERENCES eas.modules(code) ON DELETE CASCADE,
    can_view BOOLEAN NOT NULL DEFAULT false,
    can_create BOOLEAN NOT NULL DEFAULT false,
    can_update BOOLEAN NOT NULL DEFAULT false,
    can_delete BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (role_id, module_code)
);

-- ============================================================================
-- 4. BẢNG NGƯỜI DÙNG & ĐƠN NGHỈ / CÔNG TÁC (users, user_permissions, leaves)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eas.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_code TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role_id UUID REFERENCES eas.roles(id) ON DELETE SET NULL,
    job_title TEXT NOT NULL DEFAULT 'Nhân viên',
    department_id UUID REFERENCES eas.departments(id) ON DELETE SET NULL,
    avatar_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Quyền cấp riêng cho từng User độc lập (Ghi đè lên quyền chung của Role)
CREATE TABLE IF NOT EXISTS eas.user_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES eas.users(id) ON DELETE CASCADE,
    module_code TEXT NOT NULL REFERENCES eas.modules(code) ON DELETE CASCADE,
    can_view BOOLEAN NOT NULL DEFAULT false,
    can_create BOOLEAN NOT NULL DEFAULT false,
    can_update BOOLEAN NOT NULL DEFAULT false,
    can_delete BOOLEAN NOT NULL DEFAULT false,
    granted_by TEXT DEFAULT 'Admin',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, module_code)
);

-- Bảng lưu đăng ký Nghỉ có lương, Nghỉ không lương, Đi muộn, Về sớm, Công tác
CREATE TABLE IF NOT EXISTS eas.user_leave_and_trips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES eas.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('PAID_LEAVE', 'UNPAID_LEAVE', 'LATE_IN', 'EARLY_OUT', 'BUSINESS_TRIP')),
    title TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    approval_status TEXT NOT NULL DEFAULT 'APPROVED' CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    approved_by TEXT DEFAULT 'Ban Giám Đốc',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 5. BẢNG QUẢN LÝ MOCK API (mock_apis)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eas.mock_apis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_code TEXT UNIQUE NOT NULL,
    api_name TEXT NOT NULL,
    endpoint_path TEXT NOT NULL,
    http_method TEXT NOT NULL DEFAULT 'GET',
    source_system TEXT NOT NULL,
    domain_key TEXT NOT NULL,
    data_provided TEXT NOT NULL,
    mock_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    updated_by TEXT DEFAULT 'System Admin',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 6. BẢNG PHÂN LOẠI QUY TRÌNH LỚN (A, B, C), MẪU YÊU CẦU & YÊU CẦU THỰC TẾ
-- ============================================================================
CREATE TABLE IF NOT EXISTS eas.workflow_categories (
    category_code TEXT PRIMARY KEY CHECK (category_code IN ('A', 'B', 'C')),
    name TEXT NOT NULL,
    description TEXT,
    sla_hours INT NOT NULL DEFAULT 24,
    workflow_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eas.request_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    request_type TEXT NOT NULL,
    category_code TEXT NOT NULL REFERENCES eas.workflow_categories(category_code) ON UPDATE CASCADE,
    automation_weight INT NOT NULL DEFAULT 50 CHECK (automation_weight BETWEEN 0 AND 100),
    form_schema JSONB NOT NULL DEFAULT '[]'::jsonb,
    workflow_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    linked_api_id UUID REFERENCES eas.mock_apis(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eas.requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    request_type TEXT NOT NULL,
    template_id UUID REFERENCES eas.request_templates(id) ON DELETE SET NULL,
    category_code TEXT NOT NULL REFERENCES eas.workflow_categories(category_code),
    department_id UUID REFERENCES eas.departments(id) ON DELETE SET NULL,
    -- 5 vai trò tương ứng 5 giai đoạn để thống kê chi tiết theo từng nhân sự
    requester_id UUID REFERENCES eas.users(id) ON DELETE SET NULL,   -- Giai đoạn 1: Yêu cầu
    approver_id UUID REFERENCES eas.users(id) ON DELETE SET NULL,    -- Giai đoạn 2: Phê duyệt
    executor_id UUID REFERENCES eas.users(id) ON DELETE SET NULL,    -- Giai đoạn 3: Thực hiện
    evaluator_id UUID REFERENCES eas.users(id) ON DELETE SET NULL,   -- Giai đoạn 4: Nghiệm thu
    completer_id UUID REFERENCES eas.users(id) ON DELETE SET NULL,   -- Giai đoạn 5: Hoàn thành
    current_stage TEXT NOT NULL DEFAULT 'YEU_CAU' CHECK (current_stage IN ('YEU_CAU', 'PHE_DUYET', 'THUC_HIEN', 'NGHIEM_THU', 'HOAN_THANH')),
    final_status TEXT NOT NULL DEFAULT 'PROCESSING' CHECK (final_status IN ('PROCESSING', 'APPROVED', 'REJECTED')),
    processing_duration_minutes INT NOT NULL DEFAULT 45,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 7. BẢNG QUY ĐỊNH CÔNG TY & LỊCH SỬ PHIÊN BẢN QUY ĐỊNH (ĐÃ FIX KHÓA NGOẠI)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eas.company_regulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Quy định chung',
    content TEXT NOT NULL,
    version_string TEXT NOT NULL DEFAULT '1.0',
    major_version INT NOT NULL DEFAULT 1,
    minor_version INT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    updated_by TEXT DEFAULT 'Admin',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eas.regulation_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    regulation_id UUID,
    version_string TEXT NOT NULL,
    major_version INT NOT NULL,
    minor_version INT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('CREATE', 'UPDATE_MINOR', 'DELETE_MAJOR')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    change_summary TEXT,
    created_by TEXT DEFAULT 'Admin',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Đảm bảo khóa ngoại của regulation_versions cho phép NULL và ON DELETE SET NULL
-- để khi xóa quy định không bao giờ gây lỗi 23503
ALTER TABLE eas.regulation_versions ALTER COLUMN regulation_id DROP NOT NULL;
ALTER TABLE eas.regulation_versions DROP CONSTRAINT IF EXISTS regulation_versions_regulation_id_fkey;
ALTER TABLE eas.regulation_versions
    ADD CONSTRAINT regulation_versions_regulation_id_fkey
    FOREIGN KEY (regulation_id) REFERENCES eas.company_regulations(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

-- ============================================================================
-- 8. BẢNG TRẠNG THÁI AI & PHIÊN BẢN HỆ THỐNG (ai_system_state, changelog)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eas.ai_system_state (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    provider_name TEXT NOT NULL DEFAULT 'Google Gemini + Scikit-Learn Hybrid',
    model_name TEXT NOT NULL DEFAULT 'gemini-2.5-flash & nlp_risk_pipeline_v2',
    active_regulation_version TEXT NOT NULL DEFAULT '1.0',
    target_regulation_version TEXT NOT NULL DEFAULT '1.0',
    global_major_version INT NOT NULL DEFAULT 1,
    global_minor_version INT NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (sync_status IN ('IDLE', 'SYNCING', 'LEARNING', 'APPLYING', 'COMPLETED', 'ERROR')),
    current_step_index INT NOT NULL DEFAULT 4 CHECK (current_step_index BETWEEN 1 AND 4),
    current_step_label TEXT NOT NULL DEFAULT 'Đã học xong và áp dụng quy định mới',
    progress_percent INT NOT NULL DEFAULT 100 CHECK (progress_percent BETWEEN 0 AND 100),
    client_maintenance_lock BOOLEAN NOT NULL DEFAULT false,
    maintenance_message TEXT NOT NULL DEFAULT 'Hệ thống AI đang cập nhật quy định mới. Vui lòng đăng nhập lại sau ít phút.',
    steps_detail JSONB NOT NULL DEFAULT '[
        {"step": 1, "code": "SYNCING", "label": "Tiếp nhận quy định mới từ Admin", "status": "DONE"},
        {"step": 2, "code": "LEARNING", "label": "AI phân tích ngữ nghĩa & Huấn luyện lại Vector", "status": "DONE"},
        {"step": 3, "code": "APPLYING", "label": "Áp dụng bộ quy tắc mới vào luồng phê duyệt", "status": "DONE"},
        {"step": 4, "code": "COMPLETED", "label": "Hoàn tất & Mở khóa Web Client", "status": "DONE"}
    ]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eas.system_versions_changelog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_version TEXT NOT NULL,
    change_type TEXT NOT NULL CHECK (change_type IN ('REGULATION', 'WORKFLOW', 'TEMPLATE', 'PERMISSION', 'AI_CONFIG', 'API_STATUS', 'SYSTEM')),
    change_scope TEXT NOT NULL DEFAULT 'MINOR' CHECK (change_scope IN ('MAJOR', 'MINOR', 'PATCH')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    old_value JSONB DEFAULT '{}'::jsonb,
    new_value JSONB DEFAULT '{}'::jsonb,
    changed_by TEXT DEFAULT 'Admin',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 9. CÁC HÀM NGHIỆP VỤ (FUNCTIONS & VIEWS) PHỤC VỤ UI ADMIN & CLIENT
-- ============================================================================

-- 9.1. Hàm tính trạng thái làm việc của nhân viên (08:00 - 17:30, Thứ 2 - Thứ 6)
CREATE OR REPLACE FUNCTION eas.get_user_working_status(
    p_user_id UUID,
    p_check_time TIMESTAMPTZ DEFAULT now()
)
RETURNS TABLE (
    status_code TEXT,
    status_label TEXT,
    detail_reason TEXT
)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_leave RECORD;
    v_vn_time TIMESTAMP;
    v_dow INT;
    v_time TIME;
BEGIN
    -- 1. Kiểm tra xem nhân viên có đơn Công tác hoặc Nghỉ phép/Đi muộn/Về sớm ĐÃ DUYỆT trùng thời gian không
    SELECT type, title INTO v_leave
    FROM eas.user_leave_and_trips
    WHERE user_id = p_user_id
      AND approval_status = 'APPROVED'
      AND p_check_time BETWEEN start_time AND end_time
    ORDER BY
      CASE WHEN type = 'BUSINESS_TRIP' THEN 1 ELSE 2 END,
      created_at DESC
    LIMIT 1;

    IF FOUND THEN
        IF v_leave.type = 'BUSINESS_TRIP' THEN
            RETURN QUERY SELECT 'CONG_TAC'::TEXT, 'Công tác'::TEXT, v_leave.title::TEXT;
            RETURN;
        ELSE
            RETURN QUERY SELECT 'NGHI_LAM'::TEXT, 'Nghỉ làm'::TEXT, v_leave.title::TEXT;
            RETURN;
        END IF;
    END IF;

    -- 2. Nếu không có đơn nghỉ/công tác đã duyệt -> Mặc định đi làm (Khung chuẩn: 08:00 - 17:30, T2 - T6)
    v_vn_time := p_check_time AT TIME ZONE 'Asia/Ho_Chi_Minh';
    v_dow := EXTRACT(ISODOW FROM v_vn_time); -- 1 = Thứ 2 ... 5 = Thứ 6, 6 = Thứ 7, 7 = CN
    v_time := v_vn_time::TIME;

    IF v_dow BETWEEN 1 AND 5 AND v_time BETWEEN '08:00:00'::TIME AND '17:30:00'::TIME THEN
        RETURN QUERY SELECT 'DANG_LAM'::TEXT, 'Đang làm'::TEXT, 'Trong giờ hành chính (08:00 - 17:30, T2-T6)'::TEXT;
    ELSIF v_dow IN (6, 7) THEN
        RETURN QUERY SELECT 'DANG_LAM'::TEXT, 'Đang làm'::TEXT, 'Mặc định đi làm (Hôm nay cuối tuần T7/CN)'::TEXT;
    ELSE
        RETURN QUERY SELECT 'DANG_LAM'::TEXT, 'Đang làm'::TEXT, 'Mặc định đi làm (Ngoài khung 08:00 - 17:30)'::TEXT;
    END IF;
END;
$$;

-- 9.2. View tổng hợp Người dùng kèm Trạng thái & Tổng số yêu cầu ở 5 giai đoạn
CREATE OR REPLACE VIEW eas.v_users_management AS
SELECT
    u.id,
    u.employee_code,
    u.full_name,
    u.email,
    u.job_title,
    u.role_id,
    r.code AS role_code,
    r.name AS role_name,
    u.department_id,
    d.name AS department_name,
    u.avatar_url,
    u.is_active,
    ws.status_code AS working_status_code,
    ws.status_label AS working_status_label,
    ws.detail_reason AS working_status_detail,
    COALESCE(req_stats.yeu_cau_count, 0) AS stage_yeu_cau_count,
    COALESCE(req_stats.phe_duyet_count, 0) AS stage_phe_duyet_count,
    COALESCE(req_stats.thuc_hien_count, 0) AS stage_thuc_hien_count,
    COALESCE(req_stats.nghiem_thu_count, 0) AS stage_nghiem_thu_count,
    COALESCE(req_stats.hoan_thanh_count, 0) AS stage_hoan_thanh_count,
    COALESCE(req_stats.total_requests, 0) AS total_involved_requests
FROM eas.users u
LEFT JOIN eas.roles r ON r.id = u.role_id
LEFT JOIN eas.departments d ON d.id = u.department_id
LEFT JOIN LATERAL eas.get_user_working_status(u.id, now()) ws ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE current_stage = 'YEU_CAU') AS yeu_cau_count,
        COUNT(*) FILTER (WHERE current_stage = 'PHE_DUYET') AS phe_duyet_count,
        COUNT(*) FILTER (WHERE current_stage = 'THUC_HIEN') AS thuc_hien_count,
        COUNT(*) FILTER (WHERE current_stage = 'NGHIEM_THU') AS nghiem_thu_count,
        COUNT(*) FILTER (WHERE current_stage = 'HOAN_THANH') AS hoan_thanh_count,
        COUNT(*) AS total_requests
    FROM eas.requests req
    WHERE u.id IN (req.requester_id, req.approver_id, req.executor_id, req.evaluator_id, req.completer_id)
) req_stats ON true;

-- 9.3. Hàm lấy bảng chi tiết các yêu cầu của 1 User khi bấm vào con số Tổng yêu cầu
CREATE OR REPLACE FUNCTION eas.get_user_requests_detail(p_user_id UUID)
RETURNS TABLE (
    request_id UUID,
    request_code TEXT,
    title TEXT,
    content TEXT,
    request_type TEXT,
    category_code TEXT,
    current_stage TEXT,
    current_stage_label TEXT,
    final_status TEXT,
    user_role_in_request TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE sql STABLE AS $$
    SELECT
        r.id AS request_id,
        r.request_code,
        r.title,
        r.content,
        r.request_type,
        r.category_code,
        r.current_stage,
        CASE r.current_stage
            WHEN 'YEU_CAU' THEN '1. Yêu cầu'
            WHEN 'PHE_DUYET' THEN '2. Phê duyệt'
            WHEN 'THUC_HIEN' THEN '3. Thực hiện'
            WHEN 'NGHIEM_THU' THEN '4. Nghiệm thu'
            WHEN 'HOAN_THANH' THEN '5. Hoàn thành'
        END AS current_stage_label,
        r.final_status,
        ARRAY_TO_STRING(ARRAY_REMOVE(ARRAY[
            CASE WHEN r.requester_id = p_user_id THEN 'Người yêu cầu' END,
            CASE WHEN r.approver_id = p_user_id THEN 'Người phê duyệt' END,
            CASE WHEN r.executor_id = p_user_id THEN 'Người thực hiện' END,
            CASE WHEN r.evaluator_id = p_user_id THEN 'Người nghiệm thu' END,
            CASE WHEN r.completer_id = p_user_id THEN 'Người hoàn thành' END
        ], NULL), ', ') AS user_role_in_request,
        r.created_at
    FROM eas.requests r
    WHERE p_user_id IN (r.requester_id, r.approver_id, r.executor_id, r.evaluator_id, r.completer_id)
    ORDER BY r.created_at DESC;
$$;

-- 9.4. Hàm lấy quyền thực tế của User (Gộp quyền Role + Quyền cấp riêng User)
-- Điều khiển trực tiếp ẩn/hiện Sidebar và các nút Thêm, Sửa, Xóa ngoài UI
CREATE OR REPLACE FUNCTION eas.get_effective_user_permissions(p_user_id UUID)
RETURNS TABLE (
    module_code TEXT,
    module_name TEXT,
    group_name TEXT,
    route_path TEXT,
    icon_name TEXT,
    target_app TEXT,
    can_view BOOLEAN,
    can_create BOOLEAN,
    can_update BOOLEAN,
    can_delete BOOLEAN,
    show_on_sidebar BOOLEAN,
    permission_source TEXT
)
LANGUAGE sql STABLE AS $$
    SELECT
        m.code AS module_code,
        m.name AS module_name,
        m.group_name,
        m.route_path,
        m.icon_name,
        m.target_app,
        COALESCE(up.can_view, rp.can_view, false) AS can_view,
        COALESCE(up.can_create, rp.can_create, false) AS can_create,
        COALESCE(up.can_update, rp.can_update, false) AS can_update,
        COALESCE(up.can_delete, rp.can_delete, false) AS can_delete,
        -- Nếu không có quyền thao tác/xem nào thì ẩn hoàn toàn khỏi Sidebar
        (
            COALESCE(up.can_view, rp.can_view, false) OR
            COALESCE(up.can_create, rp.can_create, false) OR
            COALESCE(up.can_update, rp.can_update, false) OR
            COALESCE(up.can_delete, rp.can_delete, false)
        ) AS show_on_sidebar,
        CASE
            WHEN up.id IS NOT NULL THEN 'USER_OVERRIDE'
            ELSE 'ROLE_DEFAULT'
        END AS permission_source
    FROM eas.modules m
    LEFT JOIN eas.users u ON u.id = p_user_id
    LEFT JOIN eas.role_permissions rp ON rp.role_id = u.role_id AND rp.module_code = m.code
    LEFT JOIN eas.user_permissions up ON up.user_id = u.id AND up.module_code = m.code
    ORDER BY m.sort_order ASC;
$$;

-- 9.5. View Mẫu yêu cầu kèm trạng thái Bật/Tắt của Mock API liên kết
CREATE OR REPLACE VIEW eas.v_request_templates_full AS
SELECT
    rt.id,
    rt.code,
    rt.name,
    rt.request_type,
    rt.category_code,
    wc.name AS category_name,
    wc.sla_hours,
    rt.automation_weight,
    rt.form_schema,
    rt.workflow_steps,
    rt.linked_api_id,
    ma.api_code,
    ma.api_name,
    ma.source_system AS api_source_system,
    COALESCE(ma.is_enabled, true) AS is_api_enabled,
    (rt.is_active AND COALESCE(ma.is_enabled, true)) AS can_use_template,
    CASE
        WHEN ma.id IS NOT NULL AND ma.is_enabled = false THEN
            'Yêu cầu này hiện không thể sử dụng do kết nối API của hệ thống "' || ma.source_system || '" (' || ma.api_name || ') đang bị tắt.'
        WHEN rt.is_active = false THEN
            'Mẫu yêu cầu này đang tạm ngưng hoạt động.'
        ELSE NULL
    END AS unavailable_notice,
    rt.is_active,
    rt.updated_at
FROM eas.request_templates rt
LEFT JOIN eas.workflow_categories wc ON wc.category_code = rt.category_code
LEFT JOIN eas.mock_apis ma ON ma.id = rt.linked_api_id;

-- 9.6. Hàm để AI Service (hoặc Admin) gọi khi AI đã học xong quy định mới -> Mở khóa Web Client
CREATE OR REPLACE FUNCTION eas.complete_ai_regulation_learning()
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE eas.ai_system_state
    SET active_regulation_version = target_regulation_version,
        sync_status = 'COMPLETED',
        current_step_index = 4,
        current_step_label = 'Đã học xong và áp dụng quy định mới (v' || target_regulation_version || ')',
        progress_percent = 100,
        client_maintenance_lock = false,
        steps_detail = '[
            {"step": 1, "code": "SYNCING", "label": "Tiếp nhận quy định mới từ Admin", "status": "DONE"},
            {"step": 2, "code": "LEARNING", "label": "AI phân tích ngữ nghĩa & Huấn luyện lại Vector", "status": "DONE"},
            {"step": 3, "code": "APPLYING", "label": "Áp dụng bộ quy tắc mới vào luồng phê duyệt", "status": "DONE"},
            {"step": 4, "code": "COMPLETED", "label": "Hoàn tất & Mở khóa Web Client", "status": "DONE"}
        ]'::jsonb,
        updated_at = now()
    WHERE id = 1;
END;
$$;

-- ============================================================================
-- 10. NẠP DỮ LIỆU MẪU (SEED DATA) TRƯỚC KHI BẬT TRIGGER
-- ============================================================================

-- 10.1. Seed Trạng thái AI ban đầu (Phiên bản 1.0)
INSERT INTO eas.ai_system_state (
    id, provider_name, model_name, active_regulation_version, target_regulation_version,
    global_major_version, global_minor_version, sync_status, current_step_index,
    current_step_label, progress_percent, client_maintenance_lock
) VALUES (
    1, 'Google Gemini + Scikit-Learn Hybrid', 'gemini-2.5-flash & nlp_risk_pipeline_v2',
    '1.0', '1.0', 1, 0, 'COMPLETED', 4, 'Đã học xong và áp dụng quy định v1.0', 100, false
) ON CONFLICT (id) DO NOTHING;

-- 10.2. Seed 9 Chức năng chuẩn (Modules)
INSERT INTO eas.modules (code, name, group_name, route_path, icon_name, sort_order, target_app) VALUES
    ('dashboard', 'Tổng quan', 'Giám sát', '/dashboard', 'LayoutDashboard', 1, 'BOTH'),
    ('requests_workflows', 'Yêu cầu & Quy trình', 'Luồng công việc', '/requests-workflows', 'GitPullRequest', 2, 'BOTH'),
    ('org_chart', 'Sơ đồ công ty', 'Tổ chức & Nhân sự', '/org-chart', 'Network', 3, 'BOTH'),
    ('users', 'Người dùng', 'Tổ chức & Nhân sự', '/users', 'Users', 4, 'ADMIN'),
    ('permissions', 'Phân quyền', 'Tổ chức & Nhân sự', '/permissions', 'ShieldCheck', 5, 'ADMIN'),
    ('regulations', 'Quy định', 'Tri thức & AI', '/regulations', 'BookOpenCheck', 6, 'BOTH'),
    ('ai_engine', 'Quản trị AI', 'Tri thức & AI', '/ai-engine', 'BrainCircuit', 7, 'ADMIN'),
    ('api_management', 'Quản lý API', 'Hệ thống & Tích hợp', '/api-management', 'Webhook', 8, 'ADMIN'),
    ('system_versions', 'Phiên bản hệ thống', 'Hệ thống & Tích hợp', '/system-versions', 'History', 9, 'ADMIN')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    group_name = EXCLUDED.group_name,
    sort_order = EXCLUDED.sort_order;

-- 10.3. Seed Vai trò (Roles)
INSERT INTO eas.roles (id, code, name, description, is_system) VALUES
    ('11111111-1111-4111-8111-111111111101', 'ADMIN', 'Quản trị viên hệ thống', 'Toàn quyền quản trị hệ thống', true),
    ('11111111-1111-4111-8111-111111111102', 'MANAGER', 'Trưởng phòng / Quản lý', 'Phê duyệt yêu cầu và quản lý phòng ban', true),
    ('11111111-1111-4111-8111-111111111103', 'HR_SPECIALIST', 'Chuyên viên Nhân sự (HR)', 'Quản lý nhân sự, quy định và chấm công', false),
    ('11111111-1111-4111-8111-111111111104', 'EMPLOYEE', 'Nhân viên chính thức', 'Tạo và theo dõi yêu cầu cá nhân trên Web Client', true)
ON CONFLICT (code) DO NOTHING;

-- 10.4. Seed Ma trận Phân quyền mặc định cho các Vai trò
INSERT INTO eas.role_permissions (role_id, module_code, can_view, can_create, can_update, can_delete)
SELECT '11111111-1111-4111-8111-111111111101', code, true, true, true, true FROM eas.modules
ON CONFLICT (role_id, module_code) DO NOTHING;

INSERT INTO eas.role_permissions (role_id, module_code, can_view, can_create, can_update, can_delete) VALUES
    ('11111111-1111-4111-8111-111111111102', 'dashboard', true, false, false, false),
    ('11111111-1111-4111-8111-111111111102', 'requests_workflows', true, true, true, false),
    ('11111111-1111-4111-8111-111111111102', 'org_chart', true, false, false, false),
    ('11111111-1111-4111-8111-111111111102', 'users', true, false, false, false),
    ('11111111-1111-4111-8111-111111111102', 'regulations', true, false, false, false),
    ('11111111-1111-4111-8111-111111111104', 'dashboard', true, false, false, false),
    ('11111111-1111-4111-8111-111111111104', 'requests_workflows', true, true, false, false),
    ('11111111-1111-4111-8111-111111111104', 'org_chart', true, false, false, false),
    ('11111111-1111-4111-8111-111111111104', 'regulations', true, false, false, false)
ON CONFLICT (role_id, module_code) DO NOTHING;

-- 10.5. Seed Phòng ban (Sơ đồ công ty)
INSERT INTO eas.departments (id, code, name, parent_id, manager_name, description) VALUES
    ('22222222-2222-4222-8222-222222222201', 'BOD', 'Ban Giám Đốc', NULL, 'Nguyễn Quốc Anh', 'Ban điều hành cấp cao toàn công ty'),
    ('22222222-2222-4222-8222-222222222202', 'DEPT_IT', 'Khối Công nghệ & AI (IT)', '22222222-2222-4222-8222-222222222201', 'Phan Quang Huy', 'Phát triển phần mềm, hạ tầng IT và AI Service'),
    ('22222222-2222-4222-8222-222222222203', 'DEPT_HR', 'Phòng Hành chính - Nhân sự', '22222222-2222-4222-8222-222222222201', 'Trần Thu Hà', 'Quản lý nhân sự, lương thưởng, quy định nội bộ'),
    ('22222222-2222-4222-8222-222222222204', 'DEPT_FIN', 'Phòng Tài chính - Kế toán', '22222222-2222-4222-8222-222222222201', 'Lê Minh Tuấn', 'Quản lý ngân sách, giải ngân và kiểm soát chi phí'),
    ('22222222-2222-4222-8222-222222222205', 'DEPT_SALES', 'Phòng Kinh doanh & CRM', '22222222-2222-4222-8222-222222222201', 'Vũ Hoàng Nam', 'Phát triển khách hàng doanh nghiệp và đối tác'),
    ('22222222-2222-4222-8222-222222222206', 'DEPT_OPS', 'Phòng Mua sắm & Vận hành', '22222222-2222-4222-8222-222222222201', 'Đặng Thị Mai', 'Quản lý tài sản, cơ sở vật chất và mua sắm')
ON CONFLICT (code) DO NOTHING;

-- 10.6. Seed Người dùng & Đơn nghỉ/Công tác (để hiển thị đủ 3 trạng thái: Đang làm, Nghỉ làm, Công tác)
INSERT INTO eas.users (id, employee_code, full_name, email, role_id, job_title, department_id) VALUES
    ('33333333-3333-4333-8333-333333333301', 'EMP001', 'Phan Quang Huy', 'huy.phan@company.vn', '11111111-1111-4111-8111-111111111101', 'Giám đốc Công nghệ (Admin)', '22222222-2222-4222-8222-222222222202'),
    ('33333333-3333-4333-8333-333333333302', 'EMP002', 'Trần Thu Hà', 'ha.tran@company.vn', '11111111-1111-4111-8111-111111111103', 'Trưởng phòng Nhân sự', '22222222-2222-4222-8222-222222222203'),
    ('33333333-3333-4333-8333-333333333303', 'EMP003', 'Lê Minh Tuấn', 'tuan.le@company.vn', '11111111-1111-4111-8111-111111111102', 'Trưởng phòng Tài chính', '22222222-2222-4222-8222-222222222204'),
    ('33333333-3333-4333-8333-333333333304', 'EMP004', 'Vũ Hoàng Nam', 'nam.vu@company.vn', '11111111-1111-4111-8111-111111111102', 'Trưởng phòng Kinh doanh', '22222222-2222-4222-8222-222222222205'),
    ('33333333-3333-4333-8333-333333333305', 'EMP005', 'Nguyễn Thị Lan Anh', 'lananh.nguyen@company.vn', '11111111-1111-4111-8111-111111111104', 'Chuyên viên Backend', '22222222-2222-4222-8222-222222222202'),
    ('33333333-3333-4333-8333-333333333306', 'EMP006', 'Phạm Gia Bảo', 'bao.pham@company.vn', '11111111-1111-4111-8111-111111111104', 'Chuyên viên Mua sắm', '22222222-2222-4222-8222-222222222206')
ON CONFLICT (employee_code) DO NOTHING;

INSERT INTO eas.user_leave_and_trips (id, user_id, type, title, start_time, end_time, approval_status) VALUES
    ('44444444-4444-4444-8444-444444444401', '33333333-3333-4333-8333-333333333304', 'BUSINESS_TRIP', 'Công tác gặp đối tác chiến lược tại TP.HCM (Đã duyệt)', now() - interval '2 days', now() + interval '5 days', 'APPROVED'),
    ('44444444-4444-4444-8444-444444444402', '33333333-3333-4333-8333-333333333305', 'PAID_LEAVE', 'Nghỉ phép có lương giải quyết việc gia đình (Đã duyệt)', now() - interval '1 day', now() + interval '2 days', 'APPROVED')
ON CONFLICT (id) DO NOTHING;

-- 10.7. Seed 8 Mock APIs chuẩn theo `ai_service/data/mock/`
INSERT INTO eas.mock_apis (id, api_code, api_name, endpoint_path, source_system, domain_key, data_provided, mock_payload, is_enabled) VALUES
    ('55555555-5555-4555-8555-555555555501', 'API_HR', 'HR & Attendance Service API', '/api/v1/mock/hr', 'Hệ thống Quản trị Nhân sự (HRM)', 'hr', 'Cung cấp quỹ phép năm, chấm công 08:00-17:30, hồ sơ lương và định biên nhân sự', '{"source": "mock_hr.json", "leave_balance_check": true, "working_hours": "08:00-17:30"}'::jsonb, true),
    ('55555555-5555-4555-8555-555555555502', 'API_FINANCE', 'Finance & Budget Control API', '/api/v1/mock/finance', 'Hệ thống Tài chính Kế toán (ERP Finance)', 'finance', 'Cung cấp hạn mức ngân sách phòng ban, lịch sử tạm ứng và hoàn ứng chi phí', '{"source": "mock_finance.json", "budget_available": true, "currency": "VND"}'::jsonb, true),
    ('55555555-5555-4555-8555-555555555503', 'API_IT', 'IT Helpdesk & Access Control API', '/api/v1/mock/it', 'Hệ thống Quản trị Hạ tầng IT (ITSM)', 'it', 'Cung cấp danh mục quyền truy cập phần mềm, license và trạng thái thiết bị IT', '{"source": "mock_it.json", "license_pool": "available"}'::jsonb, true),
    ('55555555-5555-4555-8555-555555555504', 'API_PROCUREMENT', 'Procurement & Vendor API', '/api/v1/mock/procurement', 'Hệ thống Mua sắm Tập trung (e-Procurement)', 'procurement', 'Cung cấp báo giá nhà cung cấp, danh mục vật tư và hợp đồng mua sắm', '{"source": "mock_procurement.json", "approved_vendors": 18}'::jsonb, true),
    ('55555555-5555-4555-8555-555555555505', 'API_TRAVEL', 'Business Travel & Booking API', '/api/v1/mock/travel', 'Hệ thống Quản lý Công tác & Vé máy bay', 'travel', 'Cung cấp định mức công tác phí, đặt vé máy bay và khách sạn đối tác', '{"source": "mock_travel.json", "per_diem_standard": 1500000}'::jsonb, true),
    ('55555555-5555-4555-8555-555555555506', 'API_ASSETS', 'Enterprise Asset Management API', '/api/v1/mock/assets', 'Hệ thống Quản lý Tài sản (EAM)', 'assets', 'Cung cấp tồn kho laptop, màn hình, thiết bị văn phòng và lịch sử bàn giao', '{"source": "mock_assets.json", "warehouse_status": "online"}'::jsonb, true),
    ('55555555-5555-4555-8555-555555555507', 'API_FACILITIES', 'Facilities & Meeting Room API', '/api/v1/mock/facilities', 'Hệ thống Quản lý Tòa nhà & Văn phòng', 'facilities', 'Cung cấp lịch phòng họp, xe đưa đón công ty và dịch vụ hậu cần văn phòng', '{"source": "mock_facilities.json", "rooms_available": 6}'::jsonb, true),
    ('55555555-5555-4555-8555-555555555508', 'API_CRM', 'CRM & Partner Discount API', '/api/v1/mock/crm', 'Hệ thống Quản trị Khách hàng (CRM)', 'crm', 'Cung cấp hạng khách hàng, lịch sử hợp đồng và chính sách chiết khấu bán hàng', '{"source": "mock_crm.json", "max_discount_percent": 15}'::jsonb, true)
ON CONFLICT (api_code) DO NOTHING;

-- 10.8. Seed 3 Phân loại Quy trình lớn (A, B, C)
INSERT INTO eas.workflow_categories (category_code, name, description, sla_hours, workflow_steps) VALUES
    ('A', 'Phân loại A - Tự động hóa / Rủi ro thấp', 'Áp dụng cho yêu cầu thông thường, AI kiểm tra quy định và phê duyệt nhanh trong 4 giờ', 4, '[
        {"step": 1, "stage": "YEU_CAU", "name": "Khởi tạo yêu cầu & Kiểm tra API", "actor": "Người yêu cầu"},
        {"step": 2, "stage": "PHE_DUYET", "name": "AI tự động đối chiếu Quy định & Trọng số", "actor": "AI Engine"},
        {"step": 3, "stage": "HOAN_THANH", "name": "Tự động xác nhận & Đóng yêu cầu", "actor": "Hệ thống"}
    ]'::jsonb),
    ('B', 'Phân loại B - Phê duyệt cấp Phòng ban / Trung bình', 'Cần Trưởng bộ phận phê duyệt và bộ phận chuyên môn thực hiện, nghiệm thu trong 24 giờ', 24, '[
        {"step": 1, "stage": "YEU_CAU", "name": "Gửi yêu cầu & AI chấm điểm rủi ro", "actor": "Người yêu cầu"},
        {"step": 2, "stage": "PHE_DUYET", "name": "Trưởng phòng trực tiếp phê duyệt", "actor": "Trưởng phòng"},
        {"step": 3, "stage": "THUC_HIEN", "name": "Bộ phận chuyên trách triển khai", "actor": "Chuyên viên thực hiện"},
        {"step": 4, "stage": "NGHIEM_THU", "name": "Người yêu cầu kiểm tra & Nghiệm thu", "actor": "Người yêu cầu"},
        {"step": 5, "stage": "HOAN_THANH", "name": "Lưu hồ sơ & Hoàn thành", "actor": "Hệ thống"}
    ]'::jsonb),
    ('C', 'Phân loại C - Phê duyệt Đa cấp & Ban Giám Đốc / Trọng yếu', 'Yêu cầu ngân sách lớn hoặc vượt ngưỡng rủi ro, cần Kế toán thẩm định và Ban Giám Đốc duyệt trong 48 giờ', 48, '[
        {"step": 1, "stage": "YEU_CAU", "name": "Lập tờ trình chi tiết & AI phân tích rủi ro", "actor": "Người yêu cầu"},
        {"step": 2, "stage": "PHE_DUYET", "name": "Trưởng phòng & Tài chính thẩm định + Ban Giám Đốc phê duyệt", "actor": "Ban Giám Đốc"},
        {"step": 3, "stage": "THUC_HIEN", "name": "Thực hiện giải ngân / Mua sắm / Triển khai", "actor": "Phòng Vận hành / Kế toán"},
        {"step": 4, "stage": "NGHIEM_THU", "name": "Hội đồng nghiệm thu bàn giao chứng từ", "actor": "Ban Nghiệm thu"},
        {"step": 5, "stage": "HOAN_THANH", "name": "Quyết toán & Đóng yêu cầu", "actor": "Hệ thống"}
    ]'::jsonb)
ON CONFLICT (category_code) DO UPDATE SET
    name = EXCLUDED.name,
    sla_hours = EXCLUDED.sla_hours,
    workflow_steps = EXCLUDED.workflow_steps;

-- 10.9. Seed Mẫu Yêu cầu (Request Templates)
INSERT INTO eas.request_templates (id, code, name, request_type, category_code, automation_weight, linked_api_id, form_schema, workflow_steps) VALUES
    (
        '66666666-6666-4666-8666-666666666601', 'TPL_LEAVE', 'Đơn đăng ký nghỉ phép / Đi muộn về sớm', 'Nhân sự (HR)', 'A', 85,
        '55555555-5555-4555-8555-555555555501',
        '[{"field": "leave_type", "label": "Loại đăng ký", "type": "select", "options": ["Nghỉ có lương", "Nghỉ không lương", "Đi muộn", "Về sớm"]}, {"field": "days", "label": "Số ngày/giờ", "type": "number"}, {"field": "reason", "label": "Lý do chi tiết", "type": "textarea"}]'::jsonb,
        (SELECT workflow_steps FROM eas.workflow_categories WHERE category_code = 'A')
    ),
    (
        '66666666-6666-4666-8666-666666666602', 'TPL_IT_EQUIP', 'Yêu cầu cấp phát thiết bị IT & Phần mềm', 'Hạ tầng IT', 'B', 65,
        '55555555-5555-4555-8555-555555555503',
        '[{"field": "device_type", "label": "Thiết bị / Phần mềm", "type": "text"}, {"field": "estimated_cost", "label": "Chi phí dự kiến (VNĐ)", "type": "number"}, {"field": "justification", "label": "Mục đích sử dụng", "type": "textarea"}]'::jsonb,
        (SELECT workflow_steps FROM eas.workflow_categories WHERE category_code = 'B')
    ),
    (
        '66666666-6666-4666-8666-666666666603', 'TPL_BUSINESS_TRIP', 'Đăng ký đi công tác & Tạm ứng công tác phí', 'Công tác (Travel)', 'B', 70,
        '55555555-5555-4555-8555-555555555505',
        '[{"field": "destination", "label": "Địa điểm công tác", "type": "text"}, {"field": "budget", "label": "Kinh phí tạm ứng", "type": "number"}, {"field": "schedule", "label": "Lịch trình làm việc", "type": "textarea"}]'::jsonb,
        (SELECT workflow_steps FROM eas.workflow_categories WHERE category_code = 'B')
    ),
    (
        '66666666-6666-4666-8666-666666666604', 'TPL_PROCUREMENT', 'Tờ trình mua sắm tài sản & Giải ngân ngân sách lớn', 'Tài chính & Mua sắm', 'C', 30,
        '55555555-5555-4555-8555-555555555502',
        '[{"field": "item_name", "label": "Hạng mục đầu tư/mua sắm", "type": "text"}, {"field": "total_amount", "label": "Tổng giá trị thanh toán (VNĐ)", "type": "number"}, {"field": "vendor", "label": "Nhà cung cấp đề xuất", "type": "text"}]'::jsonb,
        (SELECT workflow_steps FROM eas.workflow_categories WHERE category_code = 'C')
    )
ON CONFLICT (code) DO NOTHING;

-- 10.10. Seed Yêu cầu thực tế ở đủ 5 giai đoạn để test Dashboard & Bảng chi tiết User
INSERT INTO eas.requests (
    id, request_code, title, content, request_type, template_id, category_code, department_id,
    requester_id, approver_id, executor_id, evaluator_id, completer_id,
    current_stage, final_status, processing_duration_minutes, created_at
) VALUES
    ('77777777-7777-4777-8777-777777777701', 'REQ-2026-001', 'Xin nghỉ phép có lương 2 ngày', 'Nghỉ phép giải quyết việc gia đình đã bàn giao công việc', 'Nhân sự (HR)', '66666666-6666-4666-8666-666666666601', 'A', '22222222-2222-4222-8222-222222222202', '33333333-3333-4333-8333-333333333305', '33333333-3333-4333-8333-333333333301', '33333333-3333-4333-8333-333333333302', '33333333-3333-4333-8333-333333333305', '33333333-3333-4333-8333-333333333302', 'HOAN_THANH', 'APPROVED', 15, now() - interval '6 days'),
    ('77777777-7777-4777-8777-777777777702', 'REQ-2026-002', 'Cấp màn hình đồ họa 4K cho nhóm UI/UX', 'Phục vụ thiết kế hệ thống Web Admin và Web Client đồng bộ', 'Hạ tầng IT', '66666666-6666-4666-8666-666666666602', 'B', '22222222-2222-4222-8222-222222222202', '33333333-3333-4333-8333-333333333305', '33333333-3333-4333-8333-333333333301', '33333333-3333-4333-8333-333333333306', '33333333-3333-4333-8333-333333333305', NULL, 'NGHIEM_THU', 'PROCESSING', 320, now() - interval '3 days'),
    ('77777777-7777-4777-8777-777777777703', 'REQ-2026-003', 'Đăng ký công tác TP.HCM ký hợp đồng đối tác', 'Công tác 5 ngày gặp gỡ khách hàng doanh nghiệp', 'Công tác (Travel)', '66666666-6666-4666-8666-666666666603', 'B', '22222222-2222-4222-8222-222222222205', '33333333-3333-4333-8333-333333333304', '33333333-3333-4333-8333-333333333301', '33333333-3333-4333-8333-333333333303', '33333333-3333-4333-8333-333333333304', '33333333-3333-4333-8333-333333333303', 'HOAN_THANH', 'APPROVED', 210, now() - interval '2 days'),
    ('77777777-7777-4777-8777-777777777704', 'REQ-2026-004', 'Mua sắm cụm máy chủ GPU huấn luyện AI nội bộ', 'Đầu tư 2 máy chủ GPU phục vụ mô hình NLP phân loại yêu cầu', 'Tài chính & Mua sắm', '66666666-6666-4666-8666-666666666604', 'C', '22222222-2222-4222-8222-222222222202', '33333333-3333-4333-8333-333333333301', '33333333-3333-4333-8333-333333333303', '33333333-3333-4333-8333-333333333306', NULL, NULL, 'THUC_HIEN', 'PROCESSING', 980, now() - interval '1 day'),
    ('77777777-7777-4777-8777-777777777705', 'REQ-2026-005', 'Tạm ứng chi phí tổ chức sự kiện vượt định mức', 'Chi phí vượt 200% ngân sách quý nên bị từ chối tự động', 'Tài chính & Mua sắm', '66666666-6666-4666-8666-666666666604', 'C', '22222222-2222-4222-8222-222222222205', '33333333-3333-4333-8333-333333333304', '33333333-3333-4333-8333-333333333303', NULL, NULL, NULL, 'PHE_DUYET', 'REJECTED', 60, now() - interval '12 hours'),
    ('77777777-7777-4777-8777-777777777706', 'REQ-2026-006', 'Xin cấp quyền truy cập Database Staging', 'Phục vụ kiểm thử tích hợp dữ liệu', 'Hạ tầng IT', '66666666-6666-4666-8666-666666666602', 'B', '22222222-2222-4222-8222-222222222202', '33333333-3333-4333-8333-333333333305', '33333333-3333-4333-8333-333333333301', NULL, NULL, NULL, 'YEU_CAU', 'PROCESSING', 10, now() - interval '1 hour')
ON CONFLICT (request_code) DO NOTHING;

-- 10.11. Seed Quy định công ty & Lịch sử phiên bản ban đầu (Nạp an toàn trước khi gắn Trigger)
INSERT INTO eas.company_regulations (id, code, title, category, content, version_string, major_version, minor_version, updated_by) VALUES
    ('5d08535a-ee42-4513-aa32-fc59b5ca02c6', 'REG-001', 'Quy định thời gian làm việc, nghỉ phép và công tác', 'Nhân sự & Chấm công', 'Thời gian làm việc tiêu chuẩn của công ty là từ 08:00 sáng đến 17:30 chiều, từ Thứ 2 đến Thứ 6 (nghỉ Thứ 7, Chủ nhật). Nhân viên không có đơn xin nghỉ phép, đi muộn/về sớm hoặc đăng ký công tác đã phê duyệt thì mặc định ở trạng thái Đang làm việc.', '1.0', 1, 0, 'System Admin'),
    ('5d08535a-ee42-4513-aa32-fc59b5ca02c7', 'REG-002', 'Quy định phân loại và hạn mức phê duyệt yêu cầu A, B, C', 'Quy trình & Tài chính', 'Các yêu cầu thuộc Phân loại A được AI đối chiếu tự động theo trọng số. Phân loại B yêu cầu Trưởng bộ phận phê duyệt trong 24h. Phân loại C áp dụng cho ngân sách từ 50.000.000 VNĐ trở lên và bắt buộc qua Ban Giám Đốc phê duyệt.', '1.0', 1, 0, 'System Admin'),
    ('5d08535a-ee42-4513-aa32-fc59b5ca02c8', 'REG-003', 'Quy định bảo mật API và đồng bộ tri thức AI', 'Công nghệ & AI', 'Khi cập nhật quy định mới (bản nhỏ hoặc bản lớn), hệ thống tự động đẩy sang AI Service để huấn luyện lại và tạm khóa đăng nhập trên Web Client cho tới khi hoàn tất 100%.', '1.0', 1, 0, 'System Admin')
ON CONFLICT (code) DO NOTHING;

INSERT INTO eas.regulation_versions (id, regulation_id, version_string, major_version, minor_version, action_type, title, content, change_summary, created_by) VALUES
    ('88888888-8888-4888-8888-888888888801', '5d08535a-ee42-4513-aa32-fc59b5ca02c6', '1.0', 1, 0, 'CREATE', 'Quy định thời gian làm việc, nghỉ phép và công tác', 'Thời gian làm việc tiêu chuẩn của công ty là từ 08:00 sáng đến 17:30 chiều, từ Thứ 2 đến Thứ 6 (nghỉ Thứ 7, Chủ nhật).', 'Khởi tạo quy định gốc v1.0', 'System Admin'),
    ('88888888-8888-4888-8888-888888888802', '5d08535a-ee42-4513-aa32-fc59b5ca02c7', '1.0', 1, 0, 'CREATE', 'Quy định phân loại và hạn mức phê duyệt yêu cầu A, B, C', 'Phân loại A, B, C theo trọng số tự động và hạn mức ngân sách.', 'Khởi tạo quy định gốc v1.0', 'System Admin'),
    ('88888888-8888-4888-8888-888888888803', '5d08535a-ee42-4513-aa32-fc59b5ca02c8', '1.0', 1, 0, 'CREATE', 'Quy định bảo mật API và đồng bộ tri thức AI', 'Tự động đồng bộ quy định mới sang AI Service và kiểm soát truy cập Web Client.', 'Khởi tạo quy định gốc v1.0', 'System Admin')
ON CONFLICT (id) DO NOTHING;

INSERT INTO eas.system_versions_changelog (id, system_version, change_type, change_scope, title, description, changed_by) VALUES
    ('99999999-9999-4999-8999-999999999901', 'v1.0.0', 'SYSTEM', 'MAJOR', 'Khởi tạo Hệ thống Quản trị Doanh nghiệp & AI v1.0', 'Thiết lập cấu trúc RBAC, Quy trình A/B/C, Quy định v1.0 và kết nối 8 Mock APIs.', 'System Admin')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- 11. CÀI ĐẶT CÁC TRIGGER TỰ ĐỘNG HÓA (SAU KHI ĐÃ CÓ SEED DATA)
-- ============================================================================

-- 11.1. TRIGGER PHA 1 (BEFORE INSERT OR UPDATE): Chỉ tính số Version (Major / Minor)
-- Không chèn vào bảng con ở bước BEFORE để tuyệt đối không bao giờ lỗi 23503!
CREATE OR REPLACE FUNCTION eas.fn_before_regulation_versioning()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    v_cur_major INT;
    v_cur_minor INT;
BEGIN
    SELECT COALESCE(global_major_version, 1), COALESCE(global_minor_version, 0)
    INTO v_cur_major, v_cur_minor
    FROM eas.ai_system_state
    WHERE id = 1;

    IF TG_OP = 'INSERT' THEN
        -- Thêm mới 1 quy định -> Tăng phiên bản LỚN (Major Version)
        v_cur_major := v_cur_major + 1;
        v_cur_minor := 0;
        NEW.major_version := v_cur_major;
        NEW.minor_version := v_cur_minor;
        NEW.version_string := v_cur_major || '.' || v_cur_minor;
        NEW.updated_at := now();
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        -- Nếu xóa mềm quy định (is_deleted chuyển từ false sang true) -> Tăng phiên bản LỚN (Major)
        IF COALESCE(OLD.is_deleted, false) = false AND COALESCE(NEW.is_deleted, false) = true THEN
            v_cur_major := v_cur_major + 1;
            v_cur_minor := 0;
            NEW.major_version := v_cur_major;
            NEW.minor_version := v_cur_minor;
            NEW.version_string := v_cur_major || '.' || v_cur_minor;
            NEW.updated_at := now();
        -- Nếu sửa nội dung hoặc tiêu đề của 1 quy định -> Tăng phiên bản NHỎ (Minor)
        ELSIF NEW.content IS DISTINCT FROM OLD.content OR NEW.title IS DISTINCT FROM OLD.title OR NEW.category IS DISTINCT FROM OLD.category THEN
            v_cur_minor := v_cur_minor + 1;
            NEW.major_version := v_cur_major;
            NEW.minor_version := v_cur_minor;
            NEW.version_string := v_cur_major || '.' || v_cur_minor;
            NEW.updated_at := now();
        END IF;
        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$;

-- 11.2. TRIGGER PHA 2 (AFTER INSERT OR UPDATE OR DELETE):
-- Lúc này bản ghi cha đã nằm trong company_regulations -> Ghi lịch sử & Đẩy sang AI học an toàn 100%
CREATE OR REPLACE FUNCTION eas.fn_after_regulation_versioning()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    v_action_type TEXT;
    v_scope TEXT;
    v_summary TEXT;
    v_major INT;
    v_minor INT;
    v_ver_str TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_action_type := 'CREATE';
        v_scope := 'MAJOR';
        v_major := NEW.major_version;
        v_minor := NEW.minor_version;
        v_ver_str := NEW.version_string;
        v_summary := 'Thêm mới quy định "' || NEW.title || '" -> Nâng phiên bản lớn v' || v_ver_str;

        INSERT INTO eas.regulation_versions (
            regulation_id, version_string, major_version, minor_version,
            action_type, title, content, change_summary, created_by
        ) VALUES (
            NEW.id, v_ver_str, v_major, v_minor,
            v_action_type, NEW.title, NEW.content, v_summary, COALESCE(NEW.updated_by, 'Admin')
        );

    ELSIF TG_OP = 'UPDATE' THEN
        IF COALESCE(OLD.is_deleted, false) = false AND COALESCE(NEW.is_deleted, false) = true THEN
            v_action_type := 'DELETE_MAJOR';
            v_scope := 'MAJOR';
            v_summary := 'Xóa quy định "' || NEW.title || '" -> Nâng phiên bản lớn v' || NEW.version_string;
        ELSIF NEW.version_string IS DISTINCT FROM OLD.version_string THEN
            v_action_type := 'UPDATE_MINOR';
            v_scope := 'MINOR';
            v_summary := 'Cập nhật nội dung quy định "' || NEW.title || '" -> Nâng phiên bản nhỏ v' || NEW.version_string;
        ELSE
            RETURN NEW;
        END IF;

        v_major := NEW.major_version;
        v_minor := NEW.minor_version;
        v_ver_str := NEW.version_string;

        INSERT INTO eas.regulation_versions (
            regulation_id, version_string, major_version, minor_version,
            action_type, title, content, change_summary, created_by
        ) VALUES (
            NEW.id, v_ver_str, v_major, v_minor,
            v_action_type, NEW.title, NEW.content, v_summary, COALESCE(NEW.updated_by, 'Admin')
        );

    ELSIF TG_OP = 'DELETE' THEN
        -- Trường hợp Admin xóa cứng (Hard DELETE) một quy định: tăng phiên bản lớn (Major)
        SELECT COALESCE(global_major_version, 1) + 1, 0
        INTO v_major, v_minor
        FROM eas.ai_system_state WHERE id = 1;

        v_ver_str := v_major || '.' || v_minor;
        v_action_type := 'DELETE_MAJOR';
        v_scope := 'MAJOR';
        v_summary := 'Xóa quy định "' || OLD.title || '" -> Nâng phiên bản lớn v' || v_ver_str;

        INSERT INTO eas.regulation_versions (
            regulation_id, version_string, major_version, minor_version,
            action_type, title, content, change_summary, created_by
        ) VALUES (
            NULL, v_ver_str, v_major, v_minor,
            v_action_type, OLD.title, OLD.content, v_summary, COALESCE(OLD.updated_by, 'Admin')
        );
    END IF;

    -- Đẩy trạng thái sang AI Service để học quy định mới & Tự động bật khóa bảo trì Web Client
    UPDATE eas.ai_system_state
    SET target_regulation_version = v_ver_str,
        global_major_version = v_major,
        global_minor_version = v_minor,
        sync_status = 'LEARNING',
        current_step_index = 2,
        current_step_label = 'AI đang học quy định mới (Phiên bản v' || v_ver_str || ')',
        progress_percent = 45,
        client_maintenance_lock = true,
        maintenance_message = 'Hệ thống đang cập nhật và huấn luyện AI theo Quy định phiên bản v' || v_ver_str || '. Vui lòng thoát ra và đăng nhập lại ngay khi quá trình tự động hoàn tất.',
        steps_detail = jsonb_build_array(
            jsonb_build_object('step', 1, 'code', 'SYNCING', 'label', 'Tiếp nhận quy định mới v' || v_ver_str, 'status', 'DONE'),
            jsonb_build_object('step', 2, 'code', 'LEARNING', 'label', 'AI đang phân tích & học quy định v' || v_ver_str, 'status', 'IN_PROGRESS'),
            jsonb_build_object('step', 3, 'code', 'APPLYING', 'label', 'Áp dụng quy định mới vào luồng duyệt', 'status', 'PENDING'),
            jsonb_build_object('step', 4, 'code', 'COMPLETED', 'label', 'Hoàn tất & Mở khóa Web Client', 'status', 'PENDING')
        ),
        updated_at = now()
    WHERE id = 1;

    -- Ghi nhận vào bảng Phiên bản hệ thống (Changelog)
    INSERT INTO eas.system_versions_changelog (
        system_version, change_type, change_scope, title, description, changed_by
    ) VALUES (
        'v' || v_ver_str, 'REGULATION', v_scope, v_summary,
        'Hệ thống đã đẩy quy định sang AI Service để học tự động.', 'Admin'
    );

    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER trg_before_regulation_versioning
    BEFORE INSERT OR UPDATE ON eas.company_regulations
    FOR EACH ROW
    EXECUTE FUNCTION eas.fn_before_regulation_versioning();

CREATE TRIGGER trg_after_regulation_versioning
    AFTER INSERT OR UPDATE OR DELETE ON eas.company_regulations
    FOR EACH ROW
    EXECUTE FUNCTION eas.fn_after_regulation_versioning();

-- 11.3. TRIGGER TỰ ĐỘNG CẬP NHẬT QUY TRÌNH KHI ĐẨY MẪU YÊU CẦU TỪ A SANG B/C
CREATE OR REPLACE FUNCTION eas.fn_sync_template_workflow_by_category()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    v_cat_steps JSONB;
BEGIN
    IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND NEW.category_code IS DISTINCT FROM OLD.category_code) THEN
        SELECT workflow_steps INTO v_cat_steps
        FROM eas.workflow_categories
        WHERE category_code = NEW.category_code;

        IF v_cat_steps IS NOT NULL AND (TG_OP = 'UPDATE' OR NEW.workflow_steps IS NULL OR NEW.workflow_steps = '[]'::jsonb) THEN
            NEW.workflow_steps := v_cat_steps;
        END IF;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sync_template_workflow
    BEFORE INSERT OR UPDATE ON eas.request_templates
    FOR EACH ROW
    EXECUTE FUNCTION eas.fn_sync_template_workflow_by_category();

-- Ghi log khi đẩy loại yêu cầu từ A sang B/C hoặc chỉnh trọng số
CREATE OR REPLACE FUNCTION eas.fn_log_template_changes()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.category_code IS DISTINCT FROM OLD.category_code THEN
        INSERT INTO eas.system_versions_changelog (
            system_version, change_type, change_scope, title, description, old_value, new_value
        ) VALUES (
            'v' || (SELECT active_regulation_version FROM eas.ai_system_state WHERE id = 1),
            'WORKFLOW', 'MINOR',
            'Chuyển phân loại mẫu "' || NEW.name || '" từ nhóm ' || OLD.category_code || ' sang nhóm ' || NEW.category_code,
            'Quy trình xử lý của mẫu yêu cầu đã tự động cập nhật theo chuẩn phân loại ' || NEW.category_code,
            jsonb_build_object('category_code', OLD.category_code, 'workflow_steps', OLD.workflow_steps),
            jsonb_build_object('category_code', NEW.category_code, 'workflow_steps', NEW.workflow_steps)
        );
    ELSIF NEW.automation_weight IS DISTINCT FROM OLD.automation_weight THEN
        INSERT INTO eas.system_versions_changelog (
            system_version, change_type, change_scope, title, description, old_value, new_value
        ) VALUES (
            'v' || (SELECT active_regulation_version FROM eas.ai_system_state WHERE id = 1),
            'TEMPLATE', 'PATCH',
            'Điều chỉnh trọng số tự động mẫu "' || NEW.name || '" (' || OLD.automation_weight || '% -> ' || NEW.automation_weight || '%)',
            'Cập nhật trọng số tính tự động cho mẫu yêu cầu.',
            jsonb_build_object('automation_weight', OLD.automation_weight),
            jsonb_build_object('automation_weight', NEW.automation_weight)
        );
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_after_template_workflow_log
    AFTER UPDATE ON eas.request_templates
    FOR EACH ROW
    EXECUTE FUNCTION eas.fn_log_template_changes();

-- Nếu Admin sửa quy trình gốc của nhóm A, B, C -> Đồng bộ xuống các mẫu thuộc nhóm đó
CREATE OR REPLACE FUNCTION eas.fn_propagate_category_workflow()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.workflow_steps IS DISTINCT FROM OLD.workflow_steps THEN
        UPDATE eas.request_templates
        SET workflow_steps = NEW.workflow_steps,
            updated_at = now()
        WHERE category_code = NEW.category_code;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_propagate_category_workflow
    AFTER UPDATE ON eas.workflow_categories
    FOR EACH ROW
    EXECUTE FUNCTION eas.fn_propagate_category_workflow();

-- 11.4. TRIGGER GHI LOG KHI BẬT/TẮT MOCK API
CREATE OR REPLACE FUNCTION eas.fn_log_mock_api_toggle()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.is_enabled IS DISTINCT FROM OLD.is_enabled THEN
        INSERT INTO eas.system_versions_changelog (
            system_version, change_type, change_scope, title, description, old_value, new_value
        ) VALUES (
            'v' || (SELECT active_regulation_version FROM eas.ai_system_state WHERE id = 1),
            'API_STATUS', 'MINOR',
            CASE WHEN NEW.is_enabled THEN 'Bật kết nối API: ' ELSE 'Tắt kết nối API: ' END || NEW.api_name,
            CASE WHEN NEW.is_enabled
                THEN 'Các mẫu yêu cầu liên quan đến ' || NEW.source_system || ' đã hoạt động trở lại.'
                ELSE 'Toàn bộ yêu cầu liên quan đến ' || NEW.source_system || ' đã chuyển sang trạng thái thông báo không thể sử dụng.'
            END,
            jsonb_build_object('is_enabled', OLD.is_enabled),
            jsonb_build_object('is_enabled', NEW.is_enabled)
        );
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_after_mock_api_toggle
    AFTER UPDATE ON eas.mock_apis
    FOR EACH ROW
    EXECUTE FUNCTION eas.fn_log_mock_api_toggle();

-- ============================================================================
-- 12. CẤP QUYỀN TRUY CẬP SUPABASE API & BACKEND ROLES (GRANTS & RLS POLICIES)
-- ============================================================================
GRANT USAGE ON SCHEMA eas TO postgres, service_role, eas_backend_login, eas_api, eas_worker, eas_worker_login;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA eas TO postgres, service_role, eas_backend_login, eas_api, eas_worker, eas_worker_login;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA eas TO postgres, service_role, eas_backend_login, eas_api, eas_worker, eas_worker_login;
GRANT ALL PRIVILEGES ON ALL ROUTINES IN SCHEMA eas TO postgres, service_role, eas_backend_login, eas_api, eas_worker, eas_worker_login;

ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT ALL ON TABLES TO postgres, service_role, eas_backend_login, eas_api, eas_worker, eas_worker_login;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT ALL ON SEQUENCES TO postgres, service_role, eas_backend_login, eas_api, eas_worker, eas_worker_login;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT ALL ON ROUTINES TO postgres, service_role, eas_backend_login, eas_api, eas_worker, eas_worker_login;
-- Supabase client roles never touch eas directly (AGENTS.md, Database).
REVOKE ALL ON ALL TABLES IN SCHEMA eas FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA eas FROM anon, authenticated;
REVOKE ALL ON ALL ROUTINES IN SCHEMA eas FROM anon, authenticated;
REVOKE USAGE ON SCHEMA eas FROM anon, authenticated;

DO $$
DECLARE
    t text;
    tables text[] := ARRAY[
        'departments', 'roles', 'modules', 'role_permissions', 'users',
        'user_permissions', 'user_leave_and_trips', 'mock_apis',
        'workflow_categories', 'request_templates', 'requests',
        'company_regulations', 'regulation_versions', 'ai_system_state',
        'system_versions_changelog'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS trusted_backend ON eas.%I', t);
        EXECUTE format('CREATE POLICY trusted_backend ON eas.%I FOR ALL TO eas_api, eas_worker, eas_privacy, eas_backend_login USING (true) WITH CHECK (true)', t);
        
        EXECUTE format('DROP POLICY IF EXISTS backup_read ON eas.%I', t);
        EXECUTE format('CREATE POLICY backup_read ON eas.%I FOR SELECT TO eas_backup USING (true)', t);
    END LOOP;
END $$;

COMMIT;