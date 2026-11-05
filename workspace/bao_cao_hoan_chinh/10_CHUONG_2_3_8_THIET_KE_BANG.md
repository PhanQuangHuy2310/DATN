# 2.3.8. THIẾT KẾ CHI TIẾT CÁC BẢNG DỮ LIỆU

> Toàn bộ nội dung mục này được **sinh trực tiếp từ catalog của CSDL live** (`pg_attribute`, `pg_constraint`, `pg_trigger`, `pg_indexes`) ngày 04/11/2026, rồi bổ sung mô tả nghiệp vụ. Vì vậy tên cột, kiểu, ràng buộc khớp chính xác hệ thống đang chạy.
> Tổng cộng **52 bảng hoạt động** trong schema `eas` (đầy đủ 52 bảng từ điển mục 2.10–2.16 dưới đây: 49 bảng gốc − 2 bảng di sản `workflow_categories`, `system_versions_changelog` chuyển sang kho `eas_archive` ở Migration 15 + 3 bảng mới giữ lại từ Migration 14 `privacy_case_approval`, `sla_escalation_policy`, `business_holiday` + 2 bảng danh mục `request_group`, `request_menu_item` từ Migration 17; **0 view** — 9 view bí danh cũ đã gỡ ở Migration 15), đồng bộ theo **Schema `eas` v2** (Migrations 14–17 ngày 04/11–05/11/2026). Dữ liệu của các bảng/cột di sản bị gộp được lưu trữ nguyên vẹn trong kho chỉ-đọc `eas_archive` (mục 2.17).

**Ký hiệu.** PK = khoá chính; UK = duy nhất; FK→ = khoá ngoại; FK2→ = khoá ngoại kép `(x_id, request_id)` bảo đảm bản ghi con cùng hồ sơ với bản ghi cha; NN = bắt buộc (NOT NULL); AO = bảng chỉ-ghi-thêm (trigger cấm UPDATE/DELETE).

**Quy ước chung.** Khoá chính UUID; thời gian `timestamptz` (UTC); tiền `bigint` VND; JSON dùng `jsonb` và luôn kiểm là object; mọi bảng bật Row Level Security với chính sách cho role backend.

## Bảng 2.10. Miền danh tính và tổ chức

### 2.10.1. `eas.security_epoch`

Bảng một dòng giữ phiên bản bảo mật toàn cục; dùng làm khoá tuần tự hoá giữa thay đổi quyền và thao tác nghiệp vụ. Số dòng live: 1 · Trigger: 1 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | smallint | ✔ | PK | `1` | Khoá chính |
| `version` | bigint | ✔ |  | `0` | Số phiên bản |
| `updated_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm cập nhật gần nhất |

Ràng buộc CHECK:
- `CHECK ((id = 1))`
- `CHECK ((version >= 0))`

### 2.10.2. `eas.department`

Cây phòng ban. Số dòng live: 8 · Trigger: 2 · Chỉ mục: 3

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `code` | character varying(30) | ✔ | UK |  | Mã nghiệp vụ duy nhất |
| `name` | character varying(150) | ✔ |  |  | Tên hiển thị |
| `parent_id` | uuid |  | FK→department |  | Phòng ban cấp trên |
| `is_active` | boolean | ✔ |  | `true` | Đang hoạt động hay không |

Ràng buộc CHECK:
- `CHECK ((((code) = btrim((code))) AND (length((code)) > 0)))`
- `CHECK ((length(btrim((name))) > 0))`
- `CHECK (((parent_id IS NULL) OR (parent_id <> id)))`

### 2.10.3. `eas.app_user`

Tài khoản người dùng (nhân viên, quản trị, tài khoản AI hệ thống). Số dòng live: 138 · Trigger: 3 · Chỉ mục: 5

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `email` | character varying(254) | ✔ | UK |  | Email đăng nhập (duy nhất) |
| `display_name` | character varying(150) | ✔ |  |  | Họ tên hiển thị |
| `department_id` | uuid | ✔ | FK→department |  | Phòng ban |
| `manager_id` | uuid |  | FK→app_user |  | Quản lý trực tiếp (tự tham chiếu) |
| `is_active` | boolean | ✔ |  | `true` | Đang hoạt động hay không |
| `must_change_password` | boolean | ✔ |  | `true` | Bắt buộc đổi mật khẩu ở lần đăng nhập tới |
| `auth_version` | bigint | ✔ |  | `0` | Phiên bản xác thực; tăng để vô hiệu mọi phiên cũ |
| `password_hash` | text | ✔ |  |  | Băm mật khẩu Argon2 |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `account_type` | character varying(16) | ✔ |  | `'EMPLOYEE'::character varying` | Loại tài khoản: quản trị hay nghiệp vụ |
| `is_system_account` | boolean | ✔ |  | `false` | Tài khoản hệ thống không đăng nhập (AI) |
| `employee_code` | character varying(30) |  |  |  | Mã nhân viên |

*(Ghi chú Schema v2: cột `username` trùng với phần trước `@` của `email` đã được lưu vào `eas_archive.dropped_column_value` và loại bỏ ở Migration 15.)*

Ràng buộc CHECK:
- `CHECK (((account_type) = ANY ((ARRAY['EMPLOYEE', 'ADMIN']))))`
- `CHECK ((auth_version >= 0))`
- `CHECK ((length(btrim((display_name))) > 0))`
- `CHECK ((((email) = lower(btrim((email)))) AND ((email) ~ '^[^@[:space:]]+@eas[.]com$')))`
- `CHECK ((length(password_hash) > 0))`
- `CHECK (((manager_id IS NULL) OR (manager_id <> id)))`

### 2.10.4. `eas.role_membership`

Gán vai trò có phạm vi phòng ban / loại yêu cầu và thời gian hiệu lực (Scoped RBAC). Số dòng live: 465 · Trigger: 2 · Chỉ mục: 5

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `user_id` | uuid | ✔ | FK→app_user |  | Người dùng |
| `role` | character varying(24) | ✔ | FK→role |  | Mã vai trò |
| `scope_kind` | character varying(12) | ✔ |  |  | Phạm vi: GLOBAL hoặc DEPARTMENT |
| `department_id` | uuid |  | FK→department |  | Phòng ban |
| `type_scope` | character varying(3) | ✔ |  |  | Phạm vi loại: ALL hoặc ONE |
| `type_id` | uuid |  | FK→request_type |  | Loại yêu cầu |
| `valid_from` | timestamp with time zone | ✔ |  | `now()` | Hiệu lực từ |
| `valid_to` | timestamp with time zone |  |  |  | Hiệu lực đến |
| `revoked_at` | timestamp with time zone |  |  |  | Thời điểm thu hồi |

Ràng buộc CHECK:
- `CHECK (((((scope_kind) = 'GLOBAL') AND (department_id IS NULL)) OR (((scope_kind) = 'DEPARTMENT') AND (department_id IS NOT NULL))))`
- `CHECK (((scope_kind) = ANY ((ARRAY['GLOBAL', 'DEPARTMENT']))))`
- `CHECK (((type_scope) = ANY ((ARRAY['ALL', 'ONE']))))`
- `CHECK (((((type_scope) = 'ALL') AND (type_id IS NULL)) OR (((type_scope) = 'ONE') AND (type_id IS NOT NULL))))`
- `CHECK (((valid_to IS NULL) OR (valid_to > valid_from)))`

## Bảng 2.11. Miền danh mục và cấu hình quy chế

### 2.11.1. `eas.request_type`

Danh mục loại yêu cầu. Số dòng live: 66 · Trigger: 1 · Chỉ mục: 5

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | FK2→config_release, PK | `gen_random_uuid()` | Khoá chính |
| `code` | character varying(30) | ✔ | UK |  | Mã nghiệp vụ duy nhất |
| `lifecycle` | character(1) | ✔ | FK→lifecycle |  | Mẫu vòng đời A/B/C |
| `is_active` | boolean | ✔ |  | `true` | Đang hoạt động hay không |
| `active_release_id` | uuid |  | FK2→config_release |  | Phiên bản quy chế đang hiệu lực |
| `name` | character varying(150) | ✔ |  |  | Tên hiển thị |
| `description` | character varying(500) | ✔ |  |  | Mô tả |
| `category` | character varying(30) | ✔ | FK→request_group |  | Mã nhóm yêu cầu lớn (12 nhóm theo mục đích người gửi trong `eas.request_group`) |
| `risk_weight` | smallint | ✔ |  | `3` | Trọng số rủi ro 1–5 |
| `approval_level` | smallint | ✔ |  | `1` | Số cấp duyệt 1–5 |

Ràng buộc CHECK:
- `CHECK (((approval_level >= 1) AND (approval_level <= 5)))`
- `FOREIGN KEY (category) REFERENCES eas.request_group(code) ON DELETE RESTRICT` *(Migration 17 bỏ CHECK 10 nhóm cũ `request_type_category_valid`, chuyển sang FK tới 12 nhóm trong `eas.request_group`: `ABSENCE`, `WORKTIME`, `BORROW`, `PROVISION`, `PAYMENT`, `PROCUREMENT`, `PEOPLE`, `SUPPORT`, `WORK`, `LEGAL`, `SALES`, `ASSET`; giá trị nhóm cũ lưu tại `eas_archive.dropped_column_value`)*
- `CHECK ((((code) ~ '^[A-Z][A-Z0-9_]{1,29}$') AND (lifecycle = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar]))))`
- `CHECK (((length(btrim((name))) > 0) OR ((name) = '')))`
- `CHECK ((length(btrim((name))) > 0))`
- `CHECK (((risk_weight >= 1) AND (risk_weight <= 5)))`

### 2.11.2. `eas.config_release`

Phiên bản quy chế của một loại; bất biến sau khi ban hành. Số dòng live: 78 · Trigger: 1 · Chỉ mục: 5

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK, UK(id,type_id) | `gen_random_uuid()` | Khoá chính |
| `type_id` | uuid | ✔ | FK→request_type, UK(id,type_id), UK(type_id,version) |  | Loại yêu cầu |
| `version` | integer | ✔ | UK(type_id,version) |  | Số phiên bản |
| `state` | character varying(9) | ✔ |  | `'DRAFT'::character varying` | Trạng thái |
| `lifecycle` | character(1) | ✔ | FK→lifecycle |  | Mẫu vòng đời A/B/C |
| `form_schema` | jsonb | ✔ |  |  | Lược đồ biểu mẫu (JSON Schema) |
| `route_rules` | jsonb | ✔ |  |  | Luật định tuyến |
| `actor_bindings` | jsonb | ✔ |  |  | Bảng gán người theo vị trí và phòng ban |
| `sla_profile` | jsonb | ✔ |  |  | Cấu hình SLA (giờ duyệt / thực hiện / nghiệm thu) |
| `created_by` | uuid | ✔ | FK→app_user |  | Người tạo |
| `published_by` | uuid |  | FK→app_user |  | Người ban hành |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `published_at` | timestamp with time zone |  |  |  | Thời điểm ban hành |
| `lock_version` | bigint | ✔ |  | `0` | Khoá lạc quan; mỗi lệnh ghi tăng đúng 1 |
| `content_sha256` | character(64) |  |  |  | Mã băm nội dung quy chế |

Ràng buộc CHECK:
- `CHECK ((jsonb_typeof(actor_bindings) = 'object'))`
- `CHECK ((jsonb_typeof(form_schema) = 'object'))`
- `CHECK ((lifecycle = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar])))`
- `CHECK ((lock_version >= 0))`
- `CHECK ((jsonb_typeof(route_rules) = 'object'))`
- `CHECK ((jsonb_typeof(sla_profile) = 'object'))`
- `CHECK (((state) = ANY ((ARRAY['DRAFT', 'PUBLISHED']))))`
- `CHECK ((version > 0))`
- `CHECK (((content_sha256 IS NULL) OR (content_sha256 ~ '^[0-9a-f]{64}$')))`
- `CHECK (((((state) = 'DRAFT') AND (published_by IS NULL) AND (published_at IS NULL) AND (content_sha256 IS NULL)) OR (((state) = 'PUBLISHED') AND (published_by IS NOT NULL) AND (published_at IS NOT NULL) AND (content_sha256 IS NOT NULL))))`
- `CHECK (((published_at IS NULL) OR (published_at >= created_at)))`

*(Ghi chú Schema v2: hai cột trùng `risk_weight` và `approval_level` trên `config_release`, `request` và `workflow_instance` đã được lưu giá trị lịch sử vào `eas_archive.dropped_column_value` và loại bỏ ở Migration 15; nguồn duy nhất là `eas.request_type`, bản chụp khi gửi đơn là `eas.request_revision`.)*

### 2.11.3. `eas.request_group`

Danh mục 12 nhóm yêu cầu lớn hiển thị cho người gửi theo bản chất nhu cầu (Migration 17). Số dòng live: 12 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `code` | character varying(20) | ✔ | PK |  | Mã nhóm (`ABSENCE`, `WORKTIME`, `BORROW`, `PROVISION`, `PAYMENT`, `PROCUREMENT`, `PEOPLE`, `SUPPORT`, `WORK`, `LEGAL`, `SALES`, `ASSET`) |
| `name` | character varying(80) | ✔ |  |  | Tên nhóm hiển thị |
| `description` | character varying(300) | ✔ |  |  | Mô tả điểm chung của nhóm |
| `sort_order` | smallint | ✔ |  |  | Thứ tự hiển thị trên màn hình chọn nhóm |

### 2.11.4. `eas.request_menu_item`

Danh mục 61 mục chọn loại yêu cầu nhỏ trên menu người gửi (56 loại trực tiếp + 5 mục đặt sẵn `preset` cho Đi muộn, Về sớm, Quên chấm công, Nghỉ phép có lương `CO_LUONG`, Nghỉ không lương `KHONG_LUONG` — Migration 17). Số dòng live: 61 · Trigger: 0 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `code` | character varying(40) | ✔ | PK |  | Mã mục menu duy nhất (vd `PAID_LEAVE`, `UNPAID_LEAVE`, `LATE_IN`, `EARLY_OUT`, `MISSED_CHECK_IN` hoặc mã `type_code`) |
| `group_code` | character varying(20) | ✔ | FK→request_group |  | Nhóm lớn chứa mục menu |
| `type_code` | character varying(30) | ✔ | FK→request_type |  | Loại yêu cầu nghiệp vụ tương ứng |
| `label` | character varying(120) | ✔ |  |  | Nhãn hiển thị cho người dùng |
| `preset` | jsonb | ✔ |  | `'{}'::jsonb` | Các trường điền sẵn và khoá trên giao diện (vd `{"leave_kind":"CO_LUONG"}`) |
| `sort_order` | smallint | ✔ |  |  | Thứ tự hiển thị trong nhóm |
| `is_active` | boolean | ✔ |  | `true` | Đang hiển thị trên menu hay không |

## Bảng 2.12. Miền hồ sơ và quy trình phê duyệt

### 2.12.1. `eas.request`

Hồ sơ yêu cầu (bản ghi gốc, trạng thái hiện hành). Số dòng live: 37 · Trigger: 2 · Chỉ mục: 8

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | FK2→request_revision, PK | `gen_random_uuid()` | Khoá chính |
| `code` | character varying(40) | ✔ | UK | `next_request_code()` | Mã nghiệp vụ duy nhất |
| `requester_id` | uuid | ✔ | FK→app_user |  | Người yêu cầu |
| `type_id` | uuid | ✔ | FK2→config_release, FK→request_type |  | Loại yêu cầu |
| `status` | character varying(32) | ✔ |  | `'DRAFT'::character varying` | Trạng thái |
| `draft_payload` | jsonb | ✔ |  | `'{}'::jsonb` | Dữ liệu nháp |
| `draft_amount_vnd` | bigint |  |  |  | Số tiền nháp (VND) |
| `draft_release_id` | uuid |  | FK2→config_release |  | Phiên bản quy chế dùng khi soạn nháp |
| `origin_request_id` | uuid |  | FK→request |  | Hồ sơ gốc (khi tạo từ hồ sơ khác) |
| `current_revision_id` | uuid |  | FK2→request_revision |  | Phiên bản đã gửi hiện hành |
| `lock_version` | bigint | ✔ |  | `0` | Khoá lạc quan; mỗi lệnh ghi tăng đúng 1 |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `updated_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm cập nhật gần nhất |
| `approved_at` | timestamp with time zone |  |  |  | Thời điểm duyệt cuối |
| `completed_at` | timestamp with time zone |  |  |  | Thời điểm hoàn tất |

