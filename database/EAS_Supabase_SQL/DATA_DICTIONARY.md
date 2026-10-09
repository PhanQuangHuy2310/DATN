# EAS 2.0.1 — Từ điển dữ liệu vật lý

Nguồn: `03_Du_lieu_va_API_v2.docx`, DB01–DB30. Trích từ PostgreSQL sau khi cài script 00; schema `eas`. Có 30 bảng và 260 cột. Mọi FK dùng ON DELETE RESTRICT. Cột nullable hiển thị Có/Không; NULL nghĩa là không có default trong DDL.

| ID nguồn | Bảng | Số cột | Chức năng |
|---|---|---:|---|
| DB01 | `security_epoch` | 3 | Một hàng khóa dùng chung cho thay đổi quyền và lệnh nghiệp vụ. |
| DB02 | `department` | 5 | Phòng ban; scope phòng không tự bao gồm phòng con. |
| DB03 | `app_user` | 10 | Tài khoản backend, không phải auth.users của Supabase; hash Argon2 do backend tạo. |
| DB04 | `role_membership` | 10 | Quyền nghiệp vụ theo người, phòng, loại và khoảng hiệu lực; khác PostgreSQL role. |
| DB05 | `request_type` | 5 | Ba loại hồ sơ P0. Con trỏ release được gắn FK sau khi tạo config_release. |
| DB06 | `config_release` | 15 | Snapshot cấu hình; bốn JSON đều có schema_version=1 khi publish; published bất biến. |
| DB07 | `request` | 15 | Hồ sơ hiện hành. Mã dùng sequence toàn cục có thể có khoảng trống; không reset theo năm. |
| DB08 | `request_revision` | 10 | Revision bất biến, chụp phòng, dữ liệu và release mỗi lần gửi. |
| DB09 | `workflow_instance` | 11 | Một instance cho mỗi revision; resolved_route là mảng actor ban đầu, gán thay không sửa snapshot. |
| DB10 | `request_participant` | 7 | Lịch sử tham gia và quyền đọc độc lập với role nghiệp vụ. |
| DB11 | `approval_step` | 8 | Cấp duyệt 1–3; một ACTIVE; người duyệt trong cùng instance khác nhau. |
| DB12 | `approval_decision` | 7 | Quyết định duyệt append only; ghi trước khi đóng step trong transaction service. |
| DB13 | `execution_attempt` | 12 | Vòng thực hiện; REWORK và đổi executor RUNNING tạo vòng mới; kết quả đã nộp bất biến. |
| DB14 | `acceptance_decision` | 7 | Nghiệm thu C; actor khác executor thực tế; một quyết định mỗi attempt. |
| DB15 | `execution_issue` | 7 | Sự kiện báo vướng; không phải trạng thái riêng và không dừng SLA. |
| DB16 | `attachment` | 14 | Metadata tệp riêng tư; không tạo object/bucket; object_version là phiên bản thực của kho lưu trữ. |
| DB17 | `draft_attachment` | 4 | Tập tệp nháp, có thể bỏ chọn mà không xóa tệp lịch sử. |
| DB18 | `revision_attachment` | 3 | Tệp chụp theo revision; append only. |
| DB19 | `execution_attachment` | 3 | Bằng chứng do executor upload; thêm trong lúc RUNNING trước khi nộp kết quả. |
| DB20 | `sla_stage` | 9 | Một stage mở/request; gán thay giữ ID và due_at, chỉ cập nhật target attempt khi cần. |
| DB21 | `sla_alert` | 5 | Khử trùng reminder/breach theo stage. |
| DB22 | `audit_event` | 14 | Audit request; backend cung cấp SHA256 RFC8785/NFC, DB kiểm seq/prev_hash dưới khóa. |
| DB23 | `admin_event` | 16 | Audit cấu hình/quyền/vận hành; không cần request giả; một chuỗi ADMIN. |
| DB24 | `audit_head` | 3 | Đầu chuỗi; trigger append cập nhật nguyên tử, không thay checkpoint ngoài DB. |
| DB25 | `audit_checkpoint` | 7 | Con trỏ checkpoint bên ngoài; không FK audit_head để giữ chứng cứ theo retention riêng. |
| DB26 | `outbox_event` | 14 | Outbox bốn lần thử mỗi chu kỳ; lease và ACK do worker; payload chỉ metadata tối thiểu. |
| DB27 | `notification` | 7 | Thông báo của recipient; read_at lần đầu bất biến; request phải khớp event kể cả NULL. |
| DB28 | `idempotency_record` | 11 | Lưu kết quả thành công 7 ngày; tombstone 30 ngày; không dedupe vô hạn. |
| DB29 | `privacy_case` | 10 | Hồ sơ quyền dữ liệu; pháp chế đặt due_at, không có thời hạn pháp lý mặc định. |
| DB30 | `retention_hold` | 8 | Legal hold; chỉ nhả hold theo phê duyệt, không tự xóa để purge. |

## DB01 — eas.security_epoch

