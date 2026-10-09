-- EAS 2.0 / PostgreSQL on Supabase / schema migration 2.0.1
-- Generated 2026-09-22 from documents 00..05 v2.0; database layer only.
-- Run the WHOLE file as postgres/project database administrator, ONCE on a NEW eas schema.
-- PostgreSQL >=15. No extension required. Does not touch auth, storage or public.
-- Existing eas schema -> intentional error and full rollback; this is not an upgrade script.
-- No browser/Data API grants. Backend connects using a dedicated database login.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='120s';
SET LOCAL timezone='UTC';
DO $preflight$
DECLARE n text; r record;
BEGIN
 IF current_setting('server_version_num')::integer <150000 THEN
  RAISE EXCEPTION 'EAS requires PostgreSQL 15 or newer (NULLS NOT DISTINCT)';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='eas') THEN
  RAISE EXCEPTION 'Schema eas already exists. Do not rerun or drop data; use a reviewed upgrade migration.';
 END IF;
 FOREACH n IN ARRAY ARRAY['eas_migration','eas_api','eas_worker','eas_backup','eas_privacy'] LOOP
  SELECT * INTO r FROM pg_roles WHERE rolname=n;
  IF FOUND THEN
   RAISE EXCEPTION 'Role % already exists. Initial installer refuses to reuse an unreviewed role.',n;
  END IF;
  EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',n);
  EXECUTE format('GRANT %I TO %I',n,current_user);
 END LOOP;
END
$preflight$;
CREATE SCHEMA eas AUTHORIZATION eas_migration;
SET LOCAL ROLE eas_migration;
REVOKE ALL ON SCHEMA eas FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA eas REVOKE ALL ON SEQUENCES FROM PUBLIC;
CREATE SEQUENCE eas.request_code_seq AS bigint START WITH 1 NO CYCLE;
CREATE FUNCTION eas.next_request_code() RETURNS varchar(40)
LANGUAGE sql VOLATILE SET search_path=pg_catalog,eas
AS $$ SELECT ('EAS-'||to_char(clock_timestamp() AT TIME ZONE 'Asia/Ho_Chi_Minh','YYYY')||'-'||lpad(n::text,greatest(6,length(n::text)),'0'))::varchar(40)
      FROM (SELECT nextval('eas.request_code_seq'::regclass) AS n) s $$;


-- DB01 security_epoch
CREATE TABLE eas.security_epoch (
id smallint PRIMARY KEY DEFAULT 1 CHECK (id=1),
version bigint NOT NULL DEFAULT 0 CHECK (version>=0),
updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE eas.security_epoch IS 'DB01 — Một hàng khóa dùng chung cho thay đổi quyền và lệnh nghiệp vụ.';

-- DB02 department
CREATE TABLE eas.department (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
code varchar(30) NOT NULL UNIQUE CHECK (code=btrim(code) AND length(code)>0),
name varchar(150) NOT NULL CHECK (length(btrim(name))>0),
parent_id uuid REFERENCES eas.department(id) ON DELETE RESTRICT,
is_active boolean NOT NULL DEFAULT true,
CONSTRAINT department_no_self CHECK (parent_id IS NULL OR parent_id<>id)
);
COMMENT ON TABLE eas.department IS 'DB02 — Phòng ban; scope phòng không tự bao gồm phòng con.';

-- DB03 app_user
CREATE TABLE eas.app_user (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
username varchar(80) NOT NULL UNIQUE CHECK (username=lower(btrim(username)) AND length(username)>0),
display_name varchar(150) NOT NULL CHECK (length(btrim(display_name))>0),
department_id uuid NOT NULL REFERENCES eas.department(id) ON DELETE RESTRICT,
manager_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
is_active boolean NOT NULL DEFAULT true,
must_change_password boolean NOT NULL DEFAULT true,
auth_version bigint NOT NULL DEFAULT 0 CHECK (auth_version>=0),
password_hash text NOT NULL CHECK (length(password_hash)>0),
created_at timestamptz NOT NULL DEFAULT now(),
CONSTRAINT user_no_self_manager CHECK (manager_id IS NULL OR manager_id<>id)
);
COMMENT ON TABLE eas.app_user IS 'DB03 — Tài khoản backend, không phải auth.users của Supabase; hash Argon2 do backend tạo.';

-- DB05 request_type
CREATE TABLE eas.request_type (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
code varchar(30) NOT NULL UNIQUE,
lifecycle char(1) NOT NULL,
is_active boolean NOT NULL DEFAULT true,
active_release_id uuid,
CONSTRAINT type_p0 CHECK ((code='LEAVE' AND lifecycle='A') OR (code='ACCESS' AND lifecycle='B') OR (code='EQUIPMENT' AND lifecycle='C'))
);
COMMENT ON TABLE eas.request_type IS 'DB05 — Ba loại hồ sơ P0. Con trỏ release được gắn FK sau khi tạo config_release.';

-- DB04 role_membership
CREATE TABLE eas.role_membership (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
user_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
role varchar(24) NOT NULL CHECK (role IN ('REQUESTER','APPROVER','EXECUTOR','ACCEPTOR','POLICY_ADMIN','OPS_ADMIN','AUDITOR')),
scope_kind varchar(12) NOT NULL CHECK (scope_kind IN ('GLOBAL','DEPARTMENT')),
department_id uuid REFERENCES eas.department(id) ON DELETE RESTRICT,
type_scope varchar(3) NOT NULL CHECK (type_scope IN ('ALL','ONE')),
type_id uuid REFERENCES eas.request_type(id) ON DELETE RESTRICT,
valid_from timestamptz NOT NULL DEFAULT now(),
valid_to timestamptz,
revoked_at timestamptz,
CONSTRAINT role_department_scope CHECK ((scope_kind='GLOBAL' AND department_id IS NULL) OR (scope_kind='DEPARTMENT' AND department_id IS NOT NULL)),
CONSTRAINT role_type_scope CHECK ((type_scope='ALL' AND type_id IS NULL) OR (type_scope='ONE' AND type_id IS NOT NULL)),
CONSTRAINT role_valid_interval CHECK (valid_to IS NULL OR valid_to>valid_from),
CONSTRAINT role_unique_grant UNIQUE NULLS NOT DISTINCT (user_id,role,scope_kind,department_id,type_scope,type_id,valid_from)
);
COMMENT ON TABLE eas.role_membership IS 'DB04 — Quyền nghiệp vụ theo người, phòng, loại và khoảng hiệu lực; khác PostgreSQL role.';

-- DB06 config_release
CREATE TABLE eas.config_release (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
type_id uuid NOT NULL REFERENCES eas.request_type(id) ON DELETE RESTRICT,
version integer NOT NULL CHECK (version>0),
state varchar(9) NOT NULL DEFAULT 'DRAFT' CHECK (state IN ('DRAFT','PUBLISHED')),
lifecycle char(1) NOT NULL CHECK (lifecycle IN ('A','B','C')),
form_schema jsonb NOT NULL CHECK (jsonb_typeof(form_schema)='object'),
route_rules jsonb NOT NULL CHECK (jsonb_typeof(route_rules)='object'),
actor_bindings jsonb NOT NULL CHECK (jsonb_typeof(actor_bindings)='object'),
sla_profile jsonb NOT NULL CHECK (jsonb_typeof(sla_profile)='object'),
created_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
published_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
created_at timestamptz NOT NULL DEFAULT now(),
published_at timestamptz,
lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version>=0),
content_sha256 char(64),
CONSTRAINT release_version_unique UNIQUE (type_id,version),
CONSTRAINT release_same_type_key UNIQUE (id,type_id),
CONSTRAINT release_publish_fields CHECK ((state='DRAFT' AND published_by IS NULL AND published_at IS NULL AND content_sha256 IS NULL) OR (state='PUBLISHED' AND published_by IS NOT NULL AND published_at IS NOT NULL AND content_sha256 IS NOT NULL)),
CONSTRAINT release_hash_format CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
CONSTRAINT release_publish_time CHECK (published_at IS NULL OR published_at>=created_at)
);
COMMENT ON TABLE eas.config_release IS 'DB06 — Snapshot cấu hình; bốn JSON đều có schema_version=1 khi publish; published bất biến.';

-- DB07 request
CREATE TABLE eas.request (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
code varchar(40) NOT NULL UNIQUE DEFAULT eas.next_request_code(),
requester_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
type_id uuid NOT NULL REFERENCES eas.request_type(id) ON DELETE RESTRICT,
status varchar(32) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','NEEDS_INFO','PENDING_APPROVAL','READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE','COMPLETED','REJECTED','CANCELLED')),
draft_payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(draft_payload)='object'),
draft_amount_vnd bigint CHECK (draft_amount_vnd BETWEEN 1 AND 1000000000000),
draft_release_id uuid,
origin_request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT,
current_revision_id uuid,
lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version>=0),
created_at timestamptz NOT NULL DEFAULT now(),
updated_at timestamptz NOT NULL DEFAULT now(),
approved_at timestamptz,
completed_at timestamptz,
CONSTRAINT request_draft_release_type FOREIGN KEY (draft_release_id,type_id) REFERENCES eas.config_release(id,type_id) ON DELETE RESTRICT,
CONSTRAINT request_no_self_origin CHECK (origin_request_id IS NULL OR origin_request_id<>id),
CONSTRAINT request_update_time CHECK (updated_at>=created_at),
CONSTRAINT request_complete_time CHECK ((status='COMPLETED')=(completed_at IS NOT NULL)),
CONSTRAINT request_completed_after_approval CHECK (completed_at IS NULL OR (approved_at IS NOT NULL AND completed_at>=approved_at)),
CONSTRAINT request_approved_time CHECK (approved_at IS NULL OR approved_at>=created_at),
CONSTRAINT request_approval_required CHECK (status NOT IN ('READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE','COMPLETED') OR approved_at IS NOT NULL)
);
COMMENT ON TABLE eas.request IS 'DB07 — Hồ sơ hiện hành. Mã dùng sequence toàn cục có thể có khoảng trống; không reset theo năm.';

