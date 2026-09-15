# Kế hoạch & Kiến trúc Hệ thống: Enterprise Approval System

Tài liệu này mô tả chi tiết các phân hệ (modules), kiến trúc, luồng hoạt động (workflows) và kế hoạch triển khai cho Đề tài: **"Hệ thống tự động hóa quy trình xử lý yêu cầu nội bộ đa cấp tuân thủ theo quy định của doanh nghiệp"**.

> **Đối tượng:** SME (50-200 nhân viên) | **Team:** 3 người | **Timeline:** 6-8 tuần
> **Tiêu chí DATN:** Hoàn chỉnh (end-to-end demo) + Sáng tạo (AI/Automation) + Kỹ thuật (Microservices, scalable)

---

## 1. Tổng quan Kiến trúc và Công nghệ

### 1.1. Kiến trúc Tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  Web Client  │  │  Web Admin   │  │  Mobile App        │    │
│  │  (React+Vite)│  │  (React+Vite)│  │  (Flutter)         │    │
│  │  - Form nhập │  │  - Workflow  │  │  - Quick Approve   │    │
│  │  - 4 Tab vai │  │    Builder   │  │  - Biometric Sign  │    │
│  │    trò user  │  │  - Rule Cfg  │  │  - Push Notify     │    │
│  │  - Tracking  │  │  - Dashboard │  │                    │    │
│  │  - Dashboard │  │  - Analytics │  │                    │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
│         │                 │                    │                │
└─────────┼─────────────────┼────────────────────┼────────────────┘
          │                 │                    │
          ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (Nginx/Traefik)                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Django API  │  │  FastAPI AI  │  │  Supabase    │
│  (Core)      │  │  Service     │  │  (BaaS)      │
│              │  │              │  │              │
│ - Workflow   │  │ - OCR        │  │ - Auth/JWT   │
│   Engine     │  │ - LLM        │  │ - Database   │
│ - Rule Engine│  │   Summary    │  │ - Realtime   │
│   (Python)   │  │ - Anomaly    │  │ - Storage    │
│ - Approval   │  │   Detection  │  │ - RLS        │
│   Logic      │  │ - Risk Score │  │ - Edge Fn    │
│ - Audit Log  │  │              │  │              │
│ - SLA/Escal  │  │              │  │              │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
              ┌──────────────────┐
              │   Supabase DB    │
              │  (PostgreSQL)    │
              │  + Redis Cache   │
              │  + Celery Worker │
              └──────────────────┘
```

### 1.2. Stack Công nghệ (Architecture Decision Records)

| ADR | Quyết định | Thay thế | Lý do |
|-----|-----------|----------|-------|
| **ADR-001** | **Supabase** (PostgreSQL + Auth + Realtime + Storage) | Self-hosted PostgreSQL + Django Auth | Nhanh setup, Auth + Realtime + Storage built-in, RLS bảo mật cấp row, giảm ops overhead cho team 3 người |
| **ADR-002** | **Python Rule Engine** (JSON rules trong DB) | Drools KIE Server (JVM) | Bỏ JVM dependency (giảm 1 container Docker), Admin cấu hình rules trên UI web, tích hợp Django native, dễ debug |
| **ADR-003** | **React Flow / xyflow** cho Workflow Builder | BPMN.js, Custom canvas | Ecosystem lớn, hỗ trợ custom node, serialize/deserialize JSON dễ, cộng đồng active |
| **ADR-004** | Giữ **Django** làm core API | — | Business logic phức tạp (workflow engine, approval, audit) cần framework mature |
| **ADR-005** | Giữ **FastAPI** cho AI Service | — | Async processing, tách biệt workload AI nặng khỏi Django sync |
| **ADR-006** | **Lifecycle Template** gắn vào RequestType | Hardcode lifecycle, User tự chọn | Admin cấu hình trước → nhất quán, giảm lỗi user chọn sai |
| **ADR-007** | **Rule-based + XGBoost hybrid** cho Risk Scoring | LLM thuần (GPT/Gemini) | Không cần API call, latency < 50ms, giải thích được (feature importance), train offline trên dữ liệu lịch sử |
| **ADR-008** | **Approval Load Balancer** tự động gợi ý chuyển approver | Chỉ escalation thủ công | Phân tải công bằng, giảm SLA breach, khuyến khích có peer-approver pool |
| **ADR-009** | **OPA (Open Policy Agent)** cho Compliance Policy Layer | Nhúng rule compliance vào Django | Policy-as-code tách biệt khỏi business logic, dễ audit, dễ update theo quy định mới |
| **ADR-010** | **ERP Stub / Webhook Mock** cho external integration | Tích hợp thật với ERP | Demo được luồng end-to-end (HR/ERP data flow) mà không cần hạ tầng thật; dễ thay bằng adapter thật sau |

### 1.3. Danh sách Công nghệ Chi tiết

1. **Workflow & State Machine:**
   - **Custom Python Workflow Engine**: Đọc workflow JSON (từ Workflow Builder) và điều khiển vòng đời yêu cầu qua các node (Start, Approval, Condition, Parallel, Action, End).
   - Sử dụng **django-river** hoặc custom state machine cho runtime transitions.

2. **Audit Log & Truy vết:**
   - **django-auditlog** để tự động ghi nhận mọi thay đổi. Kết hợp **Hash-chain SHA-256** tự viết đảm bảo tính bất biến (Immutable).

3. **AI Support Service:**
   - **FastAPI** cung cấp endpoint OCR, tóm tắt văn bản (LLM), và anomaly detection. Giao tiếp nội bộ với Django qua REST API.

4. **Business Rule Engine:**
   - **Python-native rule engine**: Rules lưu dưới dạng JSON trong DB. Admin cấu hình trên UI. Engine nhận request data, evaluate conditions, trả về ApprovalChain + Lifecycle Template.

5. **No-code Workflow Builder:**
   - **React Flow (xyflow)**: Admin kéo thả tạo workflow mới. Serialize thành JSON, runtime engine đọc JSON để điều khiển vòng đời.

---

## 2. Mô hình Vòng đời Yêu cầu (Request Lifecycle Model)

### 2.1. Bốn Vai trò trong Vòng đời (Four Lifecycle Roles)

Mỗi user trong hệ thống có thể đồng thời giữ **nhiều vai trò** khác nhau. Giao diện hiển thị dưới dạng **4 tabs**, mỗi tab tương ứng một vai trò, có badge số cho biết số yêu cầu đang chờ xử lý.

| Vai trò | Ký hiệu | Mô tả | Hành động có thể thực hiện |
|---------|---------|-------|---------------------------|
| **Người yêu cầu** (Requester) | 📝 | Người tạo và gửi yêu cầu | Tạo mới, lưu nháp, chỉnh sửa, theo dõi tiến trình, nghiệm thu (nếu cấu hình) |
| **Người kiểm duyệt** (Approver) | ✅ | Người phê duyệt/từ chối yêu cầu | Phê duyệt, Từ chối (bắt buộc ghi lý do), Yêu cầu bổ sung thông tin |
| **Người thực hiện** (Executor) | 🔧 | Người thực thi công việc sau khi được duyệt | Nhận việc, Hoàn thành (đính kèm kết quả), Từ chối thực hiện (ghi lý do → trả về Approver) |
| **Người nghiệm thu** (Acceptor) | 🔍 | Người kiểm tra và nghiệm thu kết quả | Nghiệm thu (Accept), Từ chối nghiệm thu (ghi lý do → trả về Executor/Approver) |

### 2.2. Ba Mẫu Lifecycle (Lifecycle Templates)

Không phải mọi yêu cầu đều đi qua toàn bộ 4 giai đoạn. Mỗi loại yêu cầu (RequestType) được Admin gắn với một **Lifecycle Template** phù hợp:

#### Template A: "Chỉ cần Duyệt" (Approve-Only)

```
📝 Requester ──→ ✅ Approver ──→ ✅ COMPLETED
                     │
                     └──→ ❌ REJECTED (ghi lý do)
```

**Ví dụ:** Mượn phòng họp, đăng ký đi muộn/về sớm, quên chấm công.
**Đặc điểm:** Duyệt xong = hoàn tất. Không cần ai thực hiện hay nghiệm thu.
**AI Auto-Approve:** ✅ Áp dụng (nếu trọng số thấp). AI duyệt xong, yêu cầu vẫn hiện trong tab Approver của người kiểm duyệt với badge "🤖 AI đã tự động duyệt" và nút "Xác nhận" / "Từ chối". Nếu timeout → tự động xác nhận.

#### Template B: "Duyệt + Thực hiện" (Approve-Execute)

```
📝 Requester ──→ ✅ Approver ──→ 🔧 Executor ──→ ✅ COMPLETED
                     │                  │
                     │                  └──→ ❌ Từ chối thực hiện (ghi lý do)
                     │                       └──→ Trả về ✅ Approver xem xét lại
                     └──→ ❌ REJECTED (ghi lý do)
```

**Ví dụ:** Yêu cầu mua sắm (cần người đi mua), cấp phát laptop (IT cấp), tạo cuộc họp (Admin setup).
**Đặc điểm:** Sau duyệt, cần người thực hiện hoàn tất công việc. Không cần nghiệm thu.
**AI Auto-Approve:** ❌ KHÔNG áp dụng — vì cần người thực hiện, AI không thể thay thế bước Execution.

#### Template C: "Duyệt + Thực hiện + Nghiệm thu" (Full Lifecycle)

```
📝 Requester ──→ ✅ Approver ──→ 🔧 Executor ──→ 🔍 Acceptor ──→ ✅ COMPLETED
                     │                  │                  │
                     │                  │                  └──→ ❌ Từ chối nghiệm thu
                     │                  │                       └──→ Trả về bước trước
                     │                  └──→ ❌ Từ chối thực hiện
                     │                       └──→ Trả về ✅ Approver
                     └──→ ❌ REJECTED (ghi lý do)
```

**Ví dụ:** Hoàn thành đầu việc/deliverable, sửa chữa cơ sở vật chất (cần kiểm tra), onboarding nhân viên mới.
**Đặc điểm:** Cần kiểm tra chất lượng kết quả. Người nghiệm thu = Requester hoặc Approver (cấu hình theo loại yêu cầu).
**AI Auto-Approve:** ❌ KHÔNG áp dụng.

### 2.3. Cơ chế AI Auto-Approve Chi Tiết

> **Nguyên tắc:** AI chỉ tự động duyệt các yêu cầu sử dụng **Template A (Approve-Only)** VÀ có trọng số rủi ro ≤ 2. Các yêu cầu cần Executor/Acceptor KHÔNG ĐƯỢC auto-approve.

**Quy trình AI Auto-Approve:**

```
1. Requester gửi yêu cầu
2. Rule Engine đánh giá:
   ├── Trọng số ≤ 2 VÀ Template A (Approve-Only)?
   │   ├── CÓ → AI Agent chạy ngầm:
   │   │       ├── Trích xuất thông tin, đối chiếu quỹ/hạn mức/luật
   │   │       ├── Hợp lệ → Trạng thái: AUTO_APPROVED
   │   │       │   └── Hiện trong tab Approver với badge "🤖 AI đã tự động duyệt"
   │   │       │       ├── Approver có nút [Xác nhận] / [Từ chối]
   │   │       │       └── Timeout (vd: 24h) → Tự động xác nhận → COMPLETED
   │   │       └── Bất thường → Đẩy lên duyệt thủ công (PENDING_APPROVAL)
   │   └── KHÔNG → Vào luồng duyệt thủ công đa cấp
```

**Quan trọng:** Kể cả khi AI đã auto-approve, yêu cầu vẫn **hiện lên trong giao diện** của người kiểm duyệt (tab Approver). Người kiểm duyệt luôn có quyền **từ chối** (phải ghi rõ lý do) để override quyết định của AI.

### 2.4. Cơ chế Từ chối ở Mọi Giai đoạn

| Giai đoạn bị từ chối | Hành vi | Trạng thái |
|-----------------------|---------|------------|
| **Approver từ chối** | Yêu cầu bị HỦY. Requester nhận thông báo kèm lý do. | `REJECTED` |
| **Approver yêu cầu bổ sung** | Trả về Requester để cập nhật thông tin. | `NEEDS_INFO` |
| **Executor từ chối thực hiện** | Trả về Approver để xem xét lại hoặc gán người khác. | `EXECUTION_REJECTED` |
| **Acceptor từ chối nghiệm thu** | Trả về bước trước (Executor hoặc Approver tùy cấu hình). | `ACCEPTANCE_REJECTED` |

**Quy tắc bắt buộc:** Mọi hành động từ chối đều PHẢI ghi rõ lý do. Lý do được lưu trong `rejection_reason` và hiển thị cho tất cả các bên liên quan.

### 2.5. Sơ đồ Trạng thái Hoàn chỉnh (State Diagram)

```
                    ┌──────────┐
                    │  DRAFT   │
                    └────┬─────┘
                         │ submit
                         ▼
                    ┌──────────┐
                    │EVALUATING│ (Rule Engine + AI Risk Score)
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              ▼                     ▼
     ┌────────────────┐    ┌───────────────┐
     │ AUTO_APPROVED  │    │PENDING_APPROVAL│
     │ (AI duyệt,    │    │  _L1 / _L2... │
     │ chờ confirm)   │    └───────┬───────┘
     └───────┬────────┘            │
             │                     │ approve / reject
     ┌───────┴─────────────────────┘
     │
     ├── reject → ┌──────────┐
     │             │ REJECTED │ (Kết thúc, ghi lý do)
     │             └──────────┘
     │
     ├── need_info → ┌───────────┐
     │                │NEEDS_INFO │ → Requester cập nhật → re-submit
     │                └───────────┘
     │
     └── approve (Template A) → ┌───────────┐
     │                           │ COMPLETED │
     │                           └───────────┘
     │
     └── approve (Template B/C) → ┌─────────────┐
                                   │ IN_PROGRESS │
                                   └──────┬──────┘
                                          │
                           ┌──────────────┼──────────────┐
                           │              │              │
                           ▼              ▼              ▼
                    ┌────────────┐  ┌───────────┐  ┌──────────┐
                    │EXEC_REJECT │  │  EXECUTED  │  │COMPLETED │
                    │(trả về     │  │(chờ nghiệm│  │(Template │
                    │ Approver)  │  │ thu-Tmpl C)│  │ B xong)  │
                    └────────────┘  └─────┬─────┘  └──────────┘
                                          │
                                   ┌──────┼──────┐
                                   ▼             ▼
                            ┌───────────┐  ┌──────────────┐
                            │ COMPLETED │  │ACCEPT_REJECT │
                            └───────────┘  │(trả về bước  │
                                           │ trước)       │
                                           └──────────────┘
```

---

## 3. Giao diện Người dùng: Hệ thống 4 Tabs

### 3.1. Cấu trúc Tab cho mỗi User

```
┌─────────────────────────────────────────────────────────────────┐
│  👤 Nguyễn Văn A - Trưởng phòng Kế toán                        │
│                                                                 │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ 📝 Yêu cầu  │ ✅ Kiểm duyệt│ 🔧 Thực hiện│ 🔍 Nghiệm thu│  │
│  │  của tôi (2) │   (5)  🔴   │    (1)       │    (0)       │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                 │
│  [Tab Kiểm duyệt đang active]                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 🤖 Nghỉ phép - Trần Thị B (1 ngày)    [AI Auto-Approved]│    │
│  │    ⏰ Tự động xác nhận sau 23h         [Xác nhận][Từ chối]│    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │ 📋 Mua sắm - Lê Văn C (Laptop 25tr)   [Chờ duyệt]      │    │
│  │    ⚠️ AI Risk Score: 3/5               [Duyệt][Từ chối] │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │ 📋 Cấp Server - Phạm D (2 VM)          [Chờ duyệt]     │    │
│  │    🔴 AI Risk Score: 5/5 - CẦN CHÚ Ý   [Duyệt][Từ chối]│    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2. Hành vi từng Tab

