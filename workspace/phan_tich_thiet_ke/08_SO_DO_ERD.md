# 08 — Sơ đồ thực thể liên kết (DOCX 2.3.7 + Phụ lục E)

> **Hiện trạng DOCX.**
> - Hình 2.25–2.27 (ER-01/02/03) là ảnh lặp.
> - Phụ lục E có 10 chú thích ER-04…ER-13, nhưng chỉ **6 ảnh là ERD thật**: ER-01, ER-04, ER-05, ER-07, ER-08, ER-10, theo đánh số in trong ảnh. 3 ảnh là sơ đồ khác (SEC-01, DP-01, DFD-01) và 1 ảnh là AR-02.
> - **Đánh số ER trong ảnh khác đánh số trong text.** Ví dụ: text "ER-07 = Quy trình & phê duyệt", còn ảnh "ER-07 = Execution & acceptance".
>
> **Ký pháp trong ảnh** trộn hai kiểu: thuộc tính vẽ hình elip và quan hệ vẽ hình thoi (Chen), cùng bội số crow's foot (IE). Nên dùng **một** ký pháp; khuyến nghị IE/crow's foot với thuộc tính trong khung thực thể, như các sơ đồ Mermaid bên dưới. Lý do: 49 bảng vẽ kiểu Chen không đọc được.
>
> **Nguồn sự thật cho các sơ đồ dưới:**
> - `database/EAS_Supabase_SQL/00_eas_supabase_schema.sql` (30 bảng lõi);
> - `database/migrations/04–13`;
> - `supabase/migrations/20261103_admin_full_upgrade.sql`;
> - `information_schema` live (04/11/2026).
>
> Khoá ngoại **kép `(id, request_id)`** là điểm mạnh của thiết kế: bảng con không thể trỏ tới bản ghi cha thuộc **hồ sơ khác**. DOCX nhắc ở 1.4.3 nhưng ERD không thể hiện. Các sơ đồ dưới ghi chú `FK2`.

## 1. Đánh số chuẩn hoá đề xuất

| Mã | Miền | Bảng | Ảnh thật hiện có |
|---|---|---|---|
| ER-01 | Tổng thể miền 1: Danh tính, cấu hình, hồ sơ lõi | security_epoch, department, app_user, role_membership, request_group, request_menu_item, request_type, config_release, request, request_revision | img_065 (chú thích sai PL-33) |
| ER-02 | Tổng thể miền 2: Quy trình, thực thi, tệp | workflow_instance, request_participant, approval_step, approval_decision, execution_attempt, execution_issue, acceptance_decision, attachment, draft/revision/execution_attachment | không có |
| ER-03 | Tổng thể miền 3: SLA, sự kiện, kiểm toán, quyền riêng tư | sla_stage, sla_alert, sla_escalation_policy, business_holiday, outbox_event, notification, idempotency_record, audit_head, audit_event, admin_event, audit_checkpoint, privacy_case, privacy_case_approval, retention_hold | không có |
| ER-04 | Chi tiết Danh tính & tổ chức | | img_067 (chú thích sai PL-35) |
| ER-05 | Chi tiết Loại đơn, cấu hình, revision | | img_071 (chú thích sai PL-39) |
| ER-06 | Chi tiết Quy trình & phê duyệt | | không có |
| ER-07 | Chi tiết Thực thi & nghiệm thu | | img_064 (chú thích sai PL-32) |
| ER-08 | Chi tiết Tệp & liên kết bất biến | | img_072 (chú thích sai PL-40) |
| ER-09 | Chi tiết SLA, outbox, thông báo | | không có |
| ER-10 | Chi tiết Kiểm toán, idempotency, quyền riêng tư | | img_068 (chú thích sai PL-36) |
| ER-11 | **Bổ sung:** Quản trị & phân quyền module | role, lifecycle, role_module_permission, user_permissions, admin_account, modules | — |
| ER-12 | **Bổ sung:** AI & quy định công ty | ai_policy_version, ai_learning_job, ai_system_state, company_regulations, regulation_versions | — |
| ER-13 | **Bổ sung:** Vận hành & thông báo hệ thống | approval_delegation (đã gộp work_handover ở Migration 15), password_reset_request, system_announcement, announcement_receipt, user_leave_and_trips, mock_apis *(các bảng di sản system_versions_changelog, workflow_categories đã dời sang kho `eas_archive`)* | — |