-- DB08 request_revision
CREATE TABLE eas.request_revision (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
revision_no integer NOT NULL CHECK (revision_no>0),
release_id uuid NOT NULL REFERENCES eas.config_release(id) ON DELETE RESTRICT,
department_id uuid NOT NULL REFERENCES eas.department(id) ON DELETE RESTRICT,
payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
amount_vnd bigint CHECK (amount_vnd BETWEEN 1 AND 1000000000000),
submitted_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
submitted_at timestamptz NOT NULL DEFAULT now(),
payload_sha256 char(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
UNIQUE (request_id,revision_no),
UNIQUE (id,request_id)
);
COMMENT ON TABLE eas.request_revision IS 'DB08 — Revision bất biến, chụp phòng, dữ liệu và release mỗi lần gửi.';

-- DB09 workflow_instance
CREATE TABLE eas.workflow_instance (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
revision_id uuid NOT NULL UNIQUE,
matched_rule_id varchar(50) NOT NULL CHECK (length(btrim(matched_rule_id))>0),
resolved_route jsonb NOT NULL CHECK (jsonb_typeof(resolved_route)='array' AND jsonb_array_length(resolved_route) BETWEEN 1 AND 3),
lifecycle char(1) NOT NULL CHECK (lifecycle IN ('A','B','C')),
state varchar(10) NOT NULL DEFAULT 'ACTIVE' CHECK (state IN ('ACTIVE','COMPLETED','REJECTED','SUPERSEDED','CANCELLED')),
planned_executor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
acceptor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
created_at timestamptz NOT NULL DEFAULT now(),
closed_at timestamptz,
CONSTRAINT instance_revision_same_request FOREIGN KEY (revision_id,request_id) REFERENCES eas.request_revision(id,request_id) ON DELETE RESTRICT,
UNIQUE (id,request_id),
CONSTRAINT instance_lifecycle_actors CHECK ((lifecycle='A' AND planned_executor_id IS NULL AND acceptor_id IS NULL) OR (lifecycle='B' AND planned_executor_id IS NOT NULL AND acceptor_id IS NULL) OR (lifecycle='C' AND planned_executor_id IS NOT NULL AND acceptor_id IS NOT NULL)),
CONSTRAINT instance_closed CHECK ((state='ACTIVE' AND closed_at IS NULL) OR (state<>'ACTIVE' AND closed_at IS NOT NULL AND closed_at>=created_at))
);
COMMENT ON TABLE eas.workflow_instance IS 'DB09 — Một instance cho mỗi revision; resolved_route là mảng actor ban đầu, gán thay không sửa snapshot.';

-- DB10 request_participant
CREATE TABLE eas.request_participant (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
user_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
first_joined_at timestamptz NOT NULL DEFAULT now(),
joined_as varchar(24) NOT NULL CHECK (joined_as IN ('REQUESTER','APPROVER','EXECUTOR','ACCEPTOR')),
read_revoked_at timestamptz,
read_revoked_reason varchar(2000),
UNIQUE (request_id,user_id),
CONSTRAINT participant_revocation CHECK ((read_revoked_at IS NULL AND read_revoked_reason IS NULL) OR (read_revoked_at IS NOT NULL AND read_revoked_reason IS NOT NULL AND length(btrim(read_revoked_reason)) BETWEEN 10 AND 2000))
);
COMMENT ON TABLE eas.request_participant IS 'DB10 — Lịch sử tham gia và quyền đọc độc lập với role nghiệp vụ.';

-- DB11 approval_step
CREATE TABLE eas.approval_step (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
instance_id uuid NOT NULL,
step_no smallint NOT NULL CHECK (step_no BETWEEN 1 AND 3),
assignee_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
state varchar(10) NOT NULL DEFAULT 'WAITING' CHECK (state IN ('WAITING','ACTIVE','APPROVED','REJECTED','NEEDS_INFO','SKIPPED')),
activated_at timestamptz,
closed_at timestamptz,
CONSTRAINT step_instance_same_request FOREIGN KEY (instance_id,request_id) REFERENCES eas.workflow_instance(id,request_id) ON DELETE RESTRICT,
UNIQUE (instance_id,step_no),
UNIQUE (instance_id,assignee_id),
UNIQUE (id,request_id),
CONSTRAINT step_state_times CHECK ((state='WAITING' AND activated_at IS NULL AND closed_at IS NULL) OR (state='ACTIVE' AND activated_at IS NOT NULL AND closed_at IS NULL) OR (state IN ('APPROVED','REJECTED','NEEDS_INFO') AND activated_at IS NOT NULL AND closed_at IS NOT NULL) OR (state='SKIPPED' AND closed_at IS NOT NULL)),
CONSTRAINT step_time_order CHECK (closed_at IS NULL OR activated_at IS NULL OR closed_at>=activated_at)
);
COMMENT ON TABLE eas.approval_step IS 'DB11 — Cấp duyệt 1–3; một ACTIVE; người duyệt trong cùng instance khác nhau.';

-- DB12 approval_decision
CREATE TABLE eas.approval_decision (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
step_id uuid NOT NULL UNIQUE,
actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
outcome varchar(10) NOT NULL CHECK (outcome IN ('APPROVE','REJECT','NEEDS_INFO')),
reason varchar(2000),
decided_at timestamptz NOT NULL DEFAULT now(),
CONSTRAINT decision_step_same_request FOREIGN KEY (step_id,request_id) REFERENCES eas.approval_step(id,request_id) ON DELETE RESTRICT,
CONSTRAINT decision_reason CHECK (outcome='APPROVE' OR (reason IS NOT NULL AND length(btrim(reason)) BETWEEN 10 AND 2000))
);
COMMENT ON TABLE eas.approval_decision IS 'DB12 — Quyết định duyệt append only; ghi trước khi đóng step trong transaction service.';

-- DB13 execution_attempt
CREATE TABLE eas.execution_attempt (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
instance_id uuid NOT NULL,
attempt_no integer NOT NULL CHECK (attempt_no>0),
executor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
state varchar(9) NOT NULL DEFAULT 'READY' CHECK (state IN ('READY','RUNNING','SUBMITTED','FINISHED')),
closure_kind varchar(10) CHECK (closure_kind IN ('SUCCESS','ACCEPTED','REWORK','REASSIGNED')),
result_note varchar(4000),
external_reference varchar(200),
started_at timestamptz,
submitted_at timestamptz,
closed_at timestamptz,
CONSTRAINT attempt_instance_same_request FOREIGN KEY (instance_id,request_id) REFERENCES eas.workflow_instance(id,request_id) ON DELETE RESTRICT,
UNIQUE (instance_id,attempt_no),
UNIQUE (id,request_id),
CONSTRAINT attempt_closure CHECK ((state='FINISHED' AND closure_kind IS NOT NULL AND closed_at IS NOT NULL) OR (state<>'FINISHED' AND closure_kind IS NULL AND closed_at IS NULL)),
CONSTRAINT attempt_progress CHECK ((state='READY' AND started_at IS NULL AND submitted_at IS NULL) OR (state='RUNNING' AND started_at IS NOT NULL AND submitted_at IS NULL) OR (state='SUBMITTED' AND started_at IS NOT NULL AND submitted_at IS NOT NULL) OR (state='FINISHED' AND started_at IS NOT NULL)),
CONSTRAINT attempt_result CHECK ((submitted_at IS NULL AND result_note IS NULL AND external_reference IS NULL) OR (submitted_at IS NOT NULL AND result_note IS NOT NULL AND length(btrim(result_note)) BETWEEN 10 AND 4000 AND external_reference IS NOT NULL AND length(btrim(external_reference)) BETWEEN 1 AND 200)),
CONSTRAINT attempt_finished_result CHECK (state<>'FINISHED' OR (closure_kind='REASSIGNED' AND submitted_at IS NULL) OR (closure_kind IN ('SUCCESS','ACCEPTED','REWORK') AND submitted_at IS NOT NULL)),
CONSTRAINT attempt_time_order CHECK ((submitted_at IS NULL OR submitted_at>=started_at) AND (closed_at IS NULL OR closed_at>=started_at) AND (closed_at IS NULL OR submitted_at IS NULL OR closed_at>=submitted_at))
);
COMMENT ON TABLE eas.execution_attempt IS 'DB13 — Vòng thực hiện; REWORK và đổi executor RUNNING tạo vòng mới; kết quả đã nộp bất biến.';

-- DB14 acceptance_decision
CREATE TABLE eas.acceptance_decision (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
attempt_id uuid NOT NULL UNIQUE,
actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
outcome varchar(6) NOT NULL CHECK (outcome IN ('ACCEPT','REWORK')),
reason varchar(2000),
decided_at timestamptz NOT NULL DEFAULT now(),
CONSTRAINT acceptance_attempt_same_request FOREIGN KEY (attempt_id,request_id) REFERENCES eas.execution_attempt(id,request_id) ON DELETE RESTRICT,
CONSTRAINT acceptance_reason CHECK (outcome='ACCEPT' OR (reason IS NOT NULL AND length(btrim(reason)) BETWEEN 10 AND 2000))
);
COMMENT ON TABLE eas.acceptance_decision IS 'DB14 — Nghiệm thu C; actor khác executor thực tế; một quyết định mỗi attempt.';

-- DB15 execution_issue
CREATE TABLE eas.execution_issue (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
attempt_id uuid NOT NULL,
actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
kind varchar(15) NOT NULL CHECK (kind IN ('UNABLE_TO_CLAIM','BLOCKED')),
reason varchar(2000) NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 2000),
created_at timestamptz NOT NULL DEFAULT now(),
CONSTRAINT issue_attempt_same_request FOREIGN KEY (attempt_id,request_id) REFERENCES eas.execution_attempt(id,request_id) ON DELETE RESTRICT
);
COMMENT ON TABLE eas.execution_issue IS 'DB15 — Sự kiện báo vướng; không phải trạng thái riêng và không dừng SLA.';