| Tab | Hiển thị | Filter/Sort | Hành động |
|-----|---------|-------------|-----------|
| **📝 Yêu cầu của tôi** | Yêu cầu do user tạo, mọi trạng thái | Theo status, ngày tạo | Tạo mới, xem chi tiết, theo dõi tiến trình, nghiệm thu (nếu là Acceptor) |
| **✅ Kiểm duyệt** | Yêu cầu cần user duyệt (bao gồm AI auto-approved chờ xác nhận) | Theo urgency, AI flag | Duyệt, Từ chối (ghi lý do), Yêu cầu bổ sung, Batch approve |
| **🔧 Thực hiện** | Yêu cầu đã duyệt, giao cho user thực hiện | Theo deadline, priority | Nhận việc, Đánh dấu hoàn thành (đính kèm kết quả), Từ chối (ghi lý do) |
| **🔍 Nghiệm thu** | Yêu cầu đã thực hiện xong, cần user nghiệm thu | Theo ngày hoàn thành | Chấp nhận (Accept), Từ chối (ghi lý do, trả về) |

---

## 4. Phân rã Các Module Chức năng (Modules)

### 4.1. Module Quản trị Định danh & Tổ chức (Identity & Organization Module)

- **Chức năng:** Quản lý User, Roles (Nhân viên, Trưởng phòng, Giám đốc), Departments (Phòng ban), và Delegation (Ủy quyền phê duyệt khi vắng mặt).
- **Công nghệ:** Supabase Auth + JWT, Row Level Security (RLS) cho phân quyền cấp record.
- **Auto-Delegation:** Khi người duyệt vắng mặt (nghỉ phép đã được duyệt), hệ thống tự động chuyển quyền duyệt cho người được ủy quyền theo `DelegationPolicy`.

```
DelegationPolicy:
  - delegator: user_A (Trưởng phòng Kế toán)
  - delegate: user_B (Phó phòng)
  - start_date: 2026-09-15
  - end_date: 2026-09-20
  - scope: ALL | specific_request_types[]
```

### 4.2. Module Quản lý Yêu cầu (Request Management Module)

- **Chức năng:** Tạo mới, lưu nháp, chỉnh sửa, đính kèm file và theo dõi trạng thái.
- **Dữ liệu:** Dynamic Forms theo từng loại yêu cầu, dựa trên `form_schema` JSON.
- **Comment Thread:** Mỗi yêu cầu có thread bình luận để các bên trao đổi.

### 4.3. Module Điều phối Quy trình (Workflow & State Module)

- **Chức năng:**
  - Điều khiển vòng đời yêu cầu theo **Lifecycle Template** (A, B, hoặc C).
  - **No-code Workflow Builder** (React Flow): Admin kéo thả tạo workflow mới.
  - Runtime Workflow Engine đọc JSON definition, điều khiển transitions.
- **Các loại node trong Workflow Builder:**
  - **Start Node**: Điểm bắt đầu
  - **Approval Node**: Chỉ định ai duyệt (role/person/department)
  - **Condition Node**: Rẽ nhánh theo điều kiện (số tiền, loại yêu cầu, risk score)
  - **Parallel Node**: Fork ra nhiều nhánh duyệt đồng thời (consensus: ALL/ANY/MAJORITY)
  - **Action Node**: Thực hiện hành động (gửi email, gọi AI, tạo ticket)
  - **End Node**: Kết thúc (Approved/Rejected/Completed)
- **SLA & Escalation:** Bộ đếm thời gian. Nếu quá SLA, kích hoạt nhắc nhở (Celery/Redis) hoặc tự động escalation.

### 4.4. Module Đánh giá Luật Nghiệp vụ (Business Rule Engine Module)

- **Chức năng:** Python-native rule engine. Rules lưu dạng JSON trong DB, Admin cấu hình trên UI.
- **Hoạt động:** Khi yêu cầu được gửi, engine evaluate conditions → trả về:
  - `ApprovalChain` (Danh sách người duyệt, theo cấp)
  - `Lifecycle Template` (A, B, hoặc C)
  - `Executor Assignment` (Ai thực hiện, nếu có)
  - `Acceptor Assignment` (Ai nghiệm thu, nếu có)
  - `SLA Duration` (Thời gian cho phép ở mỗi bước)

```python
# Ví dụ Rule JSON
{
  "name": "Purchase > 50M needs CFO",
  "conditions": [
    {"field": "request_type", "operator": "==", "value": "purchase_requisition"},
    {"field": "amount", "operator": ">", "value": 50000000}
  ],
  "actions": [
    {"type": "set_lifecycle", "template": "B"},
    {"type": "add_approver", "role": "dept_head", "level": 1},
    {"type": "add_approver", "role": "cfo", "level": 2},
    {"type": "add_approver", "role": "ceo", "level": 3},
    {"type": "assign_executor", "department": "procurement"},
    {"type": "set_sla", "hours": 48}
  ]
}
```

### 4.5. Module Trợ lý AI (AI Assistant Module)

- **Chức năng:** FastAPI cung cấp 4 dịch vụ chính:
  - **OCR:** Bóc tách thông tin từ hóa đơn, chứng từ đính kèm (giảm nhập liệu thủ công).
  - **Summarize:** LLM tóm tắt yêu cầu dài/phức tạp, giúp người phê duyệt nắm bắt nhanh (đặc biệt trên Mobile).
  - **Anomaly Detection / Risk Scoring:** Chấm điểm rủi ro (0-100). Yêu cầu chi tiêu vượt mức → cờ cảnh báo.
  - **Auto-Approve Agent:** Chạy ngầm cho yêu cầu trọng số thấp + Template A. Trích xuất thông tin, đối chiếu quỹ/hạn mức, luật. Hợp lệ → Auto-approve. Bất thường → đẩy lên duyệt thủ công.

### 4.6. Module Ghi nhận Kiểm toán (Audit & Compliance Module)

- **Chức năng:**
  - Dùng `django-auditlog` ghi nhận: Ai, làm gì, lúc nào, giá trị cũ/mới.
  - Hash-chain SHA-256: `Hash = SHA256(Hash_Previous + Action + Actor + Timestamp + Data)`.
  - API verify integrity: kiểm tra chain không bị tamper.
  - Mọi hành động từ chối đều ghi `rejection_reason` vào audit log.

### 4.7. Module Thông báo (Notification Module)

- **Chức năng:** Gắn với vòng đời Workflow:
  - **In-app Notification** (Supabase Realtime) — badge số trên 4 tabs.
  - **Push Notification** qua Firebase FCM tới Flutter.
  - **Email Notification** cho các event quan trọng (submitted, approved, rejected, SLA warning).
  - **SLA Reminder & Escalation alerts.**

### 4.8. Module Chữ ký số (Digital Signature Module)

- **Chức năng:**
  - Yêu cầu có trọng số ≥ 4: Approver phải ký số khi phê duyệt.
  - **Web:** react-signature-canvas.
  - **Mobile:** Biometric confirmation (FaceID/Fingerprint) via Flutter `local_auth`.
  - Signature lưu base64 + hash vào approval chain record.
  - **PDF Export:** Tạo PDF quyết định phê duyệt có đóng dấu chữ ký số.

### 4.9. Module Dashboard & Analytics

- **Chức năng:** Dashboard cho Manager/Admin theo dõi hiệu suất xử lý yêu cầu.
- **KPI:**
  - **Approval Rate:** % duyệt vs từ chối (Donut chart)
  - **Avg Processing Time:** Thời gian trung bình từ tạo → hoàn tất (Line chart)
  - **SLA Compliance Rate:** % xử lý đúng hạn (Gauge chart)
  - **Bottleneck Detection:** Bước nào hay bị tắc nhất (Heatmap)
  - **Department Load:** Khối lượng theo phòng ban (Bar chart)
  - **AI Auto-Approve Rate:** % AI tự duyệt thành công (Trend line)

---

## 5. Phân loại Yêu cầu và Cơ chế Trọng số (Request Types & Risk Weights)

Mỗi loại yêu cầu được gán **Trọng số rủi ro** (1-5), **Lifecycle Template** (A/B/C), và **Acceptor Type** (Requester/Approver/None).

### Quy tắc AI Auto-Approve:

- ✅ **Áp dụng** khi: Trọng số ≤ 2 **VÀ** Lifecycle Template = A (Approve-Only)
- ❌ **KHÔNG áp dụng** khi: Template B hoặc C (cần Executor/Acceptor) — bất kể trọng số bao nhiêu

### Danh mục Phân loại Yêu cầu

#### I. Nhóm Tài chính & Mua sắm (Finance & Procurement)

| Loại Yêu cầu | Trọng số | Template | Cơ chế xử lý | Acceptor | Ghi chú |
|---|:---:|:---:|---|---|---|
| **Nghỉ phép < 3 ngày** | 1 | A | 🤖 AI Auto-Approve | — | AI quét quỹ phép. Duyệt xong = cập nhật hệ thống |
| **Nghỉ phép ≥ 3 ngày** | 3 | A | 🧑 Manual (1 cấp) | — | Trưởng phòng duyệt để sắp xếp công việc |
| **Cấp VPP (văn phòng phẩm)** | 1 | B | 🤖 AI Auto-Approve bước duyệt, NHƯNG Template B nên → Manual | Executor: Admin | Admin cấp phát, không cần nghiệm thu |
| **Cấp Laptop/Thiết bị giá trị** | 3 | C | 🧑 Manual (1 cấp) | Requester | IT cấp phát → Requester nghiệm thu nhận bàn giao |
| **Đăng ký OT** | 2 | A | 🧑 Manual (1 cấp) | — | Trưởng phòng duyệt theo kế hoạch |
| **Yêu cầu mua sắm** | 4-5 | B | 🧑 Manual (2-3 cấp) | — | Drools định tuyến theo ngân sách. Phòng Mua sắm thực hiện |
| **Sửa chữa CSVC** | 1-2 | B | 🤖 AI phân loại khẩn cấp | — | AI phân loại → tạo ticket cho đội bảo trì thực hiện |

#### II. Nhóm Vận hành Kinh doanh & E-commerce (Business & Ops)

| Loại Yêu cầu | Trọng số | Template | Cơ chế xử lý | Acceptor | Ghi chú |
|---|:---:|:---:|---|---|---|
| **Hoàn tiền/Đền bù** | 2 | A | 🤖 AI Auto-Approve | — | AI tra cứu lịch sử, < hạn mức → tự động duyệt |
| **Luân chuyển kho** | 3 | B | 🧑 Manual (1 cấp) | — | Thủ kho duyệt → nhân viên kho thực hiện |
| **Flash Sale/Voucher** | 4 | B | 🧑 Manual (2 cấp) | — | AI phân tích biên lợi nhuận. Marketing thực hiện |
| **Duyệt hợp đồng** | 5 | C | 🧑 Manual (3 cấp) | Approver (Legal) | Pháp chế nghiệm thu hợp đồng đã ký |

#### III. Nhóm Kỹ thuật & Công nghệ (Tech & IT Solutions)

| Loại Yêu cầu | Trọng số | Template | Cơ chế xử lý | Acceptor | Ghi chú |
|---|:---:|:---:|---|---|---|
| **Trích xuất Data/UAT** | 3 | B | 🧑 Manual (1-2 cấp) | — | AI masking PII trước khi export |
| **Feature Request/Release** | 4 | C | 🧑 Manual (2 cấp) | Approver (PM) | PM nghiệm thu deliverable |
| **Cấp phát Server/Firewall** | 5 | C | 🧑 Manual (2-3 cấp) | Approver (CTO) | CTO xác nhận cấu hình đúng |

#### IV. Nhóm Hành chính & Quản trị Nhân sự (HR & Admin)

| Loại Yêu cầu | Trọng số | Template | Cơ chế xử lý | Acceptor | Ghi chú |
|---|:---:|:---:|---|---|---|
| **Mượn phòng họp/studio** | 1 | A | 🤖 AI Auto-Approve | — | AI quét lịch trống → phê duyệt tức thì |
| **Đi muộn/về sớm/quên CC** | 1 | A | 🤖 AI Auto-Approve | — | AI quét số lần trong tháng → tự động cập nhật |
| **Cấp phát laptop/thiết bị** | 3 | C | 🧑 Manual (1 cấp) | Requester | Requester nghiệm thu nhận thiết bị |
| **Nghỉ ≥ 3 ngày/Thuê PT** | 3 | A | 🧑 Manual (1-2 cấp) | — | Trưởng phòng duyệt sắp xếp thay thế |
| **Cấp account/VPN** | 3 | B | 🧑 Manual (1-2 cấp) | — | IT thực hiện cấp phát |
| **Onboarding nhân viên** | 3-4 | C | 🧑 Manual (1-2 cấp) | Approver (TP) | TP nghiệm thu onboarding hoàn tất |

---

## 6. Chi tiết Các Luồng Hoạt động (Workflows)

### Luồng 1: Khởi tạo và Phân loại Yêu cầu (Request Creation)

1. Nhân viên (Requester) điền form và upload chứng từ lên **Web/Mobile**.
2. **AI Module** tự động đọc ảnh OCR, trích xuất và điền vào form (nếu có).
3. Người dùng xác nhận và bấm "Gửi yêu cầu". Trạng thái: `EVALUATING`.
4. **Rule Engine** (Python) đánh giá → trả về:
   - Lifecycle Template (A/B/C)
   - Approval Chain (danh sách người duyệt)
   - Executor assignment (nếu Template B/C)
   - Acceptor assignment (nếu Template C)
   - SLA thời gian
5. Nếu **Template A + trọng số ≤ 2** → AI Auto-Approve Agent chạy ngầm.
6. Nếu không → chuyển `PENDING_APPROVAL_L1`, gửi notification cho Approver.

### Luồng 2: Phê duyệt (Approval Flow)

1. Approver nhận thông báo, mở app/web → tab **✅ Kiểm duyệt**.
2. Card yêu cầu hiển thị:
   - Thông tin tóm tắt (AI summarize nếu quá dài)
   - Risk Score badge + AI warnings
   - Badge "🤖 AI đã tự động duyệt" (nếu auto-approved)
3. Approver quyết định:
   - **Phê duyệt** → Chuyển bước tiếp (L2, hoặc Executor, hoặc COMPLETED tùy template)
   - **Từ chối** → `REJECTED` (BẮT BUỘC ghi lý do) → Requester nhận thông báo
   - **Yêu cầu bổ sung** → `NEEDS_INFO` → Requester cập nhật
4. Nếu trọng số ≥ 4: yêu cầu **chữ ký số** (web: canvas, mobile: biometric).
5. **Parallel Approval** (nếu workflow cấu hình): Nhiều Approver cùng duyệt. Consensus mode: ALL/ANY/MAJORITY.
6. **Auto-Delegation:** Nếu Approver đang vắng → tự động chuyển cho delegate.
7. Mọi quyết định → **Audit Module** ghi log + SHA-256.

### Luồng 3: Thực hiện (Execution Flow) — Template B & C

1. Sau phê duyệt hoàn toàn, yêu cầu hiện trong tab **🔧 Thực hiện** của Executor.
2. Executor:
   - **Nhận việc** và thực hiện.
   - **Hoàn thành** → đính kèm kết quả (ủy nhiệm chi, biên bản bàn giao...) → Bấm "Hoàn thành".
   - **Từ chối thực hiện** → Ghi lý do → Trả về Approver để xem xét (gán người khác hoặc hủy).
3. Nếu Template B: COMPLETED ngay sau khi Executor hoàn thành.
4. Nếu Template C: chuyển sang Nghiệm thu.

### Luồng 4: Nghiệm thu (Acceptance Flow) — Template C