## 2. Lệch tên cột giữa ảnh ERD và CSDL (áp dụng cho mọi ảnh)

| Ảnh | CSDL thật | Ghi chú |
|---|---|---|
| `request.owner_id` | `request.requester_id` | |
| `request.version` | `request.lock_version` | Text SD-19 viết `version_no` |
| `app_user.username` | `app_user.email` | Migration 05 đổi tên |
| `role_membership.role_code` | `role_membership.role` (+ `scope_kind`, `type_scope`, `revoked_at`) | Ảnh thiếu 3 cột phạm vi, mà đây là cốt lõi của Scoped RBAC |
| `role_membership.department_scope_id` | `role_membership.department_id` | |
| `department.manager_id` | *không có*; quản lý nằm ở `app_user.manager_id` | Ảnh ER-01/ER-04 vẽ quan hệ "Trưởng phòng" **không tồn tại** |
| `security_epoch.epoch` (PK) | `security_epoch.id = 1` + `version` | Bảng một dòng; **không có FK** tới `app_user` (ảnh vẽ quan hệ 1–N là sai) |
| `config_release.content_hash` | `content_sha256` | |
| `execution_attempt.closure` | `closure_kind` | |
| `execution_issue.issue_kind` | `kind` | |
| `attachment.uploaded_by` | `uploader_id` | |
| `audit_event.previous_hash`, `event_hash` | `prev_hash`, `hash` | |
| `audit_head.scope`, `last_seq` | khoá theo chuỗi `REQ:{id}` / `ADMIN` | |
| `outbox_event.state = PROCESSED` (text ER-11) | `SENT` | |
| `notification.label` (text ER-11) | — | Xem từ điển ở `09` |
| `approval_step.state = PENDING` (text ER-07) | `WAITING` | |
| `privacy_case —(Áp dụng lưu giữ)— request` (ảnh ER-10) | Quan hệ lưu giữ đi qua **`retention_hold.request_id`**; `privacy_case` chỉ nối `app_user` (subject, owner) | Ảnh thiếu thực thể `retention_hold` |

## 3. ER-01 — Danh tính, cấu hình và hồ sơ lõi

```mermaid
erDiagram
  DEPARTMENT ||--o{ DEPARTMENT : "parent_id"
  DEPARTMENT ||--o{ APP_USER : "department_id"
  APP_USER ||--o{ APP_USER : "manager_id"
  APP_USER ||--o{ ROLE_MEMBERSHIP : "user_id"
  DEPARTMENT |o--o{ ROLE_MEMBERSHIP : "department_id (scope DEPARTMENT)"
  REQUEST_TYPE |o--o{ ROLE_MEMBERSHIP : "type_id (type_scope ONE)"
  REQUEST_TYPE ||--o{ CONFIG_RELEASE : "type_id"
  REQUEST_TYPE |o--o| CONFIG_RELEASE : "active_release_id (FK2 id,type)"
  REQUEST_TYPE ||--o{ REQUEST : "type_id"
  APP_USER ||--o{ REQUEST : "requester_id"
  REQUEST |o--o| REQUEST : "origin_request_id"
  CONFIG_RELEASE ||--o{ REQUEST : "draft_release_id (FK2)"
  REQUEST ||--|{ REQUEST_REVISION : "request_id"
  REQUEST |o--o| REQUEST_REVISION : "current_revision_id (FK2)"
  CONFIG_RELEASE ||--o{ REQUEST_REVISION : "release_id (snapshot quy chế)"
  DEPARTMENT ||--o{ REQUEST_REVISION : "department_id (snapshot)"
  SECURITY_EPOCH {
    smallint id PK "=1"
    bigint version
  }
  APP_USER {
    uuid id PK
    varchar email UK
    uuid department_id FK
    uuid manager_id FK
    bool is_active
    int auth_version
    bool must_change_password
    text password_hash "Argon2"
    varchar account_type "mig 11"
    bool is_system_account "AI hệ thống"
    varchar employee_code "mig 10"
  }
  ROLE_MEMBERSHIP {
    uuid id PK
    uuid user_id FK
    varchar role "7 vai trò"
    varchar scope_kind "GLOBAL|DEPARTMENT"
    varchar type_scope "ALL|ONE"
    timestamptz valid_from
    timestamptz valid_to
    timestamptz revoked_at
  }
  REQUEST_TYPE {
    uuid id PK
    varchar code UK
    char lifecycle "A|B|C"
    varchar category
    smallint risk_weight "1..5"
    smallint approval_level "1..5"
    uuid active_release_id FK
  }
  CONFIG_RELEASE {
    uuid id PK
    uuid type_id FK
    int version
    varchar state "DRAFT|PUBLISHED"
    jsonb form_schema
    jsonb route_rules
    jsonb actor_bindings
    jsonb sla_profile
    char content_sha256
  }
  REQUEST {
    uuid id PK
    varchar code UK
    uuid requester_id FK
    varchar status "9 trạng thái"
    jsonb draft_payload
    bigint lock_version
    smallint risk_weight
    smallint approval_level
    uuid current_revision_id FK
  }
  REQUEST_REVISION {
    uuid id PK
    uuid request_id FK
    int revision_no
    jsonb payload
    bigint amount_vnd "bắt buộc với C"
    char payload_sha256
    uuid release_id FK
  }
```

## 4. ER-02 — Quy trình, thực thi và tệp

```mermaid
erDiagram
  REQUEST_REVISION ||--o| WORKFLOW_INSTANCE : "revision_id (FK2)"
  REQUEST ||--o{ REQUEST_PARTICIPANT : "request_id"
  APP_USER ||--o{ REQUEST_PARTICIPANT : "user_id"
  WORKFLOW_INSTANCE ||--|{ APPROVAL_STEP : "instance_id (FK2)"
  APP_USER ||--o{ APPROVAL_STEP : "assignee_id"
  APPROVAL_STEP ||--o| APPROVAL_DECISION : "step_id (FK2), append-only"
  WORKFLOW_INSTANCE ||--o{ EXECUTION_ATTEMPT : "instance_id (FK2)"
  APP_USER ||--o{ EXECUTION_ATTEMPT : "executor_id"
  EXECUTION_ATTEMPT ||--o{ EXECUTION_ISSUE : "attempt_id (FK2), append-only"
  EXECUTION_ATTEMPT ||--o| ACCEPTANCE_DECISION : "attempt_id (FK2), append-only"
  REQUEST ||--o{ ATTACHMENT : "request_id"
  APP_USER ||--o{ ATTACHMENT : "uploader_id"
  ATTACHMENT ||--o{ DRAFT_ATTACHMENT : "FK2"
  ATTACHMENT ||--o{ REVISION_ATTACHMENT : "FK2, append-only"
  REQUEST_REVISION ||--o{ REVISION_ATTACHMENT : "FK2"
  ATTACHMENT ||--o{ EXECUTION_ATTACHMENT : "FK2, append-only"
  EXECUTION_ATTEMPT ||--o{ EXECUTION_ATTACHMENT : "FK2"
  WORKFLOW_INSTANCE {
    uuid id PK
    uuid revision_id FK
    char lifecycle
    varchar matched_rule_id
    jsonb resolved_route
    uuid planned_executor_id FK
    uuid acceptor_id FK
    varchar state "ACTIVE|COMPLETED|REJECTED|SUPERSEDED|CANCELLED"
  }
  REQUEST_PARTICIPANT {
    uuid request_id FK
    uuid user_id FK
    varchar joined_as "REQUESTER|APPROVER|EXECUTOR|ACCEPTOR"
    timestamptz read_revoked_at
  }
  APPROVAL_STEP {
    uuid id PK
    smallint step_no
    uuid assignee_id FK
    varchar state "WAITING|ACTIVE|APPROVED|REJECTED|NEEDS_INFO|SKIPPED"
  }
  APPROVAL_DECISION {
    uuid id PK
    varchar outcome "APPROVE|REJECT|NEEDS_INFO"
    text reason "10..2000 khi REJECT/NEEDS_INFO"
    uuid actor_id FK
  }
  EXECUTION_ATTEMPT {
    uuid id PK
    int attempt_no
    varchar state "READY|RUNNING|SUBMITTED|FINISHED"
    varchar closure_kind "SUCCESS|ACCEPTED|REWORK|REASSIGNED"
    text result_note
    varchar external_reference
  }
  EXECUTION_ISSUE {
    varchar kind "UNABLE_TO_CLAIM|BLOCKED"
    text reason
  }
  ACCEPTANCE_DECISION {
    varchar outcome "ACCEPT|REWORK"
    text reason
  }
  ATTACHMENT {
    uuid id PK
    varchar storage_key
    varchar original_name
    varchar mime "pdf|jpeg|png"
    int size_bytes "<=10MiB"
    char sha256
    varchar scan_state "QUEUED|CLEAN|INFECTED|ERROR"
    timestamptz deleted_at
  }
```

