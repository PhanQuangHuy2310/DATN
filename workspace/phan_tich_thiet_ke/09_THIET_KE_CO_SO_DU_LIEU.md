# 09 — Thiết kế cơ sở dữ liệu (DOCX 1.4.3, Bảng 1.4, 2.3.8)

> **Hiện trạng DOCX 2.3.8.** Bảng 2.10–2.16 đều là **bản sao Bảng 2.1 (danh sách tác nhân)**, nên DOCX **chưa có từ điển dữ liệu**. Tệp này viết lại toàn bộ.
>
> **Nguồn số liệu:**
> - lược đồ: `database/EAS_Supabase_SQL/00_eas_supabase_schema.sql`, `DATA_DICTIONARY.md` (1.431 dòng), migration 04–13;
> - DB live, đọc bằng role backend (chỉ đọc, 04/11/2026): `information_schema`, `pg_indexes`, `pg_policy`, `pg_trigger`, `count(*)`.

## 1. Tổng quan

| Chỉ số | DOCX | Live 04/11/2026 | Ghi chú |
|---|---|---|---|
| Bảng trong schema `eas` | 30 | **52** (sau Migrations 14–17; trước đó ngày 04/11 là 49) | 30 bảng lõi + các bảng mở rộng; kho chỉ-đọc `eas_archive` giữ `dropped_column_value`, `workflow_categories_eas`, `system_versions_changelog`, `work_handover` và 10 bảng bản đầu |
| View trong `eas` | — | **0** (Migration 15 đã bỏ toàn bộ 9 view bí danh cũ: `admins`, `departments`, `requests`, `roles`, `role_permissions`, `request_templates`, `user_roles`, `v_request_templates_full`, `v_users_management`) | Code chỉ truy vấn trực tiếp bảng chuẩn v2 |
| Schema mock | 8 | 8: `mock_hr`, `mock_assets`, `mock_facilities`, `mock_crm`, `mock_procurement`, `mock_it`, `mock_finance`, `mock_travel` | KHỚP |
| Truy cập hệ thống ngoài `mock_*` | — | Qua **Mock Systems API** (`/mock-api/v1/*`, dịch vụ `mock_systems :8100`, header `X-Integration-Secret`, role `eas_mock`) | Migration 17 thu hồi toàn bộ quyền SQL trên `mock_*` khỏi `eas_api`/`eas_worker`; chỉ `eas_mock` được truy cập |
| RLS | Bật mọi bảng | Bật **49/49** bảng; mỗi bảng 1–3 policy theo role backend | KHỚP |
| Trigger (không tính nội bộ) | Có append-only | **57** | |
| Hàm trong `eas` | — | **39** | |
| Chỉ mục | B-Tree + **GIN cho JSONB** | **163** chỉ mục, trong đó 92 unique; **0 GIN** | DOCX SAI về GIN. Hiện không có truy vấn tìm trong JSONB nên **không cần GIN**: bỏ câu này khỏi DOCX |
| Pool kết nối | PgBouncer | Pool psycopg phía app (`EAS_DB_POOL_MAX_SIZE` = 10) + pooler của Supabase | LỆCH NHẸ |
| PostgreSQL | 15+ | Supabase quản lý | — |

## 2. Role và quyền (thay đoạn "Supabase RLS / anon" ở DOCX)

| Role | Dùng bởi | Quyền | Nguồn |
|---|---|---|---|
| `eas_api` (qua `eas_backend_login`) | `api_core` | DML trên `eas` theo policy; **không có quyền trên `mock_*` hay `eas_archive`** | AGENTS.md; migration 11, 15, 17 |
| `eas_worker` | worker | outbox, SLA, notification, `ai_learning_job`, SELECT trên `approval_delegation`; **không có quyền trên `mock_*`** | migration 16, 17 |
| `eas_mock` (qua `eas_mock_login`) | `mock_systems` (`:8100`) | Role **duy nhất** đọc/ghi 8 schema `mock_*` phục vụ Mock Systems API (`/mock-api/v1/*`) | migration 17 |
| `eas_privacy` | lệnh `privacy_case` | xoá dữ liệu theo case | |
| `eas_backup` | sao lưu | đọc | |
| `eas_migration` | SQL Editor (người, không phải app) | sở hữu object; chạy DDL | migration 11 §1 |
| `anon`, `authenticated` | — | **không có grant, không có USAGE** | migration 11 §2 |

