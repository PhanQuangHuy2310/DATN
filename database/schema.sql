-- ========================================================================================
-- DỰ ÁN: ENTERPRISE APPROVAL SYSTEM (EAS) - ĐẶC TẢ DỮ LIỆU VẬT LÝ V2.0
-- DATABASE ENGINE: PostgreSQL 15+ / Supabase (PostgreSQL 15-18)
-- PHIÊN BẢN MÔ HÌNH: 2.0 (Khóa theo tài liệu Thiết kế: 03_Du_lieu_va_API_v2.docx)
-- ========================================================================================

-- Kích hoạt các extension cần thiết cho UUID và mã hóa băm
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================================================================
-- 1. THIẾT LẬP SCHEMA RIÊNG (SCHEMA: eas)
-- ========================================================================================
-- Schema riêng giúp phân tách sạch sẽ 30 bảng nghiệp vụ EAS khỏi các bảng mặc định của Supabase.
-- Nếu bạn muốn cài trực tiếp vào schema 'public', hãy thay 'eas' bằng 'public' ở 2 dòng bên dưới.
CREATE SCHEMA IF NOT EXISTS eas;
SET search_path TO eas, public;

-- Cấp quyền truy cập schema cho các role mặc định của Supabase
GRANT USAGE ON SCHEMA eas TO postgres, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT ALL ON TABLES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT SELECT ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT ALL ON SEQUENCES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas GRANT USAGE, SELECT ON SEQUENCES TO authenticated;

-- ========================================================================================
-- 2. HÀM DÙNG CHUNG (TRIGGER FUNCTIONS)
-- ========================================================================================

-- Tự động cập nhật updated_at
CREATE OR REPLACE FUNCTION eas.trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Bảo vệ các bảng bất biến (Append-only / Immutable tables)
CREATE OR REPLACE FUNCTION eas.trg_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Bảng % là bất biến (Append-only/Immutable). Không cho phép UPDATE hoặc DELETE.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

-- ========================================================================================
-- 3. KHỞI TẠO 30 BẢNG VẬT LÝ MIỀN ỨNG DỤNG (DB01 - DB30)
-- ========================================================================================

-- ----------------------------------------------------------------------------------------
-- DB01: security_epoch
-- Quản lý phiên bản an ninh toàn cục, khóa đồng thời khi thay đổi cơ cấu/quyền
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.security_epoch (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    version bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------------------
-- DB02: department
-- Cơ cấu tổ chức cây phòng ban phân cấp
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.department (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(30) UNIQUE NOT NULL,
    name varchar(150) NOT NULL,
    parent_id uuid REFERENCES eas.department(id) ON DELETE RESTRICT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_department_parent_not_self CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE TRIGGER trg_department_updated_at
BEFORE UPDATE ON eas.department
FOR EACH ROW EXECUTE FUNCTION eas.trg_set_updated_at();

-- ----------------------------------------------------------------------------------------
-- DB03: app_user
-- Hồ sơ tài khoản người dùng và quan hệ quản lý trực tiếp (Org Tree)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.app_user (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username varchar(80) UNIQUE NOT NULL,
    display_name varchar(150) NOT NULL,
    department_id uuid NOT NULL REFERENCES eas.department(id) ON DELETE RESTRICT,
    manager_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT NULL,
    is_active boolean NOT NULL DEFAULT true,
    must_change_password boolean NOT NULL DEFAULT true,
    auth_version bigint NOT NULL DEFAULT 0,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_user_manager_not_self CHECK (manager_id IS NULL OR manager_id <> id),
    CONSTRAINT chk_user_username_lowercase CHECK (username = lower(username))
);

CREATE TRIGGER trg_app_user_updated_at
BEFORE UPDATE ON eas.app_user
FOR EACH ROW EXECUTE FUNCTION eas.trg_set_updated_at();

-- ----------------------------------------------------------------------------------------
-- DB05: request_type
-- Danh mục loại yêu cầu nghiệp vụ (P0: LEAVE / ACCESS / EQUIPMENT)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.request_type (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(30) UNIQUE NOT NULL,
    lifecycle char(1) NOT NULL CHECK (lifecycle IN ('A', 'B', 'C')),
    is_active boolean NOT NULL DEFAULT true,
    active_release_id uuid NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------------------
-- DB04: role_membership
-- Ma trận gán vai trò RBAC phạm vi toàn cục hoặc phòng ban
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.role_membership (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    role varchar(24) NOT NULL,
    scope_kind varchar(20) NOT NULL CHECK (scope_kind IN ('GLOBAL', 'DEPARTMENT')),
    department_id uuid REFERENCES eas.department(id) ON DELETE RESTRICT NULL,
    type_scope varchar(10) NOT NULL CHECK (type_scope IN ('ALL', 'ONE')),
    type_id uuid REFERENCES eas.request_type(id) ON DELETE RESTRICT NULL,
    valid_from timestamptz NOT NULL,
    valid_to timestamptz NULL,
    revoked_at timestamptz NULL,
    CONSTRAINT chk_role_scope_kind CHECK (
        (scope_kind = 'GLOBAL' AND department_id IS NULL) OR
        (scope_kind = 'DEPARTMENT' AND department_id IS NOT NULL)
    ),
    CONSTRAINT chk_role_type_scope CHECK (
        (type_scope = 'ALL' AND type_id IS NULL) OR
        (type_scope = 'ONE' AND type_id IS NOT NULL)
    ),
    CONSTRAINT chk_role_validity_window CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT uq_role_membership UNIQUE NULLS NOT DISTINCT (user_id, role, scope_kind, department_id, type_scope, type_id, valid_from)
);

-- ----------------------------------------------------------------------------------------
-- DB06: config_release
-- Bản phát hành cấu hình bất biến (Form schema, routing rules, actor binding, SLA profile)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.config_release (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type_id uuid NOT NULL REFERENCES eas.request_type(id) ON DELETE RESTRICT,
    version int NOT NULL CHECK (version > 0),
    state varchar(20) NOT NULL CHECK (state IN ('DRAFT', 'PUBLISHED')),
    lifecycle char(1) NOT NULL CHECK (lifecycle IN ('A', 'B', 'C')),
    form_schema jsonb NOT NULL,
    route_rules jsonb NOT NULL,
    actor_bindings jsonb NOT NULL,
    sla_profile jsonb NOT NULL,
    created_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    published_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz NULL,
    lock_version bigint NOT NULL DEFAULT 0,
    content_sha256 char(64) NULL,
    CONSTRAINT uq_config_release_type_version UNIQUE (type_id, version),
    CONSTRAINT uq_config_release_id_type UNIQUE (id, type_id)
);

-- Khóa ngoại từ request_type trỏ tới active config_release
ALTER TABLE eas.request_type
    ADD CONSTRAINT fk_request_type_active_release
    FOREIGN KEY (active_release_id, id)
    REFERENCES eas.config_release(id, type_id)
    ON DELETE RESTRICT;

-- ----------------------------------------------------------------------------------------
-- DB07: request
-- Thực thể hồ sơ yêu cầu trung tâm
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.request (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(40) UNIQUE NOT NULL,
    requester_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    type_id uuid NOT NULL REFERENCES eas.request_type(id) ON DELETE RESTRICT,
    status varchar(32) NOT NULL,
    draft_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    draft_amount_vnd bigint NULL CHECK (draft_amount_vnd IS NULL OR draft_amount_vnd > 0),
    draft_release_id uuid NULL,
    origin_request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT NULL,
    current_revision_id uuid NULL,
    lock_version bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz NULL,
    completed_at timestamptz NULL,
    CONSTRAINT fk_request_draft_release FOREIGN KEY (draft_release_id, type_id) REFERENCES eas.config_release(id, type_id) ON DELETE RESTRICT,
    CONSTRAINT chk_request_origin_not_self CHECK (origin_request_id IS NULL OR origin_request_id <> id)
);

CREATE TRIGGER trg_request_updated_at
BEFORE UPDATE ON eas.request
FOR EACH ROW EXECUTE FUNCTION eas.trg_set_updated_at();

-- ----------------------------------------------------------------------------------------
-- DB08: request_revision
-- Lịch sử phiên bản nộp hồ sơ bất biến (Snapshot dữ liệu, phòng ban, tiền)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.request_revision (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    revision_no int NOT NULL CHECK (revision_no > 0),
    release_id uuid NOT NULL REFERENCES eas.config_release(id) ON DELETE RESTRICT,
    department_id uuid NOT NULL REFERENCES eas.department(id) ON DELETE RESTRICT,
    payload jsonb NOT NULL,
    amount_vnd bigint NULL CHECK (amount_vnd IS NULL OR amount_vnd > 0),
    submitted_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    payload_sha256 char(64) NOT NULL,
    CONSTRAINT uq_request_revision_no UNIQUE (request_id, revision_no),
    CONSTRAINT uq_request_revision_id_request UNIQUE (id, request_id)
);

-- Khóa ngoại từ request trỏ tới current_revision_id (khớp request_id)
ALTER TABLE eas.request
    ADD CONSTRAINT fk_request_current_revision
    FOREIGN KEY (current_revision_id, id)
    REFERENCES eas.request_revision(id, request_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------------------------------------------------------------------
-- DB09: workflow_instance
-- Phiên thực thi workflow gắn với revision đã nộp
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.workflow_instance (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    revision_id uuid NOT NULL UNIQUE,
    matched_rule_id varchar(50) NOT NULL,
    resolved_route jsonb NOT NULL,
    lifecycle char(1) NOT NULL CHECK (lifecycle IN ('A', 'B', 'C')),
    state varchar(20) NOT NULL CHECK (state IN ('ACTIVE', 'COMPLETED', 'REJECTED', 'SUPERSEDED', 'CANCELLED')),
    planned_executor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT NULL,
    acceptor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz NULL,
    CONSTRAINT fk_workflow_instance_revision FOREIGN KEY (revision_id, request_id) REFERENCES eas.request_revision(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT uq_workflow_instance_id_request UNIQUE (id, request_id)
);

-- ----------------------------------------------------------------------------------------
-- DB10: request_participant
-- Danh sách người tham gia theo dõi/xử lý hồ sơ
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.request_participant (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    first_joined_at timestamptz NOT NULL DEFAULT now(),
    joined_as varchar(24) NOT NULL,
    read_revoked_at timestamptz NULL,
    read_revoked_reason varchar(2000) NULL,
    CONSTRAINT uq_request_participant UNIQUE (request_id, user_id)
);

-- ----------------------------------------------------------------------------------------
-- DB11: approval_step
-- Các bước phê duyệt tuần tự trong workflow (Tối đa 3 cấp)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.approval_step (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    instance_id uuid NOT NULL,
    step_no smallint NOT NULL CHECK (step_no BETWEEN 1 AND 3),
    assignee_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    state varchar(20) NOT NULL CHECK (state IN ('WAITING', 'ACTIVE', 'APPROVED', 'REJECTED', 'NEEDS_INFO', 'SKIPPED')),
    activated_at timestamptz NULL,
    closed_at timestamptz NULL,
    CONSTRAINT fk_approval_step_instance FOREIGN KEY (instance_id, request_id) REFERENCES eas.workflow_instance(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT uq_approval_step_instance_no UNIQUE (instance_id, step_no),
    CONSTRAINT uq_approval_step_id_request UNIQUE (id, request_id)
);

-- Chỉ duy nhất 1 step ở trạng thái ACTIVE trong 1 workflow instance
CREATE UNIQUE INDEX IF NOT EXISTS one_active_step 
ON eas.approval_step(instance_id) 
WHERE state = 'ACTIVE';

-- ----------------------------------------------------------------------------------------
-- DB12: approval_decision
-- Quyết định phê duyệt bất biến của người duyệt
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.approval_decision (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    step_id uuid NOT NULL UNIQUE,
    actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    outcome varchar(20) NOT NULL CHECK (outcome IN ('APPROVE', 'REJECT', 'NEEDS_INFO')),
    reason varchar(2000) NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_approval_decision_step FOREIGN KEY (step_id, request_id) REFERENCES eas.approval_step(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT chk_approval_decision_reason CHECK (
        outcome = 'APPROVE' OR (outcome IN ('REJECT', 'NEEDS_INFO') AND reason IS NOT NULL AND length(trim(reason)) BETWEEN 10 AND 2000)
    )
);

CREATE TRIGGER trg_approval_decision_immutable
BEFORE UPDATE OR DELETE ON eas.approval_decision
FOR EACH ROW EXECUTE FUNCTION eas.trg_prevent_modification();

-- ----------------------------------------------------------------------------------------
-- DB13: execution_attempt
-- Lần thực hiện/thi công của người thực thi (Executor)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.execution_attempt (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    instance_id uuid NOT NULL,
    attempt_no int NOT NULL CHECK (attempt_no > 0),
    executor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    state varchar(20) NOT NULL CHECK (state IN ('READY', 'RUNNING', 'SUBMITTED', 'FINISHED')),
    closure_kind varchar(20) NULL CHECK (closure_kind IN ('SUCCESS', 'ACCEPTED', 'REWORK', 'REASSIGNED')),
    result_note varchar(4000) NULL,
    external_reference varchar(200) NULL,
    started_at timestamptz NULL,
    submitted_at timestamptz NULL,
    closed_at timestamptz NULL,
    CONSTRAINT fk_execution_attempt_instance FOREIGN KEY (instance_id, request_id) REFERENCES eas.workflow_instance(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT uq_execution_attempt_instance_no UNIQUE (instance_id, attempt_no),
    CONSTRAINT uq_execution_attempt_id_request UNIQUE (id, request_id),
    CONSTRAINT chk_execution_attempt_finished CHECK (
        (state = 'FINISHED' AND closure_kind IS NOT NULL AND closed_at IS NOT NULL) OR
        (state <> 'FINISHED' AND closure_kind IS NULL AND closed_at IS NULL)
    )
);

-- Chỉ duy nhất 1 attempt đang trong tiến trình (READY, RUNNING, SUBMITTED)
CREATE UNIQUE INDEX IF NOT EXISTS one_current_attempt 
ON eas.execution_attempt(instance_id) 
WHERE state IN ('READY', 'RUNNING', 'SUBMITTED');

-- ----------------------------------------------------------------------------------------
-- DB14: acceptance_decision
-- Quyết định nghiệm thu kết quả thi công (Acceptor)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.acceptance_decision (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL UNIQUE,
    actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    outcome varchar(20) NOT NULL CHECK (outcome IN ('ACCEPT', 'REWORK')),
    reason varchar(2000) NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_acceptance_decision_attempt FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT chk_acceptance_decision_reason CHECK (
        outcome = 'ACCEPT' OR (outcome = 'REWORK' AND reason IS NOT NULL AND length(trim(reason)) BETWEEN 10 AND 2000)
    )
);

CREATE TRIGGER trg_acceptance_decision_immutable
BEFORE UPDATE OR DELETE ON eas.acceptance_decision
FOR EACH ROW EXECUTE FUNCTION eas.trg_prevent_modification();

-- ----------------------------------------------------------------------------------------
-- DB15: execution_issue
-- Báo cáo sự cố khi nhận việc hoặc bị chặn trong thi công
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.execution_issue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    kind varchar(30) NOT NULL CHECK (kind IN ('UNABLE_TO_CLAIM', 'BLOCKED')),
    reason varchar(2000) NOT NULL CHECK (length(trim(reason)) BETWEEN 10 AND 2000),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_execution_issue_attempt FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT
);

CREATE TRIGGER trg_execution_issue_immutable
BEFORE UPDATE OR DELETE ON eas.execution_issue
FOR EACH ROW EXECUTE FUNCTION eas.trg_prevent_modification();

-- ----------------------------------------------------------------------------------------
-- DB16: attachment
-- Quản lý tệp đính kèm, kiểm soát mã băm sha256 và trạng thái quét virus
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.attachment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    uploader_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    storage_key varchar(300) UNIQUE NOT NULL,
    object_version varchar(200) NOT NULL,
    original_name varchar(150) NOT NULL,
    mime varchar(80) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes BETWEEN 1 AND 10485760), -- Tối đa 10MB/file
    sha256 char(64) NOT NULL,
    scan_state varchar(20) NOT NULL CHECK (scan_state IN ('QUEUED', 'CLEAN', 'INFECTED', 'ERROR')),
    scan_attempts int NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    scanned_at timestamptz NULL,
    deleted_at timestamptz NULL,
    CONSTRAINT uq_attachment_id_request UNIQUE (id, request_id)
);

-- ----------------------------------------------------------------------------------------
-- DB17: draft_attachment
-- Tệp liên kết trong bản nháp
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.draft_attachment (
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    attachment_id uuid NOT NULL,
    added_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (request_id, attachment_id),
    CONSTRAINT fk_draft_attachment FOREIGN KEY (attachment_id, request_id) REFERENCES eas.attachment(id, request_id) ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------------------
-- DB18: revision_attachment
-- Tệp liên kết trong phiên bản chính thức đã nộp
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.revision_attachment (
    revision_id uuid NOT NULL,
    attachment_id uuid NOT NULL,
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    PRIMARY KEY (revision_id, attachment_id),
    CONSTRAINT fk_rev_attachment_revision FOREIGN KEY (revision_id, request_id) REFERENCES eas.request_revision(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT fk_rev_attachment_file FOREIGN KEY (attachment_id, request_id) REFERENCES eas.attachment(id, request_id) ON DELETE RESTRICT
);

CREATE TRIGGER trg_revision_attachment_immutable
BEFORE UPDATE OR DELETE ON eas.revision_attachment
FOR EACH ROW EXECUTE FUNCTION eas.trg_prevent_modification();

-- ----------------------------------------------------------------------------------------
-- DB19: execution_attachment
-- Tệp minh chứng kết quả nghiệm thu/thi công
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.execution_attachment (
    attempt_id uuid NOT NULL,
    attachment_id uuid NOT NULL,
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    PRIMARY KEY (attempt_id, attachment_id),
    CONSTRAINT fk_exec_attachment_attempt FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT fk_exec_attachment_file FOREIGN KEY (attachment_id, request_id) REFERENCES eas.attachment(id, request_id) ON DELETE RESTRICT
);

CREATE TRIGGER trg_execution_attachment_immutable
BEFORE UPDATE OR DELETE ON eas.execution_attachment
FOR EACH ROW EXECUTE FUNCTION eas.trg_prevent_modification();

-- ----------------------------------------------------------------------------------------
-- DB20: sla_stage
-- Giai đoạn cam kết SLA (Phê duyệt, Thi công hoặc Nghiệm thu)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.sla_stage (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    kind varchar(20) NOT NULL CHECK (kind IN ('APPROVAL', 'EXECUTION', 'ACCEPTANCE')),
    approval_step_id uuid NULL,
    attempt_id uuid NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    due_at timestamptz NOT NULL,
    closed_at timestamptz NULL,
    breached_at timestamptz NULL,
    CONSTRAINT uq_sla_stage_id_request UNIQUE (id, request_id),
    CONSTRAINT chk_sla_stage_timeline CHECK (due_at > started_at),
    CONSTRAINT chk_sla_stage_closed CHECK (closed_at IS NULL OR closed_at >= started_at),
    CONSTRAINT chk_sla_stage_subtype CHECK (
        (kind = 'APPROVAL' AND approval_step_id IS NOT NULL AND attempt_id IS NULL) OR
        (kind IN ('EXECUTION', 'ACCEPTANCE') AND approval_step_id IS NULL AND attempt_id IS NOT NULL)
    ),
    CONSTRAINT fk_sla_stage_step FOREIGN KEY (approval_step_id, request_id) REFERENCES eas.approval_step(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT fk_sla_stage_attempt FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT
);

-- Chỉ duy nhất 1 giai đoạn SLA đang mở trên 1 hồ sơ
CREATE UNIQUE INDEX IF NOT EXISTS one_open_stage 
ON eas.sla_stage(request_id) 
WHERE closed_at IS NULL;

-- ----------------------------------------------------------------------------------------
-- DB21: sla_alert
-- Cảnh báo nhắc nhở sắp hết hạn hoặc đã vi phạm SLA
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.sla_alert (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    stage_id uuid NOT NULL,
    kind varchar(20) NOT NULL CHECK (kind IN ('REMINDER', 'BREACH')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_sla_alert_stage FOREIGN KEY (stage_id, request_id) REFERENCES eas.sla_stage(id, request_id) ON DELETE RESTRICT,
    CONSTRAINT uq_sla_alert_stage_kind UNIQUE (stage_id, kind)
);

-- ----------------------------------------------------------------------------------------
-- DB22: audit_event
-- Nhật ký kiểm toán nghiệp vụ cấp hồ sơ (Chuỗi băm liên kết SHA-256)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.audit_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    seq bigint NOT NULL,
    actor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT NULL,
    actor_kind varchar(10) NOT NULL CHECK (actor_kind IN ('HUMAN', 'SYSTEM')),
    action varchar(80) NOT NULL,
    target_type varchar(40) NOT NULL,
    target_id uuid NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    hash_version smallint NOT NULL DEFAULT 1,
    prev_hash char(64) NOT NULL,
    hash char(64) NOT NULL,
    CONSTRAINT uq_audit_event_request_seq UNIQUE (request_id, seq),
    CONSTRAINT chk_audit_actor_kind CHECK (
        (actor_kind = 'SYSTEM' AND actor_id IS NULL) OR
        (actor_kind = 'HUMAN' AND actor_id IS NOT NULL)
    )
);

CREATE TRIGGER trg_audit_event_immutable
BEFORE UPDATE OR DELETE ON eas.audit_event
FOR EACH ROW EXECUTE FUNCTION eas.trg_prevent_modification();

-- ----------------------------------------------------------------------------------------
-- DB23: admin_event
-- Nhật ký kiểm toán thao tác hệ thống và quản trị
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.admin_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seq bigint NOT NULL UNIQUE,
    actor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT NULL,
    actor_kind varchar(10) NOT NULL CHECK (actor_kind IN ('HUMAN', 'SYSTEM')),
    action varchar(80) NOT NULL,
    target_type varchar(40) NOT NULL,
    target_id varchar(100) NOT NULL,
    department_id uuid REFERENCES eas.department(id) ON DELETE RESTRICT NULL,
    type_id uuid REFERENCES eas.request_type(id) ON DELETE RESTRICT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason text NOT NULL,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    hash_version smallint NOT NULL DEFAULT 1,
    prev_hash char(64) NOT NULL,
    hash char(64) NOT NULL,
    CONSTRAINT chk_admin_actor_kind CHECK (
        (actor_kind = 'SYSTEM' AND actor_id IS NULL) OR
        (actor_kind = 'HUMAN' AND actor_id IS NOT NULL)
    )
);

CREATE TRIGGER trg_admin_event_immutable
BEFORE UPDATE OR DELETE ON eas.admin_event
FOR EACH ROW EXECUTE FUNCTION eas.trg_prevent_modification();

-- ----------------------------------------------------------------------------------------
-- DB24: audit_head
-- Đỉnh chuỗi băm kiểm toán phục vụ ký liên tiếp
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.audit_head (
    scope_key varchar(100) PRIMARY KEY, -- 'REQ:<uuid>' hoặc 'ADMIN'
    seq bigint NOT NULL DEFAULT 0,
    last_hash char(64) NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000'
);

-- ----------------------------------------------------------------------------------------
-- DB25: audit_checkpoint
-- Điểm kiểm tra chốt băm định kỳ lưu ra kho ngoài
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.audit_checkpoint (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key varchar(100) NOT NULL,
    seq bigint NOT NULL,
    hash char(64) NOT NULL,
    external_object_key varchar(300) NOT NULL,
    external_version varchar(200) NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_audit_checkpoint UNIQUE (scope_key, seq)
);

-- ----------------------------------------------------------------------------------------
-- DB26: outbox_event
-- Hàng đợi sự kiện Outbox Pattern đảm bảo Transactional Messaging
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.outbox_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT NULL,
    event_type varchar(80) NOT NULL,
    payload jsonb NOT NULL,
    state varchar(20) NOT NULL CHECK (state IN ('PENDING', 'PROCESSING', 'SENT', 'DEAD')),
    dedupe_key varchar(200) UNIQUE NOT NULL,
    attempts int NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= 4),
    replay_count int NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_token uuid NULL,
    lease_until timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz NULL,
    last_error_code varchar(80) NULL,
    CONSTRAINT chk_outbox_sent_at CHECK (
        (state = 'SENT' AND sent_at IS NOT NULL) OR (state <> 'SENT')
    ),
    CONSTRAINT chk_outbox_processing CHECK (
        (state = 'PROCESSING' AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (state <> 'PROCESSING')
    )
);

-- ----------------------------------------------------------------------------------------
-- DB27: notification
-- Hộp thư thông báo trong ứng dụng cho người dùng
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.notification (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES eas.outbox_event(id) ON DELETE CASCADE,
    recipient_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT NULL,
    label varchar(150) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    read_at timestamptz NULL,
    CONSTRAINT uq_notification_event_recipient UNIQUE (event_id, recipient_id)
);

-- ----------------------------------------------------------------------------------------
-- DB28: idempotency_record
-- Bản ghi chống gọi lặp (Idempotency Key) cho mọi lệnh ghi
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.idempotency_record (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    command_scope varchar(200) NOT NULL,
    key varchar(64) NOT NULL,
    request_hash char(64) NOT NULL,
    http_status smallint NOT NULL,
    response_body jsonb NULL,
    request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    tombstone_until timestamptz NOT NULL,
    CONSTRAINT uq_idempotency_key UNIQUE (actor_id, command_scope, key)
);

-- ----------------------------------------------------------------------------------------
-- DB29: privacy_case
-- Yêu cầu quyền riêng tư và xử lý dữ liệu cá nhân theo pháp chế
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.privacy_case (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_user_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    case_type varchar(20) NOT NULL CHECK (case_type IN ('ACCESS', 'CORRECT', 'ERASE', 'RESTRICT', 'OBJECT')),
    status varchar(20) NOT NULL CHECK (status IN ('OPEN', 'REVIEW', 'APPROVED', 'REJECTED', 'DONE')),
    requested_at timestamptz NOT NULL DEFAULT now(),
    due_at timestamptz NOT NULL,
    completed_at timestamptz NULL,
    policy_version varchar(50) NOT NULL,
    owner_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    decision_reference varchar(200) NULL
);

-- ----------------------------------------------------------------------------------------
-- DB30: retention_hold
-- Lệnh giữ dữ liệu pháp lý (Chặn purge dữ liệu hồ sơ và tệp đính kèm)
-- ----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eas.retention_hold (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
    reason varchar(2000) NOT NULL,
    authority_reference varchar(200) NOT NULL,
    set_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    released_at timestamptz NULL,
    released_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT NULL
);

-- ========================================================================================
-- 4. CHỈ MỤC TỐI ƯU HIỆU NĂNG (INDEXES)
-- ========================================================================================
CREATE INDEX IF NOT EXISTS idx_request_requester ON eas.request(requester_id, updated_at DESC, id);
CREATE INDEX IF NOT EXISTS idx_request_status_type ON eas.request(status, type_id, updated_at DESC, id);
CREATE INDEX IF NOT EXISTS idx_request_revision_dept ON eas.request_revision(department_id, request_id);
CREATE INDEX IF NOT EXISTS idx_request_participant_user ON eas.request_participant(user_id, request_id);
CREATE INDEX IF NOT EXISTS idx_approval_step_assignee ON eas.approval_step(assignee_id, state);
CREATE INDEX IF NOT EXISTS idx_execution_attempt_executor ON eas.execution_attempt(executor_id, state);
CREATE INDEX IF NOT EXISTS idx_role_membership_user ON eas.role_membership(user_id, role, valid_from);
CREATE INDEX IF NOT EXISTS idx_sla_stage_open_due ON eas.sla_stage(due_at) WHERE closed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_outbox_event_queue ON eas.outbox_event(state, available_at, lease_until);
CREATE INDEX IF NOT EXISTS idx_notification_recipient ON eas.notification(recipient_id, read_at, created_at DESC, id);
CREATE INDEX IF NOT EXISTS idx_audit_event_request_seq ON eas.audit_event(request_id, seq);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON eas.idempotency_record(expires_at);

-- ========================================================================================
-- 5. SEED DATA KHỞI TẠO HỆ THỐNG BAN ĐẦU (BOOTSTRAP SEEDS)
-- ========================================================================================

-- Khởi tạo security epoch ban đầu
INSERT INTO eas.security_epoch (id, version, updated_at)
VALUES (1, 0, now())
ON CONFLICT (id) DO NOTHING;

-- Khởi tạo audit_head cho ADMIN
INSERT INTO eas.audit_head (scope_key, seq, last_hash)
VALUES ('ADMIN', 0, '0000000000000000000000000000000000000000000000000000000000000000')
ON CONFLICT (scope_key) DO NOTHING;

-- Khởi tạo các loại đơn chuẩn P0
INSERT INTO eas.request_type (id, code, lifecycle, is_active)
VALUES 
    ('11111111-1111-1111-1111-111111111101', 'LEAVE', 'A', true),
    ('11111111-1111-1111-1111-111111111102', 'ACCESS', 'B', true),
    ('11111111-1111-1111-1111-111111111103', 'EQUIPMENT', 'C', true)
ON CONFLICT (code) DO NOTHING;

-- Khởi tạo các phòng ban gốc
INSERT INTO eas.department (id, code, name, parent_id, is_active)
VALUES 
    ('22222222-2222-2222-2222-222222222201', 'HO', 'Ban Tổng Giám Đốc (Trụ sở chính)', NULL, true),
    ('22222222-2222-2222-2222-222222222202', 'TECH', 'Phòng Công Nghệ & Kỹ Thuật', '22222222-2222-2222-2222-222222222201', true),
    ('22222222-2222-2222-2222-222222222203', 'FIN', 'Phòng Tài Chính - Kế Toán', '22222222-2222-2222-2222-222222222201', true),
    ('22222222-2222-2222-2222-222222222204', 'HR', 'Phòng Hành Chính - Nhân Sự', '22222222-2222-2222-2222-222222222201', true),
    ('22222222-2222-2222-2222-222222222205', 'OPS', 'Phòng Vận Hành Thương Mại', '22222222-2222-2222-2222-222222222201', true)
ON CONFLICT (code) DO NOTHING;

-- Khởi tạo tài khoản Quản trị hệ thống mẫu (Mật khẩu mặc định: Admin@123456)
-- Hash PBKDF2/argon2 hoặc SHA-256 cơ bản; khi dùng Django/Supabase auth sẽ ánh xạ hoặc đổi lại
INSERT INTO eas.app_user (
    id, username, display_name, department_id, manager_id, 
    is_active, must_change_password, auth_version, password_hash
) VALUES (
    '33333333-3333-3333-3333-333333333301',
    'admin',
    'System Administrator',
    '22222222-2222-2222-2222-222222222201',
    NULL,
    true,
    true,
    1,
    'pbkdf2_sha256$600000$admin_salt$dummy_hash_for_bootstrap_change_on_first_login'
) ON CONFLICT (username) DO NOTHING;

-- Gán vai trò quản trị toàn cục (OPS_ADMIN và POLICY_ADMIN) theo đúng allowlist SRS
INSERT INTO eas.role_membership (
    id, user_id, role, scope_kind, department_id, type_scope, type_id, valid_from
) VALUES 
    ('44444444-4444-4444-4444-444444444401', '33333333-3333-3333-3333-333333333301', 'OPS_ADMIN', 'GLOBAL', NULL, 'ALL', NULL, now()),
    ('44444444-4444-4444-4444-444444444402', '33333333-3333-3333-3333-333333333301', 'POLICY_ADMIN', 'GLOBAL', NULL, 'ALL', NULL, now())
ON CONFLICT DO NOTHING;

-- ========================================================================================
-- HOÀN TẤT THIẾT KẾ CƠ SỞ DỮ LIỆU CHUẨN EAS V2.0
-- ========================================================================================