1. Yêu cầu hiện trong tab **🔍 Nghiệm thu** của Acceptor (Requester hoặc Approver tùy cấu hình).
2. Acceptor kiểm tra kết quả:
   - **Chấp nhận (Accept)** → `COMPLETED`.
   - **Từ chối nghiệm thu** → Ghi lý do → Trả về bước trước (Executor làm lại, hoặc Approver xem xét).

### Luồng 5: Theo dõi SLA và Leo thang (SLA Monitoring & Escalation)

1. **Celery Worker** quét định kỳ (15 phút/lần).
2. SLA Level 1 (quá 50% thời gian): gửi Reminder cho người đang giữ yêu cầu.
3. SLA Level 2 (quá 100% thời gian): Escalation → báo cáo lên cấp cao hơn + ghi cảnh báo audit log.
4. Áp dụng cho TẤT CẢ các giai đoạn: Approval, Execution, Acceptance.

---

## 7. Tích hợp Công nghệ vào Các Tầng

- **Tầng Frontend (React.js + Vite):**
  - **4 Tabs** theo vai trò (Requester/Approver/Executor/Acceptor) với badge count.
  - **No-code Workflow Builder** (React Flow) cho Admin.
  - **Dynamic Form renderer** dựa trên `form_schema` JSON.
  - **Dashboard Analytics** với Recharts/Chart.js.
  - **Signature Canvas** (react-signature-canvas) cho phê duyệt rủi ro cao.
  - **Comment Thread** trên mỗi yêu cầu.
  - Tracking timeline: sơ đồ cây hiển thị yêu cầu đang ở giai đoạn nào, tay ai.

- **Tầng Mobile (Flutter):**
  - **Quick Approve**: Swipe phải duyệt, trái từ chối.
  - **Biometric Sign**: FaceID/Fingerprint cho yêu cầu rủi ro cao.
  - **Push Notification** via Firebase FCM.
  - **AI Summary** hiển thị tóm tắt cho yêu cầu dài.
  - **4 Tabs** tương tự web.

- **Tầng Backend (Django + FastAPI):**
  - Tách bạch: Workflow Engine (JSON-based), Rule Engine (Python-native), Audit Log (hash-chain), AI Service (FastAPI).
  - Supabase cho Auth, Database, Realtime, Storage.

---

## 8. Kế hoạch Triển khai (Implementation Plan)

> **Team:** 3 người | **Timeline:** **10 tuần** (12/09/2026 — 21/11/2026)
> **Nguyên tắc:** Spike trước → Foundation → Core → Frontend → Polish → UAT

### Phân công Team

| Vai trò | Phụ trách | Tasks chính |
|---------|----------|-------------|
| **Backend Lead** | Django API, Workflow Engine, Rule Engine, Audit | Task 0.3, 2, 3, 4, 5, 6, 11 |
| **Frontend Lead** | Web Client, Web Admin, Workflow Builder, Dashboard | Task 0.1, 7, 8, 12 |
| **Fullstack/Mobile** | Supabase, Flutter Mobile, AI Service, DB | Task 0.2, 1, 9, 10 |

---

### Giai đoạn 0: Spike & Proof of Concept (Tuần 1)

> **Mục đích:** Validate assumption rủi ro cao TRƯỚC khi commit vào kiến trúc.

**Task 0.1: PoC — React Flow Workflow Builder**
* **Description:** Prototype kéo thả workflow với React Flow: 3 loại node (Start, Approval, End), nối edge, serialize/import JSON.
* **Acceptance criteria:**
  - [ ] Render canvas với drag-drop nodes
  - [ ] Nối edges giữa nodes
  - [ ] Export workflow ra JSON → Import lại render đúng
* **Verification:** Tạo workflow "Nghỉ phép" (Start → TP duyệt → End) → export → import → layout đúng.
* **Dependencies:** None | **Scope:** M | **Assigned:** Frontend Lead

**Task 0.2: PoC — Supabase Integration**
* **Description:** Setup Supabase. Tạo bảng `users`, `departments`. Cấu hình Auth (email login), RLS, test Realtime.
* **Acceptance criteria:**
  - [ ] Auth hoạt động: đăng ký, đăng nhập, JWT
  - [ ] RLS: user chỉ thấy data department mình
  - [ ] Realtime: subscribe bảng `requests`, nhận event khi INSERT
* **Dependencies:** None | **Scope:** S | **Assigned:** Fullstack/Mobile

**Task 0.3: PoC — Python Rule Engine**
* **Description:** Prototype rule engine. Rules dạng JSON. Engine nhận request data → trả về approval chain + lifecycle template.
* **Acceptance criteria:**
  - [ ] Define 5 rules mẫu JSON
  - [ ] `{type: "leave", days: 2}` → `{auto_approve: true, lifecycle: "A"}`
  - [ ] `{type: "purchase", amount: 60M}` → `{chain: ["dept_head", "cfo"], lifecycle: "B", executor: "procurement"}`
  - [ ] Xử lý rule priority
* **Verification:** 20 unit tests pass.
* **Dependencies:** None | **Scope:** S | **Assigned:** Backend Lead

#### 🔖 Checkpoint: Spike (Cuối tuần 1)
- [ ] React Flow prototype hoạt động
- [ ] Supabase Auth + RLS + Realtime verified
- [ ] Rule engine pass 20 tests
- [ ] **GO/NO-GO decision**

---

### Giai đoạn 1: Foundation (Tuần 2-3)

**Task 1: Database Schema**
* **Description:** Thiết kế và migrate toàn bộ schema trên Supabase.
* **Acceptance criteria:**
  - [ ] `profiles` (extends auth.users): name, role, department_id, position
  - [ ] `departments`: name, parent_id (cây), head_user_id
  - [ ] `request_types`: name, risk_weight, lifecycle_template (A/B/C), form_schema (JSON), category, acceptor_type (requester/approver/none)
  - [ ] `requests`: requester_id, type_id, status, data (JSONB), risk_score
  - [ ] `approval_chains`: request_id, approver_id, level, status, decision, decided_at, comment, rejection_reason, signature_data, is_ai_approved
  - [ ] `execution_records`: request_id, executor_id, status, result_data, rejection_reason
  - [ ] `acceptance_records`: request_id, acceptor_id, status, rejection_reason
  - [ ] `workflow_definitions`: name, json_schema, created_by, is_active
  - [ ] `rules`: name, conditions (JSON), actions (JSON), priority, is_active
  - [ ] `delegation_policies`: delegator_id, delegate_id, start/end_date, scope
  - [ ] `audit_logs`: entity_type, entity_id, action, old_value, new_value, actor_id, hash, prev_hash, rejection_reason
  - [ ] `comments`: request_id, user_id, content
  - [ ] `attachments`: request_id, file_url, file_type, extracted_data (AI OCR)
  - [ ] `notifications`: user_id, type, title, body, is_read, request_id
  - [ ] RLS policies cho tất cả bảng
* **Dependencies:** Task 0.2 | **Scope:** L | **Assigned:** Fullstack/Mobile

**Task 2: Django API Core + Supabase Client**
* **Description:** Khởi tạo Django + DRF, kết nối Supabase PostgreSQL, JWT middleware, CRUD API cơ bản.
* **Acceptance criteria:**
  - [ ] Django + DRF setup
  - [ ] Kết nối Supabase PostgreSQL
  - [ ] JWT middleware verify Supabase token
  - [ ] CRUD API cho `departments`, `request_types`
  - [ ] Swagger/OpenAPI docs
* **Dependencies:** Task 1 | **Scope:** M | **Assigned:** Backend Lead

**Task 3: Rule Engine Module (Production)**
* **Description:** Nâng PoC thành production. Tích hợp Django. Admin CRUD rules qua API. Hỗ trợ output lifecycle template + executor/acceptor assignment.
* **Acceptance criteria:**
  - [ ] Model `Rule` trong DB, API CRUD
  - [ ] `evaluate_rules(request_data)` → `{approval_chain, lifecycle_template, executor, acceptor, sla}`
  - [ ] Operators: ==, !=, >, <, >=, <=, in, not_in, contains
  - [ ] Rule priority + conflict detection
* **Verification:** 30+ unit tests.
* **Dependencies:** Task 0.3, Task 2 | **Scope:** M | **Assigned:** Backend Lead

#### 🔖 Checkpoint: Foundation (Cuối tuần 3)
- [ ] Schema deployed trên Supabase
- [ ] Django API chạy, kết nối OK
- [ ] Rule engine trả về đúng lifecycle template + approval chain

---

### Giai đoạn 2: Core Features (Tuần 3-5)

**Task 4: Workflow Engine (Runtime)**
* **Description:** Engine đọc workflow JSON, xác định bước hiện tại, xử lý transitions theo lifecycle template.
* **Acceptance criteria:**
  - [ ] Parse workflow JSON → executable state machine
  - [ ] Hỗ trợ Lifecycle Template A, B, C
  - [ ] Approval transitions: approve → next, reject → REJECTED (ghi lý do), need_info → back
  - [ ] Execution transitions: complete → next, reject → back to Approver (ghi lý do)
  - [ ] Acceptance transitions: accept → COMPLETED, reject → back (ghi lý do)
  - [ ] Parallel approval: consensus modes (ALL/ANY/MAJORITY)
  - [ ] Condition node: evaluate → chọn branch
* **Verification:**
  - [ ] Template A: Start → Approve → COMPLETED ✅
  - [ ] Template B: Start → Approve → Execute → COMPLETED ✅
  - [ ] Template C: Start → Approve → Execute → Accept → COMPLETED ✅
  - [ ] Rejection at each stage works correctly ✅
* **Dependencies:** Task 3 | **Scope:** L | **Assigned:** Backend Lead

**Task 5: Request Lifecycle API (Vertical Slice)**
* **Description:** API hoàn chỉnh cho vòng đời: tạo → submit → approve/reject → execute → accept.
* **Acceptance criteria:**
  - [ ] `POST /api/requests/` — Tạo draft
  - [ ] `POST /api/requests/{id}/submit/` — Gửi → trigger rule engine → tạo chain
  - [ ] `POST /api/requests/{id}/approve/` — Duyệt (+ signature nếu risk ≥ 4)
  - [ ] `POST /api/requests/{id}/reject/` — Từ chối (BẮT BUỘC `rejection_reason`)
  - [ ] `POST /api/requests/{id}/request-info/` — Yêu cầu bổ sung
  - [ ] `POST /api/requests/{id}/execute-complete/` — Executor hoàn thành
  - [ ] `POST /api/requests/{id}/execute-reject/` — Executor từ chối (ghi lý do)
  - [ ] `POST /api/requests/{id}/accept/` — Acceptor nghiệm thu
  - [ ] `POST /api/requests/{id}/accept-reject/` — Acceptor từ chối (ghi lý do)
  - [ ] `GET /api/requests/my-requests/` — Tab 📝 Yêu cầu của tôi
  - [ ] `GET /api/requests/pending-approval/` — Tab ✅ Kiểm duyệt
  - [ ] `GET /api/requests/pending-execution/` — Tab 🔧 Thực hiện
  - [ ] `GET /api/requests/pending-acceptance/` — Tab 🔍 Nghiệm thu
  - [ ] `POST /api/requests/batch-approve/` — Duyệt hàng loạt
  - [ ] Auto-delegation: approver vắng → chuyển delegate
  - [ ] AI Auto-Approve: Template A + risk ≤ 2 → AI duyệt ngầm, hiện trong tab Approver
* **Verification:** End-to-end tests cho cả 3 templates.
* **Dependencies:** Task 4 | **Scope:** L | **Assigned:** Backend Lead

**Task 6: Audit Log + Hash Chain**
* **Description:** Immutable Audit Log SHA-256. Mọi action (approve, reject, execute, accept) + rejection_reason đều ghi log.
* **Acceptance criteria:**
  - [ ] Hash chain: `hash = SHA256(prev_hash + action + actor + timestamp + data + rejection_reason)`
  - [ ] Verify integrity API: `GET /api/audit/verify/{request_id}/`
  - [ ] Search/filter audit logs
  - [ ] Rejection reasons searchable
* **Dependencies:** Task 5 | **Scope:** M | **Assigned:** Backend Lead

#### 🔖 Checkpoint: Core Features (Cuối tuần 5)
- [ ] Vòng đời yêu cầu chạy end-to-end (cả 3 templates)
- [ ] Từ chối ở mọi giai đoạn hoạt động đúng (kèm lý do)
- [ ] AI auto-approve hoạt động cho Template A + risk thấp
- [ ] Test coverage ≥ 70% core modules

---

### Giai đoạn 3: Frontend & Mobile (Tuần 5-7)

**Task 7: Web Client — 4 Tabs + Request Flow**
* **Description:** Giao diện nhân viên: 4 tabs (📝✅🔧🔍), dynamic form, tracking timeline, comment thread.
* **Acceptance criteria:**
  - [ ] 4 tabs với badge count (Supabase Realtime update)
  - [ ] Dynamic form renderer từ `form_schema` JSON
  - [ ] File upload → Supabase Storage → trigger AI OCR
  - [ ] Tracking timeline: hiển thị yêu cầu đang ở giai đoạn nào, tay ai
  - [ ] AI auto-approved badge "🤖 AI đã tự động duyệt" + nút Xác nhận/Từ chối
  - [ ] Rejection dialog: bắt buộc nhập lý do
  - [ ] Comment thread
  - [ ] Batch approve checkbox
  - [ ] Notification center (bell icon)
* **Dependencies:** Task 5 | **Scope:** L | **Assigned:** Frontend Lead

**Task 8: Web Admin — Workflow Builder + Rule Config + Dashboard**
* **Description:** Admin UI: kéo thả workflow (React Flow), cấu hình rules + lifecycle templates, dashboard analytics.
* **Acceptance criteria:**
  - [ ] **Workflow Builder:** Drag-drop nodes, connect edges, save JSON
  - [ ] **Node Config Panel:** Click node → sidebar cấu hình (approver role, condition, lifecycle template)
  - [ ] **Rule Config:** CRUD rules với UI (conditions + actions + lifecycle output)
  - [ ] **RequestType Config:** Gán lifecycle template (A/B/C), acceptor type, form schema
  - [ ] **Dashboard:** 6 KPI charts
  - [ ] **User/Department Management**
  - [ ] **Delegation Management**
* **Dependencies:** Task 0.1, Task 5, Task 6 | **Scope:** XL → Chia cho 2 người | **Assigned:** Frontend Lead + Fullstack

**Task 9: Mobile App — Quick Approve + 4 Tabs**
* **Description:** Flutter app: 4 tabs, swipe approve/reject, biometric, push notification.
* **Acceptance criteria:**
  - [ ] Login via Supabase Auth
  - [ ] 4 tabs với badge count
  - [ ] Swipe right → Approve, left → Reject (dialog ghi lý do)
  - [ ] Biometric cho risk ≥ 4
  - [ ] Push notification via FCM
  - [ ] AI summary cho yêu cầu dài
  - [ ] AI auto-approved badge hiển thị
* **Dependencies:** Task 5 | **Scope:** L | **Assigned:** Fullstack/Mobile

#### 🔖 Checkpoint: Frontend (Cuối tuần 7)
- [ ] Web Client 4 tabs hoạt động
- [ ] Workflow Builder tạo workflow → yêu cầu chạy đúng
- [ ] Mobile app duyệt nhanh
- [ ] Realtime sync web ↔ mobile

---

### Giai đoạn 4: AI + Polish (Tuần 7-8)

**Task 10: AI Service Integration**
* **Description:** FastAPI AI: OCR, LLM summarize, risk scoring, auto-approve agent.
* **Acceptance criteria:**
  - [ ] OCR: upload ảnh → structured data
  - [ ] Summarize: text dài → tóm tắt 2-3 câu
  - [ ] Risk score: 0-100 + explanation
  - [ ] Auto-approve agent: evaluate Template A + risk ≤ 2 → auto-approve hoặc escalate
* **Dependencies:** Task 5, Task 7 | **Scope:** M | **Assigned:** Fullstack/Mobile