Theo AGENTS.md, việc không dùng `auth.uid()` là sai lệch đã được chấp thuận: trình duyệt không bao giờ gọi Supabase trực tiếp. Quyền theo từng người do `require_actor` cùng vị từ SQL ở `api_core` cưỡng chế.

## 3. Từ điển dữ liệu — 30 bảng lõi

Ký hiệu cột: PK = khoá chính, FK2 = khoá ngoại kép `(x_id, request_id)`, AO = append-only (trigger cấm UPDATE/DELETE).

### 3.1 Miền Danh tính & Tổ chức

| Bảng | Số dòng live | Cột chính | Ràng buộc quan trọng |
|---|---|---|---|
| `security_epoch` | 1 | `id`=1, `version`, `updated_at` | Một dòng. `lock_security(true)` khoá FOR UPDATE; `lock_security(false)` khoá FOR SHARE (`schema.sql:617`) |
| `department` | 8 | `id`, `code` UK, `name`, `parent_id` → department, `is_active` | Cây phòng ban |
| `app_user` | 138 | `id`, `email` UK, `display_name`, `department_id`, `manager_id` → app_user, `is_active`, `must_change_password`, `auth_version`, `password_hash` (Argon2), `account_type`, `is_system_account`, `employee_code`, `username` (di sản) | Đổi mật khẩu hoặc quyền thì tăng `auth_version` và `security_epoch` |
| `role_membership` | 465 (còn hiệu lực theo vai trò: REQ 136 · APR 46 · EXE 97 · ACC 177 · OPS 1 · POL 1 · AUD **0**) | `user_id`, `role` (7 giá trị), `scope_kind` GLOBAL/DEPARTMENT, `department_id`, `type_scope` ALL/ONE, `type_id`, `valid_from`, `valid_to`, `revoked_at` | Trigger migration 11 cấm trộn vai trò quản trị với vai trò nghiệp vụ trên cùng tài khoản |

### 3.2 Miền Danh mục & Cấu hình

| Bảng | Số dòng live | Cột chính | Ràng buộc |
|---|---|---|---|
| `request_type` | 66 (58 đang hoạt động: A 9 · B 27 · C 22) | `code` UK, `name`, `description`, `category` FK → `request_group.code` (**12 nhóm lớn** theo mục đích người gửi), `lifecycle` A/B/C, `risk_weight` 1..5 (nguồn duy nhất), `approval_level` 1..5, `active_release_id` FK2 | Migration 17 bỏ CHECK 10 nhóm cũ, thêm `request_group` (12 nhóm) và `request_menu_item` (61 mục menu) |
| `config_release` | 78 | `type_id`, `version`, `state` DRAFT/PUBLISHED, `lifecycle`, `form_schema`, `route_rules`, `actor_bindings`, `sla_profile`, `content_sha256`, `created_by`, `published_by`, `lock_version` | PUBLISHED thì bất biến. Validator: đúng 1 rule default ở cuối; priority là số nguyên duy nhất; 1..5 slot; toán tử thuộc allowlist; `sla_profile.reminder_fraction` = 0.5; giờ SLA trong (0, 720] |

### 3.3 Miền Hồ sơ & Quy trình