## 5. ER-03 — SLA, sự kiện, kiểm toán và quyền riêng tư

```mermaid
erDiagram
  APPROVAL_STEP ||--o| SLA_STAGE : "approval_step_id (FK2), kind APPROVAL"
  EXECUTION_ATTEMPT ||--o{ SLA_STAGE : "attempt_id (FK2), kind EXECUTION|ACCEPTANCE"
  SLA_STAGE ||--o{ SLA_ALERT : "stage_id (FK2), UNIQUE(stage,kind), append-only"
  REQUEST ||--o{ OUTBOX_EVENT : "request_id"
  OUTBOX_EVENT ||--o{ NOTIFICATION : "event_id"
  APP_USER ||--o{ NOTIFICATION : "recipient_id"
  APP_USER ||--o{ IDEMPOTENCY_RECORD : "actor_id"
  REQUEST |o--o{ IDEMPOTENCY_RECORD : "request_id"
  REQUEST ||--o{ AUDIT_EVENT : "request_id (chuỗi REQ:id), append-only"
  AUDIT_HEAD ||--o{ AUDIT_EVENT : "đầu chuỗi (logic, khoá FOR UPDATE)"
  APP_USER |o--o{ AUDIT_EVENT : "actor_id (HUMAN|SYSTEM)"
  APP_USER |o--o{ ADMIN_EVENT : "actor_id, append-only"
  AUDIT_EVENT }o--o| AUDIT_CHECKPOINT : "phạm vi seq (chưa dùng)"
  APP_USER ||--o{ PRIVACY_CASE : "subject_user_id / owner_id"
  REQUEST ||--o{ RETENTION_HOLD : "request_id"
  APP_USER ||--o{ RETENTION_HOLD : "set_by / released_by"
  SLA_STAGE {
    varchar kind "APPROVAL|EXECUTION|ACCEPTANCE"
    timestamptz started_at
    timestamptz due_at
    timestamptz closed_at
    timestamptz breached_at
  }
  SLA_ALERT {
    varchar kind "REMINDER|BREACH"
  }
  OUTBOX_EVENT {
    varchar event_type
    jsonb payload
    varchar state "PENDING|PROCESSING|SENT|DEAD"
    uuid lease_token
    timestamptz lease_until
    int attempts
    int replay_count
    timestamptz available_at
    varchar dedupe_key UK
    varchar last_error_code
  }
  AUDIT_EVENT {
    bigint seq
    varchar action
    varchar actor_kind
    jsonb details "RFC 8785"
    char prev_hash
    char hash
  }
  PRIVACY_CASE {
    varchar case_type "ACCESS|CORRECT|ERASE|RESTRICT|OBJECT"
    varchar status "OPEN|REVIEW|APPROVED|REJECTED|DONE"
    varchar decision_reference
    timestamptz due_at
  }
  RETENTION_HOLD {
    text reason
    timestamptz released_at
  }
```

## 6. ER-11 → ER-13 — Các bảng mở rộng sau migration 04–13 *(DOCX chưa có)*