**Task 11: SLA Monitoring + Notification System**
* **Description:** Celery worker quét SLA cho TẤT CẢ giai đoạn (Approval, Execution, Acceptance).
* **Acceptance criteria:**
  - [ ] SLA Level 1: reminder notification
  - [ ] SLA Level 2: escalation + audit log warning
  - [ ] Email + In-app + Push notification cho events
  - [ ] SLA tracking cho Executor và Acceptor (không chỉ Approver)
* **Dependencies:** Task 5, Task 9 | **Scope:** M | **Assigned:** Backend Lead

**Task 12: Digital Signature + PDF Export**
* **Description:** Chữ ký số cho phê duyệt quan trọng. PDF export có chữ ký.
* **Acceptance criteria:**
  - [ ] Web: react-signature-canvas
  - [ ] Signature hash lưu vào approval chain
  - [ ] `GET /api/requests/{id}/export-pdf/` → PDF với lịch sử duyệt + chữ ký
* **Dependencies:** Task 5, Task 8 | **Scope:** S | **Assigned:** Frontend Lead

#### 🔖 Checkpoint: Complete (Cuối tuần 8)
- [ ] Hệ thống end-to-end: Web → API → AI → Mobile
- [ ] 3 lifecycle templates hoạt động đúng
- [ ] Từ chối ở mọi giai đoạn + lý do hiển thị đúng
- [ ] AI auto-approve + human override hoạt động
- [ ] SLA monitoring cho mọi giai đoạn
- [ ] Dashboard analytics hiển thị
- [ ] Sẵn sàng UAT và demo bảo vệ

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Workflow Builder quá phức tạp | 🔴 High | Spike tuần 1. MVP chỉ 3 node types. Condition node phase 2 |
| Supabase RLS không cover RBAC phức tạp | 🟡 Medium | Fallback: Django middleware RBAC supplement |
| AI OCR accuracy thấp | 🟡 Medium | Pre-trained model (PaddleOCR). Fallback: manual input |
| Rule conflict khó debug | 🟡 Medium | UI hiển thị conflict warnings. Priority system |
| Timeline tight (8 tuần, 3 người) | 🔴 High | Strict scope: Signature, PDF export là nice-to-have |

## 10. "Not Doing" List

| Tính năng | Lý do |
|-----------|-------|
| Multi-tenant | Ngoài scope SME |
| Approval via Email/Slack | Cần OAuth integration phức tạp |
| BPMN 2.0 compliant | Quá nặng, React Flow custom đủ |
| Mobile offline mode | Phức tạp sync, không cần cho demo |
| i18n (đa ngôn ngữ) | Chỉ cần tiếng Việt cho DATN |
| Advanced AI (fine-tuned model) | Dùng pre-trained/API đủ |

---

## 11. Giải pháp Bổ sung Đề xuất (Proposed Enhancements)

> Phần này ghi lại 4 giải pháp bổ sung được phân tích và đề xuất thêm vào kiến trúc, cùng với ADR chi tiết cho từng quyết định. Các giải pháp này lấy cảm hứng từ cách các hệ thống enterprise thực tế (ServiceNow, SAP Workflow, Camunda BPM, Temporal.io) giải quyết bài toán tương tự.

---

### 11.1. Giải pháp Bổ sung #1: Hybrid ML Risk Scoring Engine

#### Bối cảnh & Vấn đề

Plan hiện tại dùng LLM (GPT/Gemini) để risk scoring. Điều này có 3 vấn đề:
1. **Latency cao**: Mỗi lần submit yêu cầu phải chờ LLM response (2-10 giây).
2. **Chi phí không kiểm soát**: API call per request sẽ tốn kém khi scale.
3. **Hộp đen (Black box)**: Khó giải thích tại sao AI cho điểm 4/5, khó audit.

Các hệ thống enterprise thực tế (ví dụ: Workday, SAP Concur) dùng **rule-based scoring kết hợp ML nhẹ** train trên lịch sử phê duyệt — không phụ thuộc LLM cho path nhanh.

#### Giải pháp Đề xuất: Rule + XGBoost Hybrid

```
Request Data
    │
    ▼
┌─────────────────────────────────────┐
│         RISK SCORING PIPELINE       │
│                                     │
│  Step 1: Rule-based Hard Signals    │  ← Chạy đầu tiên, nhanh nhất
│  ┌─────────────────────────────┐    │
│  │ • amount > budget_limit?    │    │
│  │ • request_count_this_month? │    │
│  │ • sensitive_data_access?    │    │
│  │ • new_vendor (< 3 months)?  │    │
│  └──────────┬──────────────────┘    │
│             │ score_delta           │
│             ▼                       │
│  Step 2: XGBoost Scoring Model      │  ← Train offline, inference <5ms
│  ┌─────────────────────────────┐    │
│  │ Features:                   │    │
│  │ • requester_approval_rate   │    │
│  │ • dept_avg_amount           │    │
│  │ • day_of_week, hour         │    │
│  │ • similar_past_requests     │    │
│  │ • requester_tenure_months   │    │
│  └──────────┬──────────────────┘    │
│             │ ml_score (0-100)      │
│             ▼                       │
│  Step 3: Composite Score            │
│  final_score = 0.4*rule + 0.6*ml   │
│                                     │
│  Step 4: LLM (OPTIONAL — edge case) │  ← Chỉ gọi khi score ở vùng xám
│  • 45 ≤ final_score ≤ 65?          │    (tránh tốn API call cho clear case)
│  • LLM phân tích context sâu hơn   │
└─────────────────────────────────────┘
    │
    ▼
{ risk_score, risk_level, explanation[], confidence }
```

#### Feature Engineering

| Feature | Mô tả | Nguồn dữ liệu |
|---------|-------|---------------|
| `requester_approval_rate_30d` | Tỉ lệ yêu cầu được duyệt trong 30 ngày qua | `requests` table |
| `requester_rejection_rate_30d` | Tỉ lệ bị từ chối gần đây | `requests` table |
| `amount_vs_dept_avg_ratio` | Số tiền / trung bình phòng ban | `requests` + `departments` |
| `amount_vs_personal_avg_ratio` | Số tiền / trung bình cá nhân | `requests` table |
| `request_type_base_risk` | Risk trọng số gốc của loại yêu cầu | `request_types.risk_weight` |
| `new_vendor_flag` | Vendor mới < 3 tháng | `vendors` table (nếu có) |
| `budget_remaining_ratio` | Ngân sách còn lại / tổng ngân sách | `budget_allocations` table |
| `is_near_quarter_end` | Có phải cuối quý không? | `datetime` |
| `requester_tenure_months` | Thâm niên của người yêu cầu | `profiles.created_at` |
| `similar_requests_avg_outcome` | Outcome trung bình của yêu cầu tương tự | Cosine similarity trên `requests` |

#### Explainability Output

Thay vì chỉ hiện số điểm, UI hiện explanation list:

```json
{
  "risk_score": 72,
  "risk_level": "HIGH",
  "confidence": 0.84,
  "explanation": [
    {"factor": "amount_vs_dept_avg", "impact": "+28", "detail": "Số tiền 45tr cao hơn 3.2x mức trung bình phòng"},
    {"factor": "new_vendor", "impact": "+15", "detail": "Vendor ABC Corp mới tạo 15 ngày trước"},
    {"factor": "requester_approval_rate", "impact": "-8", "detail": "Người yêu cầu có lịch sử duyệt tốt (94%)"}
  ],
  "auto_approve_eligible": false
}
```

#### Training Strategy cho DATN

Do DATN không có dữ liệu thật, dùng **synthetic data generation**:

```python
# scripts/generate_training_data.py
# Tạo 1000+ synthetic approval records với các pattern:
# - Thấp rủi ro: nghỉ phép < 3 ngày → 95% approved
# - Cao rủi ro: mua sắm > 50tr → 60% approved, 40% rejected
# - Edge case: request cuối quý, amount bất thường

# Model evaluation:
# - Accuracy ≥ 85% trên test set
# - AUC-ROC ≥ 0.90
# - Giải thích được top-3 features
```

#### ADR-007 Chi tiết

```
# ADR-007: Hybrid Rule + ML Risk Scoring thay cho LLM thuần

Status: Accepted
Date: 2026-09-12

Context:
  - LLM API (GPT-4) latency: 2-8 giây/request
  - LLM API cost: ~$0.01-0.05 / request (không kiểm soát được)
  - Audit yêu cầu giải thích được quyết định ("tại sao score = 4?")
  - DATN timeline: 8 tuần, không có thời gian fine-tune LLM
  - Inspiration: Workday AI Risk, Coupa Risk Assess

Decision:
  Rule-based hard signals (40%) + XGBoost inference (60%).
  LLM chỉ gọi cho edge case (score 45-65) hoặc theo yêu cầu
  người dùng ("Explain này").

Alternatives Considered:
  - LLM thuần: Rejected — latency/cost không chấp nhận được
  - Only Rule Engine: Rejected — không học được pattern mới
  - Self-hosted LLM (Ollama): Rejected — resource quá lớn

Consequences:
  + Inference < 10ms (so với 2-8s của LLM)
  + Zero API cost cho 95% requests
  + SHAP values → explainability built-in
  + Cần thêm task training + model serving (FastAPI endpoint)
  - Cần synthetic dataset cho DATN (không có real data)
  - Model cần retrain khi data drift (cron job hàng tháng)
```

---

### 11.2. Giải pháp Bổ sung #2: Approval Load Balancer & Bottleneck Prevention

#### Bối cảnh & Vấn đề

Plan hiện tại xử lý quá tải approver qua SLA escalation lên cấp trên. Nhưng trong thực tế:
- Escalation lên cấp trên **không giải quyết** bottleneck — nó làm cấp trên thêm bận.
- **Approver peer pool** (nhiều người cùng role duyệt được) là pattern phổ biến hơn trong SAP/ServiceNow.
- Khi một Trưởng phòng bị 15 request chờ, hệ thống nên **gợi ý** chuyển sang Phó phòng hoặc Trưởng phòng khác cùng quyền.

#### Giải pháp Đề xuất: Smart Approval Routing

```
┌────────────────────────────────────────────────┐
│          APPROVAL LOAD BALANCER                │
│                                                │
│  Khi Rule Engine trả về ApprovalChain:         │
│                                                │
│  1. Resolve Role → User Pool                   │
│     "dept_head" → [userA, userB, userC]        │
│                                                │
│  2. Score mỗi candidate:                       │
│     score = -0.5*queue_size                    │
│            + 0.3*(1 - avg_response_time_norm)  │
│            + 0.2*expertise_match               │
│                                                │
│  3. Chọn candidate cao nhất → Assigned         │
│                                                │
│  4. Realtime Monitoring:                       │
│     queue > THRESHOLD → hiện suggestion UI    │
│     "Chuyển sang [Phó phòng B]? (3 chờ vs 12)"│
│                                                │
│  5. Auto-Rebalance (optional, nếu cho phép):   │
│     queue > 2*THRESHOLD + SLA > 80% → tự động │
└────────────────────────────────────────────────┘
```

#### Schema Bổ sung

```sql
-- Bảng mới: approver_workload (materialized view hoặc cache)
CREATE TABLE approver_workload_cache (
  user_id UUID REFERENCES profiles(id),
  pending_count INTEGER DEFAULT 0,
  avg_response_time_hours FLOAT,
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Bảng mới: approver_pools (ai cùng role duyệt được)
CREATE TABLE approver_pools (
  id UUID PRIMARY KEY,
  pool_name TEXT,          -- e.g. "dept_head_accounting"
  request_type_ids UUID[], -- loại yêu cầu áp dụng
  member_ids UUID[],       -- danh sách user trong pool
  routing_strategy TEXT    -- 'round_robin' | 'least_loaded' | 'expertise'
);
```

#### UI Component: Workload Indicator

```
┌─────────────────────────────────────────────────────┐
│  👤 Nguyễn Trưởng Phòng   ████████████  12 chờ 🔴  │
│  👤 Lê Phó Phòng          ████          3 chờ  🟢  │
│                                                     │
│  💡 Gợi ý: Chuyển 5 yêu cầu sang Lê Phó Phòng?    │
│     [Chuyển ngay]  [Chỉ gợi ý, không tự động]      │
└─────────────────────────────────────────────────────┘
```

#### ADR-008 Chi tiết

```
# ADR-008: Approval Load Balancer thay vì chỉ Escalation

Status: Accepted
Date: 2026-09-12

Context:
  - SLA escalation trong plan hiện tại chuyển lên cấp trên
    → làm C-level bận hơn thay vì phân tải ngang
  - ServiceNow dùng "Work Item Queue" với capacity planning
  - SAP Workflow dùng "Substitution Rules" cho peer approval
  - Camunda BPM có "Candidate Group" pattern

Decision:
  Thêm Approver Pool concept: mỗi approval step có thể có
  nhiều candidate. Load Balancer chọn người ít việc nhất.
  Manager có thể xem workload dashboard và manually rebalance.

Alternatives Considered:
  - Chỉ escalation (plan hiện tại): Rejected — không phân tải,
    làm cấp trên quá tải
  - Round-robin thuần: Rejected — không tính đến response time
    và expertise
  - Manual assignment bởi admin: Rejected — bottleneck ở admin

Consequences:
  + SLA breach rate giảm khi approver pool có người rảnh
  + Manager visibility vào workload distribution
  + Cần thêm table: approver_pools, workload_cache
  + Cần thêm Celery task: cập nhật workload_cache mỗi 5 phút
  + Cần UI component: workload indicator trên Admin dashboard
```

---

### 11.3. Giải pháp Bổ sung #3: Policy-as-Code với OPA (Open Policy Agent)

#### Bối cảnh & Vấn đề

Plan hiện tại có Rule Engine (Python JSON rules) và Workflow Engine. Nhưng có một lớp logic thường bị bỏ quên: **Compliance Policy** — các quy định bất biến như:
- "Không ai được tự duyệt yêu cầu của chính mình" (Self-approval prohibition)
- "Yêu cầu > 100tr PHẢI có ít nhất 2 approver" (Four-eyes principle)
- "CFO phải ký nếu yêu cầu liên quan đến M&A"

Nhúng các quy tắc này trực tiếp vào Django sẽ làm code cứng nhắc, khó update khi quy định thay đổi.

**OPA (Open Policy Agent)** — được dùng bởi Netflix, Goldman Sachs, Atlassian — cho phép viết policy dạng **Rego code** tách biệt hoàn toàn khỏi application logic.

#### Giải pháp Đề xuất: OPA Sidecar

```
┌─────────────────────────────────────────────────────┐
│              POLICY EVALUATION FLOW                 │
│                                                     │
│  Django nhận action (approve/submit/delegate)       │
│       │                                             │
│       ▼                                             │
│  POST http://opa:8181/v1/data/approval/allow        │
│  {                                                  │
│    "input": {                                       │
│      "user": {"id": "...", "role": "dept_head"},    │
│      "request": {"id": "...", "requester_id": "...",│
│                  "amount": 150000000},               │
│      "action": "approve"                            │
│    }                                                │
│  }                                                  │
│       │                                             │
│       ▼ OPA evaluates Rego policies                 │
│  {"result": true/false, "reasons": [...]}           │
│       │                                             │
│  Django proceed/block + log policy decision         │
└─────────────────────────────────────────────────────┘
```

#### Ví dụ Rego Policies

```rego
# policies/approval.rego
package approval

import future.keywords.if
import future.keywords.in

# Policy 1: Không tự duyệt
default allow := false

deny["self_approval"] if {
  input.action == "approve"
  input.user.id == input.request.requester_id
}

# Policy 2: Four-eyes principle cho số tiền lớn
deny["four_eyes_required"] if {
  input.action == "approve"
  input.request.amount > 100000000
  count(input.request.approved_by) < 2
}

# Policy 3: Delegate không thể có quyền rộng hơn delegator
deny["delegation_scope_exceeded"] if {
  input.action == "delegate"
  input.delegation.scope not in input.delegator.allowed_scopes
}

# Policy 4: Approver phải ở đúng phòng ban
deny["wrong_department"] if {
  input.action == "approve"
  input.request.required_dept != input.user.department_id
  not is_admin(input.user)
}

allow if {
  count(deny) == 0
}
```