| Bảng | Số dòng live | Cột chính | Ràng buộc |
|---|---|---|---|
| `request` | 37 (DRAFT 7 · NEEDS_INFO 2 · PENDING 6 · READY 3 · IN_PROGRESS 2 · WAIT_ACC 1 · COMPLETED 13 · REJECTED 2 · CANCELLED 1) | `code` UK, `requester_id`, `type_id`, `status` (9 giá trị), `draft_payload` (object), `draft_amount_vnd`, `draft_release_id` FK2, `origin_request_id`, `current_revision_id` FK2, `risk_weight`, `approval_level`, `lock_version`, `approved_at`, `completed_at` | `guard_request`: FSM, cấm sửa trạng thái cuối, `lock_version`+1, khớp lifecycle với trạng thái và số tiền, kiểm mốc thời gian |
| `request_revision` (AO) | 30 | `revision_no`, `release_id`, `department_id` (snapshot), `payload`, `amount_vnd` (bắt buộc với C, cấm với A/B), `payload_sha256`, `submitted_by`, `risk_weight`, `approval_level` | Chỉ tạo khi request ở DRAFT/NEEDS_INFO |
| `workflow_instance` | 30 | `revision_id` FK2, `lifecycle`, `matched_rule_id`, `resolved_route`, `planned_executor_id`, `acceptor_id`, `state` | Tối đa 1 instance ACTIVE mỗi request |
| `request_participant` | 85 | `user_id`, `joined_as`, `read_revoked_at` | Là cơ sở của quyền xem (IDOR) |
| `approval_step` | 43 | `instance_id` FK2, `step_no`, `assignee_id`, `state`, `activated_at`, `closed_at` | `guard_step` |
| `approval_decision` (AO) | 35 | `step_id` FK2, `actor_id`, `outcome`, `reason` | Reject/Needs-info bắt buộc lý do 10–2000 ký tự (ở service) |
| `execution_attempt` | 14 | `instance_id` FK2, `attempt_no`, `executor_id`, `state`, `closure_kind`, `result_note`, `external_reference`, các mốc thời gian | `one_current_attempt`; cấm đổi executor khi RUNNING/SUBMITTED |
| `acceptance_decision` (AO) | 4 | `attempt_id` FK2, `outcome` ACCEPT/REWORK, `reason` | |
| `execution_issue` (AO) | 0 | `attempt_id` FK2, `kind` UNABLE_TO_CLAIM/BLOCKED, `reason` | |

### 3.4 Miền Tệp

| Bảng | Số dòng live | Cột chính | Ràng buộc |
|---|---|---|---|
| `attachment` | 4 | `storage_key`, `object_version`, `original_name`, `mime` (pdf/jpeg/png), `size_bytes`, `sha256`, `scan_state`, `scan_attempts`, `scanned_at`, `deleted_at` | MIME nằm trong allowlist ở DB; magic bytes kiểm ở app |
| `draft_attachment` | 1 | FK2 → attachment | Chỉ người tạo; chỉ khi request ở DRAFT/NEEDS_INFO |
| `revision_attachment` (AO) | 3 | FK2 → attachment, revision | |
| `execution_attachment` (AO) | 0 | FK2 → attachment, attempt | |

### 3.5 Miền SLA, sự kiện, thông báo

| Bảng | Số dòng live | Cột chính | Ràng buộc |
|---|---|---|---|
| `sla_stage` | 44 | `kind`, `approval_step_id` / `attempt_id` (đúng một trong hai, theo `kind`), `started_at`, `due_at`, `closed_at`, `breached_at` | `sla_subtype` |
| `sla_alert` (AO) | 13 | `stage_id` FK2, `kind` REMINDER/BREACH | UNIQUE(stage, kind) để khử trùng |
| `outbox_event` | 43 | `event_type`, `payload`, `state`, `dedupe_key` UK, `attempts`, `replay_count`, `available_at`, `lease_token`, `lease_until`, `sent_at`, `last_error_code` | |
| `notification` | 43 | `recipient_id`, `request_id`, `event_id`, `read_at` | |
| `idempotency_record` | 6 | `actor_id`, khoá, hash payload, kết quả | Chống gửi trùng |

### 3.6 Miền Kiểm toán & Quyền riêng tư