Một hàng khóa dùng chung cho thay đổi quyền và lệnh nghiệp vụ.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `smallint` | Không | `1` |
| `version` | `bigint` | Không | `0` |
| `updated_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `security_epoch_id_check`: `CHECK (id = 1)`
- `security_epoch_id_not_null`: `NOT NULL id`
- `security_epoch_pkey`: `PRIMARY KEY (id)`
- `security_epoch_updated_at_not_null`: `NOT NULL updated_at`
- `security_epoch_version_check`: `CHECK (version >= 0)`
- `security_epoch_version_not_null`: `NOT NULL version`

Chỉ mục:

- `CREATE UNIQUE INDEX security_epoch_pkey ON eas.security_epoch USING btree (id)`

Guard/trigger:

- `security_epoch_guard`: `CREATE TRIGGER security_epoch_guard BEFORE DELETE OR UPDATE ON eas.security_epoch FOR EACH ROW EXECUTE FUNCTION eas.guard_security_epoch()`

## DB02 — eas.department

Phòng ban; scope phòng không tự bao gồm phòng con.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `code` | `character varying(30)` | Không | NULL |
| `name` | `character varying(150)` | Không | NULL |
| `parent_id` | `uuid` | Có | NULL |
| `is_active` | `boolean` | Không | `true` |

Ràng buộc:

- `department_acyclic`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `department_code_check`: `CHECK (code::text = btrim(code::text) AND length(code::text) > 0)`
- `department_code_key`: `UNIQUE (code)`
- `department_code_not_null`: `NOT NULL code`
- `department_id_not_null`: `NOT NULL id`
- `department_is_active_not_null`: `NOT NULL is_active`
- `department_name_check`: `CHECK (length(btrim(name::text)) > 0)`
- `department_name_not_null`: `NOT NULL name`
- `department_no_self`: `CHECK (parent_id IS NULL OR parent_id <> id)`
- `department_parent_id_fkey`: `FOREIGN KEY (parent_id) REFERENCES eas.department(id) ON DELETE RESTRICT`
- `department_pkey`: `PRIMARY KEY (id)`

Chỉ mục:

- `CREATE UNIQUE INDEX department_code_key ON eas.department USING btree (code)`
- `CREATE UNIQUE INDEX department_pkey ON eas.department USING btree (id)`
- `CREATE INDEX ix_department_parent_id ON eas.department USING btree (parent_id)`

Guard/trigger:

- `a_security_department`: `CREATE TRIGGER a_security_department BEFORE INSERT OR DELETE OR UPDATE ON eas.department FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change()`
- `department_acyclic`: `CREATE CONSTRAINT TRIGGER department_acyclic AFTER INSERT OR UPDATE ON eas.department DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_hierarchy()`

## DB03 — eas.app_user

Tài khoản backend, không phải auth.users của Supabase; hash Argon2 do backend tạo.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `username` | `character varying(80)` | Không | NULL |
| `display_name` | `character varying(150)` | Không | NULL |
| `department_id` | `uuid` | Không | NULL |
| `manager_id` | `uuid` | Có | NULL |
| `is_active` | `boolean` | Không | `true` |
| `must_change_password` | `boolean` | Không | `true` |
| `auth_version` | `bigint` | Không | `0` |
| `password_hash` | `text` | Không | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `app_user_auth_version_check`: `CHECK (auth_version >= 0)`
- `app_user_auth_version_not_null`: `NOT NULL auth_version`
- `app_user_created_at_not_null`: `NOT NULL created_at`
- `app_user_department_id_fkey`: `FOREIGN KEY (department_id) REFERENCES eas.department(id) ON DELETE RESTRICT`
- `app_user_department_id_not_null`: `NOT NULL department_id`
- `app_user_display_name_check`: `CHECK (length(btrim(display_name::text)) > 0)`
- `app_user_display_name_not_null`: `NOT NULL display_name`
- `app_user_id_not_null`: `NOT NULL id`
- `app_user_is_active_not_null`: `NOT NULL is_active`
- `app_user_manager_id_fkey`: `FOREIGN KEY (manager_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `app_user_must_change_password_not_null`: `NOT NULL must_change_password`
- `app_user_password_hash_check`: `CHECK (length(password_hash) > 0)`
- `app_user_password_hash_not_null`: `NOT NULL password_hash`
- `app_user_pkey`: `PRIMARY KEY (id)`
- `app_user_username_check`: `CHECK (username::text = lower(btrim(username::text)) AND length(username::text) > 0)`
- `app_user_username_key`: `UNIQUE (username)`
- `app_user_username_not_null`: `NOT NULL username`
- `manager_acyclic`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `user_no_self_manager`: `CHECK (manager_id IS NULL OR manager_id <> id)`

Chỉ mục:

- `CREATE UNIQUE INDEX app_user_pkey ON eas.app_user USING btree (id)`
- `CREATE UNIQUE INDEX app_user_username_key ON eas.app_user USING btree (username)`
- `CREATE INDEX ix_app_user_department_id ON eas.app_user USING btree (department_id)`
- `CREATE INDEX ix_app_user_manager_id ON eas.app_user USING btree (manager_id)`

Guard/trigger:

- `a_security_user`: `CREATE TRIGGER a_security_user BEFORE INSERT OR DELETE OR UPDATE ON eas.app_user FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change()`
- `manager_acyclic`: `CREATE CONSTRAINT TRIGGER manager_acyclic AFTER INSERT OR UPDATE ON eas.app_user DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_hierarchy()`

## DB04 — eas.role_membership

Quyền nghiệp vụ theo người, phòng, loại và khoảng hiệu lực; khác PostgreSQL role.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `user_id` | `uuid` | Không | NULL |
| `role` | `character varying(24)` | Không | NULL |
| `scope_kind` | `character varying(12)` | Không | NULL |
| `department_id` | `uuid` | Có | NULL |
| `type_scope` | `character varying(3)` | Không | NULL |
| `type_id` | `uuid` | Có | NULL |
| `valid_from` | `timestamp with time zone` | Không | `now()` |
| `valid_to` | `timestamp with time zone` | Có | NULL |
| `revoked_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `role_department_scope`: `CHECK (scope_kind::text = 'GLOBAL'::text AND department_id IS NULL OR scope_kind::text = 'DEPARTMENT'::text AND department_id IS NOT NULL)`
- `role_membership_department_id_fkey`: `FOREIGN KEY (department_id) REFERENCES eas.department(id) ON DELETE RESTRICT`
- `role_membership_id_not_null`: `NOT NULL id`
- `role_membership_pkey`: `PRIMARY KEY (id)`
- `role_membership_role_check`: `CHECK (role::text = ANY (ARRAY['REQUESTER'::character varying, 'APPROVER'::character varying, 'EXECUTOR'::character varying, 'ACCEPTOR'::character varying, 'POLICY_ADMIN'::character varying, 'OPS_ADMIN'::character varying, 'AUDITOR'::character varying]::text[]))`
- `role_membership_role_not_null`: `NOT NULL role`
- `role_membership_scope_kind_check`: `CHECK (scope_kind::text = ANY (ARRAY['GLOBAL'::character varying, 'DEPARTMENT'::character varying]::text[]))`
- `role_membership_scope_kind_not_null`: `NOT NULL scope_kind`
- `role_membership_type_id_fkey`: `FOREIGN KEY (type_id) REFERENCES eas.request_type(id) ON DELETE RESTRICT`
- `role_membership_type_scope_check`: `CHECK (type_scope::text = ANY (ARRAY['ALL'::character varying, 'ONE'::character varying]::text[]))`
- `role_membership_type_scope_not_null`: `NOT NULL type_scope`
- `role_membership_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `role_membership_user_id_not_null`: `NOT NULL user_id`
- `role_membership_valid_from_not_null`: `NOT NULL valid_from`
- `role_type_scope`: `CHECK (type_scope::text = 'ALL'::text AND type_id IS NULL OR type_scope::text = 'ONE'::text AND type_id IS NOT NULL)`
- `role_unique_grant`: `UNIQUE NULLS NOT DISTINCT (user_id, role, scope_kind, department_id, type_scope, type_id, valid_from)`
- `role_valid_interval`: `CHECK (valid_to IS NULL OR valid_to > valid_from)`

Chỉ mục:

- `CREATE INDEX ix_role_membership_department_id ON eas.role_membership USING btree (department_id)`
- `CREATE INDEX ix_role_membership_type_id ON eas.role_membership USING btree (type_id)`
- `CREATE INDEX role_lookup ON eas.role_membership USING btree (user_id, role, valid_from)`
- `CREATE UNIQUE INDEX role_membership_pkey ON eas.role_membership USING btree (id)`
- `CREATE UNIQUE INDEX role_unique_grant ON eas.role_membership USING btree (user_id, role, scope_kind, department_id, type_scope, type_id, valid_from) NULLS NOT DISTINCT`

Guard/trigger:

- `a_security_role`: `CREATE TRIGGER a_security_role BEFORE INSERT OR DELETE OR UPDATE ON eas.role_membership FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change()`

## DB05 — eas.request_type

Ba loại hồ sơ P0. Con trỏ release được gắn FK sau khi tạo config_release.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `code` | `character varying(30)` | Không | NULL |
| `lifecycle` | `character(1)` | Không | NULL |
| `is_active` | `boolean` | Không | `true` |
| `active_release_id` | `uuid` | Có | NULL |

Ràng buộc:

- `request_type_code_key`: `UNIQUE (code)`
- `request_type_code_not_null`: `NOT NULL code`
- `request_type_id_not_null`: `NOT NULL id`
- `request_type_is_active_not_null`: `NOT NULL is_active`
- `request_type_lifecycle_not_null`: `NOT NULL lifecycle`
- `request_type_pkey`: `PRIMARY KEY (id)`
- `type_active_release_same_type`: `FOREIGN KEY (active_release_id, id) REFERENCES eas.config_release(id, type_id) ON DELETE RESTRICT`
- `type_p0`: `CHECK (code::text = 'LEAVE'::text AND lifecycle = 'A'::bpchar OR code::text = 'ACCESS'::text AND lifecycle = 'B'::bpchar OR code::text = 'EQUIPMENT'::text AND lifecycle = 'C'::bpchar)`

Chỉ mục:

- `CREATE INDEX ix_request_type_active_release_id ON eas.request_type USING btree (active_release_id)`
- `CREATE UNIQUE INDEX request_type_code_key ON eas.request_type USING btree (code)`
- `CREATE UNIQUE INDEX request_type_pkey ON eas.request_type USING btree (id)`

Guard/trigger:

- `active_release_guard`: `CREATE TRIGGER active_release_guard BEFORE INSERT OR UPDATE ON eas.request_type FOR EACH ROW EXECUTE FUNCTION eas.guard_active_release()`

## DB06 — eas.config_release

Snapshot cấu hình; bốn JSON đều có schema_version=1 khi publish; published bất biến.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `type_id` | `uuid` | Không | NULL |
| `version` | `integer` | Không | NULL |
| `state` | `character varying(9)` | Không | `'DRAFT'::character varying` |
| `lifecycle` | `character(1)` | Không | NULL |
| `form_schema` | `jsonb` | Không | NULL |
| `route_rules` | `jsonb` | Không | NULL |
| `actor_bindings` | `jsonb` | Không | NULL |
| `sla_profile` | `jsonb` | Không | NULL |
| `created_by` | `uuid` | Không | NULL |
| `published_by` | `uuid` | Có | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `published_at` | `timestamp with time zone` | Có | NULL |
| `lock_version` | `bigint` | Không | `0` |
| `content_sha256` | `character(64)` | Có | NULL |

Ràng buộc:

- `config_release_actor_bindings_check`: `CHECK (jsonb_typeof(actor_bindings) = 'object'::text)`
- `config_release_actor_bindings_not_null`: `NOT NULL actor_bindings`
- `config_release_created_at_not_null`: `NOT NULL created_at`
- `config_release_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `config_release_created_by_not_null`: `NOT NULL created_by`
- `config_release_form_schema_check`: `CHECK (jsonb_typeof(form_schema) = 'object'::text)`
- `config_release_form_schema_not_null`: `NOT NULL form_schema`
- `config_release_id_not_null`: `NOT NULL id`
- `config_release_lifecycle_check`: `CHECK (lifecycle = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar]))`
- `config_release_lifecycle_not_null`: `NOT NULL lifecycle`
- `config_release_lock_version_check`: `CHECK (lock_version >= 0)`
- `config_release_lock_version_not_null`: `NOT NULL lock_version`
- `config_release_pkey`: `PRIMARY KEY (id)`
- `config_release_published_by_fkey`: `FOREIGN KEY (published_by) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `config_release_route_rules_check`: `CHECK (jsonb_typeof(route_rules) = 'object'::text)`
- `config_release_route_rules_not_null`: `NOT NULL route_rules`
- `config_release_sla_profile_check`: `CHECK (jsonb_typeof(sla_profile) = 'object'::text)`
- `config_release_sla_profile_not_null`: `NOT NULL sla_profile`
- `config_release_state_check`: `CHECK (state::text = ANY (ARRAY['DRAFT'::character varying, 'PUBLISHED'::character varying]::text[]))`
- `config_release_state_not_null`: `NOT NULL state`
- `config_release_type_id_fkey`: `FOREIGN KEY (type_id) REFERENCES eas.request_type(id) ON DELETE RESTRICT`
- `config_release_type_id_not_null`: `NOT NULL type_id`
- `config_release_version_check`: `CHECK (version > 0)`
- `config_release_version_not_null`: `NOT NULL version`
- `release_hash_format`: `CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'::text)`
- `release_publish_fields`: `CHECK (state::text = 'DRAFT'::text AND published_by IS NULL AND published_at IS NULL AND content_sha256 IS NULL OR state::text = 'PUBLISHED'::text AND published_by IS NOT NULL AND published_at IS NOT NULL AND content_sha256 IS NOT NULL)`
- `release_publish_time`: `CHECK (published_at IS NULL OR published_at >= created_at)`
- `release_same_type_key`: `UNIQUE (id, type_id)`
- `release_version_unique`: `UNIQUE (type_id, version)`

Chỉ mục:

- `CREATE UNIQUE INDEX config_release_pkey ON eas.config_release USING btree (id)`
- `CREATE INDEX ix_config_release_created_by ON eas.config_release USING btree (created_by)`
- `CREATE INDEX ix_config_release_published_by ON eas.config_release USING btree (published_by)`
- `CREATE UNIQUE INDEX release_same_type_key ON eas.config_release USING btree (id, type_id)`
- `CREATE UNIQUE INDEX release_version_unique ON eas.config_release USING btree (type_id, version)`

Guard/trigger:

- `release_guard`: `CREATE TRIGGER release_guard BEFORE INSERT OR DELETE OR UPDATE ON eas.config_release FOR EACH ROW EXECUTE FUNCTION eas.guard_release()`

## DB07 — eas.request