#### Kiến trúc Tích hợp

```yaml
# docker-compose.yml (bổ sung)
services:
  opa:
    image: openpolicyagent/opa:latest
    ports:
      - "8181:8181"
    command:
      - "run"
      - "--server"
      - "--addr=0.0.0.0:8181"
      - "/policies"
    volumes:
      - ./policies:/policies:ro  # Hot-reload policies không cần restart
    restart: unless-stopped
```

```python
# backend/core/policy_client.py
import httpx

class PolicyClient:
    OPA_URL = "http://opa:8181/v1/data/approval/allow"
    
    @classmethod
    def check(cls, user, request, action: str) -> tuple[bool, list[str]]:
        payload = {
            "input": {
                "user": {"id": str(user.id), "role": user.role,
                         "department_id": str(user.department_id)},
                "request": {"id": str(request.id),
                             "requester_id": str(request.requester_id),
                             "amount": float(request.data.get("amount", 0)),
                             "approved_by": [str(a.approver_id) 
                                            for a in request.approval_chain.all()
                                            if a.status == "approved"]},
                "action": action
            }
        }
        response = httpx.post(cls.OPA_URL, json=payload, timeout=0.5)
        result = response.json()
        return result.get("result", False), result.get("reasons", [])
```

#### ADR-009 Chi tiết

```
# ADR-009: OPA (Open Policy Agent) cho Compliance Policy Layer

Status: Accepted
Date: 2026-09-12

Context:
  - Compliance rules (four-eyes, self-approval ban) bị nhúng
    trực tiếp vào Django views → khó test riêng, khó update
  - Khi quy định thay đổi (Nghị định mới, audit requirement),
    phải deploy lại Django service
  - Netflix, Goldman Sachs, Atlassian dùng OPA cho authorization
  - OPA cho phép policy-as-code: test bằng unit test Rego,
    hot-reload không cần restart app

Decision:
  OPA chạy như sidecar container. Django gọi HTTP trước mọi
  action nhạy cảm (approve/reject/delegate/submit).
  Timeout 500ms → fail-open (log warning) hoặc fail-closed
  (tùy admin config).

Alternatives Considered:
  - Django middleware hard-code: Rejected — coupling cao,
    khó test policy độc lập
  - Casbin (Python): Rejected — model RBAC đơn giản hơn OPA,
    khó diễn đạt policy phức tạp như four-eyes
  - Nhúng vào Rule Engine: Rejected — Rule Engine là về
    routing/assignment, Policy Engine về compliance

Consequences:
  + Policies có thể update mà không deploy Django
  + Policies test được độc lập (opa test)
  + Audit trail riêng cho policy decisions
  + Thêm 1 container OPA trong docker-compose
  + Cần learning curve cho Rego syntax (1-2 ngày)
  + Latency thêm ~5-20ms per action (acceptable)
```

---

### 11.4. Giải pháp Bổ sung #4: ERP/HRM Integration via Webhook + Stub

#### Bối cảnh & Vấn đề

Một điểm yếu lớn của hệ thống approval độc lập: **Sau khi được duyệt, không có gì xảy ra trong hệ thống thực**. Ví dụ:
- Nghỉ phép được duyệt → số ngày phép trong HRM vẫn chưa trừ.
- Mua sắm được duyệt → hệ thống kế toán vẫn chưa ghi nhận.
- Cấp account được duyệt → IT vẫn phải tạo tay.

Các hệ thống enterprise (SAP, Oracle HCM, Odoo) giải quyết bằng **Event-Driven Integration** với webhook/message queue.

Trong DATN, dùng **ERP Stub (Mock Server)** để demo luồng end-to-end mà không cần hạ tầng thật.

#### Giải pháp Đề xuất: Event Bus + Adapter Pattern

```
┌────────────────────────────────────────────────────────┐
│                 INTEGRATION ARCHITECTURE                │
│                                                        │
│  Django Workflow Engine                                │
│       │ emit event on state change                     │
│       ▼                                                │
│  ┌─────────────┐                                       │
│  │ Event Bus   │ (Redis Pub/Sub hoặc Supabase Edge Fn) │
│  └──────┬──────┘                                       │
│         │ route by event_type                          │
│         ├──────────────────────────────────┐           │
│         ▼                                 ▼           │
│  ┌──────────────┐                 ┌──────────────┐    │
│  │ HRM Adapter  │                 │ ERP Adapter  │    │
│  │              │                 │              │    │
│  │ leave.approved                 │ purchase.ap- │    │
│  │ → POST /hrm  │                 │   proved     │    │
│  │   /deduct-   │                 │ → POST /erp  │    │
│  │   leave-days │                 │   /create-po │    │
│  └──────┬───────┘                 └──────┬───────┘    │
│         │                               │             │
│         ▼                               ▼             │
│  ┌──────────────┐                 ┌──────────────┐    │
│  │  HRM Stub    │                 │  ERP Stub    │    │
│  │  (FastAPI)   │                 │  (FastAPI)   │    │
│  │              │                 │              │    │
│  │ Returns mock │                 │ Returns mock │    │
│  │ HRM response │                 │ ERP response │    │
│  └──────────────┘                 └──────────────┘    │
└────────────────────────────────────────────────────────┘
```

#### Event Schema

```python
# Mỗi event được emit khi workflow transition
@dataclass
class WorkflowEvent:
    event_id: str          # UUID
    event_type: str        # "request.approved", "request.completed"
    request_id: str
    request_type: str      # "leave_request", "purchase_requisition"
    actor_id: str
    timestamp: str
    payload: dict          # Data cụ thể: {"days": 3, "employee_id": "..."}
    metadata: dict         # {"source": "workflow_engine", "version": "1"}
```

#### ERP Stub Implementation

```python
# services/erp_stub/main.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ERP Stub — Demo Only")

@app.post("/hrm/deduct-leave-days")
async def deduct_leave(data: dict):
    """Stub: Trừ ngày phép trong HRM"""
    print(f"[HRM STUB] Trừ {data['days']} ngày phép cho {data['employee_id']}")
    return {"status": "ok", "new_balance": 10 - data['days'],
            "stub": True, "message": "Demo only — not a real HRM system"}

@app.post("/erp/create-purchase-order")
async def create_po(data: dict):
    """Stub: Tạo PO trong hệ thống kế toán"""
    po_number = f"PO-{data['request_id'][:8].upper()}"
    return {"status": "ok", "po_number": po_number,
            "stub": True, "message": "Demo only — not a real ERP system"}

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "STUB"}
```

#### Webhook Configuration UI

Admin có thể cấu hình webhook endpoint cho từng loại yêu cầu:

| Sự kiện | Endpoint | Request Type áp dụng |
|---------|----------|---------------------|
| `request.approved` | `http://hrm-stub/hrm/deduct-leave-days` | leave_request |
| `request.completed` | `http://erp-stub/erp/create-purchase-order` | purchase_requisition |
| `request.approved` | `http://it-stub/it/provision-account` | account_request |

#### ADR-010 Chi tiết

```
# ADR-010: ERP/HRM Integration qua Webhook + Stub Server

Status: Accepted
Date: 2026-09-12

Context:
  - DATN cần demo luồng end-to-end để thuyết phục hội đồng
  - Không có hệ thống ERP/HRM thật để tích hợp
  - Real integration cần thương lượng với vendor (SAP, Oracle)
    → ngoài scope 8 tuần
  - Odoo và ERPNext có sẵn REST API → adapter pattern dễ thay
    sau khi demo

Decision:
  Xây dựng Adapter Layer với Webhook config trong DB.
  ERP Stub là FastAPI server trả về mock response.
  Production deployment sẽ thay URL stub bằng URL thật.
  Retry logic (Celery) đảm bảo at-least-once delivery.

Alternatives Considered:
  - Không tích hợp: Rejected — approval standalone thiếu
    thuyết phục về giá trị thực tế
  - Tích hợp thật với Odoo Community: Considered nhưng quá
    nhiều thời gian setup cho DATN timeline
  - Message Queue (RabbitMQ/Kafka): Rejected — over-engineering
    cho team 3 người, Redis Pub/Sub đủ dùng

Consequences:
  + Demo end-to-end thuyết phục (approval → HRM cập nhật)
  + Adapter pattern → thay stub bằng real URL dễ dàng
  + Retry logic đảm bảo không mất event
  + Thêm 1-2 stub FastAPI service vào docker-compose
  + Cần thêm bảng: webhook_configs, webhook_delivery_logs
```

---

## 12. So sánh với Hệ thống Tương tự (Reference Architectures)

> Phần này ghi lại cách các hệ thống enterprise nổi tiếng giải quyết bài toán tương tự, làm cơ sở để justify các quyết định thiết kế.

| Hệ thống | Workflow Engine | AI/Automation | Compliance | Integration | Điểm khác biệt so với EAS |
|----------|----------------|---------------|------------|-------------|---------------------------|
| **ServiceNow** | BPMN-based, no-code builder | ML triage, auto-routing | OPA-like rules built-in | 600+ connectors | Enterprise-grade nhưng đắt; EAS linh hoạt hơn cho SME |
| **SAP Workflow / Fiori** | BPMN 2.0, rigid | Rule-based scoring | Compliance framework | Native ERP | Tight coupling với SAP ERP; EAS vendor-agnostic |
| **Camunda BPM** | BPMN 2.0, CMMN | Ít AI built-in | External integration | REST/Kafka | Open-source nhưng Java-heavy; EAS Python-native |
| **Temporal.io** | Durable Execution | N/A | N/A | Code-first | Workflow as code, bền vững hơn; EAS có no-code builder |
| **Kissflow** | No-code drag-drop | Basic AI form fill | Limited | 50+ apps | SaaS, không customize được sâu; EAS self-hosted |
| **Odoo Approval** | Simple chained | Không có | Không có | Native Odoo | Module đơn giản; EAS có ML scoring & lifecycle templates |

### Điểm khác biệt (Differentiation) của Enterprise Approval System

1. **Lifecycle Role Model (4 vai trò)**: Hiếm hệ thống nào tách biệt Requester/Approver/Executor/Acceptor rõ ràng như vậy.
2. **3 Lifecycle Templates**: Linh hoạt hơn BPMN rigid nhưng ít phức tạp hơn — phù hợp SME.
3. **AI Explainability**: Risk score có explanation list — vượt trội so với Kissflow/Odoo.
4. **Policy-as-Code (OPA)**: Ít hệ thống SME nào tích hợp compliance layer riêng.
5. **Hash-chain Audit**: Immutable audit log — tính năng thường chỉ có ở enterprise-tier.

---

## 13. Risks Bổ sung (Updated Risk Register)

| Risk | Impact | Mitigation | Liên quan đến |
|------|--------|------------|---------------|
| OPA timeout ảnh hưởng UX | 🟡 Medium | Timeout 500ms, fail-open với warning log | ADR-009 |
| XGBoost model drift theo thời gian | 🟡 Medium | Cron job retrain hàng tháng; accuracy monitoring | ADR-007 |
| Webhook delivery thất bại | 🟡 Medium | Celery retry với exponential backoff (tối đa 5 lần) | ADR-010 |
| Approver pool config sai → yêu cầu không ai nhận | 🔴 High | Validation khi save pool; fallback về admin notification | ADR-008 |
| OPA Rego syntax khó học trong 8 tuần | 🟡 Medium | Chỉ implement 4-5 policies đơn giản cho MVP | ADR-009 |

---

## 14. Chi tiết Module — Interactions, APIs & Responsibilities

> Phần này mô tả chi tiết **từng module**: trách nhiệm, input/output, dependency với module khác, và các API endpoint chính. Đây là tài liệu kỹ thuật cho cả team khi implement.

---

### 14.1. Module Map — Tương tác giữa các Module

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                  WEB CLIENT / MOBILE                   │
                    │  (React + Vite — 4 Tabs: Requester/Approver/Executor/  │
                    │   Acceptor + Admin Panel + Dashboard)                  │
                    └────────────────────────┬────────────────────────────────┘
                                             │ HTTP/WebSocket
                                             ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │               API GATEWAY (Nginx)                      │
                    │  Rate limiting · SSL termination · Route /api → Django │
                    │                        /ai → FastAPI                   │
                    └────────┬───────────────────────────────┬───────────────┘
                             │                               │
                    ┌────────▼───────────┐       ┌──────────▼──────────┐
                    │  DJANGO API CORE   │       │  FASTAPI AI SERVICE │
                    │                   │◄──────►│                     │
                    │ ┌───────────────┐ │ REST   │ - OCR               │
                    │ │Identity Mod.  │ │        │ - Summarize         │
                    │ ├───────────────┤ │        │ - Risk Scoring      │
                    │ │Request Mod.   │ │        │ - Auto-Approve      │
                    │ ├───────────────┤ │        └─────────────────────┘
                    │ │Workflow Eng.  │ │
                    │ ├───────────────┤ │        ┌─────────────────────┐
                    │ │Rule Engine    │ │        │  OPA SIDECAR        │
                    │ ├───────────────┤ │◄──────►│  (Compliance check) │
                    │ │Audit Module   │ │ HTTP   └─────────────────────┘
                    │ ├───────────────┤ │
                    │ │Notif. Module  │ │        ┌─────────────────────┐
                    │ ├───────────────┤ │        │  ERP/HRM STUBS      │
                    │ │LoadBalancer   │ │◄──────►│  (Webhook targets)  │
                    │ ├───────────────┤ │ HTTP   └─────────────────────┘
                    │ │Signature Mod. │ │
                    │ ├───────────────┤ │        ┌─────────────────────┐
                    │ │Analytics Mod. │ │        │  CELERY WORKERS     │
                    │ └───────────────┘ │◄──────►│  - SLA Monitor      │
                    └────────┬──────────┘ Queue  │  - Notifications    │
                             │                   │  - Webhook Delivery │
                    ┌────────▼──────────┐        └─────────────────────┘
                    │  SUPABASE (BaaS)  │
                    │  - PostgreSQL DB  │        ┌─────────────────────┐
                    │  - Auth/JWT       │◄──────►│  REDIS              │
                    │  - Realtime WS    │        │  - Celery broker    │
                    │  - Storage (files)│        │  - Cache layer      │
                    │  - Edge Functions │        │  - Pub/Sub events   │
                    └───────────────────┘        └─────────────────────┘
```

---

### 14.2. Module 1: Identity & Organization (Định danh & Tổ chức)

#### Trách nhiệm
Quản lý toàn bộ định danh người dùng, cây tổ chức, phân quyền, và chính sách ủy quyền.

#### Entities
```
Profile (extends Supabase auth.users):
  id: UUID (= auth.users.id)
  full_name: str
  email: str
  department_id: FK → Department
  role: enum [staff, dept_head, director, cfo, ceo, admin, it]
  position: str
  absence_status: enum [present, on_leave, sick]
  avatar_url: str | None
  created_at: timestamp

Department:
  id: UUID
  name: str
  parent_id: FK → Department | None   ← cây phòng ban
  head_user_id: FK → Profile
  budget_limit: decimal | None

DelegationPolicy:
  id: UUID
  delegator_id: FK → Profile
  delegate_id: FK → Profile
  start_date: date
  end_date: date
  scope: enum [ALL] | list[request_type_id]
  is_active: bool

ApproverPool (ADR-008):
  id: UUID
  pool_name: str
  request_type_ids: UUID[]
  member_ids: UUID[]
  routing_strategy: enum [round_robin, least_loaded, expertise]
