# HỒ SƠ THIẾT KẾ CƠ SỞ DỮ LIỆU TOÀN DIỆN (DATABASE DESIGN & ERD)
## DỰ ÁN: HỆ THỐNG TỰ ĐỘNG HÓA QUY TRÌNH XỬ LÝ YÊU CẦU NỘI BỘ ĐA CẤP (EAS)
### HỘI ĐỒNG THẨM ĐỊNH IT 15 NĂM KINH NGHIỆM: BA, PM, DEV, UI/UX, AI, QA, PO

---

## 1. NGUYÊN TẮC THIẾT KẾ CƠ SỞ DỮ LIỆU DOANH NGHIỆP

Theo chuẩn thiết kế cơ sở dữ liệu quan hệ quốc tế (ANSI/SPARC, Chuẩn hóa 3NF/BCNF) và kiểm chứng trực tiếp trên schema `eas` của PostgreSQL 15+ trong Supabase, cơ sở dữ liệu của hệ thống EAS tuân thủ các nguyên tắc thiết kế tối thượng:
1. **Phân lập Schema chặt chẽ (Strict Schema Isolation):** Toàn bộ thực thể nghiệp vụ nằm độc quyền trong schema `eas.*`. Không dùng schema `public` để tránh xung đột và lỗ hổng bảo mật.
2. **Khóa chính toàn cầu ngẫu nhiên (UUIDv4 Primary Keys):** 100% bảng nghiệp vụ sử dụng `UUID` làm khóa chính, triệt tiêu hoàn toàn nguy cơ quét đoán ID (ID Enumeration / Insecure Direct Object References - IDOR).
3. **Mã hồ sơ thân thiện người dùng tuần tự (Business Human-Readable Sequence):** Sử dụng bảng đếm tuần tự có khóa hàng `eas.request_counter` để sinh mã đơn định dạng chuẩn doanh nghiệp: `REQ-YYYY-NNNNNN` độc lập với UUID.
4. **Bảo mật mức dòng bắt buộc (Enforced Row Level Security - RLS):** 100% bảng nghiệp vụ đều được kích hoạt RLS (`ENABLE ROW LEVEL SECURITY`). Quyền thao tác được cấp phát nghiêm ngặt cho các vai trò backend chuyên trách (`eas_api`, `eas_worker`), thu hồi toàn bộ quyền của các vai trò công cộng (`anon`, `authenticated`).
5. **Sổ cái kiểm toán bất biến chuỗi băm (Tamper-Evident Cryptographic Hash-Chain):** Mọi thay đổi dữ liệu cốt lõi đều được ghi lại vào bảng `eas.audit_log` với mã băm SHA-256 xâu chuỗi liên tục, không bao giờ được phép thực hiện câu lệnh `UPDATE` hay `DELETE` trên bảng kiểm toán.

---

## 2. DANH MỤC TOÀN BỘ 10 SƠ ĐỒ THỰC THỂ LIÊN KẾT MIỀN CHI TIẾT (ER-04 ĐẾN ER-13)

---

### SƠ ĐỒ 1: HÌNH PL-32 - MIỀN TỔ CHỨC NHÂN SỰ & PHÂN QUYỀN RBAC (ER-04)
*Quản lý cây cơ cấu phòng ban, hồ sơ nhân sự, ma trận quyền và trạng thái làm việc.*