-- DB16 attachment
CREATE TABLE eas.attachment (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
uploader_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
storage_key varchar(300) NOT NULL UNIQUE CHECK (length(storage_key)>0),
object_version varchar(200) NOT NULL CHECK (length(object_version)>0),
original_name varchar(150) NOT NULL CHECK (length(btrim(original_name))>0 AND position('/' in original_name)=0 AND position(chr(92) in original_name)=0 AND position('..' in original_name)=0),
mime varchar(80) NOT NULL CHECK (mime IN ('application/pdf','image/jpeg','image/png')),
size_bytes bigint NOT NULL CHECK (size_bytes BETWEEN 1 AND 10485760),
sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
scan_state varchar(8) NOT NULL DEFAULT 'QUEUED' CHECK (scan_state IN ('QUEUED','CLEAN','INFECTED','ERROR')),
scan_attempts integer NOT NULL DEFAULT 0 CHECK (scan_attempts BETWEEN 0 AND 3),
created_at timestamptz NOT NULL DEFAULT now(),
scanned_at timestamptz,
deleted_at timestamptz,
UNIQUE (id,request_id),
CONSTRAINT attachment_scan_time CHECK (scan_state='QUEUED' OR (scanned_at IS NOT NULL AND scan_attempts>=1)),
CONSTRAINT attachment_times CHECK ((scanned_at IS NULL OR scanned_at>=created_at) AND (deleted_at IS NULL OR deleted_at>=created_at))
);
COMMENT ON TABLE eas.attachment IS 'DB16 — Metadata tệp riêng tư; không tạo object/bucket; object_version là phiên bản thực của kho lưu trữ.';

-- DB17 draft_attachment
CREATE TABLE eas.draft_attachment (
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
attachment_id uuid NOT NULL,
added_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
added_at timestamptz NOT NULL DEFAULT now(),
PRIMARY KEY (request_id,attachment_id),
CONSTRAINT draft_file_same_request FOREIGN KEY (attachment_id,request_id) REFERENCES eas.attachment(id,request_id) ON DELETE RESTRICT
);
COMMENT ON TABLE eas.draft_attachment IS 'DB17 — Tập tệp nháp, có thể bỏ chọn mà không xóa tệp lịch sử.';

-- DB18 revision_attachment
CREATE TABLE eas.revision_attachment (
revision_id uuid NOT NULL,
attachment_id uuid NOT NULL,
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
PRIMARY KEY (revision_id,attachment_id),
CONSTRAINT revision_link_same_request FOREIGN KEY (revision_id,request_id) REFERENCES eas.request_revision(id,request_id) ON DELETE RESTRICT,
CONSTRAINT revision_file_same_request FOREIGN KEY (attachment_id,request_id) REFERENCES eas.attachment(id,request_id) ON DELETE RESTRICT
);
COMMENT ON TABLE eas.revision_attachment IS 'DB18 — Tệp chụp theo revision; append only.';

-- DB19 execution_attachment
CREATE TABLE eas.execution_attachment (
attempt_id uuid NOT NULL,
attachment_id uuid NOT NULL,
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
PRIMARY KEY (attempt_id,attachment_id),
CONSTRAINT execution_link_same_request FOREIGN KEY (attempt_id,request_id) REFERENCES eas.execution_attempt(id,request_id) ON DELETE RESTRICT,
CONSTRAINT execution_file_same_request FOREIGN KEY (attachment_id,request_id) REFERENCES eas.attachment(id,request_id) ON DELETE RESTRICT
);
COMMENT ON TABLE eas.execution_attachment IS 'DB19 — Bằng chứng do executor upload; thêm trong lúc RUNNING trước khi nộp kết quả.';

-- DB20 sla_stage
CREATE TABLE eas.sla_stage (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
kind varchar(10) NOT NULL CHECK (kind IN ('APPROVAL','EXECUTION','ACCEPTANCE')),
approval_step_id uuid,
attempt_id uuid,
started_at timestamptz NOT NULL DEFAULT now(),
due_at timestamptz NOT NULL,
closed_at timestamptz,
breached_at timestamptz,
CONSTRAINT sla_step_same_request FOREIGN KEY (approval_step_id,request_id) REFERENCES eas.approval_step(id,request_id) ON DELETE RESTRICT,
CONSTRAINT sla_attempt_same_request FOREIGN KEY (attempt_id,request_id) REFERENCES eas.execution_attempt(id,request_id) ON DELETE RESTRICT,
CONSTRAINT sla_subtype CHECK ((kind='APPROVAL' AND approval_step_id IS NOT NULL AND attempt_id IS NULL) OR (kind IN ('EXECUTION','ACCEPTANCE') AND approval_step_id IS NULL AND attempt_id IS NOT NULL)),
CONSTRAINT sla_time_order CHECK (due_at>started_at AND (closed_at IS NULL OR closed_at>=started_at)),
CONSTRAINT sla_breach_time CHECK (breached_at IS NULL OR breached_at=due_at),
UNIQUE (id,request_id)
);
COMMENT ON TABLE eas.sla_stage IS 'DB20 — Một stage mở/request; gán thay giữ ID và due_at, chỉ cập nhật target attempt khi cần.';

-- DB21 sla_alert
CREATE TABLE eas.sla_alert (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
stage_id uuid NOT NULL,
kind varchar(8) NOT NULL CHECK (kind IN ('REMINDER','BREACH')),
created_at timestamptz NOT NULL DEFAULT now(),
CONSTRAINT alert_stage_same_request FOREIGN KEY (stage_id,request_id) REFERENCES eas.sla_stage(id,request_id) ON DELETE RESTRICT,
UNIQUE (stage_id,kind)
);
COMMENT ON TABLE eas.sla_alert IS 'DB21 — Khử trùng reminder/breach theo stage.';

-- DB24 audit_head
CREATE TABLE eas.audit_head (
scope_key varchar(100) PRIMARY KEY CHECK (scope_key='ADMIN' OR scope_key ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
seq bigint NOT NULL DEFAULT 0 CHECK (seq>=0),
last_hash char(64) NOT NULL DEFAULT repeat('0',64) CHECK (last_hash ~ '^[0-9a-f]{64}$'),
CONSTRAINT head_genesis CHECK (seq<>0 OR last_hash=repeat('0',64))
);
COMMENT ON TABLE eas.audit_head IS 'DB24 — Đầu chuỗi; trigger append cập nhật nguyên tử, không thay checkpoint ngoài DB.';

-- DB22 audit_event
CREATE TABLE eas.audit_event (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
seq bigint NOT NULL CHECK (seq>0),
actor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
actor_kind varchar(6) NOT NULL CHECK (actor_kind IN ('HUMAN','SYSTEM')),
action varchar(80) NOT NULL CHECK (length(btrim(action))>0),
target_type varchar(40) NOT NULL CHECK (length(btrim(target_type))>0),
target_id uuid NOT NULL,
details jsonb NOT NULL CHECK (jsonb_typeof(details)='object'),
correlation_id uuid NOT NULL,
occurred_at timestamptz NOT NULL DEFAULT now(),
hash_version smallint NOT NULL DEFAULT 1 CHECK (hash_version=1),
prev_hash char(64) NOT NULL CHECK (prev_hash ~ '^[0-9a-f]{64}$'),
hash char(64) NOT NULL CHECK (hash ~ '^[0-9a-f]{64}$'),
CONSTRAINT audit_actor_kind CHECK ((actor_kind='HUMAN' AND actor_id IS NOT NULL) OR (actor_kind='SYSTEM' AND actor_id IS NULL)),
UNIQUE (request_id,seq)
);
COMMENT ON TABLE eas.audit_event IS 'DB22 — Audit request; backend cung cấp SHA256 RFC8785/NFC, DB kiểm seq/prev_hash dưới khóa.';

-- DB23 admin_event
CREATE TABLE eas.admin_event (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
seq bigint NOT NULL UNIQUE CHECK (seq>0),
actor_id uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
actor_kind varchar(6) NOT NULL CHECK (actor_kind IN ('HUMAN','SYSTEM')),
action varchar(80) NOT NULL CHECK (length(btrim(action))>0),
target_type varchar(40) NOT NULL CHECK (length(btrim(target_type))>0),
target_id varchar(100) NOT NULL CHECK (length(btrim(target_id))>0),
department_id uuid REFERENCES eas.department(id) ON DELETE RESTRICT,
type_id uuid REFERENCES eas.request_type(id) ON DELETE RESTRICT,
details jsonb NOT NULL CHECK (jsonb_typeof(details)='object'),
reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 2000),
correlation_id uuid NOT NULL,
occurred_at timestamptz NOT NULL DEFAULT now(),
hash_version smallint NOT NULL DEFAULT 1 CHECK (hash_version=1),
prev_hash char(64) NOT NULL CHECK (prev_hash ~ '^[0-9a-f]{64}$'),
hash char(64) NOT NULL CHECK (hash ~ '^[0-9a-f]{64}$'),
CONSTRAINT admin_actor_kind CHECK ((actor_kind='HUMAN' AND actor_id IS NOT NULL) OR (actor_kind='SYSTEM' AND actor_id IS NULL))
);
COMMENT ON TABLE eas.admin_event IS 'DB23 — Audit cấu hình/quyền/vận hành; không cần request giả; một chuỗi ADMIN.';

-- DB25 audit_checkpoint
CREATE TABLE eas.audit_checkpoint (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
scope_key varchar(100) NOT NULL CHECK (scope_key='ADMIN' OR scope_key ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
seq bigint NOT NULL CHECK (seq>=0),
hash char(64) NOT NULL CHECK (hash ~ '^[0-9a-f]{64}$'),
external_object_key varchar(300) NOT NULL CHECK (length(external_object_key)>0),
external_version varchar(200) NOT NULL CHECK (length(external_version)>0),
captured_at timestamptz NOT NULL DEFAULT now(),
UNIQUE (scope_key,seq)
);
COMMENT ON TABLE eas.audit_checkpoint IS 'DB25 — Con trỏ checkpoint bên ngoài; không FK audit_head để giữ chứng cứ theo retention riêng.';

-- DB26 outbox_event
CREATE TABLE eas.outbox_event (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT,
event_type varchar(80) NOT NULL CHECK (length(btrim(event_type))>0),
payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
state varchar(10) NOT NULL DEFAULT 'PENDING' CHECK (state IN ('PENDING','PROCESSING','SENT','DEAD')),
dedupe_key varchar(200) NOT NULL UNIQUE CHECK (length(dedupe_key)>0),
attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 4),
replay_count integer NOT NULL DEFAULT 0 CHECK (replay_count>=0),
available_at timestamptz NOT NULL DEFAULT now(),
lease_token uuid,
lease_until timestamptz,
created_at timestamptz NOT NULL DEFAULT now(),
sent_at timestamptz,
last_error_code varchar(80),
CONSTRAINT outbox_lease CHECK ((state='PROCESSING' AND lease_token IS NOT NULL AND lease_until IS NOT NULL AND attempts>=1) OR (state<>'PROCESSING' AND lease_token IS NULL AND lease_until IS NULL)),
CONSTRAINT outbox_sent CHECK ((state='SENT')=(sent_at IS NOT NULL)),
CONSTRAINT outbox_dead CHECK (state<>'DEAD' OR attempts=4),
CONSTRAINT outbox_sent_time CHECK (sent_at IS NULL OR sent_at>=created_at)
);
COMMENT ON TABLE eas.outbox_event IS 'DB26 — Outbox bốn lần thử mỗi chu kỳ; lease và ACK do worker; payload chỉ metadata tối thiểu.';