```

#### APIs
```
GET  /api/identity/profile/me/              → Profile của current user
GET  /api/identity/profiles/                → Danh sách (admin only)
PUT  /api/identity/profile/me/absence/      → Set absence_status
GET  /api/identity/departments/             → Cây phòng ban
POST /api/identity/delegation/              → Tạo DelegationPolicy
GET  /api/identity/delegation/active/       → Delegation đang active
DELETE /api/identity/delegation/{id}/
POST /api/identity/approver-pools/          → Tạo Approver Pool
GET  /api/identity/approver-pools/          → Danh sách pools
PUT  /api/identity/approver-pools/{id}/
```

#### Logic chính: Auto-Delegation
```python
def resolve_approver(role: str, department_id: UUID) -> Profile:
    """
    Tìm approver cho một role trong một department.
    Kiểm tra delegation → trả về delegate nếu đang vắng.
    """
    candidate = Profile.objects.get(
        role=role, department_id=department_id
    )
    
    # Kiểm tra có delegation active không
    delegation = DelegationPolicy.objects.filter(
        delegator=candidate,
        start_date__lte=today,
        end_date__gte=today,
        is_active=True
    ).first()
    
    if delegation:
        return delegation.delegate
    
    # Kiểm tra absence status
    if candidate.absence_status != "present":
        # Fallback: load balancer chọn từ pool
        return LoadBalancerModule.pick_from_pool(role, department_id)
    
    return candidate
```

#### Dependencies
- **Supabase Auth**: xác thực JWT, quản lý session
- **Notification Module**: gửi thông báo khi delegation được tạo/hết hạn

---

### 14.3. Module 2: Request Management (Quản lý Yêu cầu)

#### Trách nhiệm
Tạo, lưu nháp, chỉnh sửa, upload file đính kèm, và tracking trạng thái yêu cầu.

#### Entities
```
Request:
  id: UUID
  requester_id: FK → Profile
  request_type_id: FK → RequestType
  status: enum [DRAFT, EVALUATING, AUTO_APPROVED, PENDING_APPROVAL,
                NEEDS_INFO, IN_PROGRESS, EXECUTED, COMPLETED,
                REJECTED, CANCELLED, EXECUTION_REJECTED, ACCEPTANCE_REJECTED]
  data: JSONB                     ← form data theo request_type.form_schema
  risk_score: int | None          ← 0-100 từ AI Service
  risk_level: enum [LOW, MEDIUM, HIGH, CRITICAL] | None
  lifecycle_template: enum [A, B, C] | None
  workflow_definition_id: FK → WorkflowDefinition | None
  priority: enum [URGENT, NORMAL, LOW] = NORMAL
  title: str                      ← auto-generated từ request_type + data
  submitted_at: timestamp | None
  completed_at: timestamp | None
  created_at: timestamp
  updated_at: timestamp

RequestType:
  id: UUID
  name: str
  category: enum [finance, hr, it, ops]
  risk_weight: int (1-5)
  lifecycle_template: enum [A, B, C]
  acceptor_type: enum [requester, approver, none]
  form_schema: JSONB              ← JSON Schema cho dynamic form
  workflow_definition_id: FK → WorkflowDefinition | None
  sla_hours: int = 24
  is_active: bool

Attachment:
  id: UUID
  request_id: FK → Request
  uploader_id: FK → Profile
  file_url: str                   ← Supabase Storage URL
  file_name: str
  file_type: str                  ← MIME type
  file_size_kb: int
  extracted_data: JSONB | None    ← OCR result
  uploaded_at: timestamp

Comment:
  id: UUID
  request_id: FK → Request
  author_id: FK → Profile
  content: text
  created_at: timestamp
  is_internal: bool               ← True = chỉ approver thấy
```

#### APIs
```
POST   /api/requests/                         → Tạo draft
GET    /api/requests/{id}/                    → Chi tiết yêu cầu
PUT    /api/requests/{id}/                    → Cập nhật draft
POST   /api/requests/{id}/submit/             → Gửi yêu cầu (DRAFT → EVALUATING)
POST   /api/requests/{id}/cancel/             → Hủy (chỉ Requester, chỉ ở DRAFT)
GET    /api/requests/my-requests/             → Tab 📝 của current user
GET    /api/requests/pending-approval/        → Tab ✅ của current user
GET    /api/requests/pending-execution/       → Tab 🔧 của current user
GET    /api/requests/pending-acceptance/      → Tab 🔍 của current user
GET    /api/requests/search/?q=&status=&type= → Search + filter
POST   /api/requests/{id}/attachments/        → Upload file
GET    /api/requests/{id}/attachments/        → Danh sách file
POST   /api/requests/{id}/comments/           → Thêm comment
GET    /api/requests/{id}/comments/           → Thread comments
GET    /api/requests/{id}/timeline/           → Lịch sử trạng thái
GET    /api/requests/{id}/export-pdf/         → Xuất PDF
```

#### Dynamic Form Schema (ví dụ)
```json
{
  "leave_request": {
    "fields": [
      {"name": "start_date", "type": "date", "label": "Ngày bắt đầu", "required": true},
      {"name": "end_date", "type": "date", "label": "Ngày kết thúc", "required": true},
      {"name": "leave_type", "type": "select", "label": "Loại nghỉ",
       "options": ["Nghỉ phép năm", "Nghỉ ốm", "Nghỉ không lương"],
       "required": true},
      {"name": "reason", "type": "textarea", "label": "Lý do", "required": false},
      {"name": "handover_to", "type": "user_picker", "label": "Bàn giao công việc cho"}
    ],
    "computed": [
      {"name": "days", "formula": "date_diff(end_date, start_date) + 1"}
    ]
  }
}
```

#### Dependencies
- **Identity Module**: validate requester, check permissions
- **Workflow Engine**: kích hoạt khi submit
- **AI Service**: OCR khi upload file, Risk Scoring khi submit
- **Audit Module**: log mọi thay đổi trạng thái
- **Notification Module**: gửi thông báo khi submit/update
- **Supabase Storage**: lưu file đính kèm

---

### 14.4. Module 3: Workflow Engine (Điều phối Quy trình)

#### Trách nhiệm
Đọc Workflow Definition JSON, điều khiển transitions giữa các trạng thái, xử lý tất cả loại node.

#### Entities
```
WorkflowDefinition:
  id: UUID
  name: str
  description: str
  json_schema: JSONB     ← Serialized React Flow graph
  version: int
  is_active: bool
  created_by: FK → Profile
  created_at: timestamp

WorkflowInstance:
  id: UUID
  request_id: FK → Request (1:1)
  definition_id: FK → WorkflowDefinition
  current_node_id: str   ← ID node hiện tại trong JSON graph
  context: JSONB         ← Variables: {amount, requester_dept, risk_score...}
  started_at: timestamp
  completed_at: timestamp | None
```

#### Node Types & Logic
```
Node Types trong Workflow JSON:
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  StartNode          → Điểm khởi đầu, không có logic        │
│                                                             │
│  ApprovalNode       → Chỉ định approver (role/person/dept)  │
│    config:                                                  │
│      approver_role: "dept_head"                             │
│      approver_pool_id: UUID | null                          │
│      timeout_hours: 24                                      │
│      require_signature: bool  (true nếu risk ≥ 4)          │
│                                                             │
│  ConditionNode      → Rẽ nhánh theo điều kiện              │
│    config:                                                  │
│      condition: "context.amount > 50000000"                 │
│      true_edge: node_id_A                                   │
│      false_edge: node_id_B                                  │
│                                                             │
│  ParallelNode       → Fork ra nhiều nhánh đồng thời        │
│    config:                                                  │
│      branches: [node_id_1, node_id_2, node_id_3]           │
│      consensus: "ALL" | "ANY" | "MAJORITY"                  │
│      join_node: node_id_join                                │
│                                                             │
│  ExecutionNode      → Chỉ định Executor                    │
│    config:                                                  │
│      executor_department: "procurement"                     │
│      timeout_hours: 48                                      │
│                                                             │
│  AcceptanceNode     → Chỉ định Acceptor                    │
│    config:                                                  │
│      acceptor_type: "requester" | "approver" | "custom"     │
│      timeout_hours: 24                                      │
│                                                             │
│  ActionNode         → Side effects (không block workflow)  │
│    config:                                                  │
│      action_type: "send_email" | "call_webhook" | "notify"  │
│      payload: {...}                                         │
│                                                             │
│  EndNode            → Kết thúc với outcome                 │
│    config:                                                  │
│      outcome: "COMPLETED" | "REJECTED"                     │
└─────────────────────────────────────────────────────────────┘
```

#### Core Engine Interface
```python
class WorkflowEngine:
    
    @staticmethod
    def start(request: Request, definition: WorkflowDefinition) -> WorkflowInstance:
        """Khởi tạo workflow instance từ request đã được evaluate."""
        instance = WorkflowInstance.objects.create(
            request=request,
            definition=definition,
            current_node_id="start",
            context={
                "amount": request.data.get("amount", 0),
                "requester_dept": str(request.requester.department_id),
                "risk_score": request.risk_score,
                "lifecycle_template": request.lifecycle_template,
            }
        )
        return WorkflowEngine._advance(instance, "start")
    
    @staticmethod
    def transition(instance: WorkflowInstance,
                   action: str,          # "approve" | "reject" | "execute" | ...
                   actor: Profile,
                   payload: dict) -> WorkflowInstance:
        """
        Xử lý một action từ user.
        1. Validate action hợp lệ tại node hiện tại
        2. Policy check (OPA)
        3. Ghi audit log
        4. Advance sang node tiếp theo
        """
        node = WorkflowEngine._get_current_node(instance)
        
        # 1. Validate
        if not node.accepts_action(action):
            raise InvalidTransitionError(f"{action} not valid at {node.type}")
        
        # 2. Policy check
        allowed, reasons = PolicyClient.check(actor, instance.request, action)
        if not allowed:
            raise PolicyViolationError(reasons)
        
        # 3. Audit
        AuditChain.log(instance.request, actor, action, payload)
        
        # 4. Advance
        next_node_id = node.get_next(action, instance.context)
        instance.current_node_id = next_node_id
        instance.save()
        
        return WorkflowEngine._advance(instance, next_node_id)
    
    @staticmethod
    def _advance(instance: WorkflowInstance, node_id: str) -> WorkflowInstance:
        """
        Xử lý logic tại node hiện tại.
        - ActionNode: thực hiện side effect ngay
        - ConditionNode: evaluate điều kiện, tự động đến node tiếp
        - ApprovalNode, ExecutionNode, AcceptanceNode: assign actor, đợi action
        - EndNode: set request.status = outcome
        """
        ...
```

#### APIs
```
GET  /api/workflows/definitions/            → Danh sách workflow definitions
POST /api/workflows/definitions/            → Tạo mới (save từ React Flow)
GET  /api/workflows/definitions/{id}/       → Chi tiết + JSON schema
PUT  /api/workflows/definitions/{id}/       → Cập nhật
GET  /api/workflows/instances/{request_id}/ → Instance đang chạy của request
```

#### Dependencies
- **Rule Engine**: cung cấp context (lifecycle template, assignments)
- **Identity Module**: resolve approver/executor/acceptor
- **Load Balancer Module**: chọn approver khi có pool
- **Audit Module**: log mọi transition
- **Notification Module**: gửi thông báo sau mỗi transition
- **OPA Sidecar**: policy check trước mỗi action
- **ERP Integration Module**: trigger webhook khi EndNode

---

### 14.5. Module 4: Business Rule Engine (Đánh giá Luật Nghiệp vụ)

#### Trách nhiệm
Evaluate rules để xác định ApprovalChain, Lifecycle Template, Executor/Acceptor, và SLA khi request được submit.

#### Entities
```
Rule:
  id: UUID
  name: str
  description: str
  conditions: JSONB    ← Danh sách conditions (AND logic)
  actions: JSONB       ← Danh sách actions
  priority: int        ← Thứ tự ưu tiên khi nhiều rule match (cao = ưu tiên)
  is_active: bool
  created_by: FK → Profile

Condition:
  field: str           ← "request_type", "amount", "requester_role",...
  operator: enum [==, !=, >, <, >=, <=, in, not_in, contains]
  value: any

Action:
  type: enum [set_lifecycle, add_approver, assign_executor,
              assign_acceptor, set_sla, set_risk_weight, flag_ai_approve]
  params: dict
```

#### Evaluation Flow
```python
@dataclass
class EvaluationResult:
    lifecycle_template: Literal["A", "B", "C"]
    approval_chain: list[ApproverAssignment]   # Ordered list, level 1..N
    executor_dept: str | None
    acceptor_type: str | None                  # "requester" | "approver" | None
    sla_hours: int
    ai_auto_approve: bool
    matched_rules: list[str]                   # Tên các rules đã match

class RuleEngine:
    
    @classmethod
    def evaluate(cls, request_data: dict, requester: Profile) -> EvaluationResult:
        """
        1. Lấy tất cả active rules, sort theo priority DESC
        2. Evaluate từng rule → collect tất cả rules match
        3. Merge actions từ các rules match (higher priority wins conflict)
        4. Trả về EvaluationResult
        """
        active_rules = Rule.objects.filter(is_active=True).order_by("-priority")
        
        result_builder = ResultBuilder()
        matched = []
        
        for rule in active_rules:
            if cls._evaluate_conditions(rule.conditions, request_data, requester):
                matched.append(rule.name)
                result_builder.apply_actions(rule.actions, rule.priority)
        
        return result_builder.build(matched)
    
    @classmethod
    def _evaluate_conditions(cls, conditions: list, data: dict,
                              requester: Profile) -> bool:
        """AND logic: tất cả conditions phải true."""
        context = {
            **data,
            "requester_role": requester.role,
            "requester_dept": str(requester.department_id),
            "requester_tenure_days": (today - requester.created_at.date()).days,
        }
        
        return all(
            cls._evaluate_single(cond, context)
            for cond in conditions
        )
    
    OPERATORS = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">":  lambda a, b: float(a) > float(b),
        "<":  lambda a, b: float(a) < float(b),
        ">=": lambda a, b: float(a) >= float(b),
        "<=": lambda a, b: float(a) <= float(b),
        "in": lambda a, b: a in b,
        "not_in": lambda a, b: a not in b,
        "contains": lambda a, b: b in str(a),
    }
```

#### Conflict Detection (UI)
```
Khi Admin save rule mới, system tự detect conflict:
- Hai rules cùng match → cùng field action → priority khác nhau → WARNING
- Circular dependency (rất hiếm nhưng validate) → ERROR

UI hiển thị:
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ Conflict Detection                                       │
│                                                             │
│ Rule "Leave < 3 days → AI Auto" (priority 10)              │
│ Rule "Leave any → Manual" (priority 5)                      │
│                                                             │
│ → Khi leave < 3 days: Rule priority 10 thắng → AI Auto     │
│   (Hành vi mong đợi? Xác nhận để lưu)                     │
└─────────────────────────────────────────────────────────────┘
```

#### APIs
```
GET  /api/rules/                     → Danh sách rules
POST /api/rules/                     → Tạo rule mới
PUT  /api/rules/{id}/
DELETE /api/rules/{id}/
POST /api/rules/preview/             → Preview: evaluate với sample data
POST /api/rules/detect-conflicts/    → Detect conflicts trong rule set
```

#### Dependencies
- **Identity Module**: lấy thông tin requester (role, dept, tenure)
- **Workflow Engine**: nhận EvaluationResult để start workflow

---

### 14.6. Module 5: AI Assistant Service (FastAPI)

#### Trách nhiệm
4 AI capabilities độc lập, expose qua FastAPI, giao tiếp async với Django.

#### Architecture nội bộ
```
FastAPI AI Service
├── routers/
│   ├── ocr.py          → POST /ai/ocr
│   ├── summarize.py    → POST /ai/summarize
│   ├── risk_score.py   → POST /ai/risk-score
│   └── auto_approve.py → POST /ai/auto-approve
├── ml/
│   ├── risk_model.pkl  ← Trained XGBoost model
│   ├── train.py        ← Training script (offline)
│   └── features.py     ← Feature extraction
├── services/
│   ├── ocr_service.py  ← PaddleOCR
│   ├── llm_service.py  ← Gemini API client
│   └── rule_scorer.py  ← Rule-based scoring logic
└── main.py
```

#### API Contracts

**OCR Endpoint**
```
POST /ai/ocr
Content-Type: multipart/form-data
Body: file (ảnh hóa đơn / PDF)