```mermaid
erDiagram
    DEPARTMENT ||--o{ APP_USER : "thuộc về"
    APP_USER ||--o{ ROLE_MEMBERSHIP : "được gán"
    APP_USER ||--o{ USER_PERMISSIONS : "cấp quyền riêng"
    APP_USER ||--o{ USER_LEAVE_AND_TRIPS : "có lịch nghỉ/công tác"
    ROLE_MODULE_PERMISSION }o--|| ROLE_MEMBERSHIP : "xác định quyền role"

    DEPARTMENT {
        uuid id PK
        string code UK "Mã phòng ban (HR, FIN, IT, ...)"
        string name "Tên phòng ban"
        uuid parent_id FK "Phòng ban cấp cha"
        uuid manager_id FK "Trưởng phòng ban"
        timestamp created_at
    }

    APP_USER {
        uuid id PK
        string email UK "Email đăng nhập"
        string full_name "Họ và tên"
        string password_hash "Mật khẩu Argon2id"
        uuid department_id FK
        string job_title "Chức vụ"
        boolean is_active "Đang hoạt động"
        boolean is_system_account "Tài khoản hệ thống"
        timestamp last_login
        timestamp created_at
    }

    ROLE_MEMBERSHIP {
        uuid id PK
        uuid user_id FK
        string role_code "APPROVER, AUDITOR, OPS_ADMIN, POLICY_ADMIN, EXECUTOR, REQUESTER"
        timestamp created_at
    }

    ROLE_MODULE_PERMISSION {
        uuid id PK
        string role_code "Mã vai trò"
        string module_code "dashboard, workflows, org_chart, users, permissions, regulations, ai_engine, api_management, system_versions"
        boolean can_read "Quyền Xem"
        boolean can_create "Quyền Thêm"
        boolean can_update "Quyền Sửa"
        boolean can_delete "Quyền Xóa"
        timestamp updated_at
    }

    USER_PERMISSIONS {
        uuid id PK
        uuid user_id FK
        string module_code "Mã module"
        boolean can_read
        boolean can_create
        boolean can_update
        boolean can_delete
        timestamp updated_at
    }

    USER_LEAVE_AND_TRIPS {
        uuid id PK
        uuid user_id FK
        string event_type "LEAVE, BUSINESS_TRIP, REMOTE_WFH"
        date start_date "Ngày bắt đầu"
        date end_date "Ngày kết thúc"
        string reason "Lý do"
        string status "APPROVED, CANCELED"
    }
```

---

### SƠ ĐỒ 2: HÌNH PL-33 - MIỀN DANH MỤC, 12 NHÓM YÊU CẦU & BẢN PHÁT HÀNH CẤU HÌNH ĐỘNG (ER-05)
*Quản lý 66 loại yêu cầu (58 loại đang hoạt động), 12 nhóm lớn theo mục đích người dùng (`eas.request_group`), 61 mục chọn trên menu (`eas.request_menu_item`), vòng đời A/B/C và các bản phát hành cấu hình bất biến.*

```mermaid
erDiagram
    REQUEST_GROUP ||--o{ REQUEST_TYPE : "phân nhóm chính"
    REQUEST_GROUP ||--o{ REQUEST_MENU_ITEM : "hiển thị trên menu"
    REQUEST_TYPE ||--o{ REQUEST_MENU_ITEM : "ánh xạ loại + preset"
    REQUEST_TYPE ||--o{ CONFIG_RELEASE : "có nhiều bản phát hành"
    CONFIG_RELEASE ||--o{ APPROVAL_ROUTE : "chứa các lộ trình duyệt"
    APPROVAL_ROUTE ||--o{ STEP_DEFINITION : "chứa các bước duyệt"

    REQUEST_GROUP {
        string code PK "12 nhóm: ABSENCE, WORKTIME, BORROW, PROVISION, PAYMENT, PROCUREMENT, PEOPLE, SUPPORT, WORK, LEGAL, SALES, ASSET"
        string name "Tên nhóm hiển thị"
        string description "Mô tả điểm chung theo nhu cầu người gửi"
        smallint sort_order "Thứ tự hiển thị"
    }

    REQUEST_MENU_ITEM {
        string code PK "61 mục: 56 loại trực tiếp + 5 preset (PAID_LEAVE, UNPAID_LEAVE, LATE_IN, EARLY_OUT, MISSED_CHECK_IN)"
        string group_code FK "Thuộc nhóm lớn"
        string type_code FK "Trỏ tới request_type.code"
        string label "Nhãn hiển thị trên menu"
        jsonb preset "Trường điền sẵn và khóa trên UI"
        smallint sort_order
        boolean is_active
    }

    REQUEST_TYPE {
        uuid id PK
        string code UK "Mã loại đơn (LEAVE, ROOM_BOOKING, EXPENSE_CLAIM, ...)"
        string name "Tên loại đơn"
        string lifecycle "A: Chỉ duyệt, B: Thi công, C: Nghiệm thu"
        string category FK "FK -> request_group.code (12 nhóm lớn)"
        boolean is_active "Đang mở cho phép nộp"
        uuid active_release_id FK "Bản phát hành hiệu lực"
        smallint risk_weight "Nguồn duy nhất trọng số rủi ro (1-5)"
        smallint approval_level "Số cấp duyệt (1-5)"
    }

    CONFIG_RELEASE {
        uuid id PK
        uuid request_type_id FK
        string version UK "v1.0, v1.1, v2.0"
        jsonb form_schema "JSON Schema của biểu mẫu"
        string status "DRAFT, VALIDATED, PUBLISHED, SUPERSEDED"
        integer automation_weight "Trọng số tự động hóa (0-100%)"
        jsonb sla_policy "Chính sách thời hạn SLA từng bước"
        uuid created_by FK
        timestamp published_at
    }

    APPROVAL_ROUTE {
        uuid id PK
        uuid config_release_id FK
        string route_name "Tên lộ trình"
        numeric min_amount "Hạn mức tối thiểu"
        numeric max_amount "Hạn mức tối đa"
        jsonb condition_rules "Luật điều kiện JSONLogic"
    }

    STEP_DEFINITION {
        uuid id PK
        uuid approval_route_id FK
        integer step_order "Thứ tự bước (1, 2, 3...)"
        string required_role "Vai trò duyệt (LINE_MANAGER, DEPT_HEAD, CFO...)"
        integer sla_hours "Thời hạn xử lý (Giờ)"
        boolean can_auto_approve "Cho phép AI tự duyệt nếu đủ điều kiện"
    }
```

---

### SƠ ĐỒ 3: HÌNH PL-34 - MIỀN HỒ SƠ YÊU CẦU CỐT LÕI & LỊCH SỬ SỬA ĐỔI (ER-06)
*Bảng lưu trữ hồ sơ trung tâm, số hiệu tuần tự và các phiên bản sửa đổi (Revisions).*

```mermaid
erDiagram
    REQUEST ||--o{ REQUEST_REVISION : "có các phiên bản sửa"
    REQUEST ||--o{ IDEMPOTENCY_KEY : "được bảo vệ bởi"
    REQUEST_COUNTER ||--|| REQUEST : "cung cấp số hiệu"

    REQUEST {
        uuid id PK
        string code UK "Mã số hồ sơ tuần tự (REQ-2026-000123)"
        uuid request_type_id FK
        uuid config_release_id FK "Snapshot phiên bản quy chế áp dụng"
        uuid owner_id FK "Người tạo đơn"
        uuid department_id FK "Phòng ban của đơn"
        string status "DRAFT, SUBMITTED, IN_REVIEW, NEEDS_INFO, READY_FOR_EXECUTION, IN_PROGRESS, WAITING_FOR_ACCEPTANCE, COMPLETED, REJECTED, WITHDRAWN"
        integer current_stage "1: Soạn, 2: Duyệt, 3: Thi công, 4: Nghiệm thu, 5: Hoàn tất"
        integer current_step_seq "Bước duyệt hiện tại"
        numeric amount "Tổng số tiền / giá trị (nếu có)"
        boolean auto_approved "Được duyệt tự động bởi AI"
        integer risk_score "Điểm rủi ro AI (1-5)"
        integer version "Khóa lạc quan chống ghi đè"
        timestamp submitted_at
        timestamp completed_at
        timestamp created_at
    }

    REQUEST_REVISION {
        uuid id PK
        uuid request_id FK
        integer revision_number "Số lần sửa (1, 2, 3...)"
        string title "Tiêu đề yêu cầu"
        string description "Mô tả chi tiết"
        jsonb form_values "Dữ liệu các trường trong form"
        string change_reason "Lý do cập nhật/bổ sung"
        uuid created_by FK
        timestamp created_at
    }

    REQUEST_COUNTER {
        integer year PK "Năm tài chính"
        integer last_sequence "Số tuần tự đơn lớn nhất hiện tại"
    }

    IDEMPOTENCY_KEY {
        string key PK "UUID khóa gửi từ Client Header"
        uuid request_id FK
        string request_path "Đường dẫn API"
        integer response_status "Mã trạng thái phản hồi"
        jsonb response_body "Nội dung phản hồi được cache"
        timestamp expires_at
    }
```

---

### SƠ ĐỒ 4: HÌNH PL-35 - MIỀN QUY TRÌNH & QUYẾT ĐỊNH PHÊ DUYỆT ĐA CẤP (ER-07)
*Quản lý từng bước duyệt thực tế, phán quyết của cấp quản lý và luật ủy quyền.*

```mermaid
erDiagram
    REQUEST ||--o{ APPROVAL_STEP : "gồm các bước duyệt"
    APPROVAL_STEP ||--o{ STEP_DECISION : "chứa quyết định"
    APP_USER ||--o{ DELEGATION_RULE : "người ủy quyền"

    APPROVAL_STEP {
        uuid id PK
        uuid request_id FK
        integer step_seq "Thứ tự bước (1, 2, 3)"
        string step_name "Tên bước duyệt"
        string required_role "Vai trò duyệt yêu cầu"
        uuid assigned_actor_id FK "Người duyệt được gán thực tế"
        string status "PENDING, ACTIVE, APPROVED, REJECTED, NEEDS_INFO, SKIPPED, REVOKED"
        timestamp activated_at "Thời điểm kích hoạt bước"
        timestamp deadline "Thời hạn cam kết hoàn tất"
        timestamp decided_at "Thời điểm ra phán quyết"
    }

    STEP_DECISION {
        uuid id PK
        uuid approval_step_id FK
        uuid actor_id FK "Người bấm nút"
        string decision "APPROVE, REJECT, NEEDS_INFO, REVOKE"
        string note "Ý kiến phê duyệt hoặc Lý do từ chối"
        boolean is_delegated "Thực hiện qua ủy quyền"
        uuid delegated_from_id FK "Ủy quyền từ ai"
        timestamp decided_at
    }

    DELEGATION_RULE {
        uuid id PK
        uuid delegator_id FK "Người ủy quyền"
        uuid delegatee_id FK "Người được ủy quyền"
        timestamp start_time "Thời điểm bắt đầu hiệu lực"
        timestamp end_time "Thời điểm kết thúc hiệu lực"
        jsonb allowed_request_types "Danh sách loại đơn được ủy quyền"
        boolean is_active "Đang kích hoạt"
        timestamp created_at
    }
```

---

### SƠ ĐỒ 5: HÌNH PL-36 - MIỀN THỰC THI & NGHIỆM THU BÀN GIAO CÔNG VIỆC (ER-08)
*Quản lý chuyên viên thi công (Lifecycle B/C), sự cố vướng mắc và biên bản nghiệm thu độc lập.*

```mermaid
erDiagram
    REQUEST ||--o{ EXECUTION_ATTEMPT : "có các lượt thi công"
    EXECUTION_ATTEMPT ||--o{ EXECUTION_ISSUE : "phát sinh sự cố"
    REQUEST ||--o{ ACCEPTANCE_RECORD : "nghiệm thu bàn giao"

    EXECUTION_ATTEMPT {
        uuid id PK
        uuid request_id FK
        integer attempt_seq "Lần thử thi công (1, 2...)"
        uuid executor_id FK "Chuyên viên nhận việc"
        string status "READY, RUNNING, SUBMITTED, ACCEPTED, REWORK, BLOCKED"
        string result_note "Biên bản nộp kết quả thực hiện"
        timestamp lease_until "Hạn mức độc quyền nhận việc"
        timestamp started_at
        timestamp completed_at
    }

    EXECUTION_ISSUE {
        uuid id PK
        uuid execution_attempt_id FK
        uuid reporter_id FK "Người báo cáo"
        string issue_type "OUT_OF_STOCK, SPEC_MISMATCH, TECHNICAL_FAILURE"
        string description "Mô tả chi tiết vướng mắc"
        string status "OPEN, RESOLVED, DISMISSED"
        timestamp created_at
        timestamp resolved_at
    }

    ACCEPTANCE_RECORD {
        uuid id PK
        uuid request_id FK
        uuid execution_attempt_id FK
        uuid acceptor_id FK "Cán bộ nghiệm thu độc lập"
        string verdict "ACCEPTED, REWORK"
        string evaluation_note "Nhận xét chất lượng bàn giao"
        timestamp signed_at "Thời điểm ký nghiệm thu số"
    }
```

---

### SƠ ĐỒ 6: HÌNH PL-37 - MIỀN TỆP ĐÍNH KÈM AN TOÀN & QUÉT ANTIVIRUS (ER-09)
*Quản lý chứng từ đính kèm, mã băm SHA-256 và nhật ký quét mã độc.*

```mermaid
erDiagram
    REQUEST ||--o{ ATTACHMENT : "đính kèm"
    ATTACHMENT ||--o{ VIRUS_SCAN_LOG : "lịch sử quét"

    ATTACHMENT {
        uuid id PK
        uuid request_id FK
        uuid owner_id FK "Người tải lên"
        string original_filename "Tên tệp gốc"
        string storage_key "Tên tệp ngẫu nhiên trên Cloud Storage"
        string mime_type "Định dạng tệp"
        bigint file_size_bytes "Dung lượng tệp (Bytes)"
        string sha256_hash "Mã băm SHA-256 tệp tin"
        string scan_status "SCANNING, CLEAN, INFECTED, QUARANTINED"
        boolean contains_pii "Chứa dữ liệu cá nhân nhạy cảm"
        boolean is_deleted "Đã xóa logic"
        timestamp created_at
    }

    VIRUS_SCAN_LOG {
        uuid id PK
        uuid attachment_id FK
        string scanner_engine "ClamAV Daemon / YARA"
        string scan_result "CLEAN, THREAT_FOUND"
        string threat_details "Chi tiết mã độc phát hiện"
        integer scan_duration_ms "Thời gian quét (ms)"
        timestamp scanned_at
    }
```

---

### SƠ ĐỒ 7: HÌNH PL-38 - MIỀN THEO DÕI CAM KẾT SLA & CẢNH BÁO (ER-10)
*Quản lý đồng hồ đo thời gian, nhật ký vi phạm và hành động leo thang cảnh báo.*

```mermaid
erDiagram
    REQUEST ||--o{ SLA_STAGE : "theo dõi từng chặng"
    SLA_STAGE ||--o{ SLA_BREACH_LOG : "ghi nhận vi phạm"

    SLA_STAGE {
        uuid id PK
        uuid request_id FK
        string stage_name "SUBMIT_TO_APPROVE, APPROVE_TO_EXECUTE..."
        integer duration_target_hours "Cam kết thời gian (Giờ)"
        timestamp started_at "Bắt đầu tính giờ"
        timestamp deadline "Thời hạn chót"
        timestamp ended_at "Kết thúc thực tế"
        string status "NORMAL, WARNING_SENT, BREACHED, RESOLVED"
    }

    SLA_BREACH_LOG {
        uuid id PK
        uuid sla_stage_id FK
        integer breach_duration_minutes "Thời gian trễ hạn (Phút)"
        uuid responsible_actor_id FK "Người đang giữ đơn bị trễ"
        string escalation_action "ALERT_MANAGER, AUTO_REASSIGN, KPI_PENALTY"
        timestamp logged_at
    }
```

---

### SƠ ĐỒ 8: HÌNH PL-39 - MIỀN HÀNG ĐỢI SỰ KIỆN OUTBOX & THÔNG BÁO (ER-11)
*Mô hình Transactional Outbox Pattern bảo đảm gửi thông báo tin cậy không thất lạc.*

```mermaid
erDiagram
    OUTBOX_EVENT ||--o{ NOTIFICATION : "sinh ra các thông báo"
    SYSTEM_ANNOUNCEMENT ||--o{ ANNOUNCEMENT_RECEIPT : "ghi nhận đã đọc"

    OUTBOX_EVENT {
        uuid id PK
        string event_type "REQUEST_SUBMITTED, STEP_ACTIVATED, COMPLETED..."
        string aggregate_type "REQUEST, USER, CONFIG"
        uuid aggregate_id "ID của thực thể gốc"
        jsonb payload "Nội dung dữ liệu sự kiện JSON"
        string status "PENDING, DISPATCHED, FAILED"
        integer retry_count "Số lần thử lại"
        timestamp created_at
        timestamp dispatched_at
    }

    NOTIFICATION {
        uuid id PK
        uuid outbox_event_id FK
        uuid recipient_id FK "Người nhận"
        string channel "EMAIL, PUSH_MOBILE, IN_APP"
        string title "Tiêu đề thông báo"
        string body "Nội dung thông báo tóm tắt"
        boolean is_read "Đã xem thông báo"
        timestamp sent_at
        timestamp read_at
    }

    SYSTEM_ANNOUNCEMENT {
        uuid id PK
        string target_version "v1.1, v2.0"
        string title "Hệ thống đã cập nhật quy định mới"
        string summary "Tóm tắt các điểm thay đổi quy trình"
        jsonb changes "Chi tiết các quy định thêm/sửa/xóa"
        jsonb guidance "Hướng dẫn thao tác quy trình mới"
        timestamp created_at
    }

    ANNOUNCEMENT_RECEIPT {
        uuid id PK
        uuid announcement_id FK
        uuid user_id FK "Người dùng đã bấm Đã hiểu"
        timestamp read_at
    }
```

---

### SƠ ĐỒ 9: HÌNH PL-40 - MIỀN SỔ CÁI KIỂM TOÁN HASH-CHAIN & CHECKPOINT (ER-12)
*Sổ cái mật mã học SHA-256 bảo đảm tính toàn vẹn và chống chối bỏ tuyệt đối.*

```mermaid
erDiagram
    AUDIT_HEAD ||--o{ AUDIT_LOG : "quản lý đỉnh băm"
    SYSTEM_VERSIONS_CHANGELOG ||--|| AUDIT_LOG : "chi tiết thay đổi"

    AUDIT_LOG {
        bigint event_seq PK "Số tuần tự đơn điệu 1, 2, 3..."
        uuid id UK "UUID sự kiện"
        string event_type "LOGIN, SUBMIT, APPROVE, REJECT, CLAIM..."
        uuid actor_id "Người thực hiện hành động"
        string actor_ip "Địa chỉ IP client"
        string resource_type "REQUEST, RBAC, ATTACHMENT"
        uuid resource_id "ID của tài nguyên bị tác động"
        jsonb payload "Dữ liệu trạng thái Canonical JSON"
        string prev_hash "Mã băm SHA-256 của bản ghi trước"
        string current_hash "Mã băm SHA-256 của bản ghi này"
        timestamp created_at "Dấu thời gian không thể sửa đổi"
    }

    AUDIT_HEAD {
        integer checkpoint_seq PK "Số thứ tự trạm chốt"
        bigint last_event_seq FK "Số sự kiện chốt cuối"
        string last_hash "Mã băm chốt đỉnh"
        string signature "Chữ ký điện tử của trạm chốt"
        timestamp checkpoint_at
    }

    SYSTEM_VERSIONS_CHANGELOG {
        uuid id PK
        string system_version "v1.0, v2.0"
        string change_type "REGULATION, WORKFLOW, TEMPLATE, PERMISSION, API_STATUS"
        string change_scope "MAJOR, MINOR, PATCH"
        string title "Tiêu đề thay đổi cấu hình"
        string description "Mô tả chi tiết"
        jsonb old_value "Giá trị cũ (Before)"
        jsonb new_value "Giá trị mới (After)"
        uuid changed_by FK "Quản trị viên thực hiện"
        timestamp created_at
    }
```

---

### SƠ ĐỒ 10: HÌNH PL-41 - MIỀN QUYỀN RIÊNG TƯ & BẢO VỆ DỮ LIỆU GDPR (ER-13)
*Quản lý bảo vệ thông tin cá nhân và nhật ký ẩn danh hóa dữ liệu.*

```mermaid
erDiagram
    PRIVACY_REQUEST ||--o{ PRIVACY_COMPLIANCE_LOG : "nhật ký thực thi"

    PRIVACY_REQUEST {
        uuid id PK
        uuid actor_id FK "Người yêu cầu"
        string request_type "DATA_EXPORT, PII_ANONYMIZATION"
        string status "SUBMITTED, PROCESSING, COMPLETED, REJECTED"
        string rejection_reason "Lý do từ chối nếu vướng Legal Hold"
        string export_file_url "Đường dẫn tải tệp mã hóa"
        timestamp requested_at
        timestamp completed_at
    }

    PRIVACY_COMPLIANCE_LOG {
        uuid id PK
        uuid privacy_request_id FK
        uuid target_user_id FK "Nhân sự bị ẩn danh hóa"
        string action_taken "MASK_EMAIL, PURGE_AVATAR, PSEUDONYMIZE_LOGS"
        jsonb impacted_tables "Danh sách các bảng đã xóa trắng PII"
        timestamp executed_at
    }
```

---

## 3. TỔNG HỢP 8 SCHEMAS HỆ THỐNG NGOÀI (`mock_*`) QUA MOCK SYSTEMS API & BẢNG `eas.mock_apis` (CIRCUIT BREAKER)

8 schema `mock_*` giả lập 8 hệ thống thông tin độc lập của doanh nghiệp, được cô lập hoàn toàn phía sau dịch vụ **Mock Systems API** (`mock_systems` chạy ở cổng `:8100`, dùng role CSDL riêng `eas_mock`). Các role của EAS (`eas_api`, `eas_worker`) **đã bị thu hồi toàn bộ quyền SQL trên `mock_*`** (Migration 17); EAS chỉ giao tiếp với hệ thống ngoài qua HTTP `/mock-api/v1/<hệ thống>/...` kèm header `X-Integration-Secret` (qua client duy nhất `api_core/integrations/client.py`, timeout 5s) và kiểm tra công tắc Circuit Breaker trong `eas.mock_apis`:

| Schema Name | Hệ Thống Mô Phỏng | Các Bảng Chính | Mục Đích Tích Hợp Qua `/mock-api/v1/...` | Trạng Thái Circuit Breaker |
|:---|:---|:---|:---|:---:|
| `mock_hr` | Quản trị Nhân sự (HRIS) | `department`, `employee`, `leave_balance`, `leave_usage` | Đồng bộ danh bạ nhân sự (`sync_hr_directory`), kiểm tra quỹ phép còn lại khi gửi và trừ quỹ phép khi duyệt (`POST /mock-api/v1/hr/leave-usages`). | Quản lý qua `API_HR` |
| `mock_finance` | Kế toán & Ngân sách (ERP) | `cost_center_budget`, `expense_category`, `budget_commitment` | Danh mục loại chi phí & hạn mức ngày, kiểm tra ngân sách trung tâm chi phí và ghi cam kết chi khi duyệt (`POST /mock-api/v1/finance/commitments`). | Quản lý qua `API_FINANCE` |
| `mock_it` | Hạ tầng & Cấp quyền (ITSM) | `application`, `access_role`, `user_access`, `it_service` | Danh mục ứng dụng & vai trò truy cập, ghi nhận cấp quyền khi đơn hoàn tất (`POST /mock-api/v1/it/user-access`). | Quản lý qua `API_IT` |
| `mock_procurement`| Mua sắm & Chuỗi cung ứng | `supplier`, `catalog_item`, `purchase_order` | Bảng giá vật tư, danh mục nhà cung cấp phục vụ AI đối soát ngữ cảnh. | Quản lý qua `API_PROCUREMENT`|
| `mock_assets` | Quản lý Tài sản (EAM) | `asset_category`, `asset`, `asset_loan` | Kiểm tra tồn kho thiết bị, giữ chỗ khi duyệt cuối (duyệt trước thắng), ưu tiên BGĐ thu hồi (`RESOURCE_PREEMPTED`), worker tự trả khi hết hạn. | Quản lý qua `API_ASSETS` |
| `mock_facilities` | Cơ sở vật chất (Facilities)| `site`, `resource`, `reservation` | Đặt phòng họp & xe công vụ qua API giữ chỗ/huỷ/trả, kiểm tra sức chứa, ưu tiên BGĐ thu hồi đơn nhân viên trùng giờ. | Quản lý qua `API_FACILITIES` |
| `mock_travel` | Quản lý Công tác phí | `travel_policy`, `travel_option` | Định mức công tác phí khách sạn, vé máy bay theo chức danh phục vụ AI kiểm tra. | Quản lý qua `API_TRAVEL` |
| `mock_crm` | Quan hệ Khách hàng (CRM) | `customer`, `contract`, `support_case` | Hồ sơ khách hàng, giá trị hợp đồng, chiết khấu thương mại phục vụ AI kiểm tra. | Quản lý qua `API_CRM` |

### Cấu trúc Bảng Điều Khiển Circuit Breaker (`eas.mock_apis`)
```sql
CREATE TABLE eas.mock_apis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_code TEXT UNIQUE NOT NULL,             -- 'API_HR', 'API_FINANCE', 'API_IT'...
    api_name TEXT NOT NULL,                    -- 'HR & Attendance Service API'
    source_system TEXT NOT NULL,               -- 'HRM', 'ERP Finance', 'ITSM'...
    endpoint_path TEXT NOT NULL,               -- '/mock-api/v1/hr/...' (gọi nội bộ kèm X-Integration-Secret)
    http_method TEXT DEFAULT 'GET',
    domain_key TEXT NOT NULL,
    data_provided TEXT NOT NULL,               -- Mô tả dữ liệu cung cấp
    mock_payload JSONB NOT NULL DEFAULT '{}',  -- Dữ liệu mẫu JSON hiển thị trên trang Quản lý API
    is_enabled BOOLEAN DEFAULT true,           -- CÔNG TẮC CIRCUIT BREAKER (Bật/Tắt)
    updated_by TEXT DEFAULT 'System Admin',
    updated_at TIMESTAMPTZ DEFAULT now()
);
```
- **Cơ chế ngắt mạch tự động:** Khi Admin bấm **TẮT** `is_enabled = false` trên một API (ví dụ `API_HR`), ngay lập tức Cổng Web Admin và Web Client tự động phát hiện và khóa các mẫu đơn liên quan với thông báo rõ ràng: `"⚠️ Yêu cầu này hiện không thể sử dụng do kết nối API [HRM] đang bị tắt"`. Phía Backend (`api_core/integrations/client.py`) chặn lời gọi và từ chối giao dịch với mã lỗi `503 INTEGRATION_UNAVAILABLE`.