-- DB27 notification
CREATE TABLE eas.notification (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
event_id uuid NOT NULL REFERENCES eas.outbox_event(id) ON DELETE RESTRICT,
recipient_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT,
label varchar(150) NOT NULL CHECK (length(btrim(label))>0),
created_at timestamptz NOT NULL DEFAULT now(),
read_at timestamptz,
UNIQUE (event_id,recipient_id),
CONSTRAINT notification_read_time CHECK (read_at IS NULL OR read_at>=created_at)
);
COMMENT ON TABLE eas.notification IS 'DB27 — Thông báo của recipient; read_at lần đầu bất biến; request phải khớp event kể cả NULL.';

-- DB28 idempotency_record
CREATE TABLE eas.idempotency_record (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
actor_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
command_scope varchar(200) NOT NULL CHECK (length(command_scope)>0),
key varchar(64) NOT NULL CHECK (key ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
http_status smallint NOT NULL CHECK (http_status BETWEEN 200 AND 299),
response_body jsonb,
request_id uuid REFERENCES eas.request(id) ON DELETE RESTRICT,
created_at timestamptz NOT NULL DEFAULT now(),
expires_at timestamptz NOT NULL DEFAULT (now()+interval '7 days'),
tombstone_until timestamptz NOT NULL DEFAULT (now()+interval '30 days'),
UNIQUE (actor_id,command_scope,key),
CONSTRAINT idempotency_time_order CHECK (expires_at>created_at AND tombstone_until>expires_at)
);
COMMENT ON TABLE eas.idempotency_record IS 'DB28 — Lưu kết quả thành công 7 ngày; tombstone 30 ngày; không dedupe vô hạn.';

-- DB29 privacy_case
CREATE TABLE eas.privacy_case (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
subject_user_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
case_type varchar(8) NOT NULL CHECK (case_type IN ('ACCESS','CORRECT','ERASE','RESTRICT','OBJECT')),
status varchar(8) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','REVIEW','APPROVED','REJECTED','DONE')),
requested_at timestamptz NOT NULL DEFAULT now(),
due_at timestamptz NOT NULL,
completed_at timestamptz,
policy_version varchar(50) NOT NULL CHECK (length(btrim(policy_version))>0),
owner_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
decision_reference varchar(200),
CONSTRAINT privacy_due CHECK (due_at>requested_at),
CONSTRAINT privacy_done CHECK ((status='DONE')=(completed_at IS NOT NULL)),
CONSTRAINT privacy_completed_time CHECK (completed_at IS NULL OR completed_at>=requested_at),
CONSTRAINT privacy_decision_ref CHECK (status NOT IN ('APPROVED','REJECTED','DONE') OR (decision_reference IS NOT NULL AND length(btrim(decision_reference))>0))
);
COMMENT ON TABLE eas.privacy_case IS 'DB29 — Hồ sơ quyền dữ liệu; pháp chế đặt due_at, không có thời hạn pháp lý mặc định.';

-- DB30 retention_hold
CREATE TABLE eas.retention_hold (
id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE RESTRICT,
reason varchar(2000) NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 2000),
authority_reference varchar(200) NOT NULL CHECK (length(btrim(authority_reference))>0),
set_by uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
created_at timestamptz NOT NULL DEFAULT now(),
released_at timestamptz,
released_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
CONSTRAINT hold_release_fields CHECK ((released_at IS NULL AND released_by IS NULL) OR (released_at IS NOT NULL AND released_by IS NOT NULL AND released_at>=created_at))
);
COMMENT ON TABLE eas.retention_hold IS 'DB30 — Legal hold; chỉ nhả hold theo phê duyệt, không tự xóa để purge.';


ALTER TABLE eas.request_type ADD CONSTRAINT type_active_release_same_type
 FOREIGN KEY (active_release_id,id) REFERENCES eas.config_release(id,type_id) ON DELETE RESTRICT;
ALTER TABLE eas.request ADD CONSTRAINT request_current_revision_same_request
 FOREIGN KEY (current_revision_id,id) REFERENCES eas.request_revision(id,request_id)
 ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
CREATE UNIQUE INDEX one_active_instance ON eas.workflow_instance(request_id) WHERE state='ACTIVE';
CREATE UNIQUE INDEX one_active_step ON eas.approval_step(instance_id) WHERE state='ACTIVE';
CREATE UNIQUE INDEX one_current_attempt ON eas.execution_attempt(instance_id) WHERE state IN ('READY','RUNNING','SUBMITTED');
CREATE UNIQUE INDEX one_open_stage ON eas.sla_stage(request_id) WHERE closed_at IS NULL;
CREATE INDEX request_owner_updated ON eas.request(requester_id,updated_at DESC,id DESC);
CREATE INDEX request_status_type_updated ON eas.request(status,type_id,updated_at DESC,id DESC);
CREATE INDEX revision_department_request ON eas.request_revision(department_id,request_id);
CREATE INDEX participant_user_request ON eas.request_participant(user_id,request_id);
CREATE INDEX approval_inbox ON eas.approval_step(assignee_id,state);
CREATE INDEX execution_inbox ON eas.execution_attempt(executor_id,state);
CREATE INDEX role_lookup ON eas.role_membership(user_id,role,valid_from);
CREATE INDEX sla_open_due ON eas.sla_stage(due_at) WHERE closed_at IS NULL;
CREATE INDEX outbox_due ON eas.outbox_event(state,available_at,lease_until);
CREATE INDEX notification_inbox ON eas.notification(recipient_id,read_at,created_at DESC,id DESC);
CREATE INDEX idempotency_expiry ON eas.idempotency_record(tombstone_until);
CREATE INDEX attachment_scan_queue ON eas.attachment(scan_state,created_at) WHERE deleted_at IS NULL;
CREATE INDEX hold_open_request ON eas.retention_hold(request_id) WHERE released_at IS NULL;
CREATE INDEX privacy_due_open ON eas.privacy_case(due_at) WHERE status IN ('OPEN','REVIEW','APPROVED');
-- Supporting indexes for referencing keys. UNIQUE/PK indexes are not duplicated below.
CREATE INDEX ix_department_parent_id ON eas.department(parent_id);
CREATE INDEX ix_app_user_department_id ON eas.app_user(department_id);
CREATE INDEX ix_app_user_manager_id ON eas.app_user(manager_id);
CREATE INDEX ix_request_type_active_release_id ON eas.request_type(active_release_id);
CREATE INDEX ix_role_membership_department_id ON eas.role_membership(department_id);
CREATE INDEX ix_role_membership_type_id ON eas.role_membership(type_id);
CREATE INDEX ix_config_release_created_by ON eas.config_release(created_by);
CREATE INDEX ix_config_release_published_by ON eas.config_release(published_by);
CREATE INDEX ix_request_type_id ON eas.request(type_id);
CREATE INDEX ix_request_draft_release_id ON eas.request(draft_release_id);
CREATE INDEX ix_request_origin_request_id ON eas.request(origin_request_id);
CREATE INDEX ix_request_current_revision_id ON eas.request(current_revision_id);
CREATE INDEX ix_request_revision_release_id ON eas.request_revision(release_id);
CREATE INDEX ix_request_revision_submitted_by ON eas.request_revision(submitted_by);
CREATE INDEX ix_workflow_instance_request_id ON eas.workflow_instance(request_id);
CREATE INDEX ix_workflow_instance_planned_executor_id ON eas.workflow_instance(planned_executor_id);
CREATE INDEX ix_workflow_instance_acceptor_id ON eas.workflow_instance(acceptor_id);
CREATE INDEX ix_approval_step_request_id ON eas.approval_step(request_id);
CREATE INDEX ix_approval_decision_request_id ON eas.approval_decision(request_id);
CREATE INDEX ix_approval_decision_actor_id ON eas.approval_decision(actor_id);
CREATE INDEX ix_execution_attempt_request_id ON eas.execution_attempt(request_id);
CREATE INDEX ix_acceptance_decision_request_id ON eas.acceptance_decision(request_id);
CREATE INDEX ix_acceptance_decision_actor_id ON eas.acceptance_decision(actor_id);
CREATE INDEX ix_execution_issue_attempt_id ON eas.execution_issue(attempt_id);
CREATE INDEX ix_execution_issue_request_id ON eas.execution_issue(request_id);
CREATE INDEX ix_execution_issue_actor_id ON eas.execution_issue(actor_id);
CREATE INDEX ix_attachment_request_id ON eas.attachment(request_id);
CREATE INDEX ix_attachment_uploader_id ON eas.attachment(uploader_id);
CREATE INDEX ix_draft_attachment_attachment_id ON eas.draft_attachment(attachment_id);
CREATE INDEX ix_draft_attachment_added_by ON eas.draft_attachment(added_by);
CREATE INDEX ix_revision_attachment_attachment_id ON eas.revision_attachment(attachment_id);
CREATE INDEX ix_revision_attachment_request_id ON eas.revision_attachment(request_id);
CREATE INDEX ix_execution_attachment_attachment_id ON eas.execution_attachment(attachment_id);
CREATE INDEX ix_execution_attachment_request_id ON eas.execution_attachment(request_id);
CREATE INDEX ix_sla_stage_request_id ON eas.sla_stage(request_id);
CREATE INDEX ix_sla_stage_approval_step_id ON eas.sla_stage(approval_step_id);
CREATE INDEX ix_sla_stage_attempt_id ON eas.sla_stage(attempt_id);
CREATE INDEX ix_sla_alert_request_id ON eas.sla_alert(request_id);
CREATE INDEX ix_audit_event_actor_id ON eas.audit_event(actor_id);
CREATE INDEX ix_admin_event_actor_id ON eas.admin_event(actor_id);
CREATE INDEX ix_admin_event_department_id ON eas.admin_event(department_id);
CREATE INDEX ix_admin_event_type_id ON eas.admin_event(type_id);
CREATE INDEX ix_outbox_event_request_id ON eas.outbox_event(request_id);
CREATE INDEX ix_notification_request_id ON eas.notification(request_id);
CREATE INDEX ix_idempotency_record_request_id ON eas.idempotency_record(request_id);
CREATE INDEX ix_privacy_case_subject_user_id ON eas.privacy_case(subject_user_id);
CREATE INDEX ix_privacy_case_owner_id ON eas.privacy_case(owner_id);
CREATE INDEX ix_retention_hold_request_id ON eas.retention_hold(request_id);
CREATE INDEX ix_retention_hold_set_by ON eas.retention_hold(set_by);
CREATE INDEX ix_retention_hold_released_by ON eas.retention_hold(released_by);