| Bảng | Số dòng live | Cột chính | Ghi chú |
|---|---|---|---|
| `audit_head` | 36 | đầu chuỗi theo `REQ:{id}` / `ADMIN` | Khoá khi ghi |
| `audit_event` (AO) | 82 | `request_id`, `seq`, `actor_id`, `actor_kind`, `action`, `target_type`, `target_id`, `details`, `correlation_id`, `occurred_at`, `hash_version`, `prev_hash`, `hash` | RFC 8785 |
| `admin_event` (AO) | 99 | thao tác quản trị, có hash | |
| `audit_checkpoint` | **0** | | Chưa có exporter |
| `privacy_case` | 1 | `subject_user_id`, `owner_id`, `case_type`, `status`, `decision_reference`, `due_at` | Lệnh CLI |
| `retention_hold` | 1 | `request_id`, `reason`, `set_by`, `released_by`, `released_at` | Chưa có API tạo hay giải toả |

## 4. Bảng mở rộng (migration 04–13 và admin upgrade) — DOCX chưa mô tả

| Bảng | Dòng live | Mục đích | Migration |
|---|---|---|---|
| `lifecycle` | 3 | Tham chiếu A/B/C | 04 |
| `role` | 7 | Danh mục vai trò | 04 |
| `password_reset_request` | 0 | Quên mật khẩu | 05 |
| `ai_policy_version` | 0 | Phiên bản bộ luật AI (lịch sử kích hoạt) | 08 |
| `approval_delegation` | 0 | Ủy quyền & bàn giao công việc theo khoảng thời gian (Migration 15 gộp `work_handover`, thêm `scope` ∈ `{APPROVAL, EXECUTION, ACCEPTANCE, ALL}`, `source` ∈ `{MANUAL, LEAVE_REQUEST}`, `source_request_id`, `created_by`) | 10, 15, 16 |
| `role_module_permission` | 63 | Quyền màn hình theo vai trò | 11 |
| `admin_account` | 1 | Tài khoản quản trị tách riêng (chỉ admin@eas.com) | 11 |
| `ai_learning_job` | 2 (APPLIED) | Job học quy định, có lease | 12 |
| `system_announcement` | 2 | Thông báo hệ thống | 12 |
| `announcement_receipt` | 3 | Đã đọc thông báo hệ thống | 12 |
| `modules` | 9 | Danh mục module màn hình | admin upgrade |
| `user_permissions` | 0 | Ghi đè quyền theo người | admin upgrade → 11 |
| `user_leave_and_trips` | 3 | Lịch nghỉ / công tác (đồng bộ từ đơn nghỉ đã duyệt, `leave_sync.py`) | admin upgrade |
| `company_regulations` | 3 | Văn bản quy định công ty | admin upgrade |
| `regulation_versions` | 3 | Phiên bản văn bản quy định | admin upgrade |
| `ai_system_state` | 1 | Trạng thái động cơ AI | admin upgrade |
| `system_versions_changelog` | 29 | Nhật ký phiên bản hệ thống cũ — **đã chép toàn vẹn 29 dòng sang chuỗi băm `eas.admin_event` và dời sang `eas_archive.system_versions_changelog` ở Migration 15** | admin upgrade → 15 |
| `mock_apis` | 8 | Bật/tắt tích hợp từng hệ thống mô phỏng | admin upgrade |
| `workflow_categories` | 3 | **Đã dời sang kho chỉ-đọc `eas_archive.workflow_categories_eas` ở Migration 15** (trùng với `eas.lifecycle`) | 11 → 15 |
| `privacy_case_approval` (AO) | 0 | Duyệt kép xoá dữ liệu cá nhân (2 người duyệt khác nhau, khác `owner_id`, cùng `manifest_sha256`) | 14 |
| `sla_escalation_policy` | 3 | Chính sách nhắc hạn (50%), hành vi khi quá hạn (`REMIND`/`AUTO_REASSIGN`) và leo thang mức 2 (150%) | 14 |
| `business_holiday` | 0 | Lịch nghỉ lễ công ty phục vụ tính SLA theo giờ làm việc | 14 |
| `request_group` | 12 | 12 nhóm yêu cầu lớn theo mục đích người gửi (`ABSENCE`, `WORKTIME`, `BORROW`, `PROVISION`, `PAYMENT`, `PROCUREMENT`, `PEOPLE`, `SUPPORT`, `WORK`, `LEGAL`, `SALES`, `ASSET`) | 17 |
| `request_menu_item` | 61 | 61 mục chọn trên menu tạo yêu cầu (56 loại trực tiếp + 5 mục đặt sẵn `preset`) | 17 |