Ràng buộc CHECK:
- `CHECK ((((status) <> ALL ((ARRAY['READY_FOR_EXECUTION', 'IN_PROGRESS', 'WAITING_FOR_ACCEPTANCE', 'COMPLETED']))) OR (approved_at IS NOT NULL)))`
- `CHECK (((approved_at IS NULL) OR (approved_at >= created_at)))`
- `CHECK ((((status) = 'COMPLETED') = (completed_at IS NOT NULL)))`
- `CHECK (((completed_at IS NULL) OR ((approved_at IS NOT NULL) AND (completed_at >= approved_at))))`
- `CHECK (((draft_amount_vnd >= 1) AND (draft_amount_vnd <= '1000000000000')))`
- `CHECK ((jsonb_typeof(draft_payload) = 'object'))`
- `CHECK ((lock_version >= 0))`
- `CHECK (((origin_request_id IS NULL) OR (origin_request_id <> id)))`
- `CHECK (((status) = ANY ((ARRAY['DRAFT', 'NEEDS_INFO', 'PENDING_APPROVAL', 'READY_FOR_EXECUTION', 'IN_PROGRESS', 'WAITING_FOR_ACCEPTANCE', 'COMPLETED', 'REJECTED', 'CANCELLED']))))`
- `CHECK ((updated_at >= created_at))`

### 2.12.2. `eas.request_revision`