-- Guards are database invariants, NOT a replacement for the SRS service authorization.
-- Backend must acquire security_epoch -> type -> request -> child -> audit head -> outbox.
CREATE FUNCTION eas.lock_security(p_write boolean DEFAULT false) RETURNS bigint
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE v bigint;
BEGIN
 IF p_write THEN SELECT version INTO STRICT v FROM eas.security_epoch WHERE id=1 FOR UPDATE;
 ELSE SELECT version INTO STRICT v FROM eas.security_epoch WHERE id=1 FOR SHARE; END IF;
 RETURN v;
END $$;

CREATE FUNCTION eas.lock_security_change() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
BEGIN
 PERFORM eas.lock_security(true);
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER a_security_department BEFORE INSERT OR UPDATE OR DELETE ON eas.department FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change();
CREATE TRIGGER a_security_user BEFORE INSERT OR UPDATE OR DELETE ON eas.app_user FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change();
CREATE TRIGGER a_security_role BEFORE INSERT OR UPDATE OR DELETE ON eas.role_membership FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change();
CREATE TRIGGER a_security_participant BEFORE UPDATE OF read_revoked_at,read_revoked_reason ON eas.request_participant FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change();
-- Import increments epoch once in its transaction; these triggers acquire the lock only.
CREATE FUNCTION eas.check_hierarchy() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE bad boolean;
BEGIN
 IF TG_TABLE_NAME='department' THEN
  WITH RECURSIVE p AS (
   SELECT id,parent_id,ARRAY[id] AS path,false AS cycle FROM eas.department WHERE id=NEW.id
   UNION ALL SELECT d.id,d.parent_id,p.path||d.id,d.id=ANY(p.path)
    FROM eas.department d JOIN p ON d.id=p.parent_id WHERE NOT p.cycle
  ) SELECT coalesce(bool_or(cycle),false) INTO bad FROM p;
 ELSE
  WITH RECURSIVE p AS (
   SELECT id,manager_id,ARRAY[id] AS path,false AS cycle FROM eas.app_user WHERE id=NEW.id
   UNION ALL SELECT d.id,d.manager_id,p.path||d.id,d.id=ANY(p.path)
    FROM eas.app_user d JOIN p ON d.id=p.manager_id WHERE NOT p.cycle
  ) SELECT coalesce(bool_or(cycle),false) INTO bad FROM p;
 END IF;
 IF bad THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='EAS hierarchy cycle'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER department_acyclic AFTER INSERT OR UPDATE ON eas.department DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_hierarchy();
CREATE CONSTRAINT TRIGGER manager_acyclic AFTER INSERT OR UPDATE ON eas.app_user DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_hierarchy();

CREATE FUNCTION eas.guard_security_epoch() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='security_epoch cannot be deleted'; END IF;
 IF NEW.id<>OLD.id OR NEW.version<OLD.version THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='security_epoch must be monotonic'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER security_epoch_guard BEFORE UPDATE OR DELETE ON eas.security_epoch FOR EACH ROW EXECUTE FUNCTION eas.guard_security_epoch();

CREATE FUNCTION eas.assert_privacy_delete(p_request uuid) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE c uuid; owner_user uuid;
BEGIN
 IF current_user<>'eas_privacy' THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='History deletion requires eas_privacy role'; END IF;
 c:=nullif(current_setting('eas.privacy_case_id',true),'')::uuid;
 IF c IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Approved privacy case required'; END IF;
 PERFORM eas.lock_security(true);
 SELECT requester_id INTO owner_user FROM eas.request WHERE id=p_request FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='23503',MESSAGE='Privacy scope request missing'; END IF;
 IF NOT EXISTS (SELECT 1 FROM eas.privacy_case WHERE id=c AND subject_user_id=owner_user AND case_type='ERASE' AND status='APPROVED' AND decision_reference IS NOT NULL) THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Privacy case not approved for this request owner';
 END IF;
 IF EXISTS(SELECT 1 FROM eas.retention_hold WHERE request_id=p_request AND released_at IS NULL) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Open legal hold blocks deletion';
 END IF;
END $$;

CREATE FUNCTION eas.guard_append_only() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE req uuid;
BEGIN
 IF TG_OP='DELETE' AND current_user='eas_privacy' AND TG_TABLE_NAME<>'admin_event' THEN
  req:=nullif(to_jsonb(OLD)->>'request_id','')::uuid;
  IF req IS NOT NULL THEN PERFORM eas.assert_privacy_delete(req); RETURN OLD; END IF;
 END IF;
 RAISE EXCEPTION USING ERRCODE='23514',MESSAGE=TG_TABLE_NAME||' is append-only';
END $$;

CREATE FUNCTION eas.guard_release() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE lc char(1); j jsonb; r jsonb; defaults integer; cnt integer; h numeric;
BEGIN
 IF TG_OP IN ('UPDATE','DELETE') AND OLD.state='PUBLISHED' THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Published release is immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.type_id<>OLD.type_id OR NEW.version<>OLD.version OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Release identity is immutable';
 END IF;
 SELECT lifecycle INTO lc FROM eas.request_type WHERE id=NEW.type_id;
 IF FOUND AND lc<>NEW.lifecycle THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Release lifecycle differs from type'; END IF;
 IF NEW.state='PUBLISHED' THEN
  FOREACH j IN ARRAY ARRAY[NEW.form_schema,NEW.route_rules,NEW.actor_bindings,NEW.sla_profile] LOOP
   IF j->'schema_version' IS DISTINCT FROM '1'::jsonb THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Published JSON requires schema_version 1'; END IF;
  END LOOP;
  IF NEW.form_schema->>'type' IS DISTINCT FROM 'object' OR NEW.form_schema->'additionalProperties' IS DISTINCT FROM 'false'::jsonb
     OR jsonb_typeof(NEW.form_schema->'properties') IS DISTINCT FROM 'object'
     OR jsonb_typeof(NEW.form_schema->'required') IS DISTINCT FROM 'array'
     OR jsonb_typeof(NEW.actor_bindings->'departments') IS DISTINCT FROM 'object'
     OR jsonb_typeof(NEW.route_rules->'rules') IS DISTINCT FROM 'array' THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Published configuration shape invalid';
  END IF;
  defaults:=0;
  FOR r IN SELECT value FROM jsonb_array_elements(NEW.route_rules->'rules') LOOP
   IF coalesce(r->>'id','')='' OR jsonb_typeof(r->'approvers') IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Route id/approvers missing';
   END IF;
   cnt:=jsonb_array_length(r->'approvers');
   IF cnt NOT BETWEEN 1 AND 3 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Route requires 1..3 approvers'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(r->'approvers') v WHERE v NOT IN ('DIRECT_MANAGER','FINANCE','DIRECTOR')) THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Unknown approver resolver';
   END IF;
   IF r->'default'='true'::jsonb THEN defaults:=defaults+1;
    IF r ? 'when' OR r ? 'priority' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Default rule has no condition/priority'; END IF;
   ELSE
    IF jsonb_typeof(r->'priority') IS DISTINCT FROM 'number' OR (r->>'priority')::numeric<>trunc((r->>'priority')::numeric)
       OR jsonb_typeof(r->'when') IS DISTINCT FROM 'object' OR r->'when'='{}'::jsonb THEN
     RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Conditional rule requires integer priority and condition';
    END IF;
    IF EXISTS(SELECT 1 FROM jsonb_each(r->'when') v WHERE v.key NOT IN ('amount_gt','amount_gte') OR jsonb_typeof(v.value)<>'number') THEN
     RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Unknown condition/operator';
    END IF;
   END IF;
  END LOOP;
  IF defaults<>1 OR (NEW.route_rules->'rules'->-1->'default') IS DISTINCT FROM 'true'::jsonb THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Exactly one final default rule required';
  END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.route_rules->'rules') AS routes(item) GROUP BY item->>'id' HAVING count(*)>1)
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.route_rules->'rules') AS routes(item) WHERE item ? 'priority' GROUP BY item->>'priority' HAVING count(*)>1) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Duplicate route id or priority';
  END IF;
  IF NEW.sla_profile->>'clock' IS DISTINCT FROM 'CALENDAR_UTC' OR NEW.sla_profile->'reminder_fraction' IS DISTINCT FROM '0.5'::jsonb THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Unsupported SLA clock/reminder';
  END IF;
  FOREACH j IN ARRAY ARRAY[NEW.sla_profile->'approval_hours',NEW.sla_profile->'execution_hours',NEW.sla_profile->'acceptance_hours'] LOOP
   IF j IS NOT NULL AND j<>'null'::jsonb THEN
    IF jsonb_typeof(j)<>'number' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA hours must be numeric'; END IF;
    h:=j::text::numeric;
    IF h<=0 OR h>720 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA hours out of range'; END IF;
   END IF;
  END LOOP;
  IF jsonb_typeof(NEW.sla_profile->'approval_hours') IS DISTINCT FROM 'number'
   OR (NEW.lifecycle='A' AND (NEW.sla_profile->'execution_hours' IS DISTINCT FROM 'null'::jsonb OR NEW.sla_profile->'acceptance_hours' IS DISTINCT FROM 'null'::jsonb OR NEW.route_rules->'executor' IS DISTINCT FROM 'null'::jsonb OR NEW.route_rules->'acceptor' IS DISTINCT FROM 'null'::jsonb))
   OR (NEW.lifecycle='B' AND (jsonb_typeof(NEW.sla_profile->'execution_hours') IS DISTINCT FROM 'number' OR NEW.sla_profile->'acceptance_hours' IS DISTINCT FROM 'null'::jsonb OR NEW.route_rules->>'executor' IS DISTINCT FROM 'EXECUTOR_IT' OR NEW.route_rules->'acceptor' IS DISTINCT FROM 'null'::jsonb))
   OR (NEW.lifecycle='C' AND (jsonb_typeof(NEW.sla_profile->'execution_hours') IS DISTINCT FROM 'number' OR jsonb_typeof(NEW.sla_profile->'acceptance_hours') IS DISTINCT FROM 'number' OR NEW.route_rules->>'executor' IS DISTINCT FROM 'EXECUTOR_ASSET' OR NEW.route_rules->>'acceptor' IS DISTINCT FROM 'REQUESTER')) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Lifecycle/SLA/resolver mismatch';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER release_guard BEFORE INSERT OR UPDATE OR DELETE ON eas.config_release FOR EACH ROW EXECUTE FUNCTION eas.guard_release();

CREATE FUNCTION eas.guard_active_release() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.code<>OLD.code OR NEW.lifecycle<>OLD.lifecycle) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request type identity/lifecycle immutable';
 END IF;
 IF NEW.active_release_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM eas.config_release WHERE id=NEW.active_release_id AND type_id=NEW.id AND state='PUBLISHED') THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Active release must be published for this type';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER active_release_guard BEFORE INSERT OR UPDATE ON eas.request_type FOR EACH ROW EXECUTE FUNCTION eas.guard_active_release();

CREATE FUNCTION eas.guard_request() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE origin_owner uuid; lc char(1); allowed boolean;
BEGIN
 IF TG_OP='DELETE' THEN PERFORM eas.assert_privacy_delete(OLD.id); RETURN OLD; END IF;
 IF TG_OP='UPDATE' THEN
  IF current_user='eas_privacy' AND NEW.current_revision_id IS NULL
    AND (to_jsonb(NEW)-'current_revision_id')=(to_jsonb(OLD)-'current_revision_id') THEN
   PERFORM eas.assert_privacy_delete(OLD.id); RETURN NEW;
  END IF;
  IF ROW(NEW.id,NEW.code,NEW.requester_id,NEW.type_id,NEW.origin_request_id,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.code,OLD.requester_id,OLD.type_id,OLD.origin_request_id,OLD.created_at) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request identity/origin immutable';
  END IF;
  IF OLD.status IN ('COMPLETED','REJECTED','CANCELLED') AND NEW IS DISTINCT FROM OLD THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Terminal request cannot be reopened or edited';
  END IF;
  IF NEW IS DISTINCT FROM OLD AND (NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_at<OLD.updated_at) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request command requires version increment exactly once and monotonic updated_at';
  END IF;
  IF NEW.status<>OLD.status THEN
   allowed:=(OLD.status IN ('DRAFT','NEEDS_INFO') AND NEW.status IN ('PENDING_APPROVAL','CANCELLED'))
     OR (OLD.status='PENDING_APPROVAL' AND NEW.status IN ('NEEDS_INFO','REJECTED','CANCELLED','COMPLETED','READY_FOR_EXECUTION'))
     OR (OLD.status='READY_FOR_EXECUTION' AND NEW.status='IN_PROGRESS')
     OR (OLD.status='IN_PROGRESS' AND NEW.status IN ('READY_FOR_EXECUTION','WAITING_FOR_ACCEPTANCE','COMPLETED'))
     OR (OLD.status='WAITING_FOR_ACCEPTANCE' AND NEW.status IN ('READY_FOR_EXECUTION','COMPLETED'));
   IF NOT allowed THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request transition not allowed'; END IF;
  END IF;
 END IF;
 IF NEW.origin_request_id IS NOT NULL THEN
  SELECT requester_id INTO origin_owner FROM eas.request WHERE id=NEW.origin_request_id;
  IF FOUND AND origin_owner<>NEW.requester_id THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Origin request must have same owner'; END IF;
 END IF;
 SELECT lifecycle INTO lc FROM eas.request_type WHERE id=NEW.type_id;
 IF FOUND AND ((lc IN ('A','B') AND NEW.draft_amount_vnd IS NOT NULL) OR (lc='A' AND NEW.status IN ('READY_FOR_EXECUTION','IN_PROGRESS','WAITING_FOR_ACCEPTANCE')) OR (lc='B' AND NEW.status='WAITING_FOR_ACCEPTANCE')) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Request lifecycle/amount mismatch';
 END IF;
 IF NEW.status NOT IN ('DRAFT','CANCELLED') AND NEW.current_revision_id IS NULL THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Submitted request requires current revision';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER request_guard BEFORE INSERT OR UPDATE OR DELETE ON eas.request FOR EACH ROW EXECUTE FUNCTION eas.guard_request();

CREATE FUNCTION eas.guard_revision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE r eas.request; c eas.config_release;
BEGIN
 PERFORM eas.lock_security(false);
 SELECT * INTO r FROM eas.request WHERE id=NEW.request_id FOR UPDATE;
 IF NOT FOUND THEN RETURN NEW; END IF;
 SELECT * INTO c FROM eas.config_release WHERE id=NEW.release_id;
 IF NOT FOUND THEN RETURN NEW; END IF;
 IF r.status NOT IN ('DRAFT','NEEDS_INFO') OR c.type_id<>r.type_id OR c.state<>'PUBLISHED' OR NEW.submitted_by<>r.requester_id
   OR (c.lifecycle IN ('A','B') AND NEW.amount_vnd IS NOT NULL) OR (c.lifecycle='C' AND NEW.amount_vnd IS NULL) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Revision release/owner/amount invalid';
 END IF;
 IF NEW.revision_no<>(SELECT coalesce(max(revision_no),0)+1 FROM eas.request_revision WHERE request_id=NEW.request_id) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Revision numbers must be consecutive per request';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER revision_guard BEFORE INSERT ON eas.request_revision FOR EACH ROW EXECUTE FUNCTION eas.guard_revision();

CREATE FUNCTION eas.guard_instance() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE lc char(1);
BEGIN
 IF TG_OP='UPDATE' THEN
  IF (to_jsonb(NEW)-ARRAY['state','planned_executor_id','acceptor_id','closed_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','planned_executor_id','acceptor_id','closed_at']) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Instance snapshot immutable';
  END IF;
  IF OLD.state<>'ACTIVE' AND NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Closed instance immutable'; END IF;
 END IF;
 SELECT c.lifecycle INTO lc FROM eas.request_revision v JOIN eas.config_release c ON c.id=v.release_id WHERE v.id=NEW.revision_id;
 IF FOUND AND lc<>NEW.lifecycle THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Instance lifecycle differs from revision'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER instance_guard BEFORE INSERT OR UPDATE ON eas.workflow_instance FOR EACH ROW EXECUTE FUNCTION eas.guard_instance();

CREATE FUNCTION eas.guard_step() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE owner_id uuid;
BEGIN
 SELECT requester_id INTO owner_id FROM eas.request WHERE id=NEW.request_id;
 IF FOUND AND NEW.assignee_id=owner_id THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Requester cannot approve own request'; END IF;
 IF TG_OP='UPDATE' THEN
  IF ROW(NEW.id,NEW.request_id,NEW.instance_id,NEW.step_no) IS DISTINCT FROM ROW(OLD.id,OLD.request_id,OLD.instance_id,OLD.step_no)
    OR (OLD.state IN ('APPROVED','REJECTED','NEEDS_INFO','SKIPPED') AND NEW IS DISTINCT FROM OLD)
    OR (EXISTS(SELECT 1 FROM eas.approval_decision WHERE step_id=OLD.id) AND NEW.assignee_id<>OLD.assignee_id) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Step identity or decided actor immutable';
  END IF;
  IF NEW.state<>OLD.state AND NOT ((OLD.state='WAITING' AND NEW.state IN ('ACTIVE','SKIPPED')) OR (OLD.state='ACTIVE' AND NEW.state IN ('APPROVED','REJECTED','NEEDS_INFO','SKIPPED'))) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Approval step transition invalid';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER step_guard BEFORE INSERT OR UPDATE ON eas.approval_step FOR EACH ROW EXECUTE FUNCTION eas.guard_step();

CREATE FUNCTION eas.guard_decision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE s eas.approval_step; a eas.execution_attempt; i eas.workflow_instance; r eas.request;
BEGIN
 PERFORM eas.lock_security(false);
 SELECT * INTO r FROM eas.request WHERE id=NEW.request_id FOR UPDATE;
 IF NOT FOUND THEN RETURN NEW; END IF;
 IF TG_TABLE_NAME='approval_decision' THEN
  SELECT * INTO s FROM eas.approval_step WHERE id=NEW.step_id;
  IF NOT FOUND OR s.request_id<>NEW.request_id THEN RETURN NEW; END IF;
  SELECT * INTO i FROM eas.workflow_instance WHERE id=s.instance_id;
  IF s.state<>'ACTIVE' OR s.assignee_id<>NEW.actor_id OR r.requester_id=NEW.actor_id OR r.status<>'PENDING_APPROVAL' OR r.current_revision_id<>i.revision_id OR i.state<>'ACTIVE' THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Approval actor/state/current instance invalid';
  END IF;
 ELSE
  SELECT * INTO a FROM eas.execution_attempt WHERE id=NEW.attempt_id;
  IF NOT FOUND OR a.request_id<>NEW.request_id THEN RETURN NEW; END IF;
  SELECT * INTO i FROM eas.workflow_instance WHERE id=a.instance_id;
  IF a.state<>'SUBMITTED' OR i.lifecycle<>'C' OR i.acceptor_id<>NEW.actor_id OR a.executor_id=NEW.actor_id OR r.status<>'WAITING_FOR_ACCEPTANCE' OR r.current_revision_id<>i.revision_id OR i.state<>'ACTIVE' THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Acceptance actor/state/SoD/current instance invalid';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER approval_decision_guard BEFORE INSERT ON eas.approval_decision FOR EACH ROW EXECUTE FUNCTION eas.guard_decision();
CREATE TRIGGER acceptance_decision_guard BEFORE INSERT ON eas.acceptance_decision FOR EACH ROW EXECUTE FUNCTION eas.guard_decision();