## 5. Bảng 1.4 (8 schema mock) — đối chiếu "cơ chế tương tác"

> **Cập nhật 05/11/2026 (migration 17, mock 005).** `mock_*` được coi là **hệ thống ngoài**. EAS (`api_core`, worker, AI service) **không đọc bảng `mock_*` trực tiếp** nữa; mọi truy cập đi qua **Mock Systems API** (`/mock-api/v1/...`, dịch vụ `mock_systems`, header `X-Integration-Secret`). Chỉ vai trò `eas_mock` có quyền trên `mock_*`; `eas_api`/`eas_worker` không có. Ghi (mượn tài sản, đặt phòng/xe, cấp quyền) đi qua `/mock-api/v1/allocations` với khoá idempotent `source_request_id`; duyệt trước thắng, BOD được ưu tiên. Chi tiết: `docs/TICH_HOP_HE_THONG_NGOAI.md`. Bảng dưới là đối chiếu ngày 04/11, các dòng đã lỗi thời được đánh dấu.

| Schema | DOCX nói | Thực tế | Phán quyết |
|---|---|---|---|
| mock_hr | Đối soát số phép khi duyệt nghỉ | `leave_balance` qua API `/mock-api/v1/hr/leave-balances`. AI `mock_context.lookup_leave_balance` gọi cùng API (ảnh chụp JSON `ai_service/data/mock/*.json` **đã xoá** 05/11) | KHỚP (đã sửa 05/11) |
| mock_hr.attendance | — | ~~Migration `004_hrm_attendance.sql` chưa có trên live~~. **Đã xử lý 05/11:** migration mock 004 bị xoá; dữ liệu chấm công là dữ liệu ảo. Trạng thái làm việc tính bởi `eas.get_user_working_status` (migration 16): đơn nghỉ/công tác **đã duyệt** trong `eas.user_leave_and_trips`, nếu không có thì theo giờ hành chính T2–T6 08:00–12:00, 13:30–17:30 (`DANG_LAM`, `NGHI_LAM`, `CONG_TAC`, `NGOAI_GIO`) | ĐÃ GIẢI QUYẾT theo D2 |
| mock_assets | Kiểm thiết bị sẵn sàng | Qua API `/mock-api/v1/assets/categories` và `/allocations` (kiểm tồn kho lúc gửi, giữ chỗ lúc duyệt cuối — duyệt trước thắng, ưu tiên BGĐ thu hồi `RESOURCE_PREEMPTED`, worker tự trả khi hết hạn) | KHỚP (đã nâng cấp qua Mock Systems API ngày 04/11–05/11) |
| mock_facilities | Chống trùng lịch; **tự cập nhật lịch khi duyệt** | Qua API `/mock-api/v1/facilities/resources` và `/allocations` (kiểm tra trống phòng/xe & sức chứa lúc gửi, giữ chỗ lúc duyệt cuối, ưu tiên BGĐ thu hồi, worker tự trả khi hết hạn) | KHỚP (đã hiện thực qua Mock Systems API với khoá `source_request_id`) |
| mock_crm | Ngữ cảnh doanh thu | view `customer_directory`, `contract` | KHỚP |
| mock_procurement | Giá trần; **đồng bộ PO khi duyệt** | Chỉ đọc | "Đồng bộ PO" mâu thuẫn với SELECT-only. Sửa DOCX |
| mock_it | **Tự ghi nhận phân quyền mới** | Qua API `/mock-api/v1/it/applications` (danh sách chọn động) và `POST /mock-api/v1/it/user-access` ghi nhận cấp quyền khi đơn `ACCESS` hoàn tất | KHỚP (đã hiện thực qua Mock Systems API) |
| mock_finance | BRE đối soát ngân sách | Qua API `/mock-api/v1/finance/...`: kiểm tra hạn mức ngày của loại chi phí và ngân sách còn lại của trung tâm chi phí lúc gửi; ghi cam kết chi `POST /mock-api/v1/finance/commitments` lúc duyệt | KHỚP (đã hiện thực qua Mock Systems API) |
| mock_travel | Cảnh báo vượt định mức | `travel_policy` (10 dòng) và `travel_option` (18 dòng) chỉ được đọc để hiển thị qua `mock_sources`. **Không có** kiểm tra vượt định mức khi tạo đơn `BUSINESS_TRIP` | THIẾU HIỆN THỰC (P1: thêm kiểm tra vào `plan_constraints`) |