Response:
{
  "extracted_fields": {
    "vendor_name": "Công ty ABC",
    "amount": 15000000,
    "date": "2026-09-10",
    "items": [{"name": "Laptop Dell", "qty": 1, "price": 15000000}]
  },
  "confidence": 0.92,
  "raw_text": "...",
  "processing_time_ms": 450
}
```

**Summarize Endpoint**
```
POST /ai/summarize
Body: {
  "request_id": "...",
  "content": "... nội dung yêu cầu dài ...",
  "context": {"requester_name": "Trần Thị B", "request_type": "leave"}
}

Response:
{
  "summary": "Trần Thị B xin nghỉ phép 3 ngày (10-12/09) để chăm sóc gia đình.",
  "key_points": ["3 ngày", "có bàn giao cho Nguyễn C"],
  "language": "vi"
}
```

**Risk Score Endpoint**
```
POST /ai/risk-score
Body: {
  "request_id": "...",
  "request_type": "purchase_requisition",
  "data": {"amount": 45000000, "vendor": "ABC Corp"},
  "requester_id": "...",
  "context": {
    "dept_avg_amount": 14000000,
    "requester_approval_rate_30d": 0.94,
    "vendor_age_days": 15,
    "budget_remaining_ratio": 0.3
  }
}

Response:
{
  "risk_score": 72,
  "risk_level": "HIGH",          ← LOW/MEDIUM/HIGH/CRITICAL
  "confidence": 0.84,
  "auto_approve_eligible": false,
  "explanation": [
    {"factor": "amount_vs_dept_avg", "impact": "+28",
     "detail": "Số tiền 45tr cao hơn 3.2x mức trung bình phòng"},
    {"factor": "new_vendor", "impact": "+15",
     "detail": "Vendor mới tạo 15 ngày trước"},
    {"factor": "requester_history", "impact": "-8",
     "detail": "Người yêu cầu có lịch sử duyệt tốt (94%)"}
  ],
  "scoring_method": "hybrid_rule_xgboost"  ← hoặc "rule_based"
}
```

**Auto-Approve Endpoint**
```
POST /ai/auto-approve
Body: {
  "request_id": "...",
  "risk_score": 18,
  "lifecycle_template": "A",
  "data": {"leave_type": "annual", "days": 2, "employee_leave_balance": 8}
}

Response:
{
  "decision": "APPROVED" | "ESCALATE",
  "reason": "Quỹ phép đủ (8 ngày còn lại), không có bất thường",
  "checks_passed": ["leave_balance_ok", "no_conflict_with_team", "frequency_normal"],
  "checks_failed": [],
  "confidence": 0.97
}
```

#### Dependencies
- **Supabase**: đọc lịch sử request của requester (feature extraction)
- **Redis**: cache risk score (TTL 5 phút) để không tính lại khi refresh

---

### 14.7. Module 6: Audit & Compliance (Kiểm toán)

#### Trách nhiệm
Ghi nhận bất biến mọi action theo hash-chain SHA-256. Là "hộp đen" của hệ thống — không thể sửa.

#### Hash Chain Algorithm
```python
def compute_hash(prev_hash: str, entry: AuditEntry) -> str:
    """
    Hash chain: mỗi entry phụ thuộc vào entry trước.
    Tamper bất kỳ entry → chain sau đó invalid.
    """
    data = "|".join([
        prev_hash,
        entry.entity_type,
        str(entry.entity_id),
        entry.action,
        str(entry.actor_id),
        entry.timestamp.isoformat(),
        json.dumps(entry.old_value, sort_keys=True),
        json.dumps(entry.new_value, sort_keys=True),
        entry.rejection_reason or "",
    ])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
```

#### Audit Log Entry Structure
```
AuditLog:
  id: UUID
  entity_type: str          ← "request" | "approval_chain" | "rule" | ...
  entity_id: UUID
  action: str               ← "submitted" | "approved" | "rejected" | "executed" | ...
  actor_id: FK → Profile
  old_value: JSONB | None   ← Trạng thái trước
  new_value: JSONB          ← Trạng thái sau
  rejection_reason: str | None
  policy_decisions: JSONB | None  ← OPA policy check results
  timestamp: timestamp
  hash: str (SHA-256)       ← Hash của entry này
  prev_hash: str            ← Hash của entry trước (chuỗi liên kết)
  ip_address: str | None
  user_agent: str | None
```

#### Verify API
```
GET /api/audit/verify/{request_id}/
Response:
{
  "is_valid": true | false,
  "total_entries": 12,
  "first_entry_id": "...",
  "last_entry_id": "...",
  "broken_at": null | { "entry_id": "...", "position": 7 }
}
```

#### APIs
```
GET /api/audit/logs/?entity_id=&actor_id=&action=&from=&to=
GET /api/audit/logs/{request_id}/           → Audit trail của 1 request
GET /api/audit/verify/{request_id}/         → Verify hash chain integrity
GET /api/audit/rejections/?reason_contains= → Search theo lý do từ chối
```

#### Quan trọng: Write-Only
```python
class AuditChain:
    """
    AuditLog là WRITE-ONLY. Không bao giờ UPDATE hoặc DELETE.
    Signal: sau mỗi Request.save() → auto-log nếu status thay đổi.
    """
    
    @classmethod
    def log(cls, request: Request, actor: Profile,
            action: str, payload: dict) -> AuditLog:
        
        last_entry = AuditLog.objects.filter(
            entity_id=request.id
        ).order_by("-timestamp").first()
        
        prev_hash = last_entry.hash if last_entry else "GENESIS"
        
        entry = AuditLog(
            entity_type="request",
            entity_id=request.id,
            action=action,
            actor=actor,
            new_value=payload,
            rejection_reason=payload.get("rejection_reason"),
            timestamp=now(),
            prev_hash=prev_hash,
        )
        entry.hash = compute_hash(prev_hash, entry)
        entry.save()
        return entry
```

---

### 14.8. Module 7: SLA Monitoring & Notification

#### Trách nhiệm
Theo dõi thời gian xử lý tại mỗi bước, gửi nhắc nhở/escalation, phân phối thông báo đa kênh.

#### SLA Logic
```
SLA Monitoring (Celery Beat — chạy mỗi 15 phút):
┌──────────────────────────────────────────────────────────┐
│  Với mỗi request đang IN-PROGRESS:                       │
│                                                          │
│  elapsed = now() - step_started_at                       │
│  sla_total = step.sla_hours                              │
│  ratio = elapsed / sla_total                             │
│                                                          │
│  ratio < 0.5  → Bình thường, không làm gì               │
│  ratio ≥ 0.5  → Level 1: Gửi reminder cho actor hiện tại│
│  ratio ≥ 1.0  → Level 2: Escalation                     │
│                   + Gửi alert cho manager của actor      │
│                   + Ghi WARN vào audit log               │
│                   + Chuyển Approver Pool (nếu có)        │
└──────────────────────────────────────────────────────────┘
```

#### Notification Channels
```python
class NotificationService:
    
    @classmethod
    def notify(cls, event: str, recipients: list[Profile],
                request: Request, extra: dict = {}):
        """
        Gửi thông báo qua TẤT CẢ kênh đã được cấu hình.
        Không block — mọi thứ chạy qua Celery.
        """
        tasks.send_notification.delay(
            event=event,
            recipient_ids=[str(r.id) for r in recipients],
            request_id=str(request.id),
            extra=extra,
        )

# tasks.py (Celery)
@app.task(bind=True, max_retries=3)
def send_notification(self, event, recipient_ids, request_id, extra):
    recipients = Profile.objects.filter(id__in=recipient_ids)
    
    for recipient in recipients:
        # 1. In-app (Supabase INSERT → Realtime push to browser)
        Notification.objects.create(
            user=recipient, event=event, request_id=request_id, ...
        )
        
        # 2. Email (SMTP async)
        send_email_task.delay(recipient.email, event, request_id)
        
        # 3. Push notification (FCM — nếu có mobile token)
        if recipient.fcm_token:
            send_push_task.delay(recipient.fcm_token, event)
```

#### Event Types & Templates

| Event | Gửi cho | Kênh |
|-------|---------|------|
| `request.submitted` | Approver L1 | In-app + Email |
| `request.approved` | Requester, Next approver | In-app + Email |
| `request.rejected` | Requester | In-app + Email |
| `request.needs_info` | Requester | In-app + Email |
| `request.execution_ready` | Executor | In-app + Email |
| `request.acceptance_ready` | Acceptor | In-app + Email |
| `request.completed` | Requester, All actors | In-app |
| `sla.reminder` | Actor hiện tại | In-app + Email |
| `sla.escalation` | Actor + Manager | In-app + Email |
| `ai.auto_approved` | Approver (để review) | In-app |
| `delegation.activated` | Delegate | In-app + Email |

#### APIs
```
GET  /api/notifications/               → Danh sách notification của current user
POST /api/notifications/{id}/read/     → Đánh dấu đã đọc
POST /api/notifications/read-all/      → Đánh dấu tất cả đã đọc
GET  /api/notifications/unread-count/  → Badge count (cũng qua Realtime)
```

---

### 14.9. Module 8: Approval Load Balancer (ADR-008)

#### Trách nhiệm
Phân phối yêu cầu phê duyệt công bằng khi có nhiều Approver cùng role. Ngăn bottleneck.

#### Scoring Algorithm
```python
class LoadBalancerModule:
    
    WEIGHTS = {
        "queue_size":          -0.50,   # Số request đang chờ (càng ít càng tốt)
        "avg_response_time":   +0.30,   # Response time nhanh (normalized 0-1)
        "expertise_match":     +0.20,   # Match với loại request này
    }
    
    @classmethod
    def pick_from_pool(cls, pool_id: UUID, request: Request) -> Profile:
        pool = ApproverPool.objects.get(id=pool_id)
        candidates = Profile.objects.filter(id__in=pool.member_ids,
                                             absence_status="present")
        
        if not candidates:
            raise NoAvailableApproverError(f"Pool {pool.pool_name} empty")
        
        scores = {}
        for c in candidates:
            workload = ApproverWorkloadCache.objects.get(user=c)
            scores[c.id] = (
                cls.WEIGHTS["queue_size"] * workload.pending_count
                + cls.WEIGHTS["avg_response_time"] * (
                    1 - min(workload.avg_response_time_hours / 24, 1)
                )
                + cls.WEIGHTS["expertise_match"] * cls._expertise_score(c, request)
            )
        
        best_id = max(scores, key=scores.get)
        return candidates.get(id=best_id)
    
    @classmethod
    def get_rebalance_suggestions(cls, pool_id: UUID) -> list[Suggestion]:
        """Dashboard: gợi ý rebalance nếu có chênh lệch > threshold."""
        ...
```

#### Workload Cache (cập nhật mỗi 5 phút qua Celery)
```python
@app.task
def update_workload_cache():
    for profile in Profile.objects.filter(role__in=APPROVER_ROLES):
        pending = Request.objects.filter(
            current_approver=profile,
            status__startswith="PENDING_APPROVAL"
        ).count()
        
        avg_time = ApprovalChain.objects.filter(
            approver=profile,
            status="approved"
        ).aggregate(avg=Avg(F("decided_at") - F("assigned_at")))["avg"]
        
        ApproverWorkloadCache.objects.update_or_create(
            user=profile,
            defaults={
                "pending_count": pending,
                "avg_response_time_hours": avg_time.total_seconds() / 3600
                    if avg_time else None,
                "last_updated": now(),
            }
        )
```

---

### 14.10. Module 9: Digital Signature & PDF Export

#### Trách nhiệm
Thu thập chữ ký số cho approval quan trọng (risk ≥ 4). Xuất PDF quyết định.

#### Signature Flow
```
Trigger: ApprovalNode với require_signature=True (risk_weight ≥ 4)

Web:
  1. Modal mở react-signature-canvas
  2. User ký tay bằng chuột/touchpad
  3. Canvas → base64 PNG → POST /api/signatures/
  4. Backend: SHA-256(base64) → lưu vào approval_chain.signature_hash
  5. Supabase Storage: lưu ảnh gốc tại /signatures/{request_id}/{approver_id}.png

Verification:
  SHA-256(stored_base64) == approval_chain.signature_hash → Valid
```

#### PDF Export Template
```
┌─────────────────────────────────────────────────────────────┐
│           QUYẾT ĐỊNH PHÊ DUYỆT                              │
│           [LOGO CÔNG TY]                                    │
├─────────────────────────────────────────────────────────────┤
│ Mã yêu cầu: REQ-2026-001234                                 │
│ Loại: Yêu cầu mua sắm — Laptop Dell                        │
│ Người yêu cầu: Trần Thị B (Phòng IT)                       │
│ Ngày tạo: 10/09/2026                                        │
├─────────────────────────────────────────────────────────────┤
│ LỊCH SỬ PHÊ DUYỆT                                          │
│                                                             │
│ ✅ L1: Nguyễn Trưởng Phòng — 11/09/2026 09:15             │
│    "Đồng ý, trong ngân sách Q3"                             │
│    [CHỮ KÝ SỐ ẢNH]                                         │
│                                                             │
│ ✅ L2: Lê Giám đốc — 11/09/2026 14:30                     │
│    "Duyệt"                                                  │
│    [CHỮ KÝ SỐ ẢNH]                                         │
├─────────────────────────────────────────────────────────────┤
│ AUDIT HASH: 3f8a9b2c1d...e7f4                               │
│ Xác minh tại: https://system/api/audit/verify/REQ-001234   │
└─────────────────────────────────────────────────────────────┘
```

#### APIs
```
POST /api/signatures/                → Lưu chữ ký (base64 PNG)
GET  /api/signatures/{chain_id}/     → Lấy ảnh chữ ký
GET  /api/requests/{id}/export-pdf/  → Xuất PDF (stream)
```

---

### 14.11. Module 10: Analytics & Dashboard

#### Trách nhiệm
Cung cấp dữ liệu KPI cho Manager/Admin dashboard.

#### Queries & Metrics
```python
class AnalyticsService:
    
    @staticmethod
    def approval_rate(from_date, to_date, department_id=None) -> dict:
        """% yêu cầu được duyệt vs từ chối vs pending."""
        qs = Request.objects.filter(
            submitted_at__range=(from_date, to_date)
        )
        if department_id:
            qs = qs.filter(requester__department_id=department_id)
        
        total = qs.count()
        return {
            "approved": qs.filter(status="COMPLETED").count() / total,
            "rejected": qs.filter(status="REJECTED").count() / total,
            "pending":  qs.filter(status__contains="PENDING").count() / total,
            "total": total
        }
    
    @staticmethod
    def bottleneck_detection(from_date, to_date) -> list[dict]:
        """Tìm bước hay tắc nhất (avg time > expected SLA)."""
        return AuditLog.objects.filter(
            action__in=["entered_approval", "entered_execution", "entered_acceptance"],
            timestamp__range=(from_date, to_date)
        ).values("action").annotate(
            avg_duration=Avg(
                F("timestamp") - Lag("timestamp").over(...)
            )
        ).order_by("-avg_duration")
    
    @staticmethod
    def sla_compliance_rate() -> float:
        """% yêu cầu hoàn thành trong SLA."""
        ...
    
    @staticmethod
    def ai_auto_approve_rate() -> dict:
        """% AI auto-approve và accuracy (confirm vs override)."""
        ...