Mỗi lần gửi / gửi lại; bất biến. Số dòng live: 30 · Trigger: 3 · Chỉ mục: 6 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK, UK(id,request_id) | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request, UK(id,request_id), UK(request_id,revision_no) |  | Hồ sơ yêu cầu liên quan |
| `revision_no` | integer | ✔ | UK(request_id,revision_no) |  | Số thứ tự lần gửi |
| `release_id` | uuid | ✔ | FK→config_release |  | Phiên bản quy chế áp dụng (bản chụp) |
| `department_id` | uuid | ✔ | FK→department |  | Phòng ban |
| `payload` | jsonb | ✔ |  |  | Nội dung JSON |
| `amount_vnd` | bigint |  |  |  | Số tiền (VND) |
| `submitted_by` | uuid | ✔ | FK→app_user |  | Người gửi |
| `submitted_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm gửi |
| `payload_sha256` | character(64) | ✔ |  |  | Mã băm nội dung lần gửi |
| `risk_weight` | smallint | ✔ |  | `3` | Trọng số rủi ro 1–5 |
| `approval_level` | smallint | ✔ |  | `1` | Số cấp duyệt 1–5 |

Ràng buộc CHECK:
- `CHECK (((amount_vnd >= 1) AND (amount_vnd <= '1000000000000')))`
- `CHECK (((approval_level >= 1) AND (approval_level <= 5)))`
- `CHECK ((jsonb_typeof(payload) = 'object'))`
- `CHECK ((payload_sha256 ~ '^[0-9a-f]{64}$'))`
- `CHECK ((revision_no > 0))`
- `CHECK (((risk_weight >= 1) AND (risk_weight <= 5)))`

### 2.12.3. `eas.workflow_instance`

Phiên quy trình ứng với một lần gửi. Số dòng live: 30 · Trigger: 2 · Chỉ mục: 7

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK, UK(id,request_id) | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK2→request_revision, FK→request, UK(id,request_id) |  | Hồ sơ yêu cầu liên quan |
| `revision_id` | uuid | ✔ | FK2→request_revision, UK |  | Phiên bản hồ sơ |
| `matched_rule_id` | character varying(50) | ✔ |  |  | Luật định tuyến được chọn |
| `resolved_route` | jsonb | ✔ |  |  | Tuyến duyệt đã phân giải |
| `lifecycle` | character(1) | ✔ | FK→lifecycle |  | Mẫu vòng đời A/B/C |
| `state` | character varying(10) | ✔ |  | `'ACTIVE'::character varying` | Trạng thái |
| `planned_executor_id` | uuid |  | FK→app_user |  | Người thực hiện dự kiến |
| `acceptor_id` | uuid |  | FK→app_user |  | Người nghiệm thu |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `closed_at` | timestamp with time zone |  |  |  | Thời điểm đóng |

Ràng buộc CHECK:
- `CHECK (((((state) = 'ACTIVE') AND (closed_at IS NULL)) OR (((state) <> 'ACTIVE') AND (closed_at IS NOT NULL) AND (closed_at >= created_at))))`
- `CHECK ((((lifecycle = 'A'::bpchar) AND (planned_executor_id IS NULL) AND (acceptor_id IS NULL)) OR ((lifecycle = 'B'::bpchar) AND (planned_executor_id IS NOT NULL) AND (acceptor_id IS NULL)) OR ((lifecycle = 'C'::bpchar) AND (planned_executor_id IS NOT NULL…`
- `CHECK ((lifecycle = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar])))`
- `CHECK ((length(btrim((matched_rule_id))) > 0))`
- `CHECK (((jsonb_typeof(resolved_route) = 'array') AND (jsonb_array_length(resolved_route) >= 1) AND (jsonb_array_length(resolved_route) <= 5)))`
- `CHECK (((state) = ANY ((ARRAY['ACTIVE', 'COMPLETED', 'REJECTED', 'SUPERSEDED', 'CANCELLED']))))`

### 2.12.4. `eas.request_participant`

Những người được quyền xem hồ sơ theo vai trò tham gia. Số dòng live: 85 · Trigger: 3 · Chỉ mục: 3

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request, UK(request_id,user_id) |  | Hồ sơ yêu cầu liên quan |
| `user_id` | uuid | ✔ | FK→app_user, UK(request_id,user_id) |  | Người dùng |
| `first_joined_at` | timestamp with time zone | ✔ |  | `now()` | Lần đầu tham gia hồ sơ |
| `joined_as` | character varying(24) | ✔ |  |  | Vai trò tham gia |
| `read_revoked_at` | timestamp with time zone |  |  |  | Thời điểm thu hồi quyền đọc |
| `read_revoked_reason` | character varying(2000) |  |  |  | Lý do thu hồi quyền đọc |

Ràng buộc CHECK:
- `CHECK ((((read_revoked_at IS NULL) AND (read_revoked_reason IS NULL)) OR ((read_revoked_at IS NOT NULL) AND (read_revoked_reason IS NOT NULL) AND ((length(btrim((read_revoked_reason))) >= 10) AND (length(btrim((read_revoked_reason))) <= 2000)))))`
- `CHECK (((joined_as) = ANY ((ARRAY['REQUESTER', 'APPROVER', 'EXECUTOR', 'ACCEPTOR']))))`

### 2.12.5. `eas.approval_step`

Các bước duyệt của một phiên quy trình. Số dòng live: 43 · Trigger: 2 · Chỉ mục: 7

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK, UK(id,request_id) | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request, FK2→workflow_instance, UK(id,request_id) |  | Hồ sơ yêu cầu liên quan |
| `instance_id` | uuid | ✔ | FK2→workflow_instance, UK(instance_id,assignee_id), UK(instance_id,step_no) |  | Phiên quy trình |
| `step_no` | smallint | ✔ | UK(instance_id,step_no) |  | Thứ tự bước |
| `assignee_id` | uuid | ✔ | FK→app_user, UK(instance_id,assignee_id) |  | Người được giao |
| `state` | character varying(10) | ✔ |  | `'WAITING'::character varying` | Trạng thái |
| `activated_at` | timestamp with time zone |  |  |  | Thời điểm kích hoạt |
| `closed_at` | timestamp with time zone |  |  |  | Thời điểm đóng |
| `tier_level` | smallint | ✔ |  | `1` | Cấp duyệt trong tuyến |
| `resolver_code` | character varying(40) |  |  |  | Vị trí người duyệt đã phân giải (vd DIRECT_MANAGER) |

Ràng buộc CHECK:
- `CHECK (((state) = ANY ((ARRAY['WAITING', 'ACTIVE', 'APPROVED', 'REJECTED', 'NEEDS_INFO', 'SKIPPED']))))`
- `CHECK (((step_no >= 1) AND (step_no <= 5)))`
- `CHECK (((tier_level >= 1) AND (tier_level <= 5)))`
- `CHECK (((((state) = 'WAITING') AND (activated_at IS NULL) AND (closed_at IS NULL)) OR (((state) = 'ACTIVE') AND (activated_at IS NOT NULL) AND (closed_at IS NULL)) OR (((state) = ANY ((ARRAY['APPROVED', 'REJECTED', 'NEEDS_INFO']))) AND (activated_at IS NOT …`
- `CHECK (((closed_at IS NULL) OR (activated_at IS NULL) OR (closed_at >= activated_at)))`

### 2.12.6. `eas.approval_decision`

Quyết định duyệt; bất biến. Số dòng live: 35 · Trigger: 2 · Chỉ mục: 4 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request, FK2→approval_step |  | Hồ sơ yêu cầu liên quan |
| `step_id` | uuid | ✔ | FK2→approval_step, UK |  | Bước duyệt |
| `actor_id` | uuid | ✔ | FK→app_user |  | Người thực hiện thao tác |
| `outcome` | character varying(10) | ✔ |  |  | Kết quả quyết định |
| `reason` | character varying(2000) |  |  |  | Lý do (bắt buộc với thao tác nhạy cảm) |
| `decided_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm quyết định |

Ràng buộc CHECK:
- `CHECK (((outcome) = ANY ((ARRAY['APPROVE', 'REJECT', 'NEEDS_INFO']))))`
- `CHECK ((((outcome) = 'APPROVE') OR ((reason IS NOT NULL) AND ((length(btrim((reason))) >= 10) AND (length(btrim((reason))) <= 2000)))))`

## Bảng 2.13. Miền thực hiện, nghiệm thu và tệp đính kèm

### 2.13.1. `eas.execution_attempt`

Lượt thực hiện (mẫu B/C). Số dòng live: 14 · Trigger: 3 · Chỉ mục: 6

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK, UK(id,request_id) | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK2→workflow_instance, FK→request, UK(id,request_id) |  | Hồ sơ yêu cầu liên quan |
| `instance_id` | uuid | ✔ | FK2→workflow_instance, UK(instance_id,attempt_no) |  | Phiên quy trình |
| `attempt_no` | integer | ✔ | UK(instance_id,attempt_no) |  | Thứ tự lượt thực hiện |
| `executor_id` | uuid | ✔ | FK→app_user |  | Người thực hiện |
| `state` | character varying(9) | ✔ |  | `'READY'::character varying` | Trạng thái |
| `closure_kind` | character varying(10) |  |  |  | Kiểu kết thúc lượt |
| `result_note` | character varying(4000) |  |  |  | Ghi chú kết quả (10–4000 ký tự) |
| `external_reference` | character varying(200) |  |  |  | Mã tham chiếu bên ngoài |
| `started_at` | timestamp with time zone |  |  |  | Thời điểm bắt đầu |
| `submitted_at` | timestamp with time zone |  |  |  | Thời điểm gửi |
| `closed_at` | timestamp with time zone |  |  |  | Thời điểm đóng |

Ràng buộc CHECK:
- `CHECK (((((state) = 'FINISHED') AND (closure_kind IS NOT NULL) AND (closed_at IS NOT NULL)) OR (((state) <> 'FINISHED') AND (closure_kind IS NULL) AND (closed_at IS NULL))))`
- `CHECK ((((state) <> 'FINISHED') OR (((closure_kind) = 'REASSIGNED') AND (submitted_at IS NULL)) OR (((closure_kind) = ANY ((ARRAY['SUCCESS', 'ACCEPTED', 'REWORK']))) AND (submitted_at IS NOT NULL))))`
- `CHECK (((((state) = 'READY') AND (started_at IS NULL) AND (submitted_at IS NULL)) OR (((state) = 'RUNNING') AND (started_at IS NOT NULL) AND (submitted_at IS NULL)) OR (((state) = 'SUBMITTED') AND (started_at IS NOT NULL) AND (submitted_at IS NOT NULL)) OR …`
- `CHECK ((((submitted_at IS NULL) AND (result_note IS NULL) AND (external_reference IS NULL)) OR ((submitted_at IS NOT NULL) AND (result_note IS NOT NULL) AND ((length(btrim((result_note))) >= 10) AND (length(btrim((result_note))) <= 4000)) AND (external_refe…`
- `CHECK ((((submitted_at IS NULL) OR (submitted_at >= started_at)) AND ((closed_at IS NULL) OR (closed_at >= started_at)) AND ((closed_at IS NULL) OR (submitted_at IS NULL) OR (closed_at >= submitted_at))))`
- `CHECK ((attempt_no > 0))`
- `CHECK (((closure_kind) = ANY ((ARRAY['SUCCESS', 'ACCEPTED', 'REWORK', 'REASSIGNED']))))`
- `CHECK (((state) = ANY ((ARRAY['READY', 'RUNNING', 'SUBMITTED', 'FINISHED']))))`

### 2.13.2. `eas.execution_issue`

Báo cáo không thể nhận / vướng; bất biến. Số dòng live: 0 · Trigger: 1 · Chỉ mục: 4 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request, FK2→execution_attempt |  | Hồ sơ yêu cầu liên quan |
| `attempt_id` | uuid | ✔ | FK2→execution_attempt |  | Lượt thực hiện |
| `actor_id` | uuid | ✔ | FK→app_user |  | Người thực hiện thao tác |
| `kind` | character varying(15) | ✔ |  |  | Phân loại |
| `reason` | character varying(2000) | ✔ |  |  | Lý do (bắt buộc với thao tác nhạy cảm) |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK (((kind) = ANY ((ARRAY['UNABLE_TO_CLAIM', 'BLOCKED']))))`
- `CHECK (((length(btrim((reason))) >= 10) AND (length(btrim((reason))) <= 2000)))`

### 2.13.3. `eas.acceptance_decision`

Quyết định nghiệm thu; bất biến. Số dòng live: 4 · Trigger: 2 · Chỉ mục: 4 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK2→execution_attempt, FK→request |  | Hồ sơ yêu cầu liên quan |
| `attempt_id` | uuid | ✔ | FK2→execution_attempt, UK |  | Lượt thực hiện |
| `actor_id` | uuid | ✔ | FK→app_user |  | Người thực hiện thao tác |
| `outcome` | character varying(6) | ✔ |  |  | Kết quả quyết định |
| `reason` | character varying(2000) |  |  |  | Lý do (bắt buộc với thao tác nhạy cảm) |
| `decided_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm quyết định |

Ràng buộc CHECK:
- `CHECK (((outcome) = ANY ((ARRAY['ACCEPT', 'REWORK']))))`
- `CHECK ((((outcome) = 'ACCEPT') OR ((reason IS NOT NULL) AND ((length(btrim((reason))) >= 10) AND (length(btrim((reason))) <= 2000)))))`

### 2.13.4. `eas.attachment`

Siêu dữ liệu tệp đã quét sạch. Số dòng live: 4 · Trigger: 2 · Chỉ mục: 6

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK, UK(id,request_id) | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request, UK(id,request_id) |  | Hồ sơ yêu cầu liên quan |
| `uploader_id` | uuid | ✔ | FK→app_user |  | Người tải lên |
| `storage_key` | character varying(300) | ✔ | UK |  | Khoá đối tượng trong Storage (UUID) |
| `object_version` | character varying(200) | ✔ |  |  | Phiên bản đối tượng lưu trữ |
| `original_name` | character varying(150) | ✔ |  |  | Tên tệp gốc |
| `mime` | character varying(80) | ✔ |  |  | Kiểu nội dung đã xác minh |
| `size_bytes` | bigint | ✔ |  |  | Kích thước (byte, ≤ 10 MB) |
| `sha256` | character(64) | ✔ |  |  | Mã băm SHA-256 của tệp |
| `scan_state` | character varying(8) | ✔ |  | `'QUEUED'::character varying` | Kết quả quét mã độc |
| `scan_attempts` | integer | ✔ |  | `0` | Số lần quét |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `scanned_at` | timestamp with time zone |  |  |  | Thời điểm quét |
| `deleted_at` | timestamp with time zone |  |  |  | Thời điểm xoá mềm |

Ràng buộc CHECK:
- `CHECK (((mime) = ANY ((ARRAY['application/pdf', 'image/jpeg', 'image/png']))))`
- `CHECK ((length((object_version)) > 0))`
- `CHECK (((length(btrim((original_name))) > 0) AND (POSITION(('/') IN (original_name)) = 0) AND (POSITION((chr(92)) IN (original_name)) = 0) AND (POSITION(('..') IN (original_name)) = 0)))`
- `CHECK (((scan_attempts >= 0) AND (scan_attempts <= 3)))`
- `CHECK (((scan_state) = ANY ((ARRAY['QUEUED', 'CLEAN', 'INFECTED', 'ERROR']))))`
- `CHECK ((((scan_state) = 'QUEUED') OR ((scanned_at IS NOT NULL) AND (scan_attempts >= 1))))`
- `CHECK ((sha256 ~ '^[0-9a-f]{64}$'))`
- `CHECK (((size_bytes >= 1) AND (size_bytes <= 10485760)))`
- `CHECK ((length((storage_key)) > 0))`
- `CHECK ((((scanned_at IS NULL) OR (scanned_at >= created_at)) AND ((deleted_at IS NULL) OR (deleted_at >= created_at))))`

### 2.13.5. `eas.draft_attachment`

Liên kết tệp với bản nháp. Số dòng live: 1 · Trigger: 1 · Chỉ mục: 3

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `request_id` | uuid | ✔ | FK→request, FK2→attachment, PK |  | Hồ sơ yêu cầu liên quan |
| `attachment_id` | uuid | ✔ | FK2→attachment, PK |  | Tệp đính kèm |
| `added_by` | uuid | ✔ | FK→app_user |  | Người gắn tệp |
| `added_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm gắn |

### 2.13.6. `eas.revision_attachment`

Liên kết tệp với lần gửi; bất biến. Số dòng live: 3 · Trigger: 2 · Chỉ mục: 3 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `revision_id` | uuid | ✔ | FK2→request_revision, PK |  | Phiên bản hồ sơ |
| `attachment_id` | uuid | ✔ | FK2→attachment, PK |  | Tệp đính kèm |
| `request_id` | uuid | ✔ | FK→request, FK2→attachment, FK2→request_revision |  | Hồ sơ yêu cầu liên quan |

### 2.13.7. `eas.execution_attachment`

Tệp bằng chứng của lượt thực hiện; bất biến. Số dòng live: 0 · Trigger: 2 · Chỉ mục: 3 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `attempt_id` | uuid | ✔ | FK2→execution_attempt, PK |  | Lượt thực hiện |
| `attachment_id` | uuid | ✔ | FK2→attachment, PK |  | Tệp đính kèm |
| `request_id` | uuid | ✔ | FK→request, FK2→attachment, FK2→execution_attempt |  | Hồ sơ yêu cầu liên quan |

## Bảng 2.14. Miền SLA, sự kiện và thông báo

### 2.14.1. `eas.sla_stage`

Chặng theo dõi thời hạn. Số dòng live: 44 · Trigger: 2 · Chỉ mục: 7

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK, UK(id,request_id) | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK2→execution_attempt, FK→request, FK2→approval_step, UK(id,request_id) |  | Hồ sơ yêu cầu liên quan |
| `kind` | character varying(10) | ✔ |  |  | Phân loại |
| `approval_step_id` | uuid |  | FK2→approval_step |  | Bước duyệt của chặng |
| `attempt_id` | uuid |  | FK2→execution_attempt |  | Lượt thực hiện |
| `started_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm bắt đầu |
| `due_at` | timestamp with time zone | ✔ |  |  | Hạn |
| `closed_at` | timestamp with time zone |  |  |  | Thời điểm đóng |
| `breached_at` | timestamp with time zone |  |  |  | Thời điểm vi phạm |

Ràng buộc CHECK:
- `CHECK (((breached_at IS NULL) OR (breached_at = due_at)))`
- `CHECK (((kind) = ANY ((ARRAY['APPROVAL', 'EXECUTION', 'ACCEPTANCE']))))`
- `CHECK (((((kind) = 'APPROVAL') AND (approval_step_id IS NOT NULL) AND (attempt_id IS NULL)) OR (((kind) = ANY ((ARRAY['EXECUTION', 'ACCEPTANCE']))) AND (approval_step_id IS NULL) AND (attempt_id IS NOT NULL))))`
- `CHECK (((due_at > started_at) AND ((closed_at IS NULL) OR (closed_at >= started_at))))`

### 2.14.2. `eas.sla_alert`

Cảnh báo nhắc / vi phạm; tối đa một mỗi loại cho mỗi chặng; bất biến. Số dòng live: 13 · Trigger: 1 · Chỉ mục: 3 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK2→sla_stage, FK→request |  | Hồ sơ yêu cầu liên quan |
| `stage_id` | uuid | ✔ | FK2→sla_stage, UK(stage_id,kind) |  | Chặng SLA |
| `kind` | character varying(8) | ✔ | UK(stage_id,kind) |  | Phân loại |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK (((kind) = ANY ((ARRAY['REMINDER', 'BREACH']))))`

### 2.14.3. `eas.outbox_event`

Hàng đợi sự kiện giao dịch (transactional outbox). Số dòng live: 43 · Trigger: 2 · Chỉ mục: 4

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid |  | FK→request |  | Hồ sơ yêu cầu liên quan |
| `event_type` | character varying(80) | ✔ |  |  | Loại sự kiện |
| `payload` | jsonb | ✔ |  |  | Nội dung JSON |
| `state` | character varying(10) | ✔ |  | `'PENDING'::character varying` | Trạng thái |
| `dedupe_key` | character varying(200) | ✔ | UK |  | Khoá chống trùng |
| `attempts` | integer | ✔ |  | `0` | Số lần đã thử |
| `replay_count` | integer | ✔ |  | `0` | Số lần gửi lại thủ công |
| `available_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm được phép xử lý |
| `lease_token` | uuid |  |  |  | Mã thuê của worker |
| `lease_until` | timestamp with time zone |  |  |  | Hết hạn thuê |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `sent_at` | timestamp with time zone |  |  |  | Thời điểm gửi xong |
| `last_error_code` | character varying(80) |  |  |  | Mã lỗi gần nhất |

Ràng buộc CHECK:
- `CHECK ((((state) <> 'DEAD') OR (attempts = 4)))`
- `CHECK (((attempts >= 0) AND (attempts <= 4)))`
- `CHECK ((length((dedupe_key)) > 0))`
- `CHECK ((length(btrim((event_type))) > 0))`
- `CHECK ((jsonb_typeof(payload) = 'object'))`
- `CHECK ((replay_count >= 0))`
- `CHECK (((state) = ANY ((ARRAY['PENDING', 'PROCESSING', 'SENT', 'DEAD']))))`
- `CHECK (((((state) = 'PROCESSING') AND (lease_token IS NOT NULL) AND (lease_until IS NOT NULL) AND (attempts >= 1)) OR (((state) <> 'PROCESSING') AND (lease_token IS NULL) AND (lease_until IS NULL))))`
- `CHECK ((((state) = 'SENT') = (sent_at IS NOT NULL)))`
- `CHECK (((sent_at IS NULL) OR (sent_at >= created_at)))`

### 2.14.4. `eas.notification`

Thông báo trong ứng dụng. Số dòng live: 43 · Trigger: 2 · Chỉ mục: 4

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `event_id` | uuid | ✔ | FK→outbox_event, UK(event_id,recipient_id) |  | Sự kiện outbox nguồn |
| `recipient_id` | uuid | ✔ | FK→app_user, UK(event_id,recipient_id) |  | Người nhận |
| `request_id` | uuid |  | FK→request |  | Hồ sơ yêu cầu liên quan |
| `label` | character varying(150) | ✔ |  |  | Nội dung hiển thị |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `read_at` | timestamp with time zone |  |  |  | Thời điểm đã đọc |

Ràng buộc CHECK:
- `CHECK ((length(btrim((label))) > 0))`
- `CHECK (((read_at IS NULL) OR (read_at >= created_at)))`

### 2.14.5. `eas.idempotency_record`

Kết quả đã trả cho mỗi khoá chống lặp. Số dòng live: 6 · Trigger: 1 · Chỉ mục: 4

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `actor_id` | uuid | ✔ | FK→app_user, UK(actor_id,command_scope,key) |  | Người thực hiện thao tác |
| `command_scope` | character varying(200) | ✔ | UK(actor_id,command_scope,key) |  | Phạm vi lệnh (người + loại lệnh) |
| `key` | character varying(64) | ✔ | UK(actor_id,command_scope,key) |  | Khoá chống lặp |
| `request_hash` | character(64) | ✔ |  |  | Mã băm yêu cầu |
| `http_status` | smallint | ✔ |  |  | Mã HTTP đã trả |
| `response_body` | jsonb |  |  |  | Kết quả đã trả |
| `request_id` | uuid |  | FK→request |  | Hồ sơ yêu cầu liên quan |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `expires_at` | timestamp with time zone | ✔ |  | `(now() + '7 days'::interval)` | Hết hạn |
| `tombstone_until` | timestamp with time zone | ✔ |  | `(now() + '30 days'::interval)` | Giữ dấu xoá tới thời điểm |

Ràng buộc CHECK:
- `CHECK ((length((command_scope)) > 0))`
- `CHECK (((http_status >= 200) AND (http_status <= 299)))`
- `CHECK (((key) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'))`
- `CHECK ((request_hash ~ '^[0-9a-f]{64}$'))`
- `CHECK (((expires_at > created_at) AND (tombstone_until > expires_at)))`

## Bảng 2.15. Miền kiểm toán và quyền riêng tư

### 2.15.1. `eas.audit_head`

Đầu chuỗi băm theo phạm vi (REQ:{id} / ADMIN). Số dòng live: 36 · Trigger: 1 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `scope_key` | character varying(100) | ✔ | PK |  | Khoá phạm vi chuỗi (REQ:{id} / ADMIN) |
| `seq` | bigint | ✔ |  | `0` | Số thứ tự trong chuỗi |
| `last_hash` | character(64) | ✔ |  | `repeat('0'::text, 64)` | Mã băm cuối của chuỗi |

Ràng buộc CHECK:
- `CHECK ((last_hash ~ '^[0-9a-f]{64}$'))`
- `CHECK ((((scope_key) = 'ADMIN') OR ((scope_key) ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')))`
- `CHECK ((seq >= 0))`
- `CHECK (((seq <> 0) OR ((last_hash) = repeat('0', 64))))`

### 2.15.2. `eas.audit_event`

Sự kiện kiểm toán nghiệp vụ dạng chuỗi băm; bất biến. Số dòng live: 82 · Trigger: 2 · Chỉ mục: 3 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request, UK(request_id,seq) |  | Hồ sơ yêu cầu liên quan |
| `seq` | bigint | ✔ | UK(request_id,seq) |  | Số thứ tự trong chuỗi |
| `actor_id` | uuid |  | FK→app_user |  | Người thực hiện thao tác |
| `actor_kind` | character varying(6) | ✔ |  |  | HUMAN hoặc SYSTEM |
| `action` | character varying(80) | ✔ |  |  | Mã hành động |
| `target_type` | character varying(40) | ✔ |  |  | Loại đối tượng |
| `target_id` | uuid | ✔ |  |  | Mã đối tượng |
| `details` | jsonb | ✔ |  |  | Chi tiết JSON |
| `correlation_id` | uuid | ✔ |  |  | Mã tương quan với log |
| `occurred_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm xảy ra |
| `hash_version` | smallint | ✔ |  | `1` | Phiên bản thuật toán băm |
| `prev_hash` | character(64) | ✔ |  |  | Mã băm bản ghi trước |
| `hash` | character(64) | ✔ |  |  | Mã băm bản ghi |

Ràng buộc CHECK:
- `CHECK (((((actor_kind) = 'HUMAN') AND (actor_id IS NOT NULL)) OR (((actor_kind) = 'SYSTEM') AND (actor_id IS NULL))))`
- `CHECK ((length(btrim((action))) > 0))`
- `CHECK (((actor_kind) = ANY ((ARRAY['HUMAN', 'SYSTEM']))))`
- `CHECK ((jsonb_typeof(details) = 'object'))`
- `CHECK ((hash ~ '^[0-9a-f]{64}$'))`
- `CHECK ((hash_version = 1))`
- `CHECK ((prev_hash ~ '^[0-9a-f]{64}$'))`
- `CHECK ((seq > 0))`
- `CHECK ((length(btrim((target_type))) > 0))`

### 2.15.3. `eas.admin_event`

Sự kiện kiểm toán quản trị dạng chuỗi băm; bất biến. Số dòng live: 99 · Trigger: 2 · Chỉ mục: 5 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `seq` | bigint | ✔ | UK |  | Số thứ tự trong chuỗi |
| `actor_id` | uuid |  | FK→app_user |  | Người thực hiện thao tác |
| `actor_kind` | character varying(6) | ✔ |  |  | HUMAN hoặc SYSTEM |
| `action` | character varying(80) | ✔ |  |  | Mã hành động |
| `target_type` | character varying(40) | ✔ |  |  | Loại đối tượng |
| `target_id` | character varying(100) | ✔ |  |  | Mã đối tượng |
| `department_id` | uuid |  | FK→department |  | Phòng ban |
| `type_id` | uuid |  | FK→request_type |  | Loại yêu cầu |
| `details` | jsonb | ✔ |  |  | Chi tiết JSON |
| `reason` | text | ✔ |  |  | Lý do (bắt buộc với thao tác nhạy cảm) |
| `correlation_id` | uuid | ✔ |  |  | Mã tương quan với log |
| `occurred_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm xảy ra |
| `hash_version` | smallint | ✔ |  | `1` | Phiên bản thuật toán băm |
| `prev_hash` | character(64) | ✔ |  |  | Mã băm bản ghi trước |
| `hash` | character(64) | ✔ |  |  | Mã băm bản ghi |

Ràng buộc CHECK:
- `CHECK (((((actor_kind) = 'HUMAN') AND (actor_id IS NOT NULL)) OR (((actor_kind) = 'SYSTEM') AND (actor_id IS NULL))))`
- `CHECK ((length(btrim((action))) > 0))`
- `CHECK (((actor_kind) = ANY ((ARRAY['HUMAN', 'SYSTEM']))))`
- `CHECK ((jsonb_typeof(details) = 'object'))`
- `CHECK ((hash ~ '^[0-9a-f]{64}$'))`
- `CHECK ((hash_version = 1))`
- `CHECK ((prev_hash ~ '^[0-9a-f]{64}$'))`
- `CHECK (((length(btrim(reason)) >= 10) AND (length(btrim(reason)) <= 2000)))`
- `CHECK ((seq > 0))`
- `CHECK ((length(btrim((target_id))) > 0))`
- `CHECK ((length(btrim((target_type))) > 0))`

### 2.15.4. `eas.audit_checkpoint`

Mốc kiểm soát chuỗi băm (chức năng xuất là hướng phát triển). Số dòng live: 0 · Trigger: 2 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `scope_key` | character varying(100) | ✔ | UK(scope_key,seq) |  | Khoá phạm vi chuỗi (REQ:{id} / ADMIN) |
| `seq` | bigint | ✔ | UK(scope_key,seq) |  | Số thứ tự trong chuỗi |
| `hash` | character(64) | ✔ |  |  | Mã băm bản ghi |
| `external_object_key` | character varying(300) | ✔ |  |  | Khoá đối tượng ở kho ngoài |
| `external_version` | character varying(200) | ✔ |  |  | Phiên bản đối tượng ở kho ngoài |
| `captured_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm chốt |

Ràng buộc CHECK:
- `CHECK ((length((external_object_key)) > 0))`
- `CHECK ((length((external_version)) > 0))`
- `CHECK ((hash ~ '^[0-9a-f]{64}$'))`
- `CHECK ((((scope_key) = 'ADMIN') OR ((scope_key) ~ '^REQ:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')))`
- `CHECK ((seq >= 0))`

### 2.15.5. `eas.privacy_case`

Yêu cầu của chủ thể dữ liệu (truy cập, sửa, xoá, hạn chế, phản đối). Số dòng live: 1 · Trigger: 0 · Chỉ mục: 4

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `subject_user_id` | uuid | ✔ | FK→app_user |  | Chủ thể dữ liệu |
| `case_type` | character varying(8) | ✔ |  |  | Loại yêu cầu quyền riêng tư |
| `status` | character varying(8) | ✔ |  | `'OPEN'::character varying` | Trạng thái |
| `requested_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm yêu cầu |
| `due_at` | timestamp with time zone | ✔ |  |  | Hạn |
| `completed_at` | timestamp with time zone |  |  |  | Thời điểm hoàn tất |
| `policy_version` | character varying(50) | ✔ |  |  | Phiên bản chính sách áp dụng |
| `owner_id` | uuid | ✔ | FK→app_user |  | Người phụ trách |
| `decision_reference` | character varying(200) |  |  |  | Số quyết định phê duyệt |

Ràng buộc CHECK:
- `CHECK (((case_type) = ANY ((ARRAY['ACCESS', 'CORRECT', 'ERASE', 'RESTRICT', 'OBJECT']))))`
- `CHECK ((length(btrim((policy_version))) > 0))`
- `CHECK (((status) = ANY ((ARRAY['OPEN', 'REVIEW', 'APPROVED', 'REJECTED', 'DONE']))))`
- `CHECK (((completed_at IS NULL) OR (completed_at >= requested_at)))`
- `CHECK ((((status) <> ALL ((ARRAY['APPROVED', 'REJECTED', 'DONE']))) OR ((decision_reference IS NOT NULL) AND (length(btrim((decision_reference))) > 0))))`
- `CHECK ((((status) = 'DONE') = (completed_at IS NOT NULL)))`
- `CHECK ((due_at > requested_at))`

### 2.15.6. `eas.retention_hold`

Lệnh giữ pháp lý trên hồ sơ; chặn xoá. Số dòng live: 1 · Trigger: 2 · Chỉ mục: 5

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `request_id` | uuid | ✔ | FK→request |  | Hồ sơ yêu cầu liên quan |
| `reason` | character varying(2000) | ✔ |  |  | Lý do (bắt buộc với thao tác nhạy cảm) |
| `authority_reference` | character varying(200) | ✔ |  |  | Căn cứ / cơ quan yêu cầu giữ |
| `set_by` | uuid | ✔ | FK→app_user |  | Người đặt lệnh giữ |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `released_at` | timestamp with time zone |  |  |  | Thời điểm giải toả |
| `released_by` | uuid |  | FK→app_user |  | Người giải toả |

Ràng buộc CHECK:
- `CHECK ((((released_at IS NULL) AND (released_by IS NULL)) OR ((released_at IS NOT NULL) AND (released_by IS NOT NULL) AND (released_at >= created_at))))`
- `CHECK ((length(btrim((authority_reference))) > 0))`
- `CHECK (((length(btrim((reason))) >= 10) AND (length(btrim((reason))) <= 2000)))`

## Bảng 2.16. Miền quản trị, AI và vận hành (bảng mở rộng)

### 2.16.1. `eas.admin_account`

Tài khoản quản trị tách riêng (chỉ admin@eas.com). Số dòng live: 1 · Trigger: 0 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `user_id` | uuid | ✔ | FK→app_user, PK |  | Người dùng |
| `employee_user_id` | uuid |  | FK→app_user, UK |  | Tài khoản nghiệp vụ tương ứng (nếu có) |
| `created_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK (((employee_user_id IS NULL) OR (employee_user_id <> user_id)))`

### 2.16.2. `eas.ai_learning_job`

Phiên học quy định (có cơ chế thuê). Số dòng live: 2 · Trigger: 0 · Chỉ mục: 3

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `target_version` | character varying(20) | ✔ |  |  | Phiên bản đích |
| `base_version` | character varying(20) |  |  |  | Phiên bản gốc |
| `reason` | text | ✔ |  | `''::text` | Lý do (bắt buộc với thao tác nhạy cảm) |
| `status` | character varying(16) | ✔ |  | `'QUEUED'::character varying` | Trạng thái |
| `step` | smallint | ✔ |  | `0` | Bước hiện tại |
| `step_label` | text | ✔ |  | `'Đang chờ xử lý'::text` | Nhãn bước |
| `progress` | smallint | ✔ |  | `0` | Tiến độ (%) |
| `attempts` | smallint | ✔ |  | `0` | Số lần đã thử |
| `max_attempts` | smallint | ✔ |  | `3` | Số lần thử tối đa |
| `rerun_requested` | boolean | ✔ |  | `false` | Có yêu cầu chạy lại |
| `not_before` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Không chạy trước thời điểm |
| `lease_owner` | text |  |  |  | Tiến trình giữ quyền thuê |
| `lease_until` | timestamp with time zone |  |  |  | Hết hạn thuê |
| `requested_by` | uuid |  | FK→app_user |  | Người yêu cầu |
| `snapshot` | jsonb |  |  |  | Ảnh chụp đầu vào |
| `compiled_policy` | jsonb |  |  |  | Bộ luật đã biên dịch |
| `diff` | jsonb |  |  |  | Khác biệt so với bản trước |
| `error` | text |  |  |  | Lỗi |
| `created_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm tạo |
| `started_at` | timestamp with time zone |  |  |  | Thời điểm bắt đầu |
| `finished_at` | timestamp with time zone |  |  |  | Thời điểm kết thúc |
| `updated_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm cập nhật gần nhất |

Ràng buộc CHECK:
- `CHECK (((max_attempts >= 1) AND (max_attempts <= 10)))`
- `CHECK (((progress >= 0) AND (progress <= 100)))`
- `CHECK (((status) = ANY ((ARRAY['QUEUED', 'RUNNING', 'APPLIED', 'FAILED']))))`
- `CHECK (((step >= 0) AND (step <= 4)))`

### 2.16.3. `eas.ai_policy_version`

Lịch sử phiên bản bộ luật AI. Số dòng live: 0 · Trigger: 0 · Chỉ mục: 4

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `version` | character varying(50) | ✔ | UK |  | Số phiên bản |
| `document` | jsonb | ✔ |  |  | Bộ luật (JSON) |
| `state` | character varying(8) | ✔ |  | `'INACTIVE'::character varying` | Trạng thái |
| `created_by` | uuid |  | FK→app_user |  | Người tạo |
| `created_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm tạo |
| `activated_by` | uuid |  | FK→app_user |  | Người kích hoạt |
| `activated_at` | timestamp with time zone |  |  |  | Thời điểm kích hoạt |

Ràng buộc CHECK:
- `CHECK ((((state) = 'INACTIVE') OR (activated_at IS NOT NULL)))`
- `CHECK ((jsonb_typeof((document -> 'rules')) = 'array'))`
- `CHECK (((state) = ANY ((ARRAY['ACTIVE', 'INACTIVE']))))`
- `CHECK ((length(btrim((version))) > 0))`

### 2.16.4. `eas.ai_system_state`

Trạng thái động cơ AI và khoá cổng nhân viên. Số dòng live: 1 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | integer | ✔ | PK | `1` | Khoá chính |
| `provider_name` | text | ✔ |  | `'Google Gemini + Scikit-Learn Hybrid'…` | Nhà cung cấp mô hình |
| `model_name` | text | ✔ |  | `'gemini-2.5-flash & nlp_risk_pipeline…` | Tên mô hình |
| `active_regulation_version` | text | ✔ |  | `'1.0'::text` | Phiên bản quy định đang áp dụng |
| `target_regulation_version` | text | ✔ |  | `'1.0'::text` | Phiên bản quy định đang học tới |
| `global_major_version` | integer | ✔ |  | `1` | Phiên bản chính của bộ quy định |
| `global_minor_version` | integer | ✔ |  | `0` | Phiên bản phụ của bộ quy định |
| `sync_status` | text | ✔ |  | `'COMPLETED'::text` | Trạng thái đồng bộ với dịch vụ AI |
| `current_step_index` | integer | ✔ |  | `4` | Chỉ số bước học hiện tại |
| `current_step_label` | text | ✔ |  | `'Đã học xong và áp dụng quy định mới'…` | Nhãn bước học hiện tại |
| `progress_percent` | integer | ✔ |  | `100` | Tiến độ học (%) |
| `client_maintenance_lock` | boolean | ✔ |  | `false` | Đang khoá cổng nhân viên |
| `maintenance_message` | text | ✔ |  | `'Hệ thống AI đang cập nhật quy định m…` | Thông điệp hiển thị khi khoá |
| `steps_detail` | jsonb | ✔ |  | `'[{"code": "SYNCING", "step": 1, "lab…` | Chi tiết các bước học |
| `updated_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm cập nhật gần nhất |
| `applied_policy` | jsonb |  |  |  | Bộ luật đang áp dụng |
| `applied_snapshot` | jsonb |  |  |  | Ảnh chụp quy định đã áp dụng |
| `applied_at` | timestamp with time zone |  |  |  | Thời điểm áp dụng |
| `applied_job_id` | uuid |  |  |  | Phiên học đã áp dụng |

Ràng buộc CHECK:
- `CHECK (((current_step_index >= 1) AND (current_step_index <= 4)))`
- `CHECK ((id = 1))`
- `CHECK (((progress_percent >= 0) AND (progress_percent <= 100)))`
- `CHECK ((sync_status = ANY (ARRAY['IDLE', 'SYNCING', 'LEARNING', 'APPLYING', 'COMPLETED', 'ERROR'])))`

### 2.16.5. `eas.announcement_receipt`

Đánh dấu đã đọc thông báo hệ thống. Số dòng live: 3 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `announcement_id` | uuid | ✔ | FK→system_announcement, PK |  | Thông báo |
| `user_id` | uuid | ✔ | FK→app_user, PK |  | Người dùng |
| `read_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm đã đọc |

### 2.16.6. `eas.approval_delegation`

Ủy quyền phê duyệt theo khoảng thời gian. Số dòng live: 0 · Trigger: 0 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `delegator_id` | uuid | ✔ | FK→app_user |  | Người ủy quyền |
| `delegate_id` | uuid | ✔ | FK→app_user |  | Người nhận ủy quyền |
| `starts_at` | timestamp with time zone | ✔ |  |  | Bắt đầu |
| `ends_at` | timestamp with time zone | ✔ |  |  | Kết thúc |
| `reason` | character varying(500) | ✔ |  |  | Lý do (bắt buộc với thao tác nhạy cảm) |
| `created_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm tạo |
| `revoked_at` | timestamp with time zone |  |  |  | Thời điểm thu hồi |
| `scope` | character varying(10) | ✔ |  | `'APPROVAL'::character varying` | Phạm vi uỷ quyền / bàn giao: `APPROVAL`, `EXECUTION`, `ACCEPTANCE`, `ALL` (Migration 15 gộp `work_handover`) |
| `source` | character varying(14) | ✔ |  | `'MANUAL'::character varying` | Nguồn tạo: `MANUAL` hoặc `LEAVE_REQUEST` |
| `source_request_id` | uuid |  | FK→request |  | Đơn nghỉ phép nguồn (bắt buộc khi `source = 'LEAVE_REQUEST'`) |
| `created_by` | uuid |  | FK→app_user |  | Người tạo bản ghi uỷ quyền / bàn giao |

Ràng buộc CHECK:
- `CHECK ((delegator_id <> delegate_id))`
- `CHECK (((ends_at > starts_at) AND (ends_at <= (starts_at + '90 days'::interval))))`
- `CHECK (((length(btrim((reason))) >= 5) AND (length(btrim((reason))) <= 500)))`
- `CHECK ((scope IN ('ALL', 'APPROVAL', 'EXECUTION', 'ACCEPTANCE')))`
- `CHECK ((source IN ('LEAVE_REQUEST', 'MANUAL') AND (source <> 'LEAVE_REQUEST' OR source_request_id IS NOT NULL)))`

### 2.16.7. `eas.company_regulations`

Văn bản quy định công ty. Số dòng live: 3 · Trigger: 2 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `code` | text | ✔ | UK |  | Mã nghiệp vụ duy nhất |
| `title` | text | ✔ |  |  | Tiêu đề |
| `category` | text | ✔ |  | `'Quy định chung'::text` | Nhóm nghiệp vụ |
| `content` | text | ✔ |  |  | Nội dung |
| `version_string` | text | ✔ |  | `'1.0'::text` | Phiên bản dạng chuỗi (vd 1.2) |
| `major_version` | integer | ✔ |  | `1` | Phiên bản chính |
| `minor_version` | integer | ✔ |  | `0` | Phiên bản phụ |
| `is_deleted` | boolean | ✔ |  | `false` | Đã xoá mềm |
| `updated_by` | text |  |  | `'Admin'::text` | Người cập nhật |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |
| `updated_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm cập nhật gần nhất |

### 2.16.8. `eas.lifecycle`

Bảng tham chiếu mẫu vòng đời A/B/C. Số dòng live: 3 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `code` | character(1) | ✔ | PK |  | Mã nghiệp vụ duy nhất |
| `name` | character varying(50) | ✔ |  |  | Tên hiển thị |
| `description` | character varying(500) | ✔ |  |  | Mô tả |
| `has_execution` | boolean | ✔ |  | `false` | Có bước thực hiện |
| `has_acceptance` | boolean | ✔ |  | `false` | Có bước nghiệm thu |

Ràng buộc CHECK:
- `CHECK ((code = ANY (ARRAY['A'::bpchar, 'B'::bpchar, 'C'::bpchar])))`
- `CHECK (((NOT has_acceptance) OR has_execution))`
- `CHECK ((length(btrim((description))) > 0))`
- `CHECK ((length(btrim((name))) > 0))`

### 2.16.9. `eas.mock_apis`

Danh mục tích hợp hệ thống mô phỏng và trạng thái bật/tắt. Số dòng live: 8 · Trigger: 1 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `api_code` | text | ✔ | UK |  | Mã tích hợp |
| `api_name` | text | ✔ |  |  | Tên tích hợp |
| `endpoint_path` | text | ✔ |  |  | Đường dẫn API mô phỏng |
| `http_method` | text | ✔ |  | `'GET'::text` | Phương thức HTTP |
| `source_system` | text | ✔ |  |  | Hệ thống nguồn |
| `domain_key` | text | ✔ |  |  | Miền nghiệp vụ |
| `data_provided` | text | ✔ |  |  | Dữ liệu cung cấp |
| `mock_payload` | jsonb | ✔ |  | `'{}'::jsonb` | Dữ liệu mẫu |
| `is_enabled` | boolean | ✔ |  | `true` | Đang bật (tắt thì khoá loại yêu cầu phụ thuộc) |
| `updated_by` | text |  |  | `'System Admin'::text` | Người cập nhật |
| `updated_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm cập nhật gần nhất |

### 2.16.10. `eas.modules`

Danh mục module màn hình. Số dòng live: 9 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `code` | text | ✔ | PK |  | Mã nghiệp vụ duy nhất |
| `name` | text | ✔ |  |  | Tên hiển thị |
| `group_name` | text | ✔ |  |  | Nhóm menu |
| `route_path` | text | ✔ |  |  | Đường dẫn giao diện |
| `icon_name` | text | ✔ |  | `'LayoutGrid'::text` | Biểu tượng |
| `sort_order` | integer | ✔ |  | `0` | Thứ tự hiển thị |
| `target_app` | text | ✔ |  | `'BOTH'::text` | Cổng áp dụng (nhân viên / quản trị) |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK ((target_app = ANY (ARRAY['ADMIN', 'CLIENT', 'BOTH'])))`

### 2.16.11. `eas.password_reset_request`

Yêu cầu đặt lại mật khẩu chờ quản trị duyệt. Số dòng live: 0 · Trigger: 0 · Chỉ mục: 3

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `user_id` | uuid | ✔ | FK→app_user |  | Người dùng |
| `requested_email` | character varying(254) | ✔ |  |  | Email yêu cầu |
| `status` | character varying(10) | ✔ |  | `'PENDING'::character varying` | Trạng thái |
| `requested_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm yêu cầu |
| `expires_at` | timestamp with time zone | ✔ |  |  | Hết hạn |
| `resolved_at` | timestamp with time zone |  |  |  | Thời điểm xử lý |
| `resolved_by` | uuid |  | FK→app_user |  | Người xử lý |
| `resolution_reason` | character varying(2000) |  |  |  | Lý do xử lý |

Ràng buộc CHECK:
- `CHECK ((expires_at > requested_at))`
- `CHECK (((((status) = 'PENDING') AND (resolved_at IS NULL) AND (resolved_by IS NULL)) OR (((status) <> 'PENDING') AND (resolved_at IS NOT NULL))))`
- `CHECK (((status) = ANY ((ARRAY['PENDING', 'APPROVED', 'EXPIRED']))))`

### 2.16.12. `eas.regulation_versions`

Lịch sử phiên bản văn bản quy định. Số dòng live: 3 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `regulation_id` | uuid |  | FK→company_regulations |  | Văn bản quy định |
| `version_string` | text | ✔ |  |  | Phiên bản dạng chuỗi (vd 1.2) |
| `major_version` | integer | ✔ |  |  | Phiên bản chính |
| `minor_version` | integer | ✔ |  |  | Phiên bản phụ |
| `action_type` | text | ✔ |  |  | Loại thay đổi (tạo / sửa / xoá) |
| `title` | text | ✔ |  |  | Tiêu đề |
| `content` | text | ✔ |  |  | Nội dung |
| `change_summary` | text |  |  |  | Tóm tắt thay đổi |
| `created_by` | text |  |  | `'Admin'::text` | Người tạo |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK ((action_type = ANY (ARRAY['CREATE', 'UPDATE_MINOR', 'DELETE_MAJOR'])))`

### 2.16.13. `eas.role`

Danh mục 7 vai trò. Số dòng live: 7 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `code` | character varying(24) | ✔ | PK |  | Mã nghiệp vụ duy nhất |
| `name` | character varying(100) | ✔ |  |  | Tên hiển thị |
| `description` | character varying(500) | ✔ |  |  | Mô tả |
| `is_system` | boolean | ✔ |  | `true` | Vai trò hệ thống (không xoá được) |

Ràng buộc CHECK:
- `CHECK ((((code) = upper(btrim((code)))) AND (length((code)) > 0)))`
- `CHECK ((length(btrim((description))) > 0))`
- `CHECK ((length(btrim((name))) > 0))`

### 2.16.14. `eas.role_module_permission`

Ma trận quyền vai trò × module. Số dòng live: 63 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `role_code` | character varying(24) | ✔ | FK→role, PK |  | Mã vai trò |
| `module_code` | text | ✔ | FK→modules, PK |  | Mã module màn hình |
| `can_view` | boolean | ✔ |  | `false` | Quyền xem |
| `can_create` | boolean | ✔ |  | `false` | Quyền thêm |
| `can_update` | boolean | ✔ |  | `false` | Quyền sửa |
| `can_delete` | boolean | ✔ |  | `false` | Quyền xoá |
| `updated_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm cập nhật gần nhất |

### 2.16.15. `eas.system_announcement`

Thông báo toàn hệ thống (tự sinh sau khi học quy định). Số dòng live: 2 · Trigger: 0 · Chỉ mục: 3

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `job_id` | uuid |  | FK→ai_learning_job, UK |  | Phiên học sinh ra thông báo |
| `kind` | character varying(32) | ✔ |  | `'REGULATION_UPDATE'::character varying` | Phân loại |
| `audience` | character varying(16) | ✔ |  | `'ALL'::character varying` | Đối tượng nhận |
| `version` | character varying(20) | ✔ |  |  | Số phiên bản |
| `title` | text | ✔ |  |  | Tiêu đề |
| `summary` | text | ✔ |  |  | Tóm tắt |
| `changes` | jsonb | ✔ |  | `'[]'::jsonb` | Danh sách thay đổi |
| `guidance` | jsonb | ✔ |  | `'[]'::jsonb` | Hướng dẫn thao tác mới |
| `created_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK (((audience) = ANY ((ARRAY['ALL', 'ADMIN']))))`

### 2.16.16. `eas.privacy_case_approval`

Duyệt kép xoá dữ liệu cá nhân theo NĐ 13/2023/NĐ-CP (Migration 14; thao tác `execute-erase` cần 2 quyết định `APPROVE` khác người, khác `owner_id`, cùng `manifest_sha256`). Số dòng live: 0 · Trigger: 1 · Chỉ mục: 2 · **AO**

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `case_id` | uuid | ✔ | FK→privacy_case, UK(case_id,approver_id) |  | Hồ sơ quyền riêng tư |
| `approver_id` | uuid | ✔ | FK→app_user, UK(case_id,approver_id) |  | Người duyệt xoá dữ liệu |
| `manifest_sha256` | character(64) | ✔ |  |  | Mã băm danh sách dữ liệu sẽ xoá |
| `decision` | character varying(8) | ✔ |  |  | Quyết định (`APPROVE` / `REJECT`) |
| `reason` | text | ✔ |  |  | Lý do quyết định (10–2000 ký tự) |
| `decided_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm ra quyết định |

Ràng buộc CHECK:
- `CHECK ((manifest_sha256 ~ '^[0-9a-f]{64}$'))`
- `CHECK ((decision IN ('APPROVE', 'REJECT')))`
- `CHECK ((length(btrim(reason)) BETWEEN 10 AND 2000))`

### 2.16.17. `eas.user_leave_and_trips`

Lịch nghỉ / công tác đồng bộ từ đơn nghỉ đã duyệt. Số dòng live: 3 · Trigger: 0 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `user_id` | uuid | ✔ | FK→app_user |  | Người dùng |
| `type` | text | ✔ |  |  | Loại (nghỉ / công tác) |
| `title` | text | ✔ |  |  | Tiêu đề |
| `start_time` | timestamp with time zone | ✔ |  |  | Bắt đầu |
| `end_time` | timestamp with time zone | ✔ |  |  | Kết thúc |
| `approval_status` | text | ✔ |  | `'APPROVED'::text` | Trạng thái duyệt |
| `approved_by` | text |  |  | `'Ban Giám Đốc'::text` | Người duyệt |
| `created_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK ((approval_status = ANY (ARRAY['PENDING', 'APPROVED', 'REJECTED'])))`
- `CHECK ((type = ANY (ARRAY['PAID_LEAVE', 'UNPAID_LEAVE', 'LATE_IN', 'EARLY_OUT', 'BUSINESS_TRIP'])))`

### 2.16.18. `eas.user_permissions`

Ghi đè quyền module theo từng người. Số dòng live: 0 · Trigger: 0 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `user_id` | uuid | ✔ | FK→app_user, UK(user_id,module_code) |  | Người dùng |
| `module_code` | text | ✔ | FK→modules, UK(user_id,module_code) |  | Mã module màn hình |
| `can_view` | boolean | ✔ |  | `false` | Quyền xem |
| `can_create` | boolean | ✔ |  | `false` | Quyền thêm |
| `can_update` | boolean | ✔ |  | `false` | Quyền sửa |
| `can_delete` | boolean | ✔ |  | `false` | Quyền xoá |
| `granted_by` | text |  |  | `'Admin'::text` | Người cấp |
| `updated_at` | timestamp with time zone | ✔ |  | `now()` | Thời điểm cập nhật gần nhất |

### 2.16.19. `eas.sla_escalation_policy`

Chính sách nhắc hạn và leo thang SLA theo giai đoạn (Migration 14; `type_id IS NULL` là mặc định toàn hệ thống). Số dòng live: 3 · Trigger: 0 · Chỉ mục: 2

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `id` | uuid | ✔ | PK | `gen_random_uuid()` | Khoá chính |
| `type_id` | uuid |  | FK→request_type |  | Loại yêu cầu (`NULL` = mặc định toàn hệ thống) |
| `stage_kind` | character varying(10) | ✔ |  |  | Giai đoạn (`APPROVAL`, `EXECUTION`, `ACCEPTANCE`) |
| `reminder_percent` | smallint | ✔ |  | `50` | Phần trăm thời hạn gửi nhắc nhở (10–95%) |
| `on_breach` | character varying(13) | ✔ |  | `'REMIND'::character varying` | Hành động khi quá hạn (`REMIND` / `AUTO_REASSIGN`) |
| `notify_manager` | boolean | ✔ |  | `true` | Có báo quản lý trực tiếp khi quá hạn hay không |
| `level2_percent` | smallint |  |  | `150` | Ngưỡng leo thang mức 2 báo OPS_ADMIN (101–500%) |
| `updated_by` | uuid |  | FK→app_user |  | Người cập nhật |
| `updated_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm cập nhật gần nhất |

Ràng buộc CHECK:
- `CHECK ((stage_kind IN ('APPROVAL', 'EXECUTION', 'ACCEPTANCE')))`
- `CHECK ((reminder_percent BETWEEN 10 AND 95))`
- `CHECK ((on_breach IN ('REMIND', 'AUTO_REASSIGN')))`
- `CHECK ((level2_percent IS NULL OR level2_percent BETWEEN 101 AND 500))`

### 2.16.20. `eas.business_holiday`

Lịch ngày nghỉ lễ của công ty phục vụ tính SLA theo giờ hành chính (Migration 14). Số dòng live: 0 · Trigger: 0 · Chỉ mục: 1

| Cột | Kiểu | NN | Khoá | Mặc định | Mô tả |
|---|---|---|---|---|---|
| `holiday_date` | date | ✔ | PK |  | Ngày nghỉ lễ |
| `name` | character varying(150) | ✔ |  |  | Tên ngày nghỉ lễ |
| `created_by` | uuid |  | FK→app_user |  | Người tạo |
| `created_at` | timestamp with time zone | ✔ |  | `statement_timestamp()` | Thời điểm tạo |

Ràng buộc CHECK:
- `CHECK ((length(btrim(name)) > 0))`

## Bảng 2.17. Kho lưu trữ chỉ-đọc `eas_archive` (Migration 15 & 17)

Schema `eas_archive` (đổi tên từ `eas_deprecated` ở Migration 15) là kho lưu trữ chỉ-đọc dành riêng cho DBA để bảo toàn 100% dữ liệu lịch sử và hỗ trợ rollback không mất mát; toàn bộ quyền `USAGE`/`SELECT` của các role ứng dụng (`eas_api`, `eas_worker`, `eas_privacy`, `anon`, `authenticated`) đều bị thu hồi (`REVOKE ALL`).

| Bảng trong `eas_archive` | Nguồn gốc | Cấu trúc chính / Ghi chú |
|---|---|---|
| `eas_archive.dropped_column_value` | Migration 15 & 17 | `PRIMARY KEY (table_name, row_id, column_name)`, `value jsonb`, `archived_at timestamptz`. Lưu toàn bộ giá trị trước khi bỏ của 7 cột trùng ở Migration 15 (`request`, `workflow_instance`, `config_release`: `risk_weight`, `approval_level`; `app_user.username`) và mã nhóm cũ `category_before_17` của `eas.request_type` ở Migration 17 |
| `eas_archive.system_versions_changelog` | Chuyển từ `eas.system_versions_changelog` (Migration 15) | 29 dòng lịch sử thay đổi cấu hình cũ (`id`, `system_version`, `change_type`, `change_scope`, `title`, `description`, `old_value`, `new_value`, `changed_by`, `created_at`). Đã được lệnh `python manage.py import_legacy_changelog --apply` chép toàn vẹn sang chuỗi băm `eas.admin_event` (giữ `details.legacy_changelog_id`) trước khi dời sang kho |
| `eas_archive.workflow_categories_eas` | Đổi tên và chuyển từ `eas.workflow_categories` (Migration 15) | 3 dòng phân loại A/B/C di sản (`category_code`, `name`, `description`, `sla_hours`, `workflow_steps`, `updated_at`), bị thay thế hoàn toàn bởi bảng chuẩn `eas.lifecycle` và `eas.config_release.sla_profile` |
| `eas_archive.work_handover` | Chuyển từ `eas.work_handover` (Migration 15) | Bàn giao công việc khi vắng mặt; đã gộp toàn bộ dòng và 4 cột mở rộng (`scope`, `source`, `source_request_id`, `created_by`) vào bảng `eas.approval_delegation` |
| 10 bảng bản đầu (`users`, `roles`, `requests`, `departments`, `role_permissions`, `request_templates`, …) | Chuyển từ `eas_deprecated` (Migration 11 → 15) | Các bảng prototype giai đoạn đầu trước khi chuẩn hoá sang Schema `eas` 3NF |