CREATE FUNCTION eas.guard_attempt() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE lc char(1);
BEGIN
 SELECT lifecycle INTO lc FROM eas.workflow_instance WHERE id=NEW.instance_id;
 IF FOUND AND (lc='A' OR (lc='B' AND (NEW.state='SUBMITTED' OR NEW.closure_kind IN ('ACCEPTED','REWORK'))) OR (lc='C' AND NEW.closure_kind='SUCCESS')) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Attempt lifecycle mismatch';
 END IF;
 IF TG_OP='UPDATE' THEN
  IF ROW(NEW.id,NEW.request_id,NEW.instance_id,NEW.attempt_no) IS DISTINCT FROM ROW(OLD.id,OLD.request_id,OLD.instance_id,OLD.attempt_no) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Attempt identity immutable';
  END IF;
  IF OLD.state='FINISHED' AND NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Finished attempt immutable'; END IF;
  IF OLD.state IN ('RUNNING','SUBMITTED') AND NEW.executor_id<>OLD.executor_id THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Reassignment requires a new attempt'; END IF;
  IF OLD.state='SUBMITTED' AND (to_jsonb(NEW)-ARRAY['state','closure_kind','closed_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','closure_kind','closed_at']) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Submitted result immutable';
  END IF;
  IF NEW.state<>OLD.state AND NOT ((OLD.state='READY' AND NEW.state='RUNNING') OR (OLD.state='RUNNING' AND NEW.state IN ('SUBMITTED','FINISHED')) OR (OLD.state='SUBMITTED' AND NEW.state='FINISHED')) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Attempt transition invalid';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER attempt_guard BEFORE INSERT OR UPDATE ON eas.execution_attempt FOR EACH ROW EXECUTE FUNCTION eas.guard_attempt();