## 6. Quy ước thiết kế (đưa vào DOCX thay cho bảng giữ chỗ)

1. **Khoá chính** là UUID (`gen_random_uuid()`). Mã nghiệp vụ dạng `REQ-…` là cột `code` UNIQUE riêng.
2. **FK kép** `(x_id, request_id)` trên mọi bảng con của hồ sơ.
3. **Append-only** cho bảng quyết định và sự kiện (danh sách ở `schema.sql:1113`).
4. **Khoá lạc quan**: `lock_version`, mỗi lệnh tăng đúng 1 (trigger).
5. **Mốc thời gian** dùng `timestamptz` UTC. SLA tính theo lịch UTC (`clock = CALENDAR_UTC`). Giờ làm việc và ngày lễ **chưa** được hỗ trợ: cần ghi rõ giới hạn này.
6. **Tiền** dùng `bigint` VND, giới hạn 1..10^12. Không dùng số thực.
7. **JSONB** chỉ dùng cho payload theo `form_schema` và cấu hình. Luôn kiểm `jsonb_typeof = object`.
8. **Snapshot**: revision giữ `release_id` và `department_id` tại thời điểm gửi.
9. **Băm**: `sha256` của tệp; `payload_sha256` của revision; `content_sha256` của release; `hash` của audit.

## 7. Phát hiện dữ liệu live cần xử lý

| # | Phát hiện | Mức | Đề xuất |
|---|---|---|---|
| L1 | Không ai giữ vai trò AUDITOR | Cao (chức năng kiểm toán không dùng được) | Gán AUDITOR (scope GLOBAL) cho một tài khoản kiểm soát nội bộ, không phải admin |
| L2 | ~~`mock_hr.attendance` chưa có trên live~~ | — | Đã giải quyết 05/11 (migration 16, xem §5) |
| L3 | `audit_checkpoint` = 0 | Trung bình | Viết lệnh checkpoint (P1) |
| L4 | ~~`app_user.username` còn đủ 138 giá trị song song với `email`~~ | — | **Đã giải quyết 04/11 (Migration 15):** lưu giá trị vào `eas_archive.dropped_column_value` và xoá cột `username` |
| L5 | ~~`eas.workflow_categories` và 9 view tương thích còn trong `eas`~~ | — | **Đã giải quyết 04/11 (Migration 15):** xoá 9 view bí danh, dời `workflow_categories` và `system_versions_changelog` sang `eas_archive`, đổi tên `eas_deprecated` thành `eas_archive` |
| L6 | `ai_policy_version` = 0 dòng, trong khi bộ luật đang chạy nằm ở `ai_service/data/active_enterprise_policy.json` (v1.10) và kết quả `ai_learning_job.compiled_policy` | Trung bình | Thống nhất một nguồn sự thật. Khuyến nghị: DB (`ai_policy_version` ACTIVE); tệp JSON chỉ là cache của AI service |
| L7 | `execution_issue`, `execution_attachment`, `approval_delegation`, `user_permissions` đều 0 dòng | Thông tin | Chưa có dữ liệu thử thật cho các luồng này. Bổ sung kịch bản UAT |