Hồ sơ hiện hành. Mã dùng sequence toàn cục có thể có khoảng trống; không reset theo năm.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `code` | `character varying(40)` | Không | `eas.next_request_code()` |
| `requester_id` | `uuid` | Không | NULL |
| `type_id` | `uuid` | Không | NULL |
| `status` | `character varying(32)` | Không | `'DRAFT'::character varying` |
| `draft_payload` | `jsonb` | Không | `'{}'::jsonb` |
| `draft_amount_vnd` | `bigint` | Có | NULL |
| `draft_release_id` | `uuid` | Có | NULL |
| `origin_request_id` | `uuid` | Có | NULL |
| `current_revision_id` | `uuid` | Có | NULL |
| `lock_version` | `bigint` | Không | `0` |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `updated_at` | `timestamp with time zone` | Không | `now()` |
| `approved_at` | `timestamp with time zone` | Có | NULL |
| `completed_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `request_approval_required`: `CHECK ((status::text <> ALL (ARRAY['READY_FOR_EXECUTION'::character varying, 'IN_PROGRESS'::character varying, 'WAITING_FOR_ACCEPTANCE'::character varying, 'COMPLETED'::character varying]::text[])) OR approved_at IS NOT NULL)`
- `request_approved_time`: `CHECK (approved_at IS NULL OR approved_at >= created_at)`
- `request_code_key`: `UNIQUE (code)`
- `request_code_not_null`: `NOT NULL code`
- `request_complete_time`: `CHECK ((status::text = 'COMPLETED'::text) = (completed_at IS NOT NULL))`
- `request_completed_after_approval`: `CHECK (completed_at IS NULL OR approved_at IS NOT NULL AND completed_at >= approved_at)`
- `request_created_at_not_null`: `NOT NULL created_at`
- `request_current_revision_same_request`: `FOREIGN KEY (current_revision_id, id) REFERENCES eas.request_revision(id, request_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED`
- `request_draft_amount_vnd_check`: `CHECK (draft_amount_vnd >= 1 AND draft_amount_vnd <= '1000000000000'::bigint)`
- `request_draft_payload_check`: `CHECK (jsonb_typeof(draft_payload) = 'object'::text)`
- `request_draft_payload_not_null`: `NOT NULL draft_payload`
- `request_draft_release_type`: `FOREIGN KEY (draft_release_id, type_id) REFERENCES eas.config_release(id, type_id) ON DELETE RESTRICT`
- `request_id_not_null`: `NOT NULL id`
- `request_lock_version_check`: `CHECK (lock_version >= 0)`
- `request_lock_version_not_null`: `NOT NULL lock_version`
- `request_no_self_origin`: `CHECK (origin_request_id IS NULL OR origin_request_id <> id)`
- `request_origin_request_id_fkey`: `FOREIGN KEY (origin_request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `request_pkey`: `PRIMARY KEY (id)`
- `request_requester_id_fkey`: `FOREIGN KEY (requester_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `request_requester_id_not_null`: `NOT NULL requester_id`
- `request_status_check`: `CHECK (status::text = ANY (ARRAY['DRAFT'::character varying, 'NEEDS_INFO'::character varying, 'PENDING_APPROVAL'::character varying, 'READY_FOR_EXECUTION'::character varying, 'IN_PROGRESS'::character varying, 'WAITING_FOR_ACCEPTANCE'::character varying, 'COMPLETED'::character varying, 'REJECTED'::character varying, 'CANCELLED'::character varying]::text[]))`
- `request_status_not_null`: `NOT NULL status`
- `request_type_id_fkey`: `FOREIGN KEY (type_id) REFERENCES eas.request_type(id) ON DELETE RESTRICT`
- `request_type_id_not_null1`: `NOT NULL type_id`
- `request_update_time`: `CHECK (updated_at >= created_at)`
- `request_updated_at_not_null`: `NOT NULL updated_at`

Chỉ mục:

- `CREATE INDEX ix_request_current_revision_id ON eas.request USING btree (current_revision_id)`
- `CREATE INDEX ix_request_draft_release_id ON eas.request USING btree (draft_release_id)`
- `CREATE INDEX ix_request_origin_request_id ON eas.request USING btree (origin_request_id)`
- `CREATE INDEX ix_request_type_id ON eas.request USING btree (type_id)`
- `CREATE UNIQUE INDEX request_code_key ON eas.request USING btree (code)`
- `CREATE INDEX request_owner_updated ON eas.request USING btree (requester_id, updated_at DESC, id DESC)`
- `CREATE UNIQUE INDEX request_pkey ON eas.request USING btree (id)`
- `CREATE INDEX request_status_type_updated ON eas.request USING btree (status, type_id, updated_at DESC, id DESC)`

Guard/trigger:

- `request_guard`: `CREATE TRIGGER request_guard BEFORE INSERT OR DELETE OR UPDATE ON eas.request FOR EACH ROW EXECUTE FUNCTION eas.guard_request()`
- `request_head`: `CREATE TRIGGER request_head AFTER INSERT ON eas.request FOR EACH ROW EXECUTE FUNCTION eas.initialize_request_head()`

## DB08 — eas.request_revision

Revision bất biến, chụp phòng, dữ liệu và release mỗi lần gửi.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `revision_no` | `integer` | Không | NULL |
| `release_id` | `uuid` | Không | NULL |
| `department_id` | `uuid` | Không | NULL |
| `payload` | `jsonb` | Không | NULL |
| `amount_vnd` | `bigint` | Có | NULL |
| `submitted_by` | `uuid` | Không | NULL |
| `submitted_at` | `timestamp with time zone` | Không | `now()` |
| `payload_sha256` | `character(64)` | Không | NULL |

Ràng buộc:

- `request_revision_amount_vnd_check`: `CHECK (amount_vnd >= 1 AND amount_vnd <= '1000000000000'::bigint)`
- `request_revision_department_id_fkey`: `FOREIGN KEY (department_id) REFERENCES eas.department(id) ON DELETE RESTRICT`
- `request_revision_department_id_not_null`: `NOT NULL department_id`
- `request_revision_id_not_null`: `NOT NULL id`
- `request_revision_id_request_id_key`: `UNIQUE (id, request_id)`
- `request_revision_payload_check`: `CHECK (jsonb_typeof(payload) = 'object'::text)`
- `request_revision_payload_not_null`: `NOT NULL payload`
- `request_revision_payload_sha256_check`: `CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'::text)`
- `request_revision_payload_sha256_not_null`: `NOT NULL payload_sha256`
- `request_revision_pkey`: `PRIMARY KEY (id)`
- `request_revision_release_id_fkey`: `FOREIGN KEY (release_id) REFERENCES eas.config_release(id) ON DELETE RESTRICT`
- `request_revision_release_id_not_null`: `NOT NULL release_id`
- `request_revision_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `request_revision_request_id_not_null`: `NOT NULL request_id`
- `request_revision_request_id_revision_no_key`: `UNIQUE (request_id, revision_no)`
- `request_revision_revision_no_check`: `CHECK (revision_no > 0)`
- `request_revision_revision_no_not_null`: `NOT NULL revision_no`
- `request_revision_submitted_at_not_null`: `NOT NULL submitted_at`
- `request_revision_submitted_by_fkey`: `FOREIGN KEY (submitted_by) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `request_revision_submitted_by_not_null`: `NOT NULL submitted_by`
- `revision_files_complete`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`

Chỉ mục:

- `CREATE INDEX ix_request_revision_release_id ON eas.request_revision USING btree (release_id)`
- `CREATE INDEX ix_request_revision_submitted_by ON eas.request_revision USING btree (submitted_by)`
- `CREATE UNIQUE INDEX request_revision_id_request_id_key ON eas.request_revision USING btree (id, request_id)`
- `CREATE UNIQUE INDEX request_revision_pkey ON eas.request_revision USING btree (id)`
- `CREATE UNIQUE INDEX request_revision_request_id_revision_no_key ON eas.request_revision USING btree (request_id, revision_no)`
- `CREATE INDEX revision_department_request ON eas.request_revision USING btree (department_id, request_id)`

Guard/trigger:

- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.request_revision FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`
- `revision_files_complete`: `CREATE CONSTRAINT TRIGGER revision_files_complete AFTER INSERT ON eas.request_revision DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_submission_files()`
- `revision_guard`: `CREATE TRIGGER revision_guard BEFORE INSERT ON eas.request_revision FOR EACH ROW EXECUTE FUNCTION eas.guard_revision()`

## DB09 — eas.workflow_instance

Một instance cho mỗi revision; resolved_route là mảng actor ban đầu, gán thay không sửa snapshot.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `revision_id` | `uuid` | Không | NULL |
| `matched_rule_id` | `character varying(50)` | Không | NULL |
| `resolved_route` | `jsonb` | Không | NULL |
| `lifecycle` | `character(1)` | Không | NULL |
| `state` | `character varying(10)` | Không | `'ACTIVE'::character varying` |
| `planned_executor_id` | `uuid` | Có | NULL |
| `acceptor_id` | `uuid` | Có | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `closed_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `instance_closed`: `CHECK (state::text = 'ACTIVE'::text AND closed_at IS NULL OR state::text <> 'ACTIVE'::text AND closed_at IS NOT NULL AND closed_at >= created_at)`
- `instance_lifecycle_actors`: `CHECK (lifecycle = 'A'::bpchar AND planned_executor_id IS NULL AND acceptor_id IS NULL OR lifecycle = 'B'::bpchar AND planned_executor_id IS NOT NULL AND acceptor_id IS NULL OR lifecycle = 'C'::bpchar AND planned_executor_id IS NOT NULL AND acceptor_id IS NOT NULL)`
- `instance_revision_same_request`: `FOREIGN KEY (revision_id, request_id) REFERENCES eas.request_revision(id, request_id) ON DELETE RESTRICT`
- `workflow_instance_acceptor_id_fkey`: `FOREIGN KEY (acceptor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `workflow_instance_created_at_not_null`: `NOT NULL created_at`
- `workflow_instance_id_not_null`: `NOT NULL id`
- `workflow_instance_id_request_id_key`: `UNIQUE (id, request_id)`
- `workflow_instance_lifecycle_check`: `CHECK (lifecycle = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar]))`
- `workflow_instance_lifecycle_not_null`: `NOT NULL lifecycle`
- `workflow_instance_matched_rule_id_check`: `CHECK (length(btrim(matched_rule_id::text)) > 0)`
- `workflow_instance_matched_rule_id_not_null`: `NOT NULL matched_rule_id`
- `workflow_instance_pkey`: `PRIMARY KEY (id)`
- `workflow_instance_planned_executor_id_fkey`: `FOREIGN KEY (planned_executor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `workflow_instance_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `workflow_instance_request_id_not_null`: `NOT NULL request_id`
- `workflow_instance_resolved_route_check`: `CHECK (jsonb_typeof(resolved_route) = 'array'::text AND jsonb_array_length(resolved_route) >= 1 AND jsonb_array_length(resolved_route) <= 3)`
- `workflow_instance_resolved_route_not_null`: `NOT NULL resolved_route`
- `workflow_instance_revision_id_key`: `UNIQUE (revision_id)`
- `workflow_instance_revision_id_not_null`: `NOT NULL revision_id`
- `workflow_instance_state_check`: `CHECK (state::text = ANY (ARRAY['ACTIVE'::character varying, 'COMPLETED'::character varying, 'REJECTED'::character varying, 'SUPERSEDED'::character varying, 'CANCELLED'::character varying]::text[]))`
- `workflow_instance_state_not_null`: `NOT NULL state`

Chỉ mục:

- `CREATE INDEX ix_workflow_instance_acceptor_id ON eas.workflow_instance USING btree (acceptor_id)`
- `CREATE INDEX ix_workflow_instance_planned_executor_id ON eas.workflow_instance USING btree (planned_executor_id)`
- `CREATE INDEX ix_workflow_instance_request_id ON eas.workflow_instance USING btree (request_id)`
- `CREATE UNIQUE INDEX one_active_instance ON eas.workflow_instance USING btree (request_id) WHERE ((state)::text = 'ACTIVE'::text)`
- `CREATE UNIQUE INDEX workflow_instance_id_request_id_key ON eas.workflow_instance USING btree (id, request_id)`
- `CREATE UNIQUE INDEX workflow_instance_pkey ON eas.workflow_instance USING btree (id)`
- `CREATE UNIQUE INDEX workflow_instance_revision_id_key ON eas.workflow_instance USING btree (revision_id)`

Guard/trigger:

- `instance_guard`: `CREATE TRIGGER instance_guard BEFORE INSERT OR UPDATE ON eas.workflow_instance FOR EACH ROW EXECUTE FUNCTION eas.guard_instance()`
- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.workflow_instance FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`

## DB10 — eas.request_participant

Lịch sử tham gia và quyền đọc độc lập với role nghiệp vụ.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `user_id` | `uuid` | Không | NULL |
| `first_joined_at` | `timestamp with time zone` | Không | `now()` |
| `joined_as` | `character varying(24)` | Không | NULL |
| `read_revoked_at` | `timestamp with time zone` | Có | NULL |
| `read_revoked_reason` | `character varying(2000)` | Có | NULL |

Ràng buộc:

- `participant_revocation`: `CHECK (read_revoked_at IS NULL AND read_revoked_reason IS NULL OR read_revoked_at IS NOT NULL AND read_revoked_reason IS NOT NULL AND length(btrim(read_revoked_reason::text)) >= 10 AND length(btrim(read_revoked_reason::text)) <= 2000)`
- `request_participant_first_joined_at_not_null`: `NOT NULL first_joined_at`
- `request_participant_id_not_null`: `NOT NULL id`
- `request_participant_joined_as_check`: `CHECK (joined_as::text = ANY (ARRAY['REQUESTER'::character varying, 'APPROVER'::character varying, 'EXECUTOR'::character varying, 'ACCEPTOR'::character varying]::text[]))`
- `request_participant_joined_as_not_null`: `NOT NULL joined_as`
- `request_participant_pkey`: `PRIMARY KEY (id)`
- `request_participant_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `request_participant_request_id_not_null`: `NOT NULL request_id`
- `request_participant_request_id_user_id_key`: `UNIQUE (request_id, user_id)`
- `request_participant_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `request_participant_user_id_not_null`: `NOT NULL user_id`

Chỉ mục:

- `CREATE INDEX participant_user_request ON eas.request_participant USING btree (user_id, request_id)`
- `CREATE UNIQUE INDEX request_participant_pkey ON eas.request_participant USING btree (id)`
- `CREATE UNIQUE INDEX request_participant_request_id_user_id_key ON eas.request_participant USING btree (request_id, user_id)`

Guard/trigger:

- `a_security_participant`: `CREATE TRIGGER a_security_participant BEFORE UPDATE OF read_revoked_at, read_revoked_reason ON eas.request_participant FOR EACH ROW EXECUTE FUNCTION eas.lock_security_change()`
- `participant_metadata`: `CREATE TRIGGER participant_metadata BEFORE UPDATE ON eas.request_participant FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata()`
- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.request_participant FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`

## DB11 — eas.approval_step

Cấp duyệt 1–3; một ACTIVE; người duyệt trong cùng instance khác nhau.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `instance_id` | `uuid` | Không | NULL |
| `step_no` | `smallint` | Không | NULL |
| `assignee_id` | `uuid` | Không | NULL |
| `state` | `character varying(10)` | Không | `'WAITING'::character varying` |
| `activated_at` | `timestamp with time zone` | Có | NULL |
| `closed_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `approval_step_assignee_id_fkey`: `FOREIGN KEY (assignee_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `approval_step_assignee_id_not_null`: `NOT NULL assignee_id`
- `approval_step_id_not_null`: `NOT NULL id`
- `approval_step_id_request_id_key`: `UNIQUE (id, request_id)`
- `approval_step_instance_id_assignee_id_key`: `UNIQUE (instance_id, assignee_id)`
- `approval_step_instance_id_not_null`: `NOT NULL instance_id`
- `approval_step_instance_id_step_no_key`: `UNIQUE (instance_id, step_no)`
- `approval_step_pkey`: `PRIMARY KEY (id)`
- `approval_step_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `approval_step_request_id_not_null`: `NOT NULL request_id`
- `approval_step_state_check`: `CHECK (state::text = ANY (ARRAY['WAITING'::character varying, 'ACTIVE'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'NEEDS_INFO'::character varying, 'SKIPPED'::character varying]::text[]))`
- `approval_step_state_not_null`: `NOT NULL state`
- `approval_step_step_no_check`: `CHECK (step_no >= 1 AND step_no <= 3)`
- `approval_step_step_no_not_null`: `NOT NULL step_no`
- `step_instance_same_request`: `FOREIGN KEY (instance_id, request_id) REFERENCES eas.workflow_instance(id, request_id) ON DELETE RESTRICT`
- `step_state_times`: `CHECK (state::text = 'WAITING'::text AND activated_at IS NULL AND closed_at IS NULL OR state::text = 'ACTIVE'::text AND activated_at IS NOT NULL AND closed_at IS NULL OR (state::text = ANY (ARRAY['APPROVED'::character varying, 'REJECTED'::character varying, 'NEEDS_INFO'::character varying]::text[])) AND activated_at IS NOT NULL AND closed_at IS NOT NULL OR state::text = 'SKIPPED'::text AND closed_at IS NOT NULL)`
- `step_time_order`: `CHECK (closed_at IS NULL OR activated_at IS NULL OR closed_at >= activated_at)`

Chỉ mục:

- `CREATE INDEX approval_inbox ON eas.approval_step USING btree (assignee_id, state)`
- `CREATE UNIQUE INDEX approval_step_id_request_id_key ON eas.approval_step USING btree (id, request_id)`
- `CREATE UNIQUE INDEX approval_step_instance_id_assignee_id_key ON eas.approval_step USING btree (instance_id, assignee_id)`
- `CREATE UNIQUE INDEX approval_step_instance_id_step_no_key ON eas.approval_step USING btree (instance_id, step_no)`
- `CREATE UNIQUE INDEX approval_step_pkey ON eas.approval_step USING btree (id)`
- `CREATE INDEX ix_approval_step_request_id ON eas.approval_step USING btree (request_id)`
- `CREATE UNIQUE INDEX one_active_step ON eas.approval_step USING btree (instance_id) WHERE ((state)::text = 'ACTIVE'::text)`

Guard/trigger:

- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.approval_step FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`
- `step_guard`: `CREATE TRIGGER step_guard BEFORE INSERT OR UPDATE ON eas.approval_step FOR EACH ROW EXECUTE FUNCTION eas.guard_step()`

## DB12 — eas.approval_decision

Quyết định duyệt append only; ghi trước khi đóng step trong transaction service.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `step_id` | `uuid` | Không | NULL |
| `actor_id` | `uuid` | Không | NULL |
| `outcome` | `character varying(10)` | Không | NULL |
| `reason` | `character varying(2000)` | Có | NULL |
| `decided_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `approval_decision_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `approval_decision_actor_id_not_null`: `NOT NULL actor_id`
- `approval_decision_decided_at_not_null`: `NOT NULL decided_at`
- `approval_decision_id_not_null`: `NOT NULL id`
- `approval_decision_outcome_check`: `CHECK (outcome::text = ANY (ARRAY['APPROVE'::character varying, 'REJECT'::character varying, 'NEEDS_INFO'::character varying]::text[]))`
- `approval_decision_outcome_not_null`: `NOT NULL outcome`
- `approval_decision_pkey`: `PRIMARY KEY (id)`
- `approval_decision_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `approval_decision_request_id_not_null`: `NOT NULL request_id`
- `approval_decision_step_id_key`: `UNIQUE (step_id)`
- `approval_decision_step_id_not_null`: `NOT NULL step_id`
- `decision_reason`: `CHECK (outcome::text = 'APPROVE'::text OR reason IS NOT NULL AND length(btrim(reason::text)) >= 10 AND length(btrim(reason::text)) <= 2000)`
- `decision_step_same_request`: `FOREIGN KEY (step_id, request_id) REFERENCES eas.approval_step(id, request_id) ON DELETE RESTRICT`

Chỉ mục:

- `CREATE UNIQUE INDEX approval_decision_pkey ON eas.approval_decision USING btree (id)`
- `CREATE UNIQUE INDEX approval_decision_step_id_key ON eas.approval_decision USING btree (step_id)`
- `CREATE INDEX ix_approval_decision_actor_id ON eas.approval_decision USING btree (actor_id)`
- `CREATE INDEX ix_approval_decision_request_id ON eas.approval_decision USING btree (request_id)`

Guard/trigger:

- `approval_decision_guard`: `CREATE TRIGGER approval_decision_guard BEFORE INSERT ON eas.approval_decision FOR EACH ROW EXECUTE FUNCTION eas.guard_decision()`
- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.approval_decision FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`

## DB13 — eas.execution_attempt

Vòng thực hiện; REWORK và đổi executor RUNNING tạo vòng mới; kết quả đã nộp bất biến.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `instance_id` | `uuid` | Không | NULL |
| `attempt_no` | `integer` | Không | NULL |
| `executor_id` | `uuid` | Không | NULL |
| `state` | `character varying(9)` | Không | `'READY'::character varying` |
| `closure_kind` | `character varying(10)` | Có | NULL |
| `result_note` | `character varying(4000)` | Có | NULL |
| `external_reference` | `character varying(200)` | Có | NULL |
| `started_at` | `timestamp with time zone` | Có | NULL |
| `submitted_at` | `timestamp with time zone` | Có | NULL |
| `closed_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `attempt_closure`: `CHECK (state::text = 'FINISHED'::text AND closure_kind IS NOT NULL AND closed_at IS NOT NULL OR state::text <> 'FINISHED'::text AND closure_kind IS NULL AND closed_at IS NULL)`
- `attempt_finished_result`: `CHECK (state::text <> 'FINISHED'::text OR closure_kind::text = 'REASSIGNED'::text AND submitted_at IS NULL OR (closure_kind::text = ANY (ARRAY['SUCCESS'::character varying, 'ACCEPTED'::character varying, 'REWORK'::character varying]::text[])) AND submitted_at IS NOT NULL)`
- `attempt_instance_same_request`: `FOREIGN KEY (instance_id, request_id) REFERENCES eas.workflow_instance(id, request_id) ON DELETE RESTRICT`
- `attempt_progress`: `CHECK (state::text = 'READY'::text AND started_at IS NULL AND submitted_at IS NULL OR state::text = 'RUNNING'::text AND started_at IS NOT NULL AND submitted_at IS NULL OR state::text = 'SUBMITTED'::text AND started_at IS NOT NULL AND submitted_at IS NOT NULL OR state::text = 'FINISHED'::text AND started_at IS NOT NULL)`
- `attempt_result`: `CHECK (submitted_at IS NULL AND result_note IS NULL AND external_reference IS NULL OR submitted_at IS NOT NULL AND result_note IS NOT NULL AND length(btrim(result_note::text)) >= 10 AND length(btrim(result_note::text)) <= 4000 AND external_reference IS NOT NULL AND length(btrim(external_reference::text)) >= 1 AND length(btrim(external_reference::text)) <= 200)`
- `attempt_time_order`: `CHECK ((submitted_at IS NULL OR submitted_at >= started_at) AND (closed_at IS NULL OR closed_at >= started_at) AND (closed_at IS NULL OR submitted_at IS NULL OR closed_at >= submitted_at))`
- `execution_attempt_attempt_no_check`: `CHECK (attempt_no > 0)`
- `execution_attempt_attempt_no_not_null`: `NOT NULL attempt_no`
- `execution_attempt_closure_kind_check`: `CHECK (closure_kind::text = ANY (ARRAY['SUCCESS'::character varying, 'ACCEPTED'::character varying, 'REWORK'::character varying, 'REASSIGNED'::character varying]::text[]))`
- `execution_attempt_executor_id_fkey`: `FOREIGN KEY (executor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `execution_attempt_executor_id_not_null`: `NOT NULL executor_id`
- `execution_attempt_id_not_null`: `NOT NULL id`
- `execution_attempt_id_request_id_key`: `UNIQUE (id, request_id)`
- `execution_attempt_instance_id_attempt_no_key`: `UNIQUE (instance_id, attempt_no)`
- `execution_attempt_instance_id_not_null`: `NOT NULL instance_id`
- `execution_attempt_pkey`: `PRIMARY KEY (id)`
- `execution_attempt_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `execution_attempt_request_id_not_null`: `NOT NULL request_id`
- `execution_attempt_state_check`: `CHECK (state::text = ANY (ARRAY['READY'::character varying, 'RUNNING'::character varying, 'SUBMITTED'::character varying, 'FINISHED'::character varying]::text[]))`
- `execution_attempt_state_not_null`: `NOT NULL state`
- `execution_files_complete`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`

Chỉ mục:

- `CREATE UNIQUE INDEX execution_attempt_id_request_id_key ON eas.execution_attempt USING btree (id, request_id)`
- `CREATE UNIQUE INDEX execution_attempt_instance_id_attempt_no_key ON eas.execution_attempt USING btree (instance_id, attempt_no)`
- `CREATE UNIQUE INDEX execution_attempt_pkey ON eas.execution_attempt USING btree (id)`
- `CREATE INDEX execution_inbox ON eas.execution_attempt USING btree (executor_id, state)`
- `CREATE INDEX ix_execution_attempt_request_id ON eas.execution_attempt USING btree (request_id)`
- `CREATE UNIQUE INDEX one_current_attempt ON eas.execution_attempt USING btree (instance_id) WHERE ((state)::text = ANY ((ARRAY['READY'::character varying, 'RUNNING'::character varying, 'SUBMITTED'::character varying])::text[]))`

Guard/trigger:

- `attempt_guard`: `CREATE TRIGGER attempt_guard BEFORE INSERT OR UPDATE ON eas.execution_attempt FOR EACH ROW EXECUTE FUNCTION eas.guard_attempt()`
- `execution_files_complete`: `CREATE CONSTRAINT TRIGGER execution_files_complete AFTER INSERT OR UPDATE ON eas.execution_attempt DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eas.check_submission_files()`
- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.execution_attempt FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`

## DB14 — eas.acceptance_decision

Nghiệm thu C; actor khác executor thực tế; một quyết định mỗi attempt.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `attempt_id` | `uuid` | Không | NULL |
| `actor_id` | `uuid` | Không | NULL |
| `outcome` | `character varying(6)` | Không | NULL |
| `reason` | `character varying(2000)` | Có | NULL |
| `decided_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `acceptance_attempt_same_request`: `FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT`
- `acceptance_decision_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `acceptance_decision_actor_id_not_null`: `NOT NULL actor_id`
- `acceptance_decision_attempt_id_key`: `UNIQUE (attempt_id)`
- `acceptance_decision_attempt_id_not_null`: `NOT NULL attempt_id`
- `acceptance_decision_decided_at_not_null`: `NOT NULL decided_at`
- `acceptance_decision_id_not_null`: `NOT NULL id`
- `acceptance_decision_outcome_check`: `CHECK (outcome::text = ANY (ARRAY['ACCEPT'::character varying, 'REWORK'::character varying]::text[]))`
- `acceptance_decision_outcome_not_null`: `NOT NULL outcome`
- `acceptance_decision_pkey`: `PRIMARY KEY (id)`
- `acceptance_decision_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `acceptance_decision_request_id_not_null`: `NOT NULL request_id`
- `acceptance_reason`: `CHECK (outcome::text = 'ACCEPT'::text OR reason IS NOT NULL AND length(btrim(reason::text)) >= 10 AND length(btrim(reason::text)) <= 2000)`

Chỉ mục:

- `CREATE UNIQUE INDEX acceptance_decision_attempt_id_key ON eas.acceptance_decision USING btree (attempt_id)`
- `CREATE UNIQUE INDEX acceptance_decision_pkey ON eas.acceptance_decision USING btree (id)`
- `CREATE INDEX ix_acceptance_decision_actor_id ON eas.acceptance_decision USING btree (actor_id)`
- `CREATE INDEX ix_acceptance_decision_request_id ON eas.acceptance_decision USING btree (request_id)`

Guard/trigger:

- `acceptance_decision_guard`: `CREATE TRIGGER acceptance_decision_guard BEFORE INSERT ON eas.acceptance_decision FOR EACH ROW EXECUTE FUNCTION eas.guard_decision()`
- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.acceptance_decision FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`

## DB15 — eas.execution_issue

Sự kiện báo vướng; không phải trạng thái riêng và không dừng SLA.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `attempt_id` | `uuid` | Không | NULL |
| `actor_id` | `uuid` | Không | NULL |
| `kind` | `character varying(15)` | Không | NULL |
| `reason` | `character varying(2000)` | Không | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `execution_issue_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `execution_issue_actor_id_not_null`: `NOT NULL actor_id`
- `execution_issue_attempt_id_not_null`: `NOT NULL attempt_id`
- `execution_issue_created_at_not_null`: `NOT NULL created_at`
- `execution_issue_id_not_null`: `NOT NULL id`
- `execution_issue_kind_check`: `CHECK (kind::text = ANY (ARRAY['UNABLE_TO_CLAIM'::character varying, 'BLOCKED'::character varying]::text[]))`
- `execution_issue_kind_not_null`: `NOT NULL kind`
- `execution_issue_pkey`: `PRIMARY KEY (id)`
- `execution_issue_reason_check`: `CHECK (length(btrim(reason::text)) >= 10 AND length(btrim(reason::text)) <= 2000)`
- `execution_issue_reason_not_null`: `NOT NULL reason`
- `execution_issue_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `execution_issue_request_id_not_null`: `NOT NULL request_id`
- `issue_attempt_same_request`: `FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT`

Chỉ mục:

- `CREATE UNIQUE INDEX execution_issue_pkey ON eas.execution_issue USING btree (id)`
- `CREATE INDEX ix_execution_issue_actor_id ON eas.execution_issue USING btree (actor_id)`
- `CREATE INDEX ix_execution_issue_attempt_id ON eas.execution_issue USING btree (attempt_id)`
- `CREATE INDEX ix_execution_issue_request_id ON eas.execution_issue USING btree (request_id)`

Guard/trigger:

- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.execution_issue FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`

## DB16 — eas.attachment

Metadata tệp riêng tư; không tạo object/bucket; object_version là phiên bản thực của kho lưu trữ.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `uploader_id` | `uuid` | Không | NULL |
| `storage_key` | `character varying(300)` | Không | NULL |
| `object_version` | `character varying(200)` | Không | NULL |
| `original_name` | `character varying(150)` | Không | NULL |
| `mime` | `character varying(80)` | Không | NULL |
| `size_bytes` | `bigint` | Không | NULL |
| `sha256` | `character(64)` | Không | NULL |
| `scan_state` | `character varying(8)` | Không | `'QUEUED'::character varying` |
| `scan_attempts` | `integer` | Không | `0` |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `scanned_at` | `timestamp with time zone` | Có | NULL |
| `deleted_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `attachment_created_at_not_null`: `NOT NULL created_at`
- `attachment_id_not_null`: `NOT NULL id`
- `attachment_id_request_id_key`: `UNIQUE (id, request_id)`
- `attachment_mime_check`: `CHECK (mime::text = ANY (ARRAY['application/pdf'::character varying, 'image/jpeg'::character varying, 'image/png'::character varying]::text[]))`
- `attachment_mime_not_null`: `NOT NULL mime`
- `attachment_object_version_check`: `CHECK (length(object_version::text) > 0)`
- `attachment_object_version_not_null`: `NOT NULL object_version`
- `attachment_original_name_check`: `CHECK (length(btrim(original_name::text)) > 0 AND POSITION(('/'::text) IN (original_name)) = 0 AND POSITION((chr(92)) IN (original_name)) = 0 AND POSITION(('..'::text) IN (original_name)) = 0)`
- `attachment_original_name_not_null`: `NOT NULL original_name`
- `attachment_pkey`: `PRIMARY KEY (id)`
- `attachment_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `attachment_request_id_not_null`: `NOT NULL request_id`
- `attachment_scan_attempts_check`: `CHECK (scan_attempts >= 0 AND scan_attempts <= 3)`
- `attachment_scan_attempts_not_null`: `NOT NULL scan_attempts`
- `attachment_scan_state_check`: `CHECK (scan_state::text = ANY (ARRAY['QUEUED'::character varying, 'CLEAN'::character varying, 'INFECTED'::character varying, 'ERROR'::character varying]::text[]))`
- `attachment_scan_state_not_null`: `NOT NULL scan_state`
- `attachment_scan_time`: `CHECK (scan_state::text = 'QUEUED'::text OR scanned_at IS NOT NULL AND scan_attempts >= 1)`
- `attachment_sha256_check`: `CHECK (sha256 ~ '^[0-9a-f]{64}$'::text)`
- `attachment_sha256_not_null`: `NOT NULL sha256`
- `attachment_size_bytes_check`: `CHECK (size_bytes >= 1 AND size_bytes <= 10485760)`
- `attachment_size_bytes_not_null`: `NOT NULL size_bytes`
- `attachment_storage_key_check`: `CHECK (length(storage_key::text) > 0)`
- `attachment_storage_key_key`: `UNIQUE (storage_key)`
- `attachment_storage_key_not_null`: `NOT NULL storage_key`
- `attachment_times`: `CHECK ((scanned_at IS NULL OR scanned_at >= created_at) AND (deleted_at IS NULL OR deleted_at >= created_at))`
- `attachment_uploader_id_fkey`: `FOREIGN KEY (uploader_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `attachment_uploader_id_not_null`: `NOT NULL uploader_id`

Chỉ mục:

- `CREATE UNIQUE INDEX attachment_id_request_id_key ON eas.attachment USING btree (id, request_id)`
- `CREATE UNIQUE INDEX attachment_pkey ON eas.attachment USING btree (id)`
- `CREATE INDEX attachment_scan_queue ON eas.attachment USING btree (scan_state, created_at) WHERE (deleted_at IS NULL)`
- `CREATE UNIQUE INDEX attachment_storage_key_key ON eas.attachment USING btree (storage_key)`
- `CREATE INDEX ix_attachment_request_id ON eas.attachment USING btree (request_id)`
- `CREATE INDEX ix_attachment_uploader_id ON eas.attachment USING btree (uploader_id)`

Guard/trigger:

- `attachment_guard`: `CREATE TRIGGER attachment_guard BEFORE INSERT OR UPDATE ON eas.attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_attachment()`
- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`

## DB17 — eas.draft_attachment

Tập tệp nháp, có thể bỏ chọn mà không xóa tệp lịch sử.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `request_id` | `uuid` | Không | NULL |
| `attachment_id` | `uuid` | Không | NULL |
| `added_by` | `uuid` | Không | NULL |
| `added_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `draft_attachment_added_at_not_null`: `NOT NULL added_at`
- `draft_attachment_added_by_fkey`: `FOREIGN KEY (added_by) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `draft_attachment_added_by_not_null`: `NOT NULL added_by`
- `draft_attachment_attachment_id_not_null`: `NOT NULL attachment_id`
- `draft_attachment_pkey`: `PRIMARY KEY (request_id, attachment_id)`
- `draft_attachment_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `draft_attachment_request_id_not_null`: `NOT NULL request_id`
- `draft_file_same_request`: `FOREIGN KEY (attachment_id, request_id) REFERENCES eas.attachment(id, request_id) ON DELETE RESTRICT`

Chỉ mục:

- `CREATE UNIQUE INDEX draft_attachment_pkey ON eas.draft_attachment USING btree (request_id, attachment_id)`
- `CREATE INDEX ix_draft_attachment_added_by ON eas.draft_attachment USING btree (added_by)`
- `CREATE INDEX ix_draft_attachment_attachment_id ON eas.draft_attachment USING btree (attachment_id)`

Guard/trigger:

- `draft_link_guard`: `CREATE TRIGGER draft_link_guard BEFORE INSERT ON eas.draft_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_file_link()`

## DB18 — eas.revision_attachment

Tệp chụp theo revision; append only.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `revision_id` | `uuid` | Không | NULL |
| `attachment_id` | `uuid` | Không | NULL |
| `request_id` | `uuid` | Không | NULL |

Ràng buộc:

- `revision_attachment_attachment_id_not_null`: `NOT NULL attachment_id`
- `revision_attachment_pkey`: `PRIMARY KEY (revision_id, attachment_id)`
- `revision_attachment_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `revision_attachment_request_id_not_null`: `NOT NULL request_id`
- `revision_attachment_revision_id_not_null`: `NOT NULL revision_id`
- `revision_file_same_request`: `FOREIGN KEY (attachment_id, request_id) REFERENCES eas.attachment(id, request_id) ON DELETE RESTRICT`
- `revision_link_same_request`: `FOREIGN KEY (revision_id, request_id) REFERENCES eas.request_revision(id, request_id) ON DELETE RESTRICT`

Chỉ mục:

- `CREATE INDEX ix_revision_attachment_attachment_id ON eas.revision_attachment USING btree (attachment_id)`
- `CREATE INDEX ix_revision_attachment_request_id ON eas.revision_attachment USING btree (request_id)`
- `CREATE UNIQUE INDEX revision_attachment_pkey ON eas.revision_attachment USING btree (revision_id, attachment_id)`

Guard/trigger:

- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.revision_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`
- `revision_link_guard`: `CREATE TRIGGER revision_link_guard BEFORE INSERT ON eas.revision_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_file_link()`

## DB19 — eas.execution_attachment

Bằng chứng do executor upload; thêm trong lúc RUNNING trước khi nộp kết quả.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `attempt_id` | `uuid` | Không | NULL |
| `attachment_id` | `uuid` | Không | NULL |
| `request_id` | `uuid` | Không | NULL |

Ràng buộc:

- `execution_attachment_attachment_id_not_null`: `NOT NULL attachment_id`
- `execution_attachment_attempt_id_not_null`: `NOT NULL attempt_id`
- `execution_attachment_pkey`: `PRIMARY KEY (attempt_id, attachment_id)`
- `execution_attachment_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `execution_attachment_request_id_not_null`: `NOT NULL request_id`
- `execution_file_same_request`: `FOREIGN KEY (attachment_id, request_id) REFERENCES eas.attachment(id, request_id) ON DELETE RESTRICT`
- `execution_link_same_request`: `FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT`

Chỉ mục:

- `CREATE UNIQUE INDEX execution_attachment_pkey ON eas.execution_attachment USING btree (attempt_id, attachment_id)`
- `CREATE INDEX ix_execution_attachment_attachment_id ON eas.execution_attachment USING btree (attachment_id)`
- `CREATE INDEX ix_execution_attachment_request_id ON eas.execution_attachment USING btree (request_id)`

Guard/trigger:

- `execution_link_guard`: `CREATE TRIGGER execution_link_guard BEFORE INSERT ON eas.execution_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_file_link()`
- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.execution_attachment FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`

## DB20 — eas.sla_stage

Một stage mở/request; gán thay giữ ID và due_at, chỉ cập nhật target attempt khi cần.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `kind` | `character varying(10)` | Không | NULL |
| `approval_step_id` | `uuid` | Có | NULL |
| `attempt_id` | `uuid` | Có | NULL |
| `started_at` | `timestamp with time zone` | Không | `now()` |
| `due_at` | `timestamp with time zone` | Không | NULL |
| `closed_at` | `timestamp with time zone` | Có | NULL |
| `breached_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `sla_attempt_same_request`: `FOREIGN KEY (attempt_id, request_id) REFERENCES eas.execution_attempt(id, request_id) ON DELETE RESTRICT`
- `sla_breach_time`: `CHECK (breached_at IS NULL OR breached_at = due_at)`
- `sla_stage_due_at_not_null`: `NOT NULL due_at`
- `sla_stage_id_not_null`: `NOT NULL id`
- `sla_stage_id_request_id_key`: `UNIQUE (id, request_id)`
- `sla_stage_kind_check`: `CHECK (kind::text = ANY (ARRAY['APPROVAL'::character varying, 'EXECUTION'::character varying, 'ACCEPTANCE'::character varying]::text[]))`
- `sla_stage_kind_not_null`: `NOT NULL kind`
- `sla_stage_pkey`: `PRIMARY KEY (id)`
- `sla_stage_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `sla_stage_request_id_not_null`: `NOT NULL request_id`
- `sla_stage_started_at_not_null`: `NOT NULL started_at`
- `sla_step_same_request`: `FOREIGN KEY (approval_step_id, request_id) REFERENCES eas.approval_step(id, request_id) ON DELETE RESTRICT`
- `sla_subtype`: `CHECK (kind::text = 'APPROVAL'::text AND approval_step_id IS NOT NULL AND attempt_id IS NULL OR (kind::text = ANY (ARRAY['EXECUTION'::character varying, 'ACCEPTANCE'::character varying]::text[])) AND approval_step_id IS NULL AND attempt_id IS NOT NULL)`
- `sla_time_order`: `CHECK (due_at > started_at AND (closed_at IS NULL OR closed_at >= started_at))`

Chỉ mục:

- `CREATE INDEX ix_sla_stage_approval_step_id ON eas.sla_stage USING btree (approval_step_id)`
- `CREATE INDEX ix_sla_stage_attempt_id ON eas.sla_stage USING btree (attempt_id)`
- `CREATE INDEX ix_sla_stage_request_id ON eas.sla_stage USING btree (request_id)`
- `CREATE UNIQUE INDEX one_open_stage ON eas.sla_stage USING btree (request_id) WHERE (closed_at IS NULL)`
- `CREATE INDEX sla_open_due ON eas.sla_stage USING btree (due_at) WHERE (closed_at IS NULL)`
- `CREATE UNIQUE INDEX sla_stage_id_request_id_key ON eas.sla_stage USING btree (id, request_id)`
- `CREATE UNIQUE INDEX sla_stage_pkey ON eas.sla_stage USING btree (id)`

Guard/trigger:

- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.sla_stage FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`
- `sla_guard`: `CREATE TRIGGER sla_guard BEFORE UPDATE ON eas.sla_stage FOR EACH ROW EXECUTE FUNCTION eas.guard_sla()`

## DB21 — eas.sla_alert

Khử trùng reminder/breach theo stage.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `stage_id` | `uuid` | Không | NULL |
| `kind` | `character varying(8)` | Không | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `alert_stage_same_request`: `FOREIGN KEY (stage_id, request_id) REFERENCES eas.sla_stage(id, request_id) ON DELETE RESTRICT`
- `sla_alert_created_at_not_null`: `NOT NULL created_at`
- `sla_alert_id_not_null`: `NOT NULL id`
- `sla_alert_kind_check`: `CHECK (kind::text = ANY (ARRAY['REMINDER'::character varying, 'BREACH'::character varying]::text[]))`
- `sla_alert_kind_not_null`: `NOT NULL kind`
- `sla_alert_pkey`: `PRIMARY KEY (id)`
- `sla_alert_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `sla_alert_request_id_not_null`: `NOT NULL request_id`
- `sla_alert_stage_id_kind_key`: `UNIQUE (stage_id, kind)`
- `sla_alert_stage_id_not_null`: `NOT NULL stage_id`

Chỉ mục:

- `CREATE INDEX ix_sla_alert_request_id ON eas.sla_alert USING btree (request_id)`
- `CREATE UNIQUE INDEX sla_alert_pkey ON eas.sla_alert USING btree (id)`
- `CREATE UNIQUE INDEX sla_alert_stage_id_kind_key ON eas.sla_alert USING btree (stage_id, kind)`

Guard/trigger:

- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.sla_alert FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`

## DB22 — eas.audit_event

Audit request; backend cung cấp SHA256 RFC8785/NFC, DB kiểm seq/prev_hash dưới khóa.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `seq` | `bigint` | Không | NULL |
| `actor_id` | `uuid` | Có | NULL |
| `actor_kind` | `character varying(6)` | Không | NULL |
| `action` | `character varying(80)` | Không | NULL |
| `target_type` | `character varying(40)` | Không | NULL |
| `target_id` | `uuid` | Không | NULL |
| `details` | `jsonb` | Không | NULL |
| `correlation_id` | `uuid` | Không | NULL |
| `occurred_at` | `timestamp with time zone` | Không | `now()` |
| `hash_version` | `smallint` | Không | `1` |
| `prev_hash` | `character(64)` | Không | NULL |
| `hash` | `character(64)` | Không | NULL |

Ràng buộc:

- `audit_actor_kind`: `CHECK (actor_kind::text = 'HUMAN'::text AND actor_id IS NOT NULL OR actor_kind::text = 'SYSTEM'::text AND actor_id IS NULL)`
- `audit_event_action_check`: `CHECK (length(btrim(action::text)) > 0)`
- `audit_event_action_not_null`: `NOT NULL action`
- `audit_event_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `audit_event_actor_kind_check`: `CHECK (actor_kind::text = ANY (ARRAY['HUMAN'::character varying, 'SYSTEM'::character varying]::text[]))`
- `audit_event_actor_kind_not_null`: `NOT NULL actor_kind`
- `audit_event_correlation_id_not_null`: `NOT NULL correlation_id`
- `audit_event_details_check`: `CHECK (jsonb_typeof(details) = 'object'::text)`
- `audit_event_details_not_null`: `NOT NULL details`
- `audit_event_hash_check`: `CHECK (hash ~ '^[0-9a-f]{64}$'::text)`
- `audit_event_hash_not_null`: `NOT NULL hash`
- `audit_event_hash_version_check`: `CHECK (hash_version = 1)`
- `audit_event_hash_version_not_null`: `NOT NULL hash_version`
- `audit_event_id_not_null`: `NOT NULL id`
- `audit_event_occurred_at_not_null`: `NOT NULL occurred_at`
- `audit_event_pkey`: `PRIMARY KEY (id)`
- `audit_event_prev_hash_check`: `CHECK (prev_hash ~ '^[0-9a-f]{64}$'::text)`
- `audit_event_prev_hash_not_null`: `NOT NULL prev_hash`
- `audit_event_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `audit_event_request_id_not_null`: `NOT NULL request_id`
- `audit_event_request_id_seq_key`: `UNIQUE (request_id, seq)`
- `audit_event_seq_check`: `CHECK (seq > 0)`
- `audit_event_seq_not_null`: `NOT NULL seq`
- `audit_event_target_id_not_null`: `NOT NULL target_id`
- `audit_event_target_type_check`: `CHECK (length(btrim(target_type::text)) > 0)`
- `audit_event_target_type_not_null`: `NOT NULL target_type`

Chỉ mục:

- `CREATE UNIQUE INDEX audit_event_pkey ON eas.audit_event USING btree (id)`
- `CREATE UNIQUE INDEX audit_event_request_id_seq_key ON eas.audit_event USING btree (request_id, seq)`
- `CREATE INDEX ix_audit_event_actor_id ON eas.audit_event USING btree (actor_id)`

Guard/trigger:

- `advance_request_audit`: `CREATE TRIGGER advance_request_audit BEFORE INSERT ON eas.audit_event FOR EACH ROW EXECUTE FUNCTION eas.advance_audit_head()`
- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.audit_event FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`

## DB23 — eas.admin_event

Audit cấu hình/quyền/vận hành; không cần request giả; một chuỗi ADMIN.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `seq` | `bigint` | Không | NULL |
| `actor_id` | `uuid` | Có | NULL |
| `actor_kind` | `character varying(6)` | Không | NULL |
| `action` | `character varying(80)` | Không | NULL |
| `target_type` | `character varying(40)` | Không | NULL |
| `target_id` | `character varying(100)` | Không | NULL |
| `department_id` | `uuid` | Có | NULL |
| `type_id` | `uuid` | Có | NULL |
| `details` | `jsonb` | Không | NULL |
| `reason` | `text` | Không | NULL |
| `correlation_id` | `uuid` | Không | NULL |
| `occurred_at` | `timestamp with time zone` | Không | `now()` |
| `hash_version` | `smallint` | Không | `1` |
| `prev_hash` | `character(64)` | Không | NULL |
| `hash` | `character(64)` | Không | NULL |

Ràng buộc:

- `admin_actor_kind`: `CHECK (actor_kind::text = 'HUMAN'::text AND actor_id IS NOT NULL OR actor_kind::text = 'SYSTEM'::text AND actor_id IS NULL)`
- `admin_event_action_check`: `CHECK (length(btrim(action::text)) > 0)`
- `admin_event_action_not_null`: `NOT NULL action`
- `admin_event_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `admin_event_actor_kind_check`: `CHECK (actor_kind::text = ANY (ARRAY['HUMAN'::character varying, 'SYSTEM'::character varying]::text[]))`
- `admin_event_actor_kind_not_null`: `NOT NULL actor_kind`
- `admin_event_correlation_id_not_null`: `NOT NULL correlation_id`
- `admin_event_department_id_fkey`: `FOREIGN KEY (department_id) REFERENCES eas.department(id) ON DELETE RESTRICT`
- `admin_event_details_check`: `CHECK (jsonb_typeof(details) = 'object'::text)`
- `admin_event_details_not_null`: `NOT NULL details`
- `admin_event_hash_check`: `CHECK (hash ~ '^[0-9a-f]{64}$'::text)`
- `admin_event_hash_not_null`: `NOT NULL hash`
- `admin_event_hash_version_check`: `CHECK (hash_version = 1)`
- `admin_event_hash_version_not_null`: `NOT NULL hash_version`
- `admin_event_id_not_null`: `NOT NULL id`
- `admin_event_occurred_at_not_null`: `NOT NULL occurred_at`
- `admin_event_pkey`: `PRIMARY KEY (id)`
- `admin_event_prev_hash_check`: `CHECK (prev_hash ~ '^[0-9a-f]{64}$'::text)`
- `admin_event_prev_hash_not_null`: `NOT NULL prev_hash`
- `admin_event_reason_check`: `CHECK (length(btrim(reason)) >= 10 AND length(btrim(reason)) <= 2000)`
- `admin_event_reason_not_null`: `NOT NULL reason`
- `admin_event_seq_check`: `CHECK (seq > 0)`
- `admin_event_seq_key`: `UNIQUE (seq)`
- `admin_event_seq_not_null`: `NOT NULL seq`
- `admin_event_target_id_check`: `CHECK (length(btrim(target_id::text)) > 0)`
- `admin_event_target_id_not_null`: `NOT NULL target_id`
- `admin_event_target_type_check`: `CHECK (length(btrim(target_type::text)) > 0)`
- `admin_event_target_type_not_null`: `NOT NULL target_type`
- `admin_event_type_id_fkey`: `FOREIGN KEY (type_id) REFERENCES eas.request_type(id) ON DELETE RESTRICT`

Chỉ mục:

- `CREATE UNIQUE INDEX admin_event_pkey ON eas.admin_event USING btree (id)`
- `CREATE UNIQUE INDEX admin_event_seq_key ON eas.admin_event USING btree (seq)`
- `CREATE INDEX ix_admin_event_actor_id ON eas.admin_event USING btree (actor_id)`
- `CREATE INDEX ix_admin_event_department_id ON eas.admin_event USING btree (department_id)`
- `CREATE INDEX ix_admin_event_type_id ON eas.admin_event USING btree (type_id)`

Guard/trigger:

- `advance_admin_audit`: `CREATE TRIGGER advance_admin_audit BEFORE INSERT ON eas.admin_event FOR EACH ROW EXECUTE FUNCTION eas.advance_audit_head()`
- `immutable_history`: `CREATE TRIGGER immutable_history BEFORE DELETE OR UPDATE ON eas.admin_event FOR EACH ROW EXECUTE FUNCTION eas.guard_append_only()`

## DB24 — eas.audit_head

Đầu chuỗi; trigger append cập nhật nguyên tử, không thay checkpoint ngoài DB.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `scope_key` | `character varying(100)` | Không | NULL |
| `seq` | `bigint` | Không | `0` |
| `last_hash` | `character(64)` | Không | `repeat('0'::text, 64)` |

Ràng buộc:

- `audit_head_last_hash_check`: `CHECK (last_hash ~ '^[0-9a-f]{64}$'::text)`
- `audit_head_last_hash_not_null`: `NOT NULL last_hash`
- `audit_head_pkey`: `PRIMARY KEY (scope_key)`
- `audit_head_scope_key_check`: `CHECK (scope_key::text = 'ADMIN'::text OR scope_key::text ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)`
- `audit_head_scope_key_not_null`: `NOT NULL scope_key`
- `audit_head_seq_check`: `CHECK (seq >= 0)`
- `audit_head_seq_not_null`: `NOT NULL seq`
- `head_genesis`: `CHECK (seq <> 0 OR last_hash::text = repeat('0'::text, 64))`

Chỉ mục:

- `CREATE UNIQUE INDEX audit_head_pkey ON eas.audit_head USING btree (scope_key)`

Guard/trigger:

- `head_delete_guard`: `CREATE TRIGGER head_delete_guard BEFORE DELETE ON eas.audit_head FOR EACH ROW EXECUTE FUNCTION eas.guard_audit_scope_delete()`

## DB25 — eas.audit_checkpoint

Con trỏ checkpoint bên ngoài; không FK audit_head để giữ chứng cứ theo retention riêng.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `scope_key` | `character varying(100)` | Không | NULL |
| `seq` | `bigint` | Không | NULL |
| `hash` | `character(64)` | Không | NULL |
| `external_object_key` | `character varying(300)` | Không | NULL |
| `external_version` | `character varying(200)` | Không | NULL |
| `captured_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- `audit_checkpoint_captured_at_not_null`: `NOT NULL captured_at`
- `audit_checkpoint_external_object_key_check`: `CHECK (length(external_object_key::text) > 0)`
- `audit_checkpoint_external_object_key_not_null`: `NOT NULL external_object_key`
- `audit_checkpoint_external_version_check`: `CHECK (length(external_version::text) > 0)`
- `audit_checkpoint_external_version_not_null`: `NOT NULL external_version`
- `audit_checkpoint_hash_check`: `CHECK (hash ~ '^[0-9a-f]{64}$'::text)`
- `audit_checkpoint_hash_not_null`: `NOT NULL hash`
- `audit_checkpoint_id_not_null`: `NOT NULL id`
- `audit_checkpoint_pkey`: `PRIMARY KEY (id)`
- `audit_checkpoint_scope_key_check`: `CHECK (scope_key::text = 'ADMIN'::text OR scope_key::text ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)`
- `audit_checkpoint_scope_key_not_null`: `NOT NULL scope_key`
- `audit_checkpoint_scope_key_seq_key`: `UNIQUE (scope_key, seq)`
- `audit_checkpoint_seq_check`: `CHECK (seq >= 0)`
- `audit_checkpoint_seq_not_null`: `NOT NULL seq`

Chỉ mục:

- `CREATE UNIQUE INDEX audit_checkpoint_pkey ON eas.audit_checkpoint USING btree (id)`
- `CREATE UNIQUE INDEX audit_checkpoint_scope_key_seq_key ON eas.audit_checkpoint USING btree (scope_key, seq)`

Guard/trigger:

- `checkpoint_delete_guard`: `CREATE TRIGGER checkpoint_delete_guard BEFORE DELETE ON eas.audit_checkpoint FOR EACH ROW EXECUTE FUNCTION eas.guard_audit_scope_delete()`
- `checkpoint_metadata`: `CREATE TRIGGER checkpoint_metadata BEFORE UPDATE ON eas.audit_checkpoint FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata()`

## DB26 — eas.outbox_event

Outbox bốn lần thử mỗi chu kỳ; lease và ACK do worker; payload chỉ metadata tối thiểu.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Có | NULL |
| `event_type` | `character varying(80)` | Không | NULL |
| `payload` | `jsonb` | Không | NULL |
| `state` | `character varying(10)` | Không | `'PENDING'::character varying` |
| `dedupe_key` | `character varying(200)` | Không | NULL |
| `attempts` | `integer` | Không | `0` |
| `replay_count` | `integer` | Không | `0` |
| `available_at` | `timestamp with time zone` | Không | `now()` |
| `lease_token` | `uuid` | Có | NULL |
| `lease_until` | `timestamp with time zone` | Có | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `sent_at` | `timestamp with time zone` | Có | NULL |
| `last_error_code` | `character varying(80)` | Có | NULL |

Ràng buộc:

- `outbox_dead`: `CHECK (state::text <> 'DEAD'::text OR attempts = 4)`
- `outbox_event_attempts_check`: `CHECK (attempts >= 0 AND attempts <= 4)`
- `outbox_event_attempts_not_null`: `NOT NULL attempts`
- `outbox_event_available_at_not_null`: `NOT NULL available_at`
- `outbox_event_created_at_not_null`: `NOT NULL created_at`
- `outbox_event_dedupe_key_check`: `CHECK (length(dedupe_key::text) > 0)`
- `outbox_event_dedupe_key_key`: `UNIQUE (dedupe_key)`
- `outbox_event_dedupe_key_not_null`: `NOT NULL dedupe_key`
- `outbox_event_event_type_check`: `CHECK (length(btrim(event_type::text)) > 0)`
- `outbox_event_event_type_not_null`: `NOT NULL event_type`
- `outbox_event_id_not_null`: `NOT NULL id`
- `outbox_event_payload_check`: `CHECK (jsonb_typeof(payload) = 'object'::text)`
- `outbox_event_payload_not_null`: `NOT NULL payload`
- `outbox_event_pkey`: `PRIMARY KEY (id)`
- `outbox_event_replay_count_check`: `CHECK (replay_count >= 0)`
- `outbox_event_replay_count_not_null`: `NOT NULL replay_count`
- `outbox_event_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `outbox_event_state_check`: `CHECK (state::text = ANY (ARRAY['PENDING'::character varying, 'PROCESSING'::character varying, 'SENT'::character varying, 'DEAD'::character varying]::text[]))`
- `outbox_event_state_not_null`: `NOT NULL state`
- `outbox_lease`: `CHECK (state::text = 'PROCESSING'::text AND lease_token IS NOT NULL AND lease_until IS NOT NULL AND attempts >= 1 OR state::text <> 'PROCESSING'::text AND lease_token IS NULL AND lease_until IS NULL)`
- `outbox_sent`: `CHECK ((state::text = 'SENT'::text) = (sent_at IS NOT NULL))`
- `outbox_sent_time`: `CHECK (sent_at IS NULL OR sent_at >= created_at)`

Chỉ mục:

- `CREATE INDEX ix_outbox_event_request_id ON eas.outbox_event USING btree (request_id)`
- `CREATE INDEX outbox_due ON eas.outbox_event USING btree (state, available_at, lease_until)`
- `CREATE UNIQUE INDEX outbox_event_dedupe_key_key ON eas.outbox_event USING btree (dedupe_key)`
- `CREATE UNIQUE INDEX outbox_event_pkey ON eas.outbox_event USING btree (id)`

Guard/trigger:

- `outbox_metadata`: `CREATE TRIGGER outbox_metadata BEFORE UPDATE ON eas.outbox_event FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata()`
- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.outbox_event FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`

## DB27 — eas.notification

Thông báo của recipient; read_at lần đầu bất biến; request phải khớp event kể cả NULL.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `event_id` | `uuid` | Không | NULL |
| `recipient_id` | `uuid` | Không | NULL |
| `request_id` | `uuid` | Có | NULL |
| `label` | `character varying(150)` | Không | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `read_at` | `timestamp with time zone` | Có | NULL |

Ràng buộc:

- `notification_created_at_not_null`: `NOT NULL created_at`
- `notification_event_id_fkey`: `FOREIGN KEY (event_id) REFERENCES eas.outbox_event(id) ON DELETE RESTRICT`
- `notification_event_id_not_null`: `NOT NULL event_id`
- `notification_event_id_recipient_id_key`: `UNIQUE (event_id, recipient_id)`
- `notification_id_not_null`: `NOT NULL id`
- `notification_label_check`: `CHECK (length(btrim(label::text)) > 0)`
- `notification_label_not_null`: `NOT NULL label`
- `notification_pkey`: `PRIMARY KEY (id)`
- `notification_read_time`: `CHECK (read_at IS NULL OR read_at >= created_at)`
- `notification_recipient_id_fkey`: `FOREIGN KEY (recipient_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `notification_recipient_id_not_null`: `NOT NULL recipient_id`
- `notification_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`

Chỉ mục:

- `CREATE INDEX ix_notification_request_id ON eas.notification USING btree (request_id)`
- `CREATE UNIQUE INDEX notification_event_id_recipient_id_key ON eas.notification USING btree (event_id, recipient_id)`
- `CREATE INDEX notification_inbox ON eas.notification USING btree (recipient_id, read_at, created_at DESC, id DESC)`
- `CREATE UNIQUE INDEX notification_pkey ON eas.notification USING btree (id)`

Guard/trigger:

- `notification_guard`: `CREATE TRIGGER notification_guard BEFORE INSERT OR UPDATE ON eas.notification FOR EACH ROW EXECUTE FUNCTION eas.guard_notification()`
- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.notification FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`

## DB28 — eas.idempotency_record

Lưu kết quả thành công 7 ngày; tombstone 30 ngày; không dedupe vô hạn.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `actor_id` | `uuid` | Không | NULL |
| `command_scope` | `character varying(200)` | Không | NULL |
| `key` | `character varying(64)` | Không | NULL |
| `request_hash` | `character(64)` | Không | NULL |
| `http_status` | `smallint` | Không | NULL |
| `response_body` | `jsonb` | Có | NULL |
| `request_id` | `uuid` | Có | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `expires_at` | `timestamp with time zone` | Không | `(now() + '7 days'::interval)` |
| `tombstone_until` | `timestamp with time zone` | Không | `(now() + '30 days'::interval)` |

Ràng buộc:

- `idempotency_record_actor_id_command_scope_key_key`: `UNIQUE (actor_id, command_scope, key)`
- `idempotency_record_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `idempotency_record_actor_id_not_null`: `NOT NULL actor_id`
- `idempotency_record_command_scope_check`: `CHECK (length(command_scope::text) > 0)`
- `idempotency_record_command_scope_not_null`: `NOT NULL command_scope`
- `idempotency_record_created_at_not_null`: `NOT NULL created_at`
- `idempotency_record_expires_at_not_null`: `NOT NULL expires_at`
- `idempotency_record_http_status_check`: `CHECK (http_status >= 200 AND http_status <= 299)`
- `idempotency_record_http_status_not_null`: `NOT NULL http_status`
- `idempotency_record_id_not_null`: `NOT NULL id`
- `idempotency_record_key_check`: `CHECK (key::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)`
- `idempotency_record_key_not_null`: `NOT NULL key`
- `idempotency_record_pkey`: `PRIMARY KEY (id)`
- `idempotency_record_request_hash_check`: `CHECK (request_hash ~ '^[0-9a-f]{64}$'::text)`
- `idempotency_record_request_hash_not_null`: `NOT NULL request_hash`
- `idempotency_record_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `idempotency_record_tombstone_until_not_null`: `NOT NULL tombstone_until`
- `idempotency_time_order`: `CHECK (expires_at > created_at AND tombstone_until > expires_at)`

Chỉ mục:

- `CREATE INDEX idempotency_expiry ON eas.idempotency_record USING btree (tombstone_until)`
- `CREATE UNIQUE INDEX idempotency_record_actor_id_command_scope_key_key ON eas.idempotency_record USING btree (actor_id, command_scope, key)`
- `CREATE UNIQUE INDEX idempotency_record_pkey ON eas.idempotency_record USING btree (id)`
- `CREATE INDEX ix_idempotency_record_request_id ON eas.idempotency_record USING btree (request_id)`

Guard/trigger:

- `idempotency_guard`: `CREATE TRIGGER idempotency_guard BEFORE DELETE OR UPDATE ON eas.idempotency_record FOR EACH ROW EXECUTE FUNCTION eas.guard_idempotency()`

## DB29 — eas.privacy_case

Hồ sơ quyền dữ liệu; pháp chế đặt due_at, không có thời hạn pháp lý mặc định.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `subject_user_id` | `uuid` | Không | NULL |
| `case_type` | `character varying(8)` | Không | NULL |
| `status` | `character varying(8)` | Không | `'OPEN'::character varying` |
| `requested_at` | `timestamp with time zone` | Không | `now()` |
| `due_at` | `timestamp with time zone` | Không | NULL |
| `completed_at` | `timestamp with time zone` | Có | NULL |
| `policy_version` | `character varying(50)` | Không | NULL |
| `owner_id` | `uuid` | Không | NULL |
| `decision_reference` | `character varying(200)` | Có | NULL |

Ràng buộc:

- `privacy_case_case_type_check`: `CHECK (case_type::text = ANY (ARRAY['ACCESS'::character varying, 'CORRECT'::character varying, 'ERASE'::character varying, 'RESTRICT'::character varying, 'OBJECT'::character varying]::text[]))`
- `privacy_case_case_type_not_null`: `NOT NULL case_type`
- `privacy_case_due_at_not_null`: `NOT NULL due_at`
- `privacy_case_id_not_null`: `NOT NULL id`
- `privacy_case_owner_id_fkey`: `FOREIGN KEY (owner_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `privacy_case_owner_id_not_null`: `NOT NULL owner_id`
- `privacy_case_pkey`: `PRIMARY KEY (id)`
- `privacy_case_policy_version_check`: `CHECK (length(btrim(policy_version::text)) > 0)`
- `privacy_case_policy_version_not_null`: `NOT NULL policy_version`
- `privacy_case_requested_at_not_null`: `NOT NULL requested_at`
- `privacy_case_status_check`: `CHECK (status::text = ANY (ARRAY['OPEN'::character varying, 'REVIEW'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'DONE'::character varying]::text[]))`
- `privacy_case_status_not_null`: `NOT NULL status`
- `privacy_case_subject_user_id_fkey`: `FOREIGN KEY (subject_user_id) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `privacy_case_subject_user_id_not_null`: `NOT NULL subject_user_id`
- `privacy_completed_time`: `CHECK (completed_at IS NULL OR completed_at >= requested_at)`
- `privacy_decision_ref`: `CHECK ((status::text <> ALL (ARRAY['APPROVED'::character varying, 'REJECTED'::character varying, 'DONE'::character varying]::text[])) OR decision_reference IS NOT NULL AND length(btrim(decision_reference::text)) > 0)`
- `privacy_done`: `CHECK ((status::text = 'DONE'::text) = (completed_at IS NOT NULL))`
- `privacy_due`: `CHECK (due_at > requested_at)`

Chỉ mục:

- `CREATE INDEX ix_privacy_case_owner_id ON eas.privacy_case USING btree (owner_id)`
- `CREATE INDEX ix_privacy_case_subject_user_id ON eas.privacy_case USING btree (subject_user_id)`
- `CREATE UNIQUE INDEX privacy_case_pkey ON eas.privacy_case USING btree (id)`
- `CREATE INDEX privacy_due_open ON eas.privacy_case USING btree (due_at) WHERE ((status)::text = ANY ((ARRAY['OPEN'::character varying, 'REVIEW'::character varying, 'APPROVED'::character varying])::text[]))`

## DB30 — eas.retention_hold

Legal hold; chỉ nhả hold theo phê duyệt, không tự xóa để purge.

| Cột | Kiểu PostgreSQL | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | Không | `gen_random_uuid()` |
| `request_id` | `uuid` | Không | NULL |
| `reason` | `character varying(2000)` | Không | NULL |
| `authority_reference` | `character varying(200)` | Không | NULL |
| `set_by` | `uuid` | Không | NULL |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `released_at` | `timestamp with time zone` | Có | NULL |
| `released_by` | `uuid` | Có | NULL |

Ràng buộc:

- `hold_release_fields`: `CHECK (released_at IS NULL AND released_by IS NULL OR released_at IS NOT NULL AND released_by IS NOT NULL AND released_at >= created_at)`
- `retention_hold_authority_reference_check`: `CHECK (length(btrim(authority_reference::text)) > 0)`
- `retention_hold_authority_reference_not_null`: `NOT NULL authority_reference`
- `retention_hold_created_at_not_null`: `NOT NULL created_at`
- `retention_hold_id_not_null`: `NOT NULL id`
- `retention_hold_pkey`: `PRIMARY KEY (id)`
- `retention_hold_reason_check`: `CHECK (length(btrim(reason::text)) >= 10 AND length(btrim(reason::text)) <= 2000)`
- `retention_hold_reason_not_null`: `NOT NULL reason`
- `retention_hold_released_by_fkey`: `FOREIGN KEY (released_by) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `retention_hold_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES eas.request(id) ON DELETE RESTRICT`
- `retention_hold_request_id_not_null`: `NOT NULL request_id`
- `retention_hold_set_by_fkey`: `FOREIGN KEY (set_by) REFERENCES eas.app_user(id) ON DELETE RESTRICT`
- `retention_hold_set_by_not_null`: `NOT NULL set_by`

Chỉ mục:

- `CREATE INDEX hold_open_request ON eas.retention_hold USING btree (request_id) WHERE (released_at IS NULL)`
- `CREATE INDEX ix_retention_hold_released_by ON eas.retention_hold USING btree (released_by)`
- `CREATE INDEX ix_retention_hold_request_id ON eas.retention_hold USING btree (request_id)`
- `CREATE INDEX ix_retention_hold_set_by ON eas.retention_hold USING btree (set_by)`
- `CREATE UNIQUE INDEX retention_hold_pkey ON eas.retention_hold USING btree (id)`

Guard/trigger:

- `hold_metadata`: `CREATE TRIGGER hold_metadata BEFORE UPDATE ON eas.retention_hold FOR EACH ROW EXECUTE FUNCTION eas.guard_stable_metadata()`
- `privacy_delete_guard`: `CREATE TRIGGER privacy_delete_guard BEFORE DELETE ON eas.retention_hold FOR EACH ROW EXECUTE FUNCTION eas.guard_request_delete()`