CREATE FUNCTION eas.guard_attachment() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE used_bytes bigint;
BEGIN
 PERFORM eas.lock_security(false);
 PERFORM 1 FROM eas.request WHERE id=NEW.request_id FOR UPDATE;
 IF TG_OP='INSERT' THEN
  SELECT coalesce(sum(size_bytes),0) INTO used_bytes FROM eas.attachment WHERE request_id=NEW.request_id AND deleted_at IS NULL;
  IF NEW.deleted_at IS NULL AND used_bytes+NEW.size_bytes>209715200 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Attachment quota 200 MiB exceeded'; END IF;
 ELSE
  IF (to_jsonb(NEW)-ARRAY['scan_state','scan_attempts','scanned_at','deleted_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['scan_state','scan_attempts','scanned_at','deleted_at']) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Attachment object metadata immutable';
  END IF;
  IF OLD.deleted_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Deleted attachment cannot be restored by update'; END IF;
 END IF;
 IF NEW.deleted_at IS NOT NULL AND (TG_OP='INSERT' OR OLD.deleted_at IS NULL) THEN
  IF EXISTS(SELECT 1 FROM eas.retention_hold WHERE request_id=NEW.request_id AND released_at IS NULL)
   OR EXISTS(SELECT 1 FROM eas.draft_attachment WHERE attachment_id=NEW.id)
   OR EXISTS(SELECT 1 FROM eas.revision_attachment WHERE attachment_id=NEW.id)
   OR EXISTS(SELECT 1 FROM eas.execution_attachment WHERE attachment_id=NEW.id) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Referenced or held attachment cannot be deleted';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER attachment_guard BEFORE INSERT OR UPDATE ON eas.attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_attachment();

CREATE FUNCTION eas.guard_file_link() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE a eas.attachment; r eas.request; ex eas.execution_attempt; v eas.request_revision; n integer;
BEGIN
 PERFORM eas.lock_security(false);
 SELECT * INTO r FROM eas.request WHERE id=NEW.request_id FOR UPDATE;
 SELECT * INTO a FROM eas.attachment WHERE id=NEW.attachment_id;
 IF NOT FOUND OR a.request_id<>NEW.request_id THEN RETURN NEW; END IF;
 IF a.scan_state<>'CLEAN' OR a.deleted_at IS NOT NULL THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Attachment must be CLEAN and available'; END IF;
 IF TG_TABLE_NAME='draft_attachment' THEN
  IF a.uploader_id<>r.requester_id OR NEW.added_by<>r.requester_id OR r.status NOT IN ('DRAFT','NEEDS_INFO') THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Draft attachment owner/state invalid'; END IF;
  SELECT count(*) INTO n FROM eas.draft_attachment WHERE request_id=NEW.request_id;
 ELSIF TG_TABLE_NAME='revision_attachment' THEN
  IF a.uploader_id<>r.requester_id THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Revision attachment uploader invalid'; END IF;
  SELECT * INTO v FROM eas.request_revision WHERE id=NEW.revision_id;
  IF NOT FOUND OR v.request_id<>NEW.request_id THEN RETURN NEW; END IF;
  IF r.status NOT IN ('DRAFT','NEEDS_INFO') OR r.current_revision_id=NEW.revision_id
    OR v.revision_no<>(SELECT max(revision_no) FROM eas.request_revision WHERE request_id=NEW.request_id) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Revision files must be captured before switching current revision';
  END IF;
  SELECT count(*) INTO n FROM eas.revision_attachment WHERE revision_id=NEW.revision_id;
 ELSE
  SELECT * INTO ex FROM eas.execution_attempt WHERE id=NEW.attempt_id;
  IF NOT FOUND OR ex.request_id<>NEW.request_id THEN RETURN NEW; END IF;
  IF a.uploader_id<>ex.executor_id OR ex.state<>'RUNNING' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Execution attachment requires RUNNING assigned uploader'; END IF;
  SELECT count(*) INTO n FROM eas.execution_attachment WHERE attempt_id=NEW.attempt_id;
 END IF;
 IF n>=5 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Maximum five linked files'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER draft_link_guard BEFORE INSERT ON eas.draft_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_file_link();
CREATE TRIGGER revision_link_guard BEFORE INSERT ON eas.revision_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_file_link();
CREATE TRIGGER execution_link_guard BEFORE INSERT ON eas.execution_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_file_link();

CREATE FUNCTION eas.check_submission_files() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE a eas.execution_attempt; n integer; lc char(1);
BEGIN
 IF TG_TABLE_NAME='execution_attempt' THEN
  SELECT * INTO a FROM eas.execution_attempt WHERE id=NEW.id;
  IF NOT FOUND OR a.submitted_at IS NULL THEN RETURN NULL; END IF;
  SELECT count(*) INTO n FROM eas.execution_attachment WHERE attempt_id=a.id;
  IF n NOT BETWEEN 1 AND 5 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Submitted result requires 1..5 evidence files'; END IF;
 ELSE
  SELECT c.lifecycle INTO lc FROM eas.request_revision v JOIN eas.config_release c ON c.id=v.release_id WHERE v.id=NEW.id;
  IF NOT FOUND THEN RETURN NULL; END IF;
  SELECT count(*) INTO n FROM eas.revision_attachment WHERE revision_id=NEW.id;
  IF n>5 OR (lc='C' AND n=0) THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Equipment revision requires quote; maximum five files'; END IF;
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER revision_files_complete AFTER INSERT ON eas.request_revision DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_submission_files();
CREATE CONSTRAINT TRIGGER execution_files_complete AFTER INSERT OR UPDATE ON eas.execution_attempt DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_submission_files();

CREATE FUNCTION eas.guard_sla() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE old_instance uuid; new_instance uuid; old_closure text;
BEGIN
 IF ROW(NEW.id,NEW.request_id,NEW.kind,NEW.approval_step_id,NEW.started_at,NEW.due_at) IS DISTINCT FROM ROW(OLD.id,OLD.request_id,OLD.kind,OLD.approval_step_id,OLD.started_at,OLD.due_at)
  OR (OLD.closed_at IS NOT NULL AND NEW IS DISTINCT FROM OLD)
  OR (OLD.breached_at IS NOT NULL AND NEW.breached_at IS DISTINCT FROM OLD.breached_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA identity/deadline/closed history immutable';
 END IF;
 IF NEW.attempt_id IS DISTINCT FROM OLD.attempt_id THEN
  SELECT instance_id,closure_kind INTO old_instance,old_closure FROM eas.execution_attempt WHERE id=OLD.attempt_id;
  SELECT instance_id INTO new_instance FROM eas.execution_attempt WHERE id=NEW.attempt_id;
  IF NEW.kind<>'EXECUTION' OR old_instance IS DISTINCT FROM new_instance OR old_closure IS DISTINCT FROM 'REASSIGNED' THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='SLA target can change only for reassigned execution in same instance';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sla_guard BEFORE UPDATE ON eas.sla_stage FOR EACH ROW EXECUTE FUNCTION eas.guard_sla();

CREATE FUNCTION eas.initialize_request_head() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,eas AS $$
BEGIN
 INSERT INTO eas.audit_head(scope_key) VALUES('REQ:'||NEW.id::text);
 RETURN NEW;
END $$;
CREATE TRIGGER request_head AFTER INSERT ON eas.request FOR EACH ROW EXECUTE FUNCTION eas.initialize_request_head();

CREATE FUNCTION eas.lock_audit_head(p_scope text) RETURNS TABLE(seq bigint,last_hash char(64))
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,eas AS $$
 SELECT h.seq,h.last_hash FROM eas.audit_head h WHERE h.scope_key=p_scope FOR UPDATE
$$;
CREATE FUNCTION eas.advance_audit_head() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,eas AS $$
DECLARE scope text; h eas.audit_head;
BEGIN
 IF TG_TABLE_NAME='audit_event' THEN scope:='REQ:'||NEW.request_id::text; ELSE scope:='ADMIN'; END IF;
 SELECT * INTO h FROM eas.audit_head WHERE scope_key=scope FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='23503',MESSAGE='Audit head not found'; END IF;
 IF NEW.seq<>h.seq+1 OR NEW.prev_hash<>h.last_hash THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Audit sequence/previous hash mismatch'; END IF;
 UPDATE eas.audit_head SET seq=NEW.seq,last_hash=NEW.hash WHERE scope_key=scope;
 RETURN NEW;
END $$;
CREATE TRIGGER advance_request_audit BEFORE INSERT ON eas.audit_event FOR EACH ROW EXECUTE FUNCTION eas.advance_audit_head();
CREATE TRIGGER advance_admin_audit BEFORE INSERT ON eas.admin_event FOR EACH ROW EXECUTE FUNCTION eas.advance_audit_head();
-- The supplied hash is NOT recomputed from jsonb::text: that is not RFC8785.
-- Backend signs the complete canonical event before INSERT and verifies against external checkpoints.

CREATE FUNCTION eas.guard_notification() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE q uuid;
BEGIN
 IF TG_OP='INSERT' THEN
  SELECT request_id INTO q FROM eas.outbox_event WHERE id=NEW.event_id;
  IF FOUND AND NEW.request_id IS DISTINCT FROM q THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Notification request must match event including NULL'; END IF;
 ELSE
  IF (to_jsonb(NEW)-'read_at') IS DISTINCT FROM (to_jsonb(OLD)-'read_at') OR (OLD.read_at IS NOT NULL AND NEW.read_at IS DISTINCT FROM OLD.read_at) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Notification content and first read timestamp immutable';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER notification_guard BEFORE INSERT OR UPDATE ON eas.notification FOR EACH ROW EXECUTE FUNCTION eas.guard_notification();

CREATE FUNCTION eas.guard_idempotency() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  IF current_user='eas_privacy' AND OLD.request_id IS NOT NULL THEN PERFORM eas.assert_privacy_delete(OLD.request_id); RETURN OLD; END IF;
  IF clock_timestamp()<OLD.tombstone_until THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Idempotency tombstone must remain until expiry'; END IF;
  RETURN OLD;
 END IF;
 IF (to_jsonb(NEW)-'response_body') IS DISTINCT FROM (to_jsonb(OLD)-'response_body')
  OR NEW.response_body IS NOT NULL OR clock_timestamp()<OLD.expires_at THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Only expired response body may be cleared';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER idempotency_guard BEFORE UPDATE OR DELETE ON eas.idempotency_record FOR EACH ROW EXECUTE FUNCTION eas.guard_idempotency();

CREATE FUNCTION eas.guard_request_delete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
BEGIN
 PERFORM eas.assert_privacy_delete(OLD.request_id); RETURN OLD;
END $$;
CREATE FUNCTION eas.guard_audit_scope_delete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
BEGIN
 IF OLD.scope_key='ADMIN' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='ADMIN audit scope cannot be purged here'; END IF;
 PERFORM eas.assert_privacy_delete(substring(OLD.scope_key FROM 5)::uuid); RETURN OLD;
END $$;

DO $guards$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['request_revision','approval_decision','acceptance_decision','execution_issue','revision_attachment','execution_attachment','sla_alert','audit_event','admin_event'] LOOP
  EXECUTE format('CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON eas.%I FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['workflow_instance','request_participant','approval_step','execution_attempt','attachment','sla_stage','outbox_event','notification','retention_hold'] LOOP
  EXECUTE format('CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.%I FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()',t);
 END LOOP;
END
$guards$;
CREATE TRIGGER head_delete_guard BEFORE DELETE ON eas.audit_head FOR EACH ROW EXECUTE FUNCTION eas.guard_audit_scope_delete();
CREATE TRIGGER checkpoint_delete_guard BEFORE DELETE ON eas.audit_checkpoint FOR EACH ROW EXECUTE FUNCTION eas.guard_audit_scope_delete();

CREATE FUNCTION eas.guard_stable_metadata() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,eas AS $$
DECLARE mutable_fields text[];
BEGIN
 IF TG_TABLE_NAME='request_participant' THEN
  mutable_fields:=ARRAY['read_revoked_at','read_revoked_reason'];
 ELSIF TG_TABLE_NAME='outbox_event' THEN
  mutable_fields:=ARRAY['state','attempts','replay_count','available_at','lease_token','lease_until','sent_at','last_error_code'];
 ELSIF TG_TABLE_NAME='retention_hold' THEN
  mutable_fields:=ARRAY['released_at','released_by'];
  IF OLD.released_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Released hold is immutable; create a new hold';
  END IF;
 ELSE
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Checkpoint is immutable';
 END IF;
 IF (to_jsonb(NEW)-mutable_fields) IS DISTINCT FROM (to_jsonb(OLD)-mutable_fields) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE=TG_TABLE_NAME||' identity/content immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER participant_metadata BEFORE UPDATE ON eas.request_participant FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata();
CREATE TRIGGER outbox_metadata BEFORE UPDATE ON eas.outbox_event FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata();
CREATE TRIGGER hold_metadata BEFORE UPDATE ON eas.retention_hold FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata();
CREATE TRIGGER checkpoint_metadata BEFORE UPDATE ON eas.audit_checkpoint FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata();

-- End-user authorization belongs to the backend. These are trusted service roles,
-- not the seven business roles in role_membership and not Supabase JWT roles.
GRANT USAGE ON SCHEMA eas TO eas_api,eas_worker,eas_backup,eas_privacy;
GRANT SELECT ON ALL TABLES IN SCHEMA eas TO eas_api,eas_worker,eas_backup,eas_privacy;
GRANT USAGE,SELECT ON SEQUENCE eas.request_code_seq TO eas_api;
GRANT SELECT ON SEQUENCE eas.request_code_seq TO eas_backup;
GRANT EXECUTE ON FUNCTION eas.next_request_code() TO eas_api;
GRANT EXECUTE ON FUNCTION eas.lock_security(boolean) TO eas_api,eas_worker,eas_privacy;
GRANT EXECUTE ON FUNCTION eas.lock_audit_head(text) TO eas_api,eas_worker,eas_privacy;
GRANT EXECUTE ON FUNCTION eas.assert_privacy_delete(uuid) TO eas_privacy;

GRANT INSERT ON eas.department,eas.app_user,eas.role_membership,eas.config_release,
 eas.request,eas.request_revision,eas.workflow_instance,eas.request_participant,
 eas.approval_step,eas.approval_decision,eas.execution_attempt,eas.acceptance_decision,
 eas.execution_issue,eas.attachment,eas.draft_attachment,eas.revision_attachment,
 eas.execution_attachment,eas.sla_stage,eas.sla_alert,eas.audit_event,eas.admin_event,
 eas.outbox_event,eas.notification,eas.idempotency_record,eas.privacy_case,eas.retention_hold
 TO eas_api;
GRANT UPDATE ON eas.department,eas.app_user,eas.role_membership,eas.request_type,
 eas.config_release,eas.request,eas.workflow_instance,eas.request_participant,
 eas.approval_step,eas.execution_attempt,eas.attachment,eas.sla_stage,
 eas.privacy_case,eas.retention_hold TO eas_api;
GRANT UPDATE (version,updated_at) ON eas.security_epoch TO eas_api,eas_worker,eas_privacy;
GRANT UPDATE (state,attempts,replay_count,available_at,lease_token,lease_until,sent_at,last_error_code)
 ON eas.outbox_event TO eas_api,eas_worker;
GRANT UPDATE (read_at) ON eas.notification TO eas_api;
GRANT DELETE ON eas.draft_attachment TO eas_api;

GRANT INSERT ON eas.sla_alert,eas.audit_event,eas.admin_event,eas.audit_checkpoint,
 eas.outbox_event,eas.notification TO eas_worker;
GRANT UPDATE (breached_at) ON eas.sla_stage TO eas_worker;
GRANT UPDATE (scan_state,scan_attempts,scanned_at,deleted_at) ON eas.attachment TO eas_worker;
GRANT UPDATE (response_body) ON eas.idempotency_record TO eas_worker;
GRANT DELETE ON eas.idempotency_record TO eas_worker;
-- SELECT FOR UPDATE used by guarded worker operations requires an UPDATE privilege.
-- The worker must not actually issue request updates; this column grant only enables locking.
GRANT UPDATE (lock_version) ON eas.request TO eas_worker;

-- Privacy is an offline operator role. Never grant this role to the web/worker login.
-- A request may be purged only with an APPROVED ERASE case and no open legal hold.
GRANT UPDATE (current_revision_id) ON eas.request TO eas_privacy;
GRANT UPDATE (status,completed_at,decision_reference) ON eas.privacy_case TO eas_privacy;
GRANT INSERT ON eas.admin_event TO eas_privacy;
GRANT DELETE ON eas.request,eas.request_revision,eas.workflow_instance,
 eas.request_participant,eas.approval_step,eas.approval_decision,eas.execution_attempt,
 eas.acceptance_decision,eas.execution_issue,eas.attachment,eas.draft_attachment,
 eas.revision_attachment,eas.execution_attachment,eas.sla_stage,eas.sla_alert,
 eas.audit_event,eas.audit_head,eas.audit_checkpoint,eas.outbox_event,eas.notification,
 eas.idempotency_record,eas.retention_hold TO eas_privacy;

DO $rls$
DECLARE t record; r text;
BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='eas' LOOP
  EXECUTE format('ALTER TABLE eas.%I ENABLE ROW LEVEL SECURITY',t.tablename);
  EXECUTE format('CREATE POLICY trusted_backend ON eas.%I FOR ALL TO eas_api,eas_worker,eas_privacy USING (true) WITH CHECK (true)',t.tablename);
  EXECUTE format('CREATE POLICY backup_read ON eas.%I FOR SELECT TO eas_backup USING (true)',t.tablename);
 END LOOP;
 -- Restrict this schema only; do not change other Supabase applications.
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE format('REVOKE ALL ON SCHEMA eas FROM %I',r);
   EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA eas FROM %I',r);
   EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA eas FROM %I',r);
   EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA eas FROM %I',r);
  END IF;
 END LOOP;
END
$rls$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA eas FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA eas FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA eas FROM PUBLIC;

-- Reference data needed by an EMPTY production schema. No fake user/password/policy.
INSERT INTO eas.security_epoch(id) VALUES(1);
INSERT INTO eas.audit_head(scope_key) VALUES('ADMIN');
INSERT INTO eas.request_type(id,code,lifecycle) VALUES
 ('00000000-0000-4000-8000-000000000001','LEAVE','A'),
 ('00000000-0000-4000-8000-000000000002','ACCESS','B'),
 ('00000000-0000-4000-8000-000000000003','EQUIPMENT','C');
COMMENT ON SCHEMA eas IS 'EAS schema migration 2.0.1; 30 domain tables; backend-only; docs v2.0; 2026-09-22';
RESET ROLE;
COMMIT;
SELECT 'EAS 2.0.1 installed' AS result, count(*) AS domain_tables
FROM information_schema.tables WHERE table_schema='eas' AND table_type='BASE TABLE';