```mermaid
erDiagram
  ROLE ||--o{ ROLE_MODULE_PERMISSION : "role_code"
  MODULES ||--o{ ROLE_MODULE_PERMISSION : "module_code"
  APP_USER ||--o{ USER_PERMISSIONS : "user_id (ghi đè theo người)"
  APP_USER ||--o| ADMIN_ACCOUNT : "tài khoản quản trị (chỉ admin@eas.com)"
  LIFECYCLE ||--o{ REQUEST_TYPE : "A|B|C (bảng tham chiếu)"
  APP_USER ||--o{ APPROVAL_DELEGATION : "delegator_id / delegate_id"
  APP_USER ||--o{ PASSWORD_RESET_REQUEST : "user_id"
  APP_USER ||--o{ USER_LEAVE_AND_TRIPS : "user_id (đồng bộ từ đơn nghỉ đã duyệt)"
  COMPANY_REGULATIONS ||--o{ REGULATION_VERSIONS : "phiên bản văn bản"
  COMPANY_REGULATIONS ||--o{ AI_LEARNING_JOB : "kích hoạt học"
  AI_LEARNING_JOB ||--o| AI_POLICY_VERSION : "bộ luật sinh ra"
  SYSTEM_ANNOUNCEMENT ||--o{ ANNOUNCEMENT_RECEIPT : "đã đọc"
  APP_USER ||--o{ ANNOUNCEMENT_RECEIPT : "user_id"
  APPROVAL_DELEGATION {
    uuid delegator_id
    uuid delegate_id
    timestamptz starts_at
    timestamptz ends_at
    timestamptz revoked_at
  }
  AI_LEARNING_JOB {
    varchar target_version
    varchar status "QUEUED|RUNNING|APPLIED|FAILED"
    varchar step
    int progress
    varchar lease_owner
    timestamptz lease_until
    int attempts
    int max_attempts
    jsonb snapshot
    jsonb compiled_policy
    jsonb diff
  }
  AI_POLICY_VERSION {
    varchar version
    jsonb document "bộ luật"
    varchar state "ACTIVE|INACTIVE"
  }
```

> Các quan hệ COMPANY_REGULATIONS → AI_LEARNING_JOB → AI_POLICY_VERSION là **quan hệ logic** (liên kết qua `target_version`, `snapshot`). Chúng không phải FK.
>
> Live `app_user` vẫn còn cột **`username`** (di sản, song song với `email`) và có thêm `is_system_account`. Đề xuất: xoá `username` sau khi xác nhận không còn code đọc cột này, theo quy trình expand/contract.

**Cần xử lý ở CSDL live.** Migration 11 dự kiến chuyển `workflow_categories` và các view phụ thuộc sang `eas_deprecated`. Nhưng live vẫn có `eas.workflow_categories` (3 dòng) và các view `user_roles`, `v_request_templates_full`, `v_users_management` trong schema `eas`. Có hai khả năng:
- migration admin upgrade (`supabase/migrations/20261103_admin_full_upgrade.sql`) đã chạy lại sau migration 11; hoặc
- bảng đó được cố ý giữ lại.

**Cần DBA xác nhận** trước khi chạy `scheduled/2026-11-17_drop_eas_deprecated_after_11.sql`.

## 7. Nhận xét chất lượng thiết kế dữ liệu (theo kinh nghiệm)

| # | Điểm | Đánh giá |
|---|---|---|
| Q1 | FK kép `(id, request_id)` trên mọi bảng con | Rất tốt. Chặn lỗi chéo hồ sơ ngay ở DB |
| Q2 | Bảng quyết định / sự kiện append-only bằng trigger: `request_revision`, `approval_decision`, `acceptance_decision`, `execution_issue`, `revision_attachment`, `execution_attachment`, `sla_alert`, `audit_event`, `admin_event` (`schema.sql:1113`) | Đúng chuẩn kiểm toán |
| Q3 | Snapshot quy chế (`release_id`) và phòng ban (`department_id`) trong revision | Đúng. Thay đổi tổ chức sau này không làm sai hồ sơ cũ |
| Q4 | Bảng trùng chức năng từ admin upgrade (`users`, `departments`, `requests`, `roles` …) | Đã dọn ở migration 11. Phải chốt lịch xoá `eas_deprecated` |
| Q5 | `request.risk_weight`/`approval_level` và `request_revision.risk_weight`/`approval_level` | Lưu ở cả hai nơi là hợp lý: revision là bản chụp bất biến, request là giá trị hiện hành |
| Q6 | `audit_checkpoint`, `retention_hold`, `privacy_case` có bảng nhưng thiếu luồng ứng dụng | Xem `12` |