```

#### APIs
```
GET /api/analytics/summary/          → Tổng quan KPI
GET /api/analytics/approval-rate/    → Donut chart data
GET /api/analytics/processing-time/  → Line chart (trend theo thời gian)
GET /api/analytics/sla-compliance/   → Gauge data
GET /api/analytics/bottleneck/       → Heatmap data
GET /api/analytics/department-load/  → Bar chart
GET /api/analytics/ai-metrics/       → AI auto-approve rate + accuracy
GET /api/analytics/rejection-reasons/→ Top N lý do từ chối
```

---

## 15. Sequence Diagrams — Luồng Hoạt động Chi tiết

> Mỗi luồng mô tả step-by-step tương tác giữa các actor và module. Bao gồm happy path và các nhánh lỗi quan trọng.

---

### Luồng 1: Tạo & Submit Yêu cầu (Request Submission)

```
Requester      Web Client        Django API        Rule Engine      AI Service       Notification
    │               │                │                  │                │                │
    │──[Chọn type]──►│                │                  │                │                │
    │               │──GET form_schema►│                  │                │                │
    │               │◄──form_schema───│                  │                │                │
    │               │                │                  │                │                │
    │──[Upload file]─►│                │                  │                │                │
    │               │──POST /attach───►│                  │                │                │
    │               │                │──Store Supabase   │                │                │
    │               │                │──POST /ai/ocr──────────────────────►│                │
    │               │                │◄──extracted_data───────────────────│                │
    │               │◄──fill form────│                  │                │                │
    │               │                │                  │                │                │
    │──[Bấm Gửi]────►│                │                  │                │                │
    │               │──POST /submit───►│                  │                │                │
    │               │                │──[status=EVALUATING]               │                │
    │               │                │                  │                │                │
    │               │                │──evaluate(data)──►│                │                │
    │               │                │◄──EvaluationResult│                │                │
    │               │                │  {template=A,    │                │                │
    │               │                │   chain=[TP],    │                │                │
    │               │                │   sla=24h}       │                │                │
    │               │                │                  │                │                │
    │               │                │──POST /ai/risk-score──────────────►│                │
    │               │                │◄──{score:18, eligible:true}────────│                │
    │               │                │                  │                │                │
    │               │         [risk ≤ 2 + Template A?]                   │                │
    │               │                │──POST /ai/auto-approve────────────►│                │
    │               │                │◄──{decision: APPROVED}─────────────│                │
    │               │                │                  │                │                │
    │               │                │──[status=AUTO_APPROVED]            │                │
    │               │                │──AuditChain.log("ai_auto_approved")│                │
    │               │                │──notify(Approver, "ai.auto_approved")──────────────►│
    │               │                │──notify(Requester, "request.submitted")─────────────►│
    │               │◄──{status:AUTO_APPROVED}│         │                │                │
    │◄──[UI update]─│                │                  │                │                │

NHÁNH: risk > 2 hoặc Template B/C:
    │               │                │──[status=PENDING_APPROVAL]         │                │
    │               │                │──Assign Approver (LoadBalancer)    │                │
    │               │                │──notify(Approver, "request.submitted")──────────────►│
    │               │◄──{status:PENDING_APPROVAL}│      │                │                │
```

---

### Luồng 2: Phê duyệt Thủ công (Manual Approval)

```
Approver       Web Client        Django API        OPA             Workflow Engine   Audit
    │               │                │               │                   │              │
    │──[Mở app]─────►│                │               │                   │              │
    │               │──GET /pending-approval►│         │                   │              │
    │               │◄──[List requests]──────│         │                   │              │
    │               │                │               │                   │              │
    │──[Click vào]──►│                │               │                   │              │
    │               │──GET /{id}/───────►│             │                   │              │
    │               │──GET /ai/summarize (nếu dài)     │                   │              │
    │               │◄──{summary, risk_score, explanation}                 │              │
    │               │◄──request detail──│             │                   │              │
    │               │                │               │                   │              │
    │──[Bấm Duyệt]──►│                │               │                   │              │
    │   (risk ≥ 4 → hiện signature modal)             │                   │              │
    │──[Ký tên]─────►│                │               │                   │              │
    │               │──POST /approve/────►│            │                   │              │
    │               │                │──check(actor, │                   │              │
    │               │                │   request,    │                   │              │
    │               │                │   "approve")──►│                   │              │
    │               │                │◄──{allow:true}│                   │              │
    │               │                │               │                   │              │
    │               │                │──transition("approve")─────────────►│              │
    │               │                │               │                   │──next_node()  │
    │               │                │               │                   │              │
    │               │       [Template A → EndNode COMPLETED]              │              │
    │               │       [Template B → ExecutionNode]                  │              │
    │               │       [Multi-level → Next ApprovalNode]             │              │
    │               │                │               │                   │              │
    │               │                │──AuditChain.log("approved")────────────────────────►│
    │               │                │──notify(stakeholders)             │              │
    │               │◄──{status:COMPLETED}──│          │                 │              │

NHÁNH: Từ chối
    │──[Bấm Từ chối]►│                │               │                   │              │
    │──[Nhập lý do]──►│                │               │                   │              │
    │               │──POST /reject/ + {reason}─►│     │                   │              │
    │               │                │──check OPA────►│                   │              │
    │               │                │──transition("reject")──────────────►│              │
    │               │                │──[status=REJECTED]                 │              │
    │               │                │──AuditChain.log("rejected", reason)────────────────►│
    │               │                │──notify(Requester, "rejected", reason)              │

NHÁNH: Yêu cầu bổ sung
    │──[Bấm Bổ sung]─►│               │               │                   │              │
    │──[Ghi câu hỏi]──►│               │               │                   │              │
    │               │──POST /request-info/─►│           │                   │              │
    │               │                │──[status=NEEDS_INFO]                │              │
    │               │                │──notify(Requester, "needs_info")    │              │
```

---

### Luồng 3: AI Auto-Approve + Human Override

```
Approver       Web Client        Django API        AI Service       Timer (Celery)
    │               │                │                  │                │
    │               │   [request đã AUTO_APPROVED]       │                │
    │               │                │                  │                │
    │──[Mở tab ✅]──►│                │                  │                │
    │               │──GET /pending-approval►│            │                │
    │               │◄──[Card với badge "🤖 AI đã tự động duyệt"]         │
    │               │   [⏰ Xác nhận trong 23h]           │                │
    │               │                │                  │                │
    │──[Xem xét]────►│                │                  │                │
    │               │                │                  │                │
    │  ──CHỌN A: Xác nhận──────────────────────────────────────────────  │
    │──[Bấm Xác nhận]►│               │                  │                │
    │               │──POST /confirm-ai/──►│              │                │
    │               │                │──[status=COMPLETED]                │
    │               │                │──AuditChain.log("human_confirmed_ai")          │
    │               │◄──{status:COMPLETED}│               │                │
    │               │                │                  │                │
    │  ──CHỌN B: Từ chối (Override)────────────────────────────────────  │
    │──[Bấm Từ chối]►│                │                  │                │
    │──[Nhập lý do]──►│               │                  │                │
    │               │──POST /override-reject/ + {reason}──►│              │
    │               │                │──[status=REJECTED]                 │
    │               │                │──AuditChain.log("human_overrode_ai", reason)  │
    │               │                │──[Retrain signal → ML model]       │
    │               │                │                  │                │
    │  ──CHỌN C: Timeout────────────────────────────────────────────────  │
    │               │                │                  │──[24h elapsed]  │
    │               │                │◄─────────────────────────────────[auto_confirm]
    │               │                │──[status=COMPLETED]                │
    │               │                │──AuditChain.log("timeout_auto_confirmed")      │
```

---

### Luồng 4: Thực hiện & Nghiệm thu (Template C)

```
Executor       Web Client        Django API        Workflow Engine   Acceptor
    │               │                │                   │              │
    │──[Mở tab 🔧]──►│                │                   │              │
    │               │──GET /pending-execution►│            │              │
    │               │◄──[List yêu cầu cần thực hiện]       │              │
    │               │                │                   │              │
    │──[Nhận việc]──►│                │                   │              │
    │               │──POST /claim/─────►│                │              │
    │               │                │──[status=IN_PROGRESS, executor=me]│              │
    │               │                │──AuditChain.log("claimed")        │              │
    │               │◄──OK────────────│                   │              │
    │               │                │                   │              │
    │ [Làm việc thực tế...]          │                   │              │
    │               │                │                   │              │
    │──[Hoàn thành]─►│                │                   │              │
    │──[Upload kết quả file]──────────►│                  │              │
    │               │──POST /execute-complete/──►│         │              │
    │               │   + {result_note, attachment_ids}    │              │
    │               │                │──transition("execute_complete")───►│
    │               │                │                   │──next_node()  │
    │               │                │                   │  (Template C → AcceptanceNode)
    │               │                │──Assign Acceptor───────────────────────────────►│
    │               │                │──notify(Acceptor, "acceptance_ready")───────────►│
    │               │◄──{status:EXECUTED}│                │              │
    │               │                │                   │              │
    │  ──NHÁNH: Từ chối thực hiện────────────────────────────────────────│
    │──[Từ chối]────►│                │                   │              │
    │──[Nhập lý do]──►│               │                   │              │
    │               │──POST /execute-reject/──►│           │              │
    │               │                │──[status=EXECUTION_REJECTED]      │              │
    │               │                │──notify(Approver, "exec_rejected")│              │
    │               │                │──[Approver xem xét: gán người khác?]             │
    │               │                │                   │              │
    │               │                │              [Acceptor flow]      │
    │               │                │                   │              │
    │               │                │                   │──[Mở tab 🔍]─►│
    │               │                │                   │              │──GET /pending-acceptance
    │               │                │                   │◄─────────────│
    │               │                │                   │              │──[Kiểm tra kết quả]
    │               │                │                   │              │──POST /accept/
    │               │                │──transition("accept")─────────────►│
    │               │                │──[status=COMPLETED]               │
    │               │                │──notify(all_actors, "completed")  │
    │               │                │──emit(WorkflowEvent "request.completed")
    │               │                │──ERP Webhook trigger───────────────────────────►
```

---

### Luồng 5: SLA Escalation

```
Celery (15min)   Django API        Approver          Manager          Audit
    │                │                 │                │               │
    │──[tick]─────────►│                │                │               │
    │                │──Query overdue requests           │               │
    │                │                 │                │               │
    │                │  [Request REQ-001: elapsed=14h, sla=24h, ratio=0.58]
    │                │──Level 1 (ratio≥0.5):             │               │
    │                │──notify(Approver, "sla.reminder")►│               │
    │                │   "Yêu cầu REQ-001 đã chờ 14/24h"│               │
    │                │                 │                │               │
    │ (next tick, 15min sau)           │                │               │
    │──[tick]─────────►│                │                │               │
    │                │  [Request REQ-001: elapsed=26h, ratio=1.08]
    │                │──Level 2 (ratio≥1.0):             │               │
    │                │──notify(Approver, "sla.escalation")►│              │
    │                │──notify(Manager, "sla.escalation")──────────────►│ │
    │                │──AuditChain.log("sla_breach")─────────────────────────────────►│
    │                │──LoadBalancer.suggest_rebalance() │                │
    │                │                 │                │               │
    │                │  [Nếu có Approver Pool]           │               │
    │                │──auto_reassign to least_loaded────────────────────────────────
    │                │──notify(NewApprover, "request.submitted")          │
    │                │──AuditChain.log("auto_reassigned")───────────────────────────►│
```

---

### Luồng 6: Delegation Tự động

```
System           Django API        Delegator         Delegate          Requester
    │                │                 │                │               │
    │  [DelegationPolicy: user_A → user_B, 15-20/09]   │               │
    │                │                 │                │               │
    │  [Ngày 15/09, Celery morning job]                 │               │
    │──[activate]────►│                 │                │               │
    │                │──DelegationPolicy.is_active = True               │
    │                │──notify(Delegate, "delegation.activated")─────────►│
    │                │   "Bạn đang thay mặt Nguyễn TP từ 15-20/09"     │
    │                │                 │                │               │
    │  [User gửi yêu cầu trong giai đoạn này]           │               │
    │                │                 │                │◄──[Submit]────│
    │                │──evaluate(request)               │               │
    │                │──resolve_approver("dept_head")   │               │
    │                │  → delegation active → return Delegate           │
    │                │──assign Delegate as Approver─────────────────────►│
    │                │──notify(Delegate, "request.submitted")────────────►│
    │                │  "Bạn có 1 yêu cầu mới (thay mặt Nguyễn TP)"   │
    │                │                 │                │               │
    │  [Ngày 21/09, Celery morning job]                 │               │
    │──[deactivate]──►│                │                │               │
    │                │──DelegationPolicy.is_active = False              │
    │                │──notify(Delegator, "delegation.ended")────────────►│
```

---

### Luồng 7: ERP/HRM Integration (Webhook)

```
Workflow Engine  Django API        Redis Pub/Sub    Webhook Adapter   HRM/ERP Stub
    │                │                 │                │               │
    │  [Template A: request COMPLETED] │               │               │
    │──emit_event────►│                │               │               │
    │                │──WorkflowEvent(│               │               │
    │                │  type="request.completed",      │               │
    │                │  request_type="leave_request",  │               │
    │                │  payload={days:2, employee_id}  │               │
    │                │)──────────────►│               │               │
    │                │               │──route event──►│               │
    │                │               │  by event_type │               │
    │                │               │               │──POST /hrm/deduct-leave-days►│
    │                │               │               │  {employee_id, days}         │
    │                │               │               │◄──{status:ok, new_balance:8}─│
    │                │               │               │               │
    │                │               │               │──WebhookDeliveryLog.create(  │
    │                │               │               │   status="success", ...)     │
    │                │               │               │               │
    │  [Nếu webhook thất bại]         │               │               │
    │                │               │               │──HTTPError────────────────────►
    │                │               │               │◄──timeout                    │
    │                │               │               │               │
    │                │               │               │──retry with exponential backoff
    │                │               │               │──[max 5 lần]  │               │
    │                │               │               │──WebhookDeliveryLog.update(  │
    │                │               │               │   status="failed", attempts=5)
    │                │               │               │──notify(Admin, "webhook.failed")
```

---

### Luồng 8: Admin — Tạo Workflow mới bằng Builder

```
Admin          Web Admin (React Flow)    Django API        Validation
    │               │                       │                 │
    │──[Mở Builder]─►│                       │                 │
    │               │──GET /workflows/──────►│                 │
    │               │◄──[existing workflows]─│                 │
    │               │                       │                 │
    │──[Drag Start node]──────────►│         │                 │
    │──[Drag Approval node]────────►│         │                 │
    │──[Config node: role=dept_head]►│        │                 │
    │──[Drag Condition node]───────►│         │                 │
    │──[Config: if amount>50M → branch]►│    │                 │
    │──[Drag Approval node (CFO)]──►│         │                 │
    │──[Connect edges]─────────────►│         │                 │
    │──[Drag End node]─────────────►│         │                 │
    │──[Bấm Lưu]───────────────────►│         │                 │
    │               │──serialize JSON graph  │                 │
    │               │──POST /workflows/─────►│                 │
    │               │   {name, json_schema}  │                 │
    │               │                       │──validate_graph()►│
    │               │                       │  - Có Start node?│
    │               │                       │  - Có End node?  │
    │               │                       │  - No cycles?    │
    │               │                       │  - All nodes reachable?
    │               │                       │◄──{valid: true}──│
    │               │                       │──save to DB      │
    │               │◄──{id, version:1}─────│                 │
    │               │                       │                 │
    │──[Gán cho RequestType]────────────────►│                 │
    │               │──PUT /request-types/{id}──►│             │
    │               │   {workflow_definition_id}  │             │
    │               │◄──OK──────────────────│                 │
    │◄──[Thông báo "Workflow đã lưu"]────────│                 │
```

