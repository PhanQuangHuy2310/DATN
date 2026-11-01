-- REFERENCE ONLY: copied from user export; not safe to execute.
-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE eas.security_epoch (
  id smallint NOT NULL DEFAULT 1 CHECK (id = 1),
  version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT security_epoch_pkey PRIMARY KEY (id)
);
CREATE TABLE eas.department (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  code character varying NOT NULL UNIQUE CHECK (code::text = btrim(code::text) AND length(code::text) > 0),
  name character varying NOT NULL CHECK (length(btrim(name::text)) > 0),
  parent_id uuid,
  is_active boolean NOT NULL DEFAULT true,
  CONSTRAINT department_pkey PRIMARY KEY (id),
  CONSTRAINT department_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES eas.department(id)
);
CREATE TABLE eas.app_user (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  username character varying NOT NULL UNIQUE CHECK (username::text = lower(btrim(username::text)) AND length(username::text) > 0),
  display_name character varying NOT NULL CHECK (length(btrim(display_name::text)) > 0),
  department_id uuid NOT NULL,
  manager_id uuid,
  is_active boolean NOT NULL DEFAULT true,
  must_change_password boolean NOT NULL DEFAULT true,
  auth_version bigint NOT NULL DEFAULT 0 CHECK (auth_version >= 0),
  password_hash text NOT NULL CHECK (length(password_hash) > 0),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT app_user_pkey PRIMARY KEY (id),
  CONSTRAINT app_user_department_id_fkey FOREIGN KEY (department_id) REFERENCES eas.department(id),
  CONSTRAINT app_user_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.request_type (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  code character varying NOT NULL UNIQUE,
  lifecycle character NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  active_release_id uuid,
  name character varying NOT NULL CHECK (length(btrim(name::text)) > 0 OR name::text = ''::text),
  description character varying NOT NULL,
  category character varying NOT NULL CHECK (category::text = ANY (ARRAY['HR'::character varying, 'IT'::character varying, 'FACILITY'::character varying, 'PROCUREMENT'::character varying, 'ASSET'::character varying, 'FINANCE'::character varying, 'GENERAL'::character varying]::text[])),
  CONSTRAINT request_type_pkey PRIMARY KEY (id),
  CONSTRAINT request_type_lifecycle_fk FOREIGN KEY (lifecycle) REFERENCES eas.lifecycle(code),
  CONSTRAINT type_active_release_same_type FOREIGN KEY (active_release_id) REFERENCES eas.config_release(id),
  CONSTRAINT type_active_release_same_type FOREIGN KEY (id) REFERENCES eas.config_release(type_id)
);
CREATE TABLE eas.role_membership (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  role character varying NOT NULL,
  scope_kind character varying NOT NULL CHECK (scope_kind::text = ANY (ARRAY['GLOBAL'::character varying, 'DEPARTMENT'::character varying]::text[])),
  department_id uuid,
  type_scope character varying NOT NULL CHECK (type_scope::text = ANY (ARRAY['ALL'::character varying, 'ONE'::character varying]::text[])),
  type_id uuid,
  valid_from timestamp with time zone NOT NULL DEFAULT now(),
  valid_to timestamp with time zone,
  revoked_at timestamp with time zone,
  CONSTRAINT role_membership_pkey PRIMARY KEY (id),
  CONSTRAINT role_membership_role_fk FOREIGN KEY (role) REFERENCES eas.role(code),
  CONSTRAINT role_membership_user_id_fkey FOREIGN KEY (user_id) REFERENCES eas.app_user(id),
  CONSTRAINT role_membership_department_id_fkey FOREIGN KEY (department_id) REFERENCES eas.department(id),
  CONSTRAINT role_membership_type_id_fkey FOREIGN KEY (type_id) REFERENCES eas.request_type(id)
);
CREATE TABLE eas.config_release (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  type_id uuid NOT NULL,
  version integer NOT NULL CHECK (version > 0),
  state character varying NOT NULL DEFAULT 'DRAFT'::character varying CHECK (state::text = ANY (ARRAY['DRAFT'::character varying, 'PUBLISHED'::character varying]::text[])),
  lifecycle character NOT NULL CHECK (lifecycle = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar])),
  form_schema jsonb NOT NULL CHECK (jsonb_typeof(form_schema) = 'object'::text),
  route_rules jsonb NOT NULL CHECK (jsonb_typeof(route_rules) = 'object'::text),
  actor_bindings jsonb NOT NULL CHECK (jsonb_typeof(actor_bindings) = 'object'::text),
  sla_profile jsonb NOT NULL CHECK (jsonb_typeof(sla_profile) = 'object'::text),
  created_by uuid NOT NULL,
  published_by uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  published_at timestamp with time zone,
  lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version >= 0),
  content_sha256 character CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'::text),
  CONSTRAINT config_release_pkey PRIMARY KEY (id),
  CONSTRAINT config_release_lifecycle_fk FOREIGN KEY (lifecycle) REFERENCES eas.lifecycle(code),
  CONSTRAINT config_release_published_by_fkey FOREIGN KEY (published_by) REFERENCES eas.app_user(id),
  CONSTRAINT config_release_type_id_fkey FOREIGN KEY (type_id) REFERENCES eas.request_type(id),
  CONSTRAINT config_release_created_by_fkey FOREIGN KEY (created_by) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.request (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  code character varying NOT NULL DEFAULT eas.next_request_code() UNIQUE,
  requester_id uuid NOT NULL,
  type_id uuid NOT NULL,
  status character varying NOT NULL DEFAULT 'DRAFT'::character varying CHECK (status::text = ANY (ARRAY['DRAFT'::character varying, 'NEEDS_INFO'::character varying, 'PENDING_APPROVAL'::character varying, 'READY_FOR_EXECUTION'::character varying, 'IN_PROGRESS'::character varying, 'WAITING_FOR_ACCEPTANCE'::character varying, 'COMPLETED'::character varying, 'REJECTED'::character varying, 'CANCELLED'::character varying]::text[])),
  draft_payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(draft_payload) = 'object'::text),
  draft_amount_vnd bigint CHECK (draft_amount_vnd >= 1 AND draft_amount_vnd <= '1000000000000'::bigint),
  draft_release_id uuid,
  origin_request_id uuid,
  current_revision_id uuid,
  lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version >= 0),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  approved_at timestamp with time zone,
  completed_at timestamp with time zone,
  CONSTRAINT request_pkey PRIMARY KEY (id),
  CONSTRAINT request_requester_id_fkey FOREIGN KEY (requester_id) REFERENCES eas.app_user(id),
  CONSTRAINT request_type_id_fkey FOREIGN KEY (type_id) REFERENCES eas.request_type(id),
  CONSTRAINT request_origin_request_id_fkey FOREIGN KEY (origin_request_id) REFERENCES eas.request(id),
  CONSTRAINT request_draft_release_type FOREIGN KEY (draft_release_id) REFERENCES eas.config_release(id),
  CONSTRAINT request_draft_release_type FOREIGN KEY (type_id) REFERENCES eas.config_release(type_id),
  CONSTRAINT request_current_revision_same_request FOREIGN KEY (current_revision_id) REFERENCES eas.request_revision(id),
  CONSTRAINT request_current_revision_same_request FOREIGN KEY (id) REFERENCES eas.request_revision(request_id)
);
CREATE TABLE eas.request_revision (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  revision_no integer NOT NULL CHECK (revision_no > 0),
  release_id uuid NOT NULL,
  department_id uuid NOT NULL,
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'::text),
  amount_vnd bigint CHECK (amount_vnd >= 1 AND amount_vnd <= '1000000000000'::bigint),
  submitted_by uuid NOT NULL,
  submitted_at timestamp with time zone NOT NULL DEFAULT now(),
  payload_sha256 character NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'::text),
  CONSTRAINT request_revision_pkey PRIMARY KEY (id),
  CONSTRAINT request_revision_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT request_revision_release_id_fkey FOREIGN KEY (release_id) REFERENCES eas.config_release(id),
  CONSTRAINT request_revision_department_id_fkey FOREIGN KEY (department_id) REFERENCES eas.department(id),
  CONSTRAINT request_revision_submitted_by_fkey FOREIGN KEY (submitted_by) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.workflow_instance (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  revision_id uuid NOT NULL UNIQUE,
  matched_rule_id character varying NOT NULL CHECK (length(btrim(matched_rule_id::text)) > 0),
  resolved_route jsonb NOT NULL CHECK (jsonb_typeof(resolved_route) = 'array'::text AND jsonb_array_length(resolved_route) >= 1 AND jsonb_array_length(resolved_route) <= 3),
  lifecycle character NOT NULL CHECK (lifecycle = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar])),
  state character varying NOT NULL DEFAULT 'ACTIVE'::character varying CHECK (state::text = ANY (ARRAY['ACTIVE'::character varying, 'COMPLETED'::character varying, 'REJECTED'::character varying, 'SUPERSEDED'::character varying, 'CANCELLED'::character varying]::text[])),
  planned_executor_id uuid,
  acceptor_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  closed_at timestamp with time zone,
  CONSTRAINT workflow_instance_pkey PRIMARY KEY (id),
  CONSTRAINT workflow_instance_lifecycle_fk FOREIGN KEY (lifecycle) REFERENCES eas.lifecycle(code),
  CONSTRAINT workflow_instance_acceptor_id_fkey FOREIGN KEY (acceptor_id) REFERENCES eas.app_user(id),
  CONSTRAINT instance_revision_same_request FOREIGN KEY (revision_id) REFERENCES eas.request_revision(id),
  CONSTRAINT instance_revision_same_request FOREIGN KEY (request_id) REFERENCES eas.request_revision(request_id),
  CONSTRAINT workflow_instance_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT workflow_instance_planned_executor_id_fkey FOREIGN KEY (planned_executor_id) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.request_participant (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  user_id uuid NOT NULL,
  first_joined_at timestamp with time zone NOT NULL DEFAULT now(),
  joined_as character varying NOT NULL CHECK (joined_as::text = ANY (ARRAY['REQUESTER'::character varying, 'APPROVER'::character varying, 'EXECUTOR'::character varying, 'ACCEPTOR'::character varying]::text[])),
  read_revoked_at timestamp with time zone,
  read_revoked_reason character varying,
  CONSTRAINT request_participant_pkey PRIMARY KEY (id),
  CONSTRAINT request_participant_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT request_participant_user_id_fkey FOREIGN KEY (user_id) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.approval_step (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  instance_id uuid NOT NULL,
  step_no smallint NOT NULL CHECK (step_no >= 1 AND step_no <= 3),
  assignee_id uuid NOT NULL,
  state character varying NOT NULL DEFAULT 'WAITING'::character varying CHECK (state::text = ANY (ARRAY['WAITING'::character varying, 'ACTIVE'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'NEEDS_INFO'::character varying, 'SKIPPED'::character varying]::text[])),
  activated_at timestamp with time zone,
  closed_at timestamp with time zone,
  CONSTRAINT approval_step_pkey PRIMARY KEY (id),
  CONSTRAINT approval_step_assignee_id_fkey FOREIGN KEY (assignee_id) REFERENCES eas.app_user(id),
  CONSTRAINT step_instance_same_request FOREIGN KEY (instance_id) REFERENCES eas.workflow_instance(id),
  CONSTRAINT step_instance_same_request FOREIGN KEY (request_id) REFERENCES eas.workflow_instance(request_id),
  CONSTRAINT approval_step_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id)
);
CREATE TABLE eas.approval_decision (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  step_id uuid NOT NULL UNIQUE,
  actor_id uuid NOT NULL,
  outcome character varying NOT NULL CHECK (outcome::text = ANY (ARRAY['APPROVE'::character varying, 'REJECT'::character varying, 'NEEDS_INFO'::character varying]::text[])),
  reason character varying,
  decided_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT approval_decision_pkey PRIMARY KEY (id),
  CONSTRAINT approval_decision_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT approval_decision_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES eas.app_user(id),
  CONSTRAINT decision_step_same_request FOREIGN KEY (step_id) REFERENCES eas.approval_step(id),
  CONSTRAINT decision_step_same_request FOREIGN KEY (request_id) REFERENCES eas.approval_step(request_id)
);
CREATE TABLE eas.execution_attempt (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  instance_id uuid NOT NULL,
  attempt_no integer NOT NULL CHECK (attempt_no > 0),
  executor_id uuid NOT NULL,
  state character varying NOT NULL DEFAULT 'READY'::character varying CHECK (state::text = ANY (ARRAY['READY'::character varying, 'RUNNING'::character varying, 'SUBMITTED'::character varying, 'FINISHED'::character varying]::text[])),
  closure_kind character varying CHECK (closure_kind::text = ANY (ARRAY['SUCCESS'::character varying, 'ACCEPTED'::character varying, 'REWORK'::character varying, 'REASSIGNED'::character varying]::text[])),
  result_note character varying,
  external_reference character varying,
  started_at timestamp with time zone,
  submitted_at timestamp with time zone,
  closed_at timestamp with time zone,
  CONSTRAINT execution_attempt_pkey PRIMARY KEY (id),
  CONSTRAINT execution_attempt_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT execution_attempt_executor_id_fkey FOREIGN KEY (executor_id) REFERENCES eas.app_user(id),
  CONSTRAINT attempt_instance_same_request FOREIGN KEY (instance_id) REFERENCES eas.workflow_instance(id),
  CONSTRAINT attempt_instance_same_request FOREIGN KEY (request_id) REFERENCES eas.workflow_instance(request_id)
);
CREATE TABLE eas.acceptance_decision (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  attempt_id uuid NOT NULL UNIQUE,
  actor_id uuid NOT NULL,
  outcome character varying NOT NULL CHECK (outcome::text = ANY (ARRAY['ACCEPT'::character varying, 'REWORK'::character varying]::text[])),
  reason character varying,
  decided_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT acceptance_decision_pkey PRIMARY KEY (id),
  CONSTRAINT acceptance_decision_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT acceptance_decision_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES eas.app_user(id),
  CONSTRAINT acceptance_attempt_same_request FOREIGN KEY (attempt_id) REFERENCES eas.execution_attempt(id),
  CONSTRAINT acceptance_attempt_same_request FOREIGN KEY (request_id) REFERENCES eas.execution_attempt(request_id)
);
CREATE TABLE eas.execution_issue (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  attempt_id uuid NOT NULL,
  actor_id uuid NOT NULL,
  kind character varying NOT NULL CHECK (kind::text = ANY (ARRAY['UNABLE_TO_CLAIM'::character varying, 'BLOCKED'::character varying]::text[])),
  reason character varying NOT NULL CHECK (length(btrim(reason::text)) >= 10 AND length(btrim(reason::text)) <= 2000),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT execution_issue_pkey PRIMARY KEY (id),
  CONSTRAINT execution_issue_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT execution_issue_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES eas.app_user(id),
  CONSTRAINT issue_attempt_same_request FOREIGN KEY (attempt_id) REFERENCES eas.execution_attempt(id),
  CONSTRAINT issue_attempt_same_request FOREIGN KEY (request_id) REFERENCES eas.execution_attempt(request_id)
);
CREATE TABLE eas.attachment (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  uploader_id uuid NOT NULL,
  storage_key character varying NOT NULL UNIQUE CHECK (length(storage_key::text) > 0),
  object_version character varying NOT NULL CHECK (length(object_version::text) > 0),
  original_name character varying NOT NULL CHECK (length(btrim(original_name::text)) > 0 AND POSITION(('/'::text) IN (original_name)) = 0 AND POSITION((chr(92)) IN (original_name)) = 0 AND POSITION(('..'::text) IN (original_name)) = 0),
  mime character varying NOT NULL CHECK (mime::text = ANY (ARRAY['application/pdf'::character varying, 'image/jpeg'::character varying, 'image/png'::character varying]::text[])),
  size_bytes bigint NOT NULL CHECK (size_bytes >= 1 AND size_bytes <= 10485760),
  sha256 character NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'::text),
  scan_state character varying NOT NULL DEFAULT 'QUEUED'::character varying CHECK (scan_state::text = ANY (ARRAY['QUEUED'::character varying, 'CLEAN'::character varying, 'INFECTED'::character varying, 'ERROR'::character varying]::text[])),
  scan_attempts integer NOT NULL DEFAULT 0 CHECK (scan_attempts >= 0 AND scan_attempts <= 3),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  scanned_at timestamp with time zone,
  deleted_at timestamp with time zone,
  CONSTRAINT attachment_pkey PRIMARY KEY (id),
  CONSTRAINT attachment_uploader_id_fkey FOREIGN KEY (uploader_id) REFERENCES eas.app_user(id),
  CONSTRAINT attachment_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id)
);
CREATE TABLE eas.draft_attachment (
  request_id uuid NOT NULL,
  attachment_id uuid NOT NULL,
  added_by uuid NOT NULL,
  added_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT draft_attachment_pkey PRIMARY KEY (request_id, attachment_id),
  CONSTRAINT draft_file_same_request FOREIGN KEY (attachment_id) REFERENCES eas.attachment(id),
  CONSTRAINT draft_file_same_request FOREIGN KEY (request_id) REFERENCES eas.attachment(request_id),
  CONSTRAINT draft_attachment_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT draft_attachment_added_by_fkey FOREIGN KEY (added_by) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.revision_attachment (
  revision_id uuid NOT NULL,
  attachment_id uuid NOT NULL,
  request_id uuid NOT NULL,
  CONSTRAINT revision_attachment_pkey PRIMARY KEY (revision_id, attachment_id),
  CONSTRAINT revision_attachment_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT revision_link_same_request FOREIGN KEY (revision_id) REFERENCES eas.request_revision(id),
  CONSTRAINT revision_link_same_request FOREIGN KEY (request_id) REFERENCES eas.request_revision(request_id),
  CONSTRAINT revision_file_same_request FOREIGN KEY (attachment_id) REFERENCES eas.attachment(id),
  CONSTRAINT revision_file_same_request FOREIGN KEY (request_id) REFERENCES eas.attachment(request_id)
);
CREATE TABLE eas.execution_attachment (
  attempt_id uuid NOT NULL,
  attachment_id uuid NOT NULL,
  request_id uuid NOT NULL,
  CONSTRAINT execution_attachment_pkey PRIMARY KEY (attempt_id, attachment_id),
  CONSTRAINT execution_attachment_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT execution_link_same_request FOREIGN KEY (attempt_id) REFERENCES eas.execution_attempt(id),
  CONSTRAINT execution_link_same_request FOREIGN KEY (request_id) REFERENCES eas.execution_attempt(request_id),
  CONSTRAINT execution_file_same_request FOREIGN KEY (attachment_id) REFERENCES eas.attachment(id),
  CONSTRAINT execution_file_same_request FOREIGN KEY (request_id) REFERENCES eas.attachment(request_id)
);
CREATE TABLE eas.sla_stage (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  kind character varying NOT NULL CHECK (kind::text = ANY (ARRAY['APPROVAL'::character varying, 'EXECUTION'::character varying, 'ACCEPTANCE'::character varying]::text[])),
  approval_step_id uuid,
  attempt_id uuid,
  started_at timestamp with time zone NOT NULL DEFAULT now(),
  due_at timestamp with time zone NOT NULL,
  closed_at timestamp with time zone,
  breached_at timestamp with time zone,
  CONSTRAINT sla_stage_pkey PRIMARY KEY (id),
  CONSTRAINT sla_stage_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT sla_step_same_request FOREIGN KEY (approval_step_id) REFERENCES eas.approval_step(id),
  CONSTRAINT sla_step_same_request FOREIGN KEY (request_id) REFERENCES eas.approval_step(request_id),
  CONSTRAINT sla_attempt_same_request FOREIGN KEY (attempt_id) REFERENCES eas.execution_attempt(id),
  CONSTRAINT sla_attempt_same_request FOREIGN KEY (request_id) REFERENCES eas.execution_attempt(request_id)
);
CREATE TABLE eas.sla_alert (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  stage_id uuid NOT NULL,
  kind character varying NOT NULL CHECK (kind::text = ANY (ARRAY['REMINDER'::character varying, 'BREACH'::character varying]::text[])),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT sla_alert_pkey PRIMARY KEY (id),
  CONSTRAINT sla_alert_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT alert_stage_same_request FOREIGN KEY (stage_id) REFERENCES eas.sla_stage(id),
  CONSTRAINT alert_stage_same_request FOREIGN KEY (request_id) REFERENCES eas.sla_stage(request_id)
);
CREATE TABLE eas.audit_head (
  scope_key character varying NOT NULL CHECK (scope_key::text = 'ADMIN'::text OR scope_key::text ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text),
  seq bigint NOT NULL DEFAULT 0 CHECK (seq >= 0),
  last_hash character NOT NULL DEFAULT repeat('0'::text, 64) CHECK (last_hash ~ '^[0-9a-f]{64}$'::text),
  CONSTRAINT audit_head_pkey PRIMARY KEY (scope_key)
);
CREATE TABLE eas.audit_event (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  seq bigint NOT NULL CHECK (seq > 0),
  actor_id uuid,
  actor_kind character varying NOT NULL CHECK (actor_kind::text = ANY (ARRAY['HUMAN'::character varying, 'SYSTEM'::character varying]::text[])),
  action character varying NOT NULL CHECK (length(btrim(action::text)) > 0),
  target_type character varying NOT NULL CHECK (length(btrim(target_type::text)) > 0),
  target_id uuid NOT NULL,
  details jsonb NOT NULL CHECK (jsonb_typeof(details) = 'object'::text),
  correlation_id uuid NOT NULL,
  occurred_at timestamp with time zone NOT NULL DEFAULT now(),
  hash_version smallint NOT NULL DEFAULT 1 CHECK (hash_version = 1),
  prev_hash character NOT NULL CHECK (prev_hash ~ '^[0-9a-f]{64}$'::text),
  hash character NOT NULL CHECK (hash ~ '^[0-9a-f]{64}$'::text),
  CONSTRAINT audit_event_pkey PRIMARY KEY (id),
  CONSTRAINT audit_event_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES eas.app_user(id),
  CONSTRAINT audit_event_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id)
);
CREATE TABLE eas.admin_event (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  seq bigint NOT NULL UNIQUE CHECK (seq > 0),
  actor_id uuid,
  actor_kind character varying NOT NULL CHECK (actor_kind::text = ANY (ARRAY['HUMAN'::character varying, 'SYSTEM'::character varying]::text[])),
  action character varying NOT NULL CHECK (length(btrim(action::text)) > 0),
  target_type character varying NOT NULL CHECK (length(btrim(target_type::text)) > 0),
  target_id character varying NOT NULL CHECK (length(btrim(target_id::text)) > 0),
  department_id uuid,
  type_id uuid,
  details jsonb NOT NULL CHECK (jsonb_typeof(details) = 'object'::text),
  reason text NOT NULL CHECK (length(btrim(reason)) >= 10 AND length(btrim(reason)) <= 2000),
  correlation_id uuid NOT NULL,
  occurred_at timestamp with time zone NOT NULL DEFAULT now(),
  hash_version smallint NOT NULL DEFAULT 1 CHECK (hash_version = 1),
  prev_hash character NOT NULL CHECK (prev_hash ~ '^[0-9a-f]{64}$'::text),
  hash character NOT NULL CHECK (hash ~ '^[0-9a-f]{64}$'::text),
  CONSTRAINT admin_event_pkey PRIMARY KEY (id),
  CONSTRAINT admin_event_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES eas.app_user(id),
  CONSTRAINT admin_event_department_id_fkey FOREIGN KEY (department_id) REFERENCES eas.department(id),
  CONSTRAINT admin_event_type_id_fkey FOREIGN KEY (type_id) REFERENCES eas.request_type(id)
);
CREATE TABLE eas.audit_checkpoint (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  scope_key character varying NOT NULL CHECK (scope_key::text = 'ADMIN'::text OR scope_key::text ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text),
  seq bigint NOT NULL CHECK (seq >= 0),
  hash character NOT NULL CHECK (hash ~ '^[0-9a-f]{64}$'::text),
  external_object_key character varying NOT NULL CHECK (length(external_object_key::text) > 0),
  external_version character varying NOT NULL CHECK (length(external_version::text) > 0),
  captured_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT audit_checkpoint_pkey PRIMARY KEY (id)
);
CREATE TABLE eas.outbox_event (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid,
  event_type character varying NOT NULL CHECK (length(btrim(event_type::text)) > 0),
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'::text),
  state character varying NOT NULL DEFAULT 'PENDING'::character varying CHECK (state::text = ANY (ARRAY['PENDING'::character varying, 'PROCESSING'::character varying, 'SENT'::character varying, 'DEAD'::character varying]::text[])),
  dedupe_key character varying NOT NULL UNIQUE CHECK (length(dedupe_key::text) > 0),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= 4),
  replay_count integer NOT NULL DEFAULT 0 CHECK (replay_count >= 0),
  available_at timestamp with time zone NOT NULL DEFAULT now(),
  lease_token uuid,
  lease_until timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  sent_at timestamp with time zone,
  last_error_code character varying,
  CONSTRAINT outbox_event_pkey PRIMARY KEY (id),
  CONSTRAINT outbox_event_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id)
);
CREATE TABLE eas.notification (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  recipient_id uuid NOT NULL,
  request_id uuid,
  label character varying NOT NULL CHECK (length(btrim(label::text)) > 0),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  read_at timestamp with time zone,
  CONSTRAINT notification_pkey PRIMARY KEY (id),
  CONSTRAINT notification_event_id_fkey FOREIGN KEY (event_id) REFERENCES eas.outbox_event(id),
  CONSTRAINT notification_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES eas.app_user(id),
  CONSTRAINT notification_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id)
);
CREATE TABLE eas.idempotency_record (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  actor_id uuid NOT NULL,
  command_scope character varying NOT NULL CHECK (length(command_scope::text) > 0),
  key character varying NOT NULL CHECK (key::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text),
  request_hash character NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'::text),
  http_status smallint NOT NULL CHECK (http_status >= 200 AND http_status <= 299),
  response_body jsonb,
  request_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  expires_at timestamp with time zone NOT NULL DEFAULT (now() + '7 days'::interval),
  tombstone_until timestamp with time zone NOT NULL DEFAULT (now() + '30 days'::interval),
  CONSTRAINT idempotency_record_pkey PRIMARY KEY (id),
  CONSTRAINT idempotency_record_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES eas.app_user(id),
  CONSTRAINT idempotency_record_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id)
);
CREATE TABLE eas.privacy_case (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  subject_user_id uuid NOT NULL,
  case_type character varying NOT NULL CHECK (case_type::text = ANY (ARRAY['ACCESS'::character varying, 'CORRECT'::character varying, 'ERASE'::character varying, 'RESTRICT'::character varying, 'OBJECT'::character varying]::text[])),
  status character varying NOT NULL DEFAULT 'OPEN'::character varying CHECK (status::text = ANY (ARRAY['OPEN'::character varying, 'REVIEW'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'DONE'::character varying]::text[])),
  requested_at timestamp with time zone NOT NULL DEFAULT now(),
  due_at timestamp with time zone NOT NULL,
  completed_at timestamp with time zone,
  policy_version character varying NOT NULL CHECK (length(btrim(policy_version::text)) > 0),
  owner_id uuid NOT NULL,
  decision_reference character varying,
  CONSTRAINT privacy_case_pkey PRIMARY KEY (id),
  CONSTRAINT privacy_case_subject_user_id_fkey FOREIGN KEY (subject_user_id) REFERENCES eas.app_user(id),
  CONSTRAINT privacy_case_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.retention_hold (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL,
  reason character varying NOT NULL CHECK (length(btrim(reason::text)) >= 10 AND length(btrim(reason::text)) <= 2000),
  authority_reference character varying NOT NULL CHECK (length(btrim(authority_reference::text)) > 0),
  set_by uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  released_at timestamp with time zone,
  released_by uuid,
  CONSTRAINT retention_hold_pkey PRIMARY KEY (id),
  CONSTRAINT retention_hold_request_id_fkey FOREIGN KEY (request_id) REFERENCES eas.request(id),
  CONSTRAINT retention_hold_set_by_fkey FOREIGN KEY (set_by) REFERENCES eas.app_user(id),
  CONSTRAINT retention_hold_released_by_fkey FOREIGN KEY (released_by) REFERENCES eas.app_user(id)
);
CREATE TABLE eas.lifecycle (
  code character NOT NULL CHECK (code = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar])),
  name character varying NOT NULL CHECK (length(btrim(name::text)) > 0),
  description character varying NOT NULL CHECK (length(btrim(description::text)) > 0),
  has_execution boolean NOT NULL DEFAULT false,
  has_acceptance boolean NOT NULL DEFAULT false,
  CONSTRAINT lifecycle_pkey PRIMARY KEY (code)
);
CREATE TABLE eas.role (
  code character varying NOT NULL CHECK (code::text = upper(btrim(code::text)) AND length(code::text) > 0),
  name character varying NOT NULL CHECK (length(btrim(name::text)) > 0),
  description character varying NOT NULL CHECK (length(btrim(description::text)) > 0),
  is_system boolean NOT NULL DEFAULT true,
  CONSTRAINT role_pkey PRIMARY KEY (code)
);