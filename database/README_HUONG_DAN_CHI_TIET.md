# 📖 Hướng Dẫn Cơ Sở Dữ Liệu Enterprise Approval System (EAS)

> **Dành cho:** Tất cả thành viên trong nhóm phát triển (Backend, Frontend, Mobile, AI, QA)  
> **Hệ quản trị CSDL:** PostgreSQL 15+ trên **Supabase**  
> **Schema lưu trữ:** `eas` (Đã được tạo hoàn tất trên Supabase của dự án)  
> **Tài liệu đặc tả gốc:** `Thiết kế/03_Du_lieu_va_API_v2.docx` & `Thiết kế/01_SRS_v2.docx`

---

## 📌 1. Thông Tin Nhanh Cho Thành Viên Nhóm (Quickstart)

- **Trạng thái hiện tại:** CSDL đã được khởi tạo **đầy đủ 100% (gồm 30 bảng vật lý, triggers, indexes và dữ liệu mẫu)** trên Supabase. Bạn **không cần phải chạy lại script SQL** trừ khi muốn dựng lại môi trường mới từ đầu.
- **Cách xem bảng trên Supabase:**
  1. Đăng nhập vào [Supabase Dashboard](https://supabase.com/dashboard/project/emnusiybdkpibtqsplta).
  2. Vào mục **Table Editor** (icon bảng tính 🗄️).
  3. Ở góc trên bên trái, bấm vào menu chọn schema và chọn sang **`eas`** *(nếu chưa thấy, vào Project Settings -> API -> thêm `eas` vào ô Exposed schemas)*.
- **Lưu ý khi Backend kết nối:**
  - Các bảng nằm trong schema `eas`, vì vậy trong câu truy vấn SQL cần ghi rõ `eas.<tên_bảng>` (ví dụ: `SELECT * FROM eas.request;`), hoặc thiết lập connection search path: `SET search_path TO eas, public;`.

---

## 🎯 2. Dữ Liệu Khởi Tạo Sẵn Để Test (Seed Data)

Hệ thống đã có sẵn dữ liệu mẫu trong DB để nhóm test ngay API/UI:

| Bảng | Dữ Liệu Mẫu Đã Tạo | Ghi Chú |
| :--- | :--- | :--- |
| **`department`** | `HO` (Ban Tổng Giám Đốc), `TECH` (Phòng Công Nghệ), `FIN` (Tài Chính - Kế Toán), `HR` (Hành Chính - Nhân Sự), `OPS` (Vận Hành) | 5 phòng ban mẫu trong cơ cấu công ty |
| **`request_type`** | `LEAVE` (Nghỉ phép), `ACCESS` (Cấp quyền), `EQUIPMENT` (Yêu cầu thiết bị) | 3 loại đơn đại diện cho 3 mô hình vòng đời A, B, C |
| **`app_user`** | `username`: **`admin`**, mật khẩu mẫu ban đầu: `Admin@123456` | Tài khoản Quản trị viên hệ thống |
| **`role_membership`** | User `admin` được gán vai trò: **`OPS_ADMIN`** và **`POLICY_ADMIN`** phạm vi toàn cục (`GLOBAL`) | Đầy đủ quyền quản trị vận hành và cấu hình |

---

## 🔄 3. Hiểu Về Vòng Đời Nghiệp Vụ (Workflow & Lifecycles)

Để Backend và Frontend phối hợp nhịp nhàng, hệ thống chia tất cả các loại đơn thành **3 mô hình vòng đời (Lifecycle)**:

```
[Mô hình A - Chỉ duyệt]
Requester (Tạo đơn) ──► Approver (Phê duyệt) ──► COMPLETED

[Mô hình B - Duyệt + Thi công]
Requester (Tạo đơn) ──► Approver (Phê duyệt) ──► Executor (Thi công) ──► COMPLETED

[Mô hình C - Duyệt + Thi công + Nghiệm thu]
Requester (Tạo đơn) ──► Approver (Phê duyệt) ──► Executor (Thi công) ──► Acceptor (Nghiệm thu) ──► COMPLETED
```

* **Mô hình A (Ví dụ: `LEAVE` - Nghỉ phép):** Đơn chỉ cần sếp duyệt xong là hoàn tất (`COMPLETED`), không cần ai thi công hay nghiệm thu.
* **Mô hình B (Ví dụ: `ACCESS` - Xin quyền hệ thống/VPN):** Sếp duyệt xong $\rightarrow$ Chuyển sang IT (`Executor`) mở quyền $\rightarrow$ Hoàn tất.
* **Mô hình C (Ví dụ: `EQUIPMENT` - Mua sắm/Cấp máy tính):** Sếp duyệt $\rightarrow$ Chuyên viên mua/giao máy (`Executor`) $\rightarrow$ Người nhận kiểm tra đạt và bấm Nghiệm thu (`Acceptor`) $\rightarrow$ Hoàn tất.

---

## 🗂️ 4. Bản Đồ 30 Bảng CSDL (Tra Cứu Nhanh Cho Lập Trình Viên)

Toàn bộ CSDL gồm **30 bảng**, chia thành **7 phân hệ** rõ ràng:

### Nhóm 1: Tổ Chức, Nhân Sự & Phân Quyền
| Bảng | Tác Dụng | Các Cột Quan Trọng Cần Nhớ |
| :--- | :--- | :--- |
| **`security_epoch`** | Phiên bản bảo mật toàn cục, dùng để khóa đồng thời khi thay đổi quyền nhân sự | `id = 1`, `version`, `updated_at` |
| **`department`** | Danh sách phòng ban cây phân cấp | `code`, `name`, `parent_id` (trỏ phòng ban cha) |
| **`app_user`** | Tài khoản nhân sự | `username` (viết thường), `display_name`, `department_id`, `manager_id` (sếp trực tiếp) |
| **`role_membership`** | Bảng gán quyền RBAC | `user_id`, `role`, `scope_kind` (`GLOBAL`/`DEPARTMENT`), `valid_from`, `valid_to` |

> [!NOTE]
> **7 Vai trò hợp lệ (Allowlist Roles) trong `role_membership`:**
> `REQUESTER` (Người tạo đơn), `APPROVER` (Người duyệt), `EXECUTOR` (Người thi công), `ACCEPTOR` (Người nghiệm thu), `POLICY_ADMIN` (Quản trị chính sách/form), `OPS_ADMIN` (Quản trị vận hành), `AUDITOR` (Kiểm toán viên).

---

### Nhóm 2: Loại Đơn & Cấu Hình Động (Dynamic Config)
| Bảng | Tác Dụng | Các Cột Quan Trọng Cần Nhớ |
| :--- | :--- | :--- |
| **`request_type`** | Danh mục loại đơn | `code` (`LEAVE`, `ACCESS`, `EQUIPMENT`), `lifecycle` (`A`, `B`, `C`), `active_release_id` |
| **`config_release`** | Bản phát hành cấu hình động dạng JSON bất biến | `form_schema` (JSON form động), `route_rules` (luật định tuyến), `sla_profile` (giờ SLA), `state` (`DRAFT`/`PUBLISHED`) |

---

### Nhóm 3: Hồ Sơ Yêu Cầu & Quy Trình Duyệt
| Bảng | Tác Dụng | Các Cột Quan Trọng Cần Nhớ |
| :--- | :--- | :--- |
| **`request`** | Bảng gốc của mỗi hồ sơ yêu cầu | `code` (Mã đơn duy nhất), `status`, `draft_payload` (dữ liệu nháp JSON), `current_revision_id` |
| **`request_revision`** | Lịch sử nộp đơn chính thức (mỗi lần submit/resubmit là 1 revision mới, cấm sửa/xóa) | `revision_no`, `payload` (dữ liệu form chính thức), `amount_vnd` (số tiền), `payload_sha256` |
| **`workflow_instance`** | Phiên thực thi workflow gắn với revision đã nộp | `matched_rule_id`, `resolved_route` (tuyến duyệt), `planned_executor_id`, `acceptor_id` |
| **`request_participant`** | Danh sách những người có quyền xem/xử lý hồ sơ này | `request_id`, `user_id`, `joined_as` |
| **`approval_step`** | Các bước phê duyệt tuần tự (Cấp 1 $\rightarrow$ Cấp 2 $\rightarrow$ Cấp 3) | `step_no` (1..3), `assignee_id` (người cần duyệt), `state` (`WAITING`, `ACTIVE`, `APPROVED`...) |
| **`approval_decision`** | Quyết định duyệt chính thức của Approver (Bất biến) | `outcome` (`APPROVE`, `REJECT`, `NEEDS_INFO`), `reason` (bắt buộc $\ge 10$ ký tự khi từ chối) |

---

### Nhóm 4: Thực Thi Nhiệm Vụ & Nghiệm Thu
| Bảng | Tác Dụng | Các Cột Quan Trọng Cần Nhớ |
| :--- | :--- | :--- |
| **`execution_attempt`** | Lần thi công/thực hiện của Executor | `attempt_no`, `executor_id`, `state` (`READY`, `RUNNING`, `SUBMITTED`, `FINISHED`), `closure_kind` |
| **`acceptance_decision`** | Quyết định nghiệm thu của Acceptor (Bất biến) | `outcome` (`ACCEPT` hoặc `REWORK`), `reason` ($\ge 10$ ký tự nếu bắt làm lại) |
| **`execution_issue`** | Báo cáo sự cố khi làm việc (bị kẹt, hết kho...) | `kind` (`UNABLE_TO_CLAIM`, `BLOCKED`), `reason` |

---

### Nhóm 5: Quản Lý Tệp Đính Kèm (File & Antivirus)
| Bảng | Tác Dụng | Các Cột Quan Trọng Cần Nhớ |
| :--- | :--- | :--- |
| **`attachment`** | Metadata file tải lên (hóa đơn, chứng từ, ảnh) | `storage_key`, `size_bytes` ($\le 10\text{MB}$), `sha256`, `scan_state` (`QUEUED`, `CLEAN`, `INFECTED`) |
| **`draft_attachment`** | File tạm trong bản nháp (tối đa 5 file) | `request_id`, `attachment_id`, `added_by` |
| **`revision_attachment`** | File chính thức gắn chặt với lần nộp đơn | `revision_id`, `attachment_id` |
| **`execution_attachment`** | File ảnh/kết quả nghiệm thu do Executor nộp | `attempt_id`, `attachment_id` |

---

### Nhóm 6: Giám Sát Thời Gian (SLA) & Cảnh Báo
| Bảng | Tác Dụng | Các Cột Quan Trọng Cần Nhớ |
| :--- | :--- | :--- |
| **`sla_stage`** | Giai đoạn đếm ngược SLA cho từng bước | `kind` (`APPROVAL`, `EXECUTION`, `ACCEPTANCE`), `started_at`, `due_at`, `breached_at` |
| **`sla_alert`** | Lịch sử bắn thông báo nhắc việc hoặc cảnh báo muộn | `stage_id`, `kind` (`REMINDER`, `BREACH`) |

---

### Nhóm 7: Sổ Kiểm Toán (Audit), Outbox & Pháp Lý
| Bảng | Tác Dụng | Các Cột Quan Trọng Cần Nhớ |
| :--- | :--- | :--- |
| **`audit_event`** | Sổ kiểm toán chi tiết từng hành động trên hồ sơ | Chuỗi băm SHA-256 (`prev_hash`, `hash`), `actor_kind` (`HUMAN`/`SYSTEM`), `details` |
| **`admin_event`** | Sổ kiểm toán các hành động quản trị hệ thống | Băm SHA-256, `action`, `reason`, `details` |
| **`audit_head`** | Đỉnh chuỗi băm dùng để tính tiếp mã băm của event sau | `scope_key` (`REQ:<uuid>` hoặc `ADMIN`), `last_hash` |
| **`audit_checkpoint`** | Điểm chốt băm lưu trữ định kỳ ra kho lạnh ngoài DB | `scope_key`, `seq`, `hash`, `external_object_key` |
| **`outbox_event`** | Bảng Outbox Pattern để bắn thông báo bất đồng bộ | `event_type`, `payload`, `state` (`PENDING`, `PROCESSING`, `SENT`, `DEAD`), `lease_token` |
| **`notification`** | Hộp thư thông báo trong app cho từng user | `recipient_id`, `label`, `read_at` |
| **`idempotency_record`** | Bản ghi chống gửi trùng request qua mạng (Idempotency Key) | `key`, `command_scope`, `http_status`, `response_body` |
| **`privacy_case`** | Tiếp nhận yêu cầu quyền riêng tư dữ liệu (xóa/sửa thông tin) | `subject_user_id`, `case_type`, `status` |
| **`retention_hold`** | Lệnh giữ hồ sơ pháp lý (chặn tự động purge dữ liệu) | `request_id`, `reason`, `released_at` |

---

## 🛡️ 5. Các Quy Tắc Kỹ Thuật Quan Trọng Cần Lưu Ý Khi Code

1. **Không thể UPDATE hay DELETE các bảng lịch sử (Append-Only):**
   - Các bảng: `approval_decision`, `acceptance_decision`, `execution_issue`, `revision_attachment`, `execution_attachment`, `audit_event`, `admin_event` đều có Trigger chống sửa xóa. Nếu cố tình chạy lệnh `UPDATE` hoặc `DELETE`, Database sẽ báo lỗi ngay lập tức!
2. **Khóa ngoại kép an toàn `(id, request_id)`:**
   - Các bảng chi tiết (như bước duyệt, tệp đính kèm, lần thi công) đều kiểm tra khóa ngoại kép trỏ tới cả `id` và `request_id` của bảng cha để đảm bảo không bao giờ bị gắn nhầm dữ liệu giữa 2 hồ sơ khác nhau.
3. **Chỉ có duy nhất 1 bước mở tại 1 thời điểm:**
   - Chỉ có tối đa **1 bước duyệt `ACTIVE`** trên một instance.
   - Chỉ có tối đa **1 lần thi công đang chạy** (`READY`, `RUNNING`, `SUBMITTED`).
   - Chỉ có tối đa **1 chặng SLA mở** (`closed_at IS NULL`) trên mỗi hồ sơ.

---

## 📁 6. Các File Trong Thư Mục `database/`

```text
database/
├── README.md           # Tài liệu hướng dẫn này
├── schema.sql          # File SQL toàn bộ cấu trúc 30 bảng, trigger, indexes và dữ liệu seed
└── verify.sql          # Script tự động kiểm tra xác nhận CSDL đã đủ 30 bảng và seed data
```

Nếu cần chạy lại script kiểm tra xem DB trên Supabase có hoạt động tốt không:  
👉 Chỉ cần copy nội dung file **[verify.sql](file:///d:/GitHub/DATN/database/verify.sql)**, dán vào **SQL Editor** trên Supabase và bấm **Run**, nếu trả về dòng thông báo:  
`NOTICE: Xác thực thành công toàn bộ 30 bảng và bootstrap data cho schema eas!` nghĩa là CSDL hoàn toàn sẵn sàng và chuẩn xác 100%.
