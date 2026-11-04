# HỒ SƠ THIẾT KẾ TOÀN DIỆN CÁC SƠ ĐỒ TUẦN TỰ (SEQUENCE DIAGRAMS)
## DỰ ÁN: HỆ THỐNG TỰ ĐỘNG HÓA QUY TRÌNH XỬ LÝ YÊU CẦU NỘI BỘ ĐA CẤP (EAS)
### HỘI ĐỒNG THẨM ĐỊNH IT 15 NĂM KINH NGHIỆM: BA, PM, DEV, UI/UX, AI, QA, PO

---

## 1. NGUYÊN TẮC THIẾT KẾ SƠ ĐỒ TUẦN TỰ DOANH NGHIỆP

Theo tiêu chuẩn UML 2.5 Sequence Diagrams và đối soát chi tiết mã nguồn xử lý thời gian thực trong `api_core/middleware.py`, `api_core/workflow/service.py`, `api_core/worker.py` và `ai_service/main.py`, toàn bộ 22 sơ đồ tuần tự tuân thủ các nguyên tắc kỹ thuật cốt lõi:
1. **Kiểm soát ranh giới tin cậy (Trust Boundaries):** Mọi request từ Client (Web/Mobile) đều phải đi qua Cổng Gateway, chạy Authentication & CSRF Middleware trước khi chạm vào Business Handler.
2. **Khóa chống tranh chấp đồng thời (Concurrency Control):** Mọi thao tác thay đổi trạng thái (Submit, Approve, Claim, Accept, Reassign) đều sử dụng khóa bi quan `FOR UPDATE` hoặc khóa lạc quan `expected_version` để giải quyết triệt để Race Condition.
3. **Mô hình Xuất bản Hàng đợi tin cậy (Transactional Outbox Pattern):** Sự kiện thông báo và tác vụ nền không bao giờ gửi trực tiếp từ HTTP thread; chúng được lưu vào bảng `eas.outbox_event` cùng transaction nghiệp vụ để bảo đảm tính "At-least-once Delivery".
4. **Bảo mật và Quyền riêng tư (Zero-Trust & Data Privacy):** Ngăn chặn hoàn toàn lỗi IDOR, bóc tách PII khi xuất log và bảo toàn chuỗi băm SHA-256 Hash-chain.

---

## 2. DANH MỤC ĐẦY ĐỦ 22 SƠ ĐỒ TUẦN TỰ (SD-01 ĐẾN SD-22)

---

### SƠ ĐỒ 1: HÌNH 2.9 - ĐĂNG NHẬP, XÁC THỰC VÀ QUẢN LÝ PHIÊN (SD-01)
*Quy trình xác thực an toàn, cấp phát cookie HttpOnly, phân lập cổng và bảo vệ chống Brute-force.*

```mermaid
sequenceDiagram
    autonumber
    actor User as "Người dùng (Web/Mobile)"
    participant GW as "API Gateway / Nginx"
    participant AuthMW as "Authentication Middleware"
    participant Core as "Auth Service (Django)"
    participant Redis as "Redis Session & Rate Limit"
    participant DB as "PostgreSQL (eas Schema)"

    User->>GW: POST /api/v1/auth/login {email, password}
    GW->>Redis: Kiểm tra Rate Limit IP (Tối đa 5 lần thử / 15 phút)
    alt Vượt quá giới hạn thử đăng nhập
        Redis-->>GW: Rate limit exceeded (HTTP 429)
        GW-->>User: 429 Too Many Requests (Khóa tạm thời IP)
    else Trong giới hạn cho phép
        GW->>AuthMW: Chuyển tiếp request
        AuthMW->>Core: Gọi hàm authenticate_credentials(email, password)
        Core->>DB: SELECT * FROM eas.app_user WHERE email = %s AND is_active = true
        DB-->>Core: Trả về thông tin user & hash Argon2id
        Core->>Core: Xác minh băm mật khẩu Argon2id
        alt Mật khẩu không chính xác
            Core->>Redis: Tăng biến đếm số lần thất bại (Failed Attempts + 1)
            Core-->>GW: 401 Unauthorized (Sai thông tin đăng nhập)
            GW-->>User: 401 Thông tin đăng nhập không hợp lệ
        else Xác thực thành công
            Core->>Core: Kiểm tra ranh giới cổng truy cập:
            Note over Core: Admin (admin@eas.com) -> Chỉ vào Cổng 8081\nNhân viên -> Chỉ vào Cổng 8080
            Core->>DB: Đọc `security_epoch` và quyền của user
            DB-->>Core: Trả về roles, department_id, security_epoch
            Core->>Redis: Lưu Session Token & Epoch (TTL: 8 giờ)
            Core->>DB: INSERT INTO eas.audit_log (Login Event)
            Core-->>GW: 200 OK + Set-Cookie (sessionid, HttpOnly, SameSite=Lax, Secure)
            GW-->>User: 200 OK (Chuyển hướng vào màn hình Dashboard)
        end
    end
```

---

### SƠ ĐỒ 2: HÌNH PL-14 - TẢI LÊN TỆP ĐÍNH KÈM VÀ QUÉT MÃ ĐỘC ANTIVIRUS (SD-02)
*Quy trình upload tệp chứng từ an toàn, kiểm tra Magic Bytes và quét virus stream.*

```mermaid
sequenceDiagram
    autonumber
    actor Req as "Requester"
    participant GW as "API Gateway"
    participant Core as "Attachment Service"
    participant ClamAV as "ClamAV Daemon / Scanner"
    participant Storage as "Encrypted Object Storage"
    participant DB as "PostgreSQL (eas Schema)"

    Req->>GW: POST /api/v1/attachments/upload (Multipart/form-data)
    GW->>Core: Nhận luồng dữ liệu stream
    Core->>Core: 1. Đọc Magic Bytes (Kiểm tra phần đầu tệp thật)
    alt Không đúng định dạng PDF/JPG/PNG cho phép
        Core-->>GW: 400 Bad Request (Tệp tin không đúng định dạng)
        GW-->>Req: 400 Định dạng tệp không được chấp nhận
    else Định dạng hợp chuẩn
        Core->>Core: 2. Đổi tên tệp thành UUID ngẫu nhiên (chống Path Traversal)
        Core->>ClamAV: 3. Gửi luồng byte tệp để quét mã độc (Stream Scan)
        ClamAV-->>Core: Kết quả quét virus
        alt Phát hiện Malware / Ransomware / Virus
            Core->>DB: INSERT INTO eas.security_incident_log (Malware Detected)
            Core-->>GW: 422 Unprocessable Entity (Tệp tin chứa mã độc)
            GW-->>Req: 422 Cảnh báo: Tệp tin bị phát hiện chứa mã độc và đã bị hủy!
        else Tệp tin hoàn toàn sạch (Clean)
            Core->>Storage: 4. Lưu tệp mã hóa AES-256 vào Object Storage riêng biệt
            Storage-->>Core: Trả về Storage Object Key
            Core->>DB: 5. INSERT INTO eas.attachment (id, key, size, sha256_hash, status='CLEAN')
            DB-->>Core: Bản ghi đính kèm đã lưu
            Core-->>GW: 201 Created {attachment_id, file_name, size}
            GW-->>Req: 201 Upload thành công, sẵn sàng liên kết vào đơn
        end
    end
```

---

### SƠ ĐỒ 3: HÌNH 2.10 - GỬI ĐƠN VÀ GỬI LẠI NGUYÊN TỬ (SUBMIT/RESUBMIT) (SD-03)
*Giao dịch gửi hồ sơ vào luồng duyệt với Idempotency-Key và kiểm tra release snapshot.*

```mermaid
sequenceDiagram
    autonumber
    actor Req as "Requester"
    participant Core as "Workflow Engine (Django)"
    participant AI as "AI Subsystem (:8001)"
    participant DB as "PostgreSQL (eas Schema)"
    participant Outbox as "Outbox Publisher"

    Req->>Core: POST /api/v1/requests/submit\nHeader: Idempotency-Key: <uuid>\nBody: {request_id, form_data, attachments}
    
    Core->>DB: SELECT * FROM eas.idempotency_key WHERE key = %s FOR UPDATE
    alt Khóa đã được xử lý thành công trước đó
        DB-->>Core: Trả về kết quả giao dịch đã lưu trong bộ đệm
        Core-->>Req: 200 OK (Kết quả đã xử lý trước đó, chống nộp đúp)
    else Khóa mới hợp lệ
        Core->>DB: BEGIN TRANSACTION
        Core->>DB: SELECT * FROM eas.request WHERE id = %s FOR UPDATE
        DB-->>Core: Trả về bản ghi đơn hiện tại (DRAFT / NEEDS_INFO)
        
        Core->>DB: Lấy Active Config Release & Schema tương ứng
        DB-->>Core: Trả về Release snapshot (v2.x)
        
        Core->>AI: POST /ai/risk/score {title, content, amount, category}
        AI-->>Core: Trả về {risk_weight: 2, label: 'LOW_RISK'}
        
        Core->>Core: Phân giải lộ trình duyệt (Resolve Approval Route)
        Core->>DB: INSERT INTO eas.approval_step (step_seq, assigned_role, status='ACTIVE')
        Core->>DB: UPDATE eas.request SET status = 'SUBMITTED', current_stage = 2
        Core->>DB: INSERT INTO eas.audit_log (Tạo chuỗi băm SHA-256 nối tiếp)
        Core->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_SUBMITTED)
        Core->>DB: INSERT INTO eas.idempotency_key (Ghi nhận khóa giao dịch thành công)
        
        Core->>DB: COMMIT TRANSACTION
        DB-->>Core: Giao dịch thành công 100%
        
        Core->>Outbox: Kích hoạt sự kiện nền (Signal Outbox Wakeup)
        Core-->>Req: 200 OK {request_id, status: 'SUBMITTED', message: 'Nộp đơn thành công'}
    end
```

---

### SƠ ĐỒ 4: HÌNH 2.11 - QUYẾT ĐỊNH PHÊ DUYỆT, TỪ CHỐI VÀ YÊU CẦU BỔ SUNG (SD-04)
*Xử lý 3 nhánh quyết định của cấp quản lý, khóa hàng chống tranh chấp đồng thời.*

```mermaid
sequenceDiagram
    autonumber
    actor App as "Approver (Cấp quản lý)"
    participant Core as "Workflow Engine"
    participant DB as "PostgreSQL (eas Schema)"
    participant Outbox as "Outbox Event Queue"

    App->>Core: POST /api/v1/requests/{id}/decision\nBody: {decision: 'APPROVE'|'REJECT'|'NEEDS_INFO', note, expected_version}
    
    Core->>DB: BEGIN TRANSACTION
    Core->>DB: SELECT * FROM eas.request WHERE id = %s FOR UPDATE
    Core->>DB: SELECT * FROM eas.approval_step WHERE request_id = %s AND status = 'ACTIVE' FOR UPDATE
    DB-->>Core: Trả về bước duyệt hiện tại và version của hồ sơ
    
    alt Phiên bản hồ sơ không khớp (expected_version != db_version)
        Core->>DB: ROLLBACK
        Core-->>App: 409 Conflict (Hồ sơ đã được cập nhật bởi phiên khác, vui lòng tải lại)
    else Approver vi phạm Separation of Duties (chính là Requester)
        Core->>DB: ROLLBACK
        Core-->>App: 403 Forbidden (Không được tự duyệt đơn của mình)
    else Dữ liệu hợp lệ, thực thi theo quyết định:
        alt Quyết định = APPROVE (Chấp thuận)
            Core->>DB: UPDATE eas.approval_step SET status = 'APPROVED', decided_at = now()
            Core->>DB: INSERT INTO eas.step_decision (step_id, actor_id, decision='APPROVE')
            alt Còn cấp duyệt tiếp theo trong ma trận
                Core->>DB: INSERT INTO eas.approval_step (next_seq, status = 'ACTIVE')
                Core->>DB: INSERT INTO eas.outbox_event (Event: STEP_ACTIVATED)
            else Đã hoàn tất cấp duyệt cuối cùng
                alt Lifecycle A (Chỉ phê duyệt)
                    Core->>DB: UPDATE eas.request SET status = 'COMPLETED', completed_at = now()
                    Core->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_COMPLETED)
                else Lifecycle B hoặc C (Cần thực thi)
                    Core->>DB: UPDATE eas.request SET status = 'READY_FOR_EXECUTION'
                    Core->>DB: INSERT INTO eas.outbox_event (Event: READY_FOR_EXECUTION)
                end
            end
        else Quyết định = REJECT (Bác bỏ)
            Core->>DB: UPDATE eas.approval_step SET status = 'REJECTED', note = %s
            Core->>DB: UPDATE eas.request SET status = 'REJECTED', closed_at = now()
            Core->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_REJECTED)
        else Quyết định = NEEDS_INFO (Yêu cầu làm rõ)
            Core->>DB: UPDATE eas.approval_step SET status = 'NEEDS_INFO', note = %s
            Core->>DB: UPDATE eas.request SET status = 'NEEDS_INFO'
            Core->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_NEEDS_INFO)
        end
        
        Core->>DB: INSERT INTO eas.audit_log (Ghi nhật ký kiểm toán băm nối tiếp)
        Core->>DB: COMMIT TRANSACTION
        Core-->>App: 200 OK {status: 'SUCCESS', message: 'Đã lưu quyết định thành công'}
    end
```

---

### SƠ ĐỒ 5: HÌNH PL-15 - PHÊ DUYỆT TỰ ĐỘNG BẰNG AI VÀ PHÁT HIỆN BẤT THƯỜNG (SD-05)
*Cơ chế Zero-Step Approval khi hội tụ đủ 5 điều kiện an toàn chính sách.*

```mermaid
sequenceDiagram
    autonumber
    actor Worker as "Workflow Background Task"
    participant Engine as "Auto-Approve Engine"
    participant AI as "AI Service (:8001)"
    participant MockSys as "Mock Enterprise APIs"
    participant DB as "PostgreSQL (eas Schema)"

    Worker->>Engine: Kích hoạt đánh giá Auto-Approval (request_id)
    Engine->>DB: Đọc cấu hình loại đơn (`request_type`), mẫu vòng đời, automation_weight
    DB-->>Engine: Trả về thông số: Lifecycle A, Automation Weight = 80%

    Engine->>AI: POST /ai/auto-approve/evaluate {request_data, attachments}
    AI->>AI: Chấm điểm rủi ro và trích xuất dữ liệu hóa đơn VAT
    AI-->>Engine: Trả về: {auto_approve_eligible: true, risk_weight: 1, anomaly_flags: []}

    Engine->>MockSys: GET /api/v1/mock/finance/budget-check (Kiểm tra hạn mức ngân sách)
    MockSys-->>Engine: Hạn mức phòng ban còn đủ, chưa vượt trần

    alt Hội tụ đủ 100% điều kiện: Lifecycle A + Risk <= 2 + Hạn mức OK + Circuit Breaker BẬT
        Engine->>DB: BEGIN TRANSACTION
        Engine->>DB: UPDATE eas.request SET status = 'COMPLETED', auto_approved = true
        Engine->>DB: INSERT INTO eas.approval_step (seq=1, actor='AI_SYSTEM', status='APPROVED', note='Tự động phê duyệt bởi AI Engine')
        Engine->>DB: INSERT INTO eas.audit_log (Audit Event: AI_AUTO_APPROVED)
        Engine->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_AUTO_APPROVED)
        Engine->>DB: COMMIT TRANSACTION
        Engine-->>Worker: Tự động phê duyệt thành công (0 cấp duyệt)
    else Có bất thường hoặc vi phạm chính sách
        Engine->>DB: Gán cờ rủi ro `risk_flag = true`, lý do bất thường
        Engine->>DB: Khởi tạo bước duyệt cấp 1 (ACTIVE Step) cho Cán bộ quản lý
        Engine-->>Worker: Chuyển tiếp cho con người duyệt tay có kèm cảnh báo
    end
```

---

### SƠ ĐỒ 6: HÌNH 2.12 - TIẾP NHẬN, NỘP KẾT QUẢ THỰC HIỆN VÀ NGHIỆM THU CÔNG VIỆC (SD-06)
*Quy trình thực thi chuyên môn (Lifecycle B & C) và nghiệm thu độc lập (Four-Eyes).*

```mermaid
sequenceDiagram
    autonumber
    actor Exe as "Executor (Cán bộ thi công)"
    actor Acc as "Acceptor (Cán bộ nghiệm thu)"
    participant Core as "Execution Service"
    participant DB as "PostgreSQL (eas Schema)"
    participant Outbox as "Outbox Event Queue"

    Note over Exe,DB: GIAI ĐOẠN 1: TIẾP NHẬN VIỆC (CLAIM LEASE)
    Exe->>Core: POST /api/v1/requests/{id}/claim
    Core->>DB: BEGIN TRANSACTION
    Core->>DB: SELECT * FROM eas.request WHERE id = %s AND status = 'READY_FOR_EXECUTION' FOR UPDATE
    Core->>DB: INSERT INTO eas.execution_attempt (executor_id, status='RUNNING', lease_until = now() + interval '24 hours')
    Core->>DB: UPDATE eas.request SET status = 'IN_PROGRESS'
    Core->>DB: COMMIT TRANSACTION
    Core-->>Exe: 200 OK (Đã tiếp nhận công việc thành công)

    Note over Exe,DB: GIAI ĐOẠN 2: THỰC HIỆN VÀ NỘP BIÊN BẢN
    Exe->>Core: POST /api/v1/requests/{id}/submit-result {result_note, evidence_attachments}
    Core->>DB: BEGIN TRANSACTION
    Core->>DB: UPDATE eas.execution_attempt SET status = 'SUBMITTED', completed_at = now()
    
    alt Lifecycle B (Không nghiệm thu độc lập)
        Core->>DB: UPDATE eas.request SET status = 'COMPLETED', completed_at = now()
        Core->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_COMPLETED)
        Core->>DB: COMMIT TRANSACTION
        Core-->>Exe: 200 OK (Hồ sơ hoàn tất viên mãn)
    else Lifecycle C (Bắt buộc nghiệm thu độc lập)
        Core->>DB: UPDATE eas.request SET status = 'WAITING_FOR_ACCEPTANCE'
        Core->>DB: INSERT INTO eas.outbox_event (Event: WAITING_FOR_ACCEPTANCE)
        Core->>DB: COMMIT TRANSACTION
        Core-->>Exe: 200 OK (Đã chuyển tiếp hồ sơ sang bộ phận nghiệm thu)

        Note over Acc,DB: GIAI ĐOẠN 3: NGHIỆM THU BÀN GIAO ĐỘC LẬP
        Acc->>Core: POST /api/v1/requests/{id}/accept {verdict: 'ACCEPT'|'REWORK', note}
        Core->>DB: BEGIN TRANSACTION
        alt Acceptor trùng với Executor (Vi phạm SoD)
            Core->>DB: ROLLBACK
            Core-->>Acc: 403 Forbidden (Người thực hiện không được tự nghiệm thu kết quả của chính mình)
        else Verdict = REWORK (Yêu cầu làm lại)
            Core->>DB: UPDATE eas.execution_attempt SET status = 'REWORK', note = %s
            Core->>DB: UPDATE eas.request SET status = 'READY_FOR_EXECUTION'
            Core->>DB: INSERT INTO eas.outbox_event (Event: EXECUTION_REWORK_REQUIRED)
            Core->>DB: COMMIT TRANSACTION
            Core-->>Acc: 200 OK (Đã yêu cầu làm lại)
        else Verdict = ACCEPT (Chấp thuận nghiệm thu)
            Core->>DB: INSERT INTO eas.acceptance_record (acceptor_id, status='ACCEPTED', signed_at=now())
            Core->>DB: UPDATE eas.request SET status = 'COMPLETED', completed_at = now()
            Core->>DB: INSERT INTO eas.audit_log (Audit Event: ACCEPTANCE_COMPLETED)
            Core->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_COMPLETED)
            Core->>DB: COMMIT TRANSACTION
            Core-->>Acc: 200 OK (Nghiệm thu hoàn tất, đơn đóng thành công)
        end
    end
```

---

### SƠ ĐỒ 7: HÌNH PL-16 - QUẢN TRỊ PHÂN QUYỀN RBAC VÀ LÀM MỚI PHIÊN NGƯỜI DÙNG (SD-07)
*Điều chỉnh ma trận quyền, bảo vệ 4 module tối cao và cơ chế tăng Kỷ nguyên An ninh (Security Epoch).*

```mermaid
sequenceDiagram
    autonumber
    actor Admin as "Ops Admin (:8081)"
    participant Core as "RBAC Management Service"
    participant Redis as "Redis Cache"
    participant DB as "PostgreSQL (eas Schema)"
    actor Client as "Web Client (:8080)"

    Admin->>Core: PATCH /api/v1/admin/rbac/matrix\nBody: {role: 'APPROVER', module: 'requests_workflows', actions: {can_read: true, can_create: true, can_update: false, can_delete: false}}
    
    Core->>Core: 1. Kiểm tra bảo vệ 4 Module Tối cao:\n(permissions, ai_engine, api_management, system_versions)
    alt Cố tình cấp 4 quyền này cho Role thông thường
        Core-->>Admin: 403 Forbidden (4 module này khóa cứng vĩnh viễn cho Admin, không thể cấp phát)
    else Cập nhật module nghiệp vụ thông thường
        Core->>DB: BEGIN TRANSACTION
        Core->>DB: UPSERT INTO eas.role_module_permission (role_code, module_code, can_read, can_create, can_update, can_delete)
        Core->>DB: UPDATE eas.system_security_state SET security_epoch = security_epoch + 1 RETURNING security_epoch
        DB-->>Core: Trả về Security Epoch mới = 105
        Core->>DB: INSERT INTO eas.admin_event (action='RBAC_MODIFIED', changed_by=Admin.id)
        Core->>DB: INSERT INTO eas.system_versions_changelog (change_type='PERMISSION')
        Core->>DB: COMMIT TRANSACTION
        
        Core->>Redis: Xóa sạch bộ đệm phân quyền (Cache Invalidation: `del eas:rbac:*`)
        Core-->>Admin: 200 OK (Đã lưu ma trận phân quyền và kích hoạt Epoch 105)
        
        Note over Client,Core: CLIENT TỰ ĐỘNG ĐỒNG BỘ PHÂN QUYỀN THEO ĐỊNH KỲ
        Client->>Core: GET /api/v1/auth/me (Polling mỗi 60s hoặc khi đổi trang)
        Core->>Core: Kiểm tra epoch của client (104) != server (105)
        Core-->>Client: 200 OK {user, security_epoch: 105, permissions: [...]}
        Client->>Client: Làm mới Menu Sidebar và ẩn/hiện tức thì các nút thao tác Thêm/Sửa/Xóa
    end
```

---

### SƠ ĐỒ 8: HÌNH 2.13 - XỬ LÝ HÀNG ĐỢI SỰ KIỆN OUTBOX VÀ GIÁM SÁT SLA (SD-08)
*Tiến trình giải phóng sự kiện Outbox, gửi thông báo và quét mốc cảnh báo trễ hạn.*

```mermaid
sequenceDiagram
    autonumber
    participant Worker as "Celery Background Worker"
    participant DB as "PostgreSQL (eas Schema)"
    participant Email as "Email SMTP / SMS Gateway"
    participant Push as "Firebase Cloud Messaging (FCM)"

    loop Mỗi chu kỳ 10 giây: Quét Outbox
        Worker->>DB: SELECT * FROM eas.outbox_event WHERE status = 'PENDING' ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED
        DB-->>Worker: Trả về danh sách 50 sự kiện mới
        loop Duyệt qua từng sự kiện Outbox
            Worker->>Worker: Phân tích loại sự kiện (Event Type) và danh sách người nhận
            par Gửi Email
                Worker->>Email: Gửi email thông báo định dạng HTML mẫu
                Email-->>Worker: SMTP 250 Message accepted
            and Gửi Push Notification Mobile
                Worker->>Push: Gửi FCM payload đến thiết bị điện thoại của Quản lý
                Push-->>Worker: FCM 200 Success
            end
            Worker->>DB: UPDATE eas.outbox_event SET status = 'DISPATCHED', delivered_at = now() WHERE id = %s
        end
    end

    loop Mỗi chu kỳ 60 giây: Quét vi phạm SLA
        Worker->>DB: SELECT * FROM eas.sla_stage WHERE status = 'ACTIVE' AND deadline < now()
        DB-->>Worker: Trả về các hồ sơ đã vượt hạn mức thời gian cam kết
        loop Duyệt qua từng hồ sơ vi phạm
            Worker->>DB: INSERT INTO eas.sla_breach_log (request_id, breach_duration, escalated_to)
            Worker->>DB: INSERT INTO eas.outbox_event (Event: SLA_ESCALATION_ALERT)
            Worker->>DB: UPDATE eas.sla_stage SET status = 'BREACHED'
        end
    end
```

---

### SƠ ĐỒ 9: HÌNH PL-17 - KIỂM TRA TÍNH TOÀN VẸN CHUỖI KHỐI KIỂM TOÁN HASH-CHAIN (SD-09)
*Thuật toán quét kiểm tra mật mã học từng nút trong chuỗi băm chống chối bỏ.*

```mermaid
sequenceDiagram
    autonumber
    actor Auditor as "Auditor (Kiểm toán viên)"
    participant Core as "Audit Ledger Service"
    participant DB as "PostgreSQL (eas Schema)"

    Auditor->>Core: POST /api/v1/audit/verify-chain {from_date, to_date}
    Core->>DB: SELECT * FROM eas.audit_head ORDER BY checkpoint_seq DESC LIMIT 1
    DB-->>Core: Lấy mã băm trạm kiểm soát gần nhất (Last Checkpoint Hash)

    Core->>DB: SELECT * FROM eas.audit_log WHERE created_at BETWEEN %s AND %s ORDER BY event_seq ASC
    DB-->>Core: Trả về danh sách n bản ghi sự kiện tuần tự

    Core->>Core: Khởi tạo biến: current_hash = Last Checkpoint Hash
    loop Duyệt từng bản ghi kiểm toán từ 1 đến n
        Core->>Core: Canonical_Payload = JSON_CANONICAL(record.payload)
        Core->>Core: Calculated_Hash = SHA256(current_hash + Canonical_Payload + record.created_at)
        alt Calculated_Hash != record.stored_hash
            Core-->>Auditor: 422 Unprocessable Entity {status: 'TAMPER_DETECTED', corrupted_seq: record.event_seq, message: 'Dữ liệu tại bản ghi đã bị can thiệp trái phép!'}
        else Mã băm khớp hoàn hảo
            Core->>Core: current_hash = Calculated_Hash (Tiếp tục xâu chuỗi)
        end
    end

    Core-->>Auditor: 200 OK {status: 'CHAIN_VERIFIED_100%', total_records: n, checkpoint_status: 'VALID'}
```

---

### SƠ ĐỒ 10: HÌNH PL-18 - HUẤN LUYỆN LẠI MÔ HÌNH AI VÀ TRIỂN KHAI CANARY (SD-10)
*Quy trình nạp dữ liệu mới, huấn luyện lại, kiểm thử kiểm chuẩn và phát hành Canary.*

```mermaid
sequenceDiagram
    autonumber
    actor Admin as "AI Administrator"
    participant Core as "AI Engine Management"
    participant AI as "FastAPI AI Service (:8001)"
    participant Registry as "Model Registry Storage"
    participant DB as "PostgreSQL (eas Schema)"

    Admin->>Core: POST /api/v1/admin/ai-engine/retrain {target_version: 'v2.0'}
    Core->>DB: INSERT INTO eas.ai_learning_job (status='QUEUED', target_version='v2.0')
    Core->>DB: UPDATE eas.system_state SET client_maintenance_lock = true
    
    Core->>AI: Khởi chạy luồng Worker huấn luyện chuyên trách
    AI->>DB: Lấy dữ liệu 1000 đơn mới và bộ quy chế quy chuẩn v2.0
    DB-->>AI: Trả về tập dữ liệu đã làm sạch
    
    AI->>AI: Huấn luyện lại bộ phân loại TF-IDF và mô hình Gradient Boosting
    AI->>AI: Chạy bài kiểm tra Vàng (Golden Test Suite - 100 ca thực tế)
    
    alt Kết quả kiểm chuẩn không đạt (F1-Score < 0.95 hoặc có vi phạm logic)
        AI->>DB: UPDATE eas.ai_learning_job SET status = 'FAILED', error = 'Accuracy below safety threshold'
        AI->>DB: UPDATE eas.system_state SET client_maintenance_lock = false
        AI-->>Core: Báo cáo thất bại, tự động giữ nguyên mô hình cũ an toàn
        Core-->>Admin: 422 Unprocessable Entity (Huấn luyện thất bại, đã giữ nguyên bản cũ)
    else Đạt chuẩn an toàn tuyệt đối
        AI->>Registry: Lưu file mô hình mới `nlp_risk_pipeline_v2.pkl`
        AI->>DB: UPDATE eas.ai_learning_job SET status = 'APPLIED', model_version = 'v2.0'
        AI->>DB: UPDATE eas.system_state SET client_maintenance_lock = false
        AI->>DB: INSERT INTO eas.system_announcement (Title: 'Hệ thống đã cập nhật quy định v2.0')
        AI-->>Core: Huấn luyện và kiểm chuẩn thành công 100%
        Core-->>Admin: 200 OK (Mô hình mới đã kích hoạt, Cổng nhân viên đã mở lại)
    end
```

---

### SƠ ĐỒ 11: HÌNH PL-19 - XUẤT DỮ LIỆU CÁ NHÂN THEO YÊU CẦU QUYỀN RIÊNG TƯ GDPR (SD-11)
*Đóng gói hồ sơ cá nhân có mã hóa theo tiêu chuẩn Data Portability.*

```mermaid
sequenceDiagram
    autonumber
    actor User as "Người dùng (Chủ thể dữ liệu)"
    participant Core as "Privacy Service"
    participant DB as "PostgreSQL (eas Schema)"
    participant Storage as "Export Vault"

    User->>Core: POST /api/v1/privacy/export-request {reason: 'Personal backup'}
    Core->>Core: Xác thực mật khẩu và gửi OTP xác nhận danh tính
    User->>Core: Nhập mã OTP xác thực 6 số
    Core->>DB: INSERT INTO eas.privacy_request (actor_id, type='EXPORT', status='PROCESSING')

    Core->>DB: SELECT * FROM eas.app_user WHERE id = %s
    Core->>DB: SELECT * FROM eas.request WHERE owner_id = %s
    Core->>DB: SELECT * FROM eas.step_decision WHERE actor_id = %s
    DB-->>Core: Toàn bộ dữ liệu gắn liền với nhân sự
    
    Core->>Core: Đóng gói thành file JSON chuẩn hóa kèm chứng chỉ toàn vẹn
    Core->>Core: Nén file ZIP và mã hóa bằng khóa riêng của người dùng
    Core->>Storage: Lưu trữ tệp ZIP mã hóa (TTL: 24 giờ tự hủy)
    Storage-->>Core: Trả về Presigned Download URL
    
    Core->>DB: UPDATE eas.privacy_request SET status = 'COMPLETED', download_url = %s
    Core-->>User: 200 OK (Gửi link tải tệp dữ liệu cá nhân mã hóa)
```

---

### SƠ ĐỒ 12: HÌNH PL-20 - ẨN DANH HÓA DỮ LIỆU CÁ NHÂN ĐỊNH KỲ GDPR (SD-12)
*Xóa bỏ thông tin PII nhưng bảo toàn tính liên tục của chuỗi băm sổ cái kiểm toán.*

```mermaid
sequenceDiagram
    autonumber
    participant Worker as "Privacy Scheduled Task"
    participant DB as "PostgreSQL (eas Schema)"

    Worker->>DB: SELECT * FROM eas.app_user WHERE status = 'RESIGNED' AND resigned_at < now() - interval '5 years'
    DB-->>Worker: Trả về danh sách tài khoản hết thời hạn lưu trữ pháp lý

    loop Duyệt từng nhân sự hết hạn
        Worker->>DB: BEGIN TRANSACTION
        Worker->>DB: UPDATE eas.app_user SET full_name = 'Cựu nhân viên đã ẩn danh', email = 'anonymized_' || id || '@eas.local', phone_number = NULL, national_id = NULL WHERE id = %s
        Worker->>DB: UPDATE eas.attachment SET is_deleted = true WHERE owner_id = %s AND contains_pii = true
        Note over Worker,DB: BẢO TOÀN SỔ CÁI KIỂM TOÁN HASH-CHAIN:\nKhông xóa dòng trong `eas.audit_log`, chỉ mã hóa băm một chiều danh tính
        Worker->>DB: INSERT INTO eas.privacy_compliance_log (actor_id, action='PII_ANONYMIZED', timestamp=now())
        Worker->>DB: COMMIT TRANSACTION
    end
    Worker-->>Worker: Hoàn tất chu kỳ ẩn danh hóa định kỳ
```

---

### SƠ ĐỒ 13: HÌNH PL-21 - THU HỒI QUYẾT ĐỊNH PHÊ DUYỆT TỰ ĐỘNG CỦA AI (SD-15)
*Cơ chế phanh khẩn cấp (Emergency Brake): Cấp quản lý can thiệp hủy quyết định tự duyệt của AI.*

```mermaid
sequenceDiagram
    autonumber
    actor Mgr as "Quản lý có thẩm quyền"
    participant Core as "Workflow Engine"
    participant DB as "PostgreSQL (eas Schema)"
    participant Outbox as "Outbox Queue"

    Mgr->>Core: POST /api/v1/requests/{id}/revoke-ai-approval\nBody: {reason: 'Phát hiện sai sót nghiệp vụ phát sinh sau duyệt'}
    
    Core->>DB: BEGIN TRANSACTION
    Core->>DB: SELECT * FROM eas.request WHERE id = %s FOR UPDATE
    DB-->>Core: Trả về đơn: auto_approved = true, approved_at = <timestamp>
    
    alt Thời gian duyệt đã vượt quá cửa sổ an toàn (24 giờ)
        Core->>DB: ROLLBACK
        Core-->>Mgr: 422 Unprocessable Entity (Đã quá thời hạn 24h thu hồi quyết định tự động)
    else Còn trong hạn 24 giờ và Manager có thẩm quyền
        Core->>DB: UPDATE eas.request SET status = 'IN_REVIEW', auto_approved = false
        Core->>DB: INSERT INTO eas.approval_step (seq=2, actor_id=Mgr.id, status='ACTIVE', note='Thu hồi phê duyệt AI')
        Core->>DB: INSERT INTO eas.audit_log (Audit Event: AI_APPROVAL_REVOKED, reason=%s)
        Core->>DB: INSERT INTO eas.outbox_event (Event: AI_APPROVAL_REVOKED)
        Core->>DB: COMMIT TRANSACTION
        Core-->>Mgr: 200 OK (Thu hồi thành công, hồ sơ chuyển sang trạng thái duyệt tay)
    end
```

---

### SƠ ĐỒ 14: HÌNH PL-22 - ỦY QUYỀN PHÊ DUYỆT KHẨN CẤP CÓ THỜI HẠN (SD-16)
*Ủy quyền có hiệu lực trong khoảng thời gian xác định và kiểm soát chống vòng lặp ủy quyền.*

```mermaid
sequenceDiagram
    autonumber
    actor Delegator as "Người ủy quyền (Trưởng phòng A)"
    actor Delegatee as "Người được ủy quyền (Phó phòng B)"
    participant Core as "Delegation Service"
    participant DB as "PostgreSQL (eas Schema)"

    Delegator->>Core: POST /api/v1/delegations\nBody: {delegatee_id, start_time, end_time, request_types: ['ALL']}
    
    Core->>Core: 1. Kiểm tra thời gian: end_time phải lớn hơn start_time
    Core->>Core: 2. Kiểm tra Delegatee có đang hoạt động (is_active = true)
    Core->>DB: SELECT * FROM eas.delegation_rule WHERE delegator_id = %s AND is_active = true
    alt Delegatee đang ủy quyền ngược lại cho Delegator (Vòng lặp ủy quyền)
        Core-->>Delegator: 400 Bad Request (Phát hiện vòng lặp ủy quyền chéo)
    else Hợp lệ
        Core->>DB: INSERT INTO eas.delegation_rule (delegator_id, delegatee_id, start_time, end_time, is_active=true)
        Core->>DB: INSERT INTO eas.audit_log (Audit Event: DELEGATION_CREATED)
        Core-->>Delegator: 201 Created (Thiết lập ủy quyền thành công)
    end

    Note over Delegatee,DB: KHI CÓ ĐƠN NỘP VÀO TRONG KHOẢNG THỜI GIAN HIỆU LỰC
    Core->>DB: Phân giải lộ trình duyệt: Phát hiện Delegator có ủy quyền đang ACTIVE
    Core->>DB: Gán lượt duyệt cho Delegatee (Ghi nhận rõ: Duyệt thay mặt Delegator)
```

---

### SƠ ĐỒ 15: HÌNH PL-23 - CHUYỂN ĐỔI DỰ PHÒNG HỆ THỐNG VÀ KHÔI PHỤC SỰ CỐ (SD-17)
*Cơ chế tự động Failover giữa Primary Database và Read-Replica / Standby Cluster.*

```mermaid
sequenceDiagram
    autonumber
    participant App as "Backend API Cluster"
    participant Health as "Health Check Sentinel"
    participant Primary as "PostgreSQL Primary (Master)"
    participant Standby as "PostgreSQL Standby (Hot Replica)"

    loop Mỗi 5 giây
        Health->>Primary: SELECT 1 (Heartbeat Ping)
        alt Primary gặp sự cố phần cứng / Mất mạng
            Primary--xHealth: Timeout (Không phản hồi sau 3 lần)
            Health->>Health: BÁO ĐỘNG SỰ CỐ PRIMARY DIE
            Health->>Standby: Kích hoạt thăng cấp: `pg_ctl promote`
            Standby->>Standby: Chuyển đổi từ Read-Only sang Read-Write Master
            Standby-->>Health: Standby đã trở thành Primary mới!
            Health->>App: Cập nhật Connection Pool chuỗi kết nối Database mới
            App->>Standby: Tiếp tục nhận các giao dịch ghi bình thường (Downtime < 15 giây)
        end
    end
```

---

### SƠ ĐỒ 16: HÌNH PL-24 - PHỤC HỒI DỮ LIỆU THỜI ĐIỂM PITR VÀ ĐỐI SOÁT (SD-18)
*Quy trình khôi phục trạng thái CSDL về thời điểm chính xác trước sự cố.*

```mermaid
sequenceDiagram
    autonumber
    actor DBA as "Database Administrator (DBA)"
    participant Supabase as "Supabase PITR Engine"
    participant RecoveryDB as "Isolated Recovery Instance"
    participant Core as "Audit Ledger Verifier"

    DBA->>Supabase: Yêu cầu khôi phục PITR về thời điểm: 2026-11-03T10:15:00Z
    Supabase->>RecoveryDB: Áp dụng Base Backup + Tua lại nhật ký giao dịch WAL (Replay WAL logs)
    RecoveryDB-->>DBA: Khởi động thành công Database tại mốc thời gian chỉ định

    DBA->>Core: Khởi chạy đối soát toàn vẹn chuỗi băm trên Instance phục hồi
    Core->>RecoveryDB: Quét toàn bộ bảng `eas.audit_log` đến mốc 10:15:00Z
    RecoveryDB-->>Core: 100% Hash-chain khớp với Checkpoint đã lưu ngoài WORM Storage
    Core-->>DBA: Đối soát thành công, dữ liệu nhất quán không mất mát
    DBA->>Supabase: Hoán đổi Instance phục hồi thành CSDL chính thức
```

---

### SƠ ĐỒ 17: HÌNH PL-25 - LƯU BẢN NHÁP CHỐNG GHI ĐÈ PHIÊN BẢN (SD-19)
*Cơ chế Khóa lạc quan (Optimistic Concurrency Control) ngăn chặn ghi đè khi sửa nháp.*

```mermaid
sequenceDiagram
    autonumber
    actor User as "Requester (Trình duyệt A)"
    actor UserB as "Requester (Trình duyệt B / Điện thoại)"
    participant Core as "Draft Service"
    participant DB as "PostgreSQL (eas Schema)"

    User->>Core: GET /api/v1/requests/{id}/draft
    DB-->>Core: Trả về bản nháp: content = "Đề xuất mua máy", version = 3
    Core-->>User: Hiển thị form nháp (version = 3)

    UserB->>Core: GET /api/v1/requests/{id}/draft
    DB-->>Core: Trả về bản nháp: content = "Đề xuất mua máy", version = 3
    Core-->>UserB: Hiển thị form nháp (version = 3)

    User->>Core: PUT /api/v1/requests/{id}/draft {content: "Mua laptop Dell", expected_version: 3}
    Core->>DB: UPDATE eas.request_revision SET content = %s, version = 4 WHERE id = %s AND version = 3
    DB-->>Core: 1 row updated (Thành công)
    Core-->>User: 200 OK (Đã lưu bản nháp version = 4)

    UserB->>Core: PUT /api/v1/requests/{id}/draft {content: "Mua máy bàn Asus", expected_version: 3}
    Core->>DB: UPDATE eas.request_revision SET content = %s, version = 4 WHERE id = %s AND version = 3
    DB-->>Core: 0 rows updated (Do version trong DB hiện đã là 4!)
    Core-->>UserB: 409 Conflict (Bản nháp đã được sửa đổi từ thiết bị khác, vui lòng tải lại dữ liệu mới nhất)
```

---

### SƠ ĐỒ 18: HÌNH PL-26 - YÊU CẦU BỔ SUNG THÔNG TIN VÀ NỘP LẠI HỒ SƠ (SD-20)
*Quy trình luân chuyển đơn từ chặng phê duyệt về soạn thảo và tăng phiên bản sửa đổi.*

```mermaid
sequenceDiagram
    autonumber
    actor App as "Approver"
    actor Req as "Requester"
    participant Core as "Workflow Engine"
    participant DB as "PostgreSQL (eas Schema)"

    App->>Core: POST /api/v1/requests/{id}/decision {decision: 'NEEDS_INFO', note: 'Thiếu hóa đơn VAT và báo giá 3 bên'}
    Core->>DB: UPDATE eas.request SET status = 'NEEDS_INFO', current_stage = 1
    Core->>DB: INSERT INTO eas.outbox_event (Event: REQUEST_NEEDS_INFO)
    Core-->>App: 200 OK (Đã trả hồ sơ về cho người tạo đơn)

    Req->>Core: GET /api/v1/requests/{id}
    Core-->>Req: Trả về hồ sơ kèm ghi chú yêu cầu của cấp trên
    Req->>Core: Tải bổ sung tệp đính kèm hóa đơn VAT mới
    Req->>Core: POST /api/v1/requests/{id}/resubmit {clarification_text: 'Đã bổ sung báo giá 3 bên'}
    
    Core->>DB: BEGIN TRANSACTION
    Core->>DB: INSERT INTO eas.request_revision (request_id, revision_num = revision_num + 1, content)
    Core->>DB: UPDATE eas.request SET status = 'SUBMITTED', current_stage = 2
    Core->>DB: UPDATE eas.approval_step SET status = 'ACTIVE' WHERE request_id = %s AND step_seq = 1
    Core->>DB: INSERT INTO eas.audit_log (Audit Event: REQUEST_RESUBMITTED)
    Core->>DB: COMMIT TRANSACTION
    Core-->>Req: 200 OK (Hồ sơ đã nộp lại thành công vào luồng xét duyệt)
```

---

### SƠ ĐỒ 19: HÌNH PL-27 - BÁO CÁO KHÔNG THỂ TIẾP NHẬN VIỆC VÀ XỬ LÝ SỰ CỐ (SD-21)
*Quy trình ghi nhận vướng mắc thi công và tự động báo động điều chuyển.*

```mermaid
sequenceDiagram
    autonumber
    actor Exe as "Executor"
    actor Ops as "Ops Admin"
    participant Core as "Execution Issue Service"
    participant DB as "PostgreSQL (eas Schema)"

    Exe->>Core: POST /api/v1/requests/{id}/report-issue {issue_type: 'OUT_OF_STOCK', description: 'Nhà cung cấp báo hết hàng'}
    Core->>DB: BEGIN TRANSACTION
    Core->>DB: INSERT INTO eas.execution_issue (request_id, executor_id, issue_type, description, status='OPEN')
    Core->>DB: UPDATE eas.request SET status = 'BLOCKED'
    Core->>DB: INSERT INTO eas.outbox_event (Event: EXECUTION_BLOCKED_ALERT)
    Core->>DB: COMMIT TRANSACTION
    Core-->>Exe: 200 OK (Đã ghi nhận sự cố, hồ sơ tạm dừng)

    Ops->>Core: GET /api/v1/admin/operations/blocked-tasks
    Core-->>Ops: Hiển thị danh sách hồ sơ bị kẹt do thiếu hàng
    Ops->>Core: POST /api/v1/admin/requests/{id}/resolve-issue {action: 'SWITCH_SUPPLIER', new_executor_id: Exe2.id}
    Core->>DB: UPDATE eas.execution_issue SET status = 'RESOLVED'
    Core->>DB: UPDATE eas.request SET status = 'READY_FOR_EXECUTION'
    Core-->>Ops: 200 OK (Sự cố đã được tháo gỡ)
```

---

### SƠ ĐỒ 20: HÌNH PL-28 - ĐIỀU CHUYỂN NGƯỜI DUYỆT / NGHIỆM THU VẮNG MẶT (SD-22)
*Xử lý linh hoạt khi nhân sự nghỉ ốm, công tác đột xuất mà không làm gián đoạn dòng chảy công việc.*

```mermaid
sequenceDiagram
    autonumber
    actor Ops as "Ops Admin"
    participant Core as "Workflow Reassign Service"
    participant DB as "PostgreSQL (eas Schema)"
    actor NewApp as "Người duyệt thay thế"

    Ops->>Core: POST /api/v1/admin/requests/{id}/reassign-step\nBody: {step_id, current_assignee, new_assignee: NewApp.id, reason: 'Quản lý đi công tác nước ngoài'}
    
    Core->>Core: 1. Kiểm tra NewApp có thuộc vai trò tương đương trong phòng ban?
    Core->>Core: 2. Kiểm tra NewApp có trùng với Requester (SoD Guard)?
    alt Vi phạm phân tách nhiệm vụ
        Core-->>Ops: 403 Forbidden (Người được điều chuyển không được trùng người tạo đơn)
    else Hợp lệ
        Core->>DB: BEGIN TRANSACTION
        Core->>DB: UPDATE eas.approval_step SET assigned_actor_id = NewApp.id, reassigned_by = Ops.id WHERE id = %s
        Core->>DB: INSERT INTO eas.audit_log (Audit Event: STEP_REASSIGNED, old_actor, new_actor, reason)
        Core->>DB: INSERT INTO eas.outbox_event (Event: STEP_REASSIGNED_NOTIFY, recipient=NewApp.id)
        Core->>DB: COMMIT TRANSACTION
        Core-->>Ops: 200 OK (Điều chuyển người duyệt thành công)
        Core-->>NewApp: Gửi thông báo: Bạn được phân công duyệt thay thế đơn #REQ-xxx
    end
```

---

### SƠ ĐỒ 21: BỔ SUNG CHƯƠNG 2 - XỬ LÝ TRANH CHẤP RÚT ĐƠN CẠNH TRANH VỚI PHÊ DUYỆT (SD-05 BIZ)
*Xử lý triệt để tranh chấp tài nguyên (Race Condition) bằng khóa hàng FOR UPDATE.*

```mermaid
sequenceDiagram
    autonumber
    actor Req as "Requester (Muốn rút đơn)"
    actor App as "Approver (Đang bấm duyệt)"
    participant Core as "Workflow Engine"
    participant DB as "PostgreSQL (eas Schema)"

    par Requester gửi lệnh rút đơn
        Req->>Core: POST /api/v1/requests/{id}/withdraw
        Core->>DB: BEGIN TX 1: SELECT * FROM eas.request WHERE id = %s FOR UPDATE
    and Approver gửi lệnh duyệt đơn
        App->>Core: POST /api/v1/requests/{id}/decision {decision: 'APPROVE'}
        Core->>DB: BEGIN TX 2: SELECT * FROM eas.request WHERE id = %s FOR UPDATE
    end

    Note over DB: Cơ chế Khóa hàng (Row-level Lock):\nTX 1 đến trước mili-giây sẽ giữ khóa; TX 2 phải đợi TX 1 kết thúc.

    DB-->>Core: TX 1 lấy được khóa, đơn đang ở trạng thái SUBMITTED
    Core->>DB: TX 1: UPDATE eas.request SET status = 'WITHDRAWN', closed_at = now()
    Core->>DB: TX 1: COMMIT
    Core-->>Req: 200 OK (Bạn đã rút hồ sơ thành công)

    DB-->>Core: TX 2 tiếp tục lấy khóa sau khi TX 1 commit
    Core->>Core: TX 2 kiểm tra: Đơn hiện đã ở trạng thái WITHDRAWN!
    Core->>DB: TX 2: ROLLBACK
    Core-->>App: 409 Conflict (Hồ sơ đã được người tạo đơn rút lại trước đó, không thể phê duyệt)
```

---

### SƠ ĐỒ 22: BỔ SUNG CHƯƠNG 2 - THU HỒI QUYỀN CẠNH TRANH VỚI GIAO DỊCH DUYỆT (SD-12 BIZ)
*Xử lý khi Quản trị viên thu hồi vai trò đúng vào thời điểm Approver đang ký đơn.*

```mermaid
sequenceDiagram
    autonumber
    actor Admin as "Ops Admin"
    actor App as "Approver (Bị tước quyền)"
    participant Core as "API Core Handler"
    participant DB as "PostgreSQL (eas Schema)"

    par Admin thu hồi quyền Approver
        Admin->>Core: DELETE /api/v1/admin/users/{id}/roles/APPROVER
        Core->>DB: BEGIN TX 1: DELETE FROM eas.role_membership WHERE user_id = %s
        Core->>DB: TX 1: UPDATE eas.system_security_state SET security_epoch = security_epoch + 1
        Core->>DB: TX 1: COMMIT
    and Approver bấm ký duyệt hồ sơ
        App->>Core: POST /api/v1/requests/{id}/decision {decision: 'APPROVE'}
        Core->>Core: Kiểm tra Actor Role trong Session bộ đệm
    end

    Core->>DB: Đọc Security Epoch hiện tại của hệ thống
    Core->>Core: Phát hiện Token của Approver mang Epoch cũ (Lạc hậu)
    Core->>DB: SELECT * FROM eas.role_membership WHERE user_id = App.id
    DB-->>Core: 0 rows (Quyền Approver không còn tồn tại!)
    Core-->>App: 403 Forbidden (Quyền duyệt của bạn đã bị thu hồi bởi Quản trị viên)
```

---

## 3. BẢNG ĐỐI SOÁT TOÀN DIỆN 22 SƠ ĐỒ TUẦN TỰ VỚI SOURCE CODE

| Mã Sơ Đồ | Tên Quy Trình Tuần Tự | Source Code Backend | Rủi Ro Kỹ Thuật Đã Triệt Tiêu |
|:---:|:---|:---|:---|
| **SD-01** | Đăng nhập & Quản lý phiên | `api_core/authn/views.py` | Chặn đứng Brute-force và Session Fixation; phân lập cổng 8080 vs 8081. |
| **SD-02** | Quét virus tệp đính kèm | `api_core/workflow/attachments.py` | Chặn đứng tải lên file thực thi độc hại (Ransomware, Webshell) qua Magic Bytes. |
| **SD-03** | Nộp đơn nguyên tử (Submit) | `api_core/workflow/service.py` | Ngăn chặn nộp đúp mạng lag bằng `Idempotency-Key` và snapshot release. |
| **SD-04** | Quyết định phê duyệt đa cấp | `api_core/workflow/service.py` | Giải quyết triệt để xung đột duyệt đồng thời bằng `FOR UPDATE`. |
| **SD-05** | Phê duyệt tự động AI | `api_core/workflow/service.py` | Cơ chế cổng bảo vệ kép: Không bao giờ tự duyệt nếu vi phạm chính sách tài chính. |
| **SD-06** | Thực thi & Nghiệm thu | `api_core/workflow/service.py` | Khóa Claim Lease độc quyền và cưỡng chế nguyên tắc Four-Eyes trong nghiệm thu. |
| **SD-07** | Phân quyền RBAC & Epoch | `api_core/administration/org_users_rbac.py` | Khóa cứng 4 module hệ thống; ép client làm mới phiên tức thì bằng Security Epoch. |
| **SD-08** | Hàng đợi Outbox & SLA | `api_core/worker.py` | Đảm bảo thông báo không bao giờ mất (At-least-once) và quét SLA 3 mức. |
| **SD-09** | Đối soát chuỗi băm Hash-chain | `api_core/audit.py` | Phát hiện ngay lập tức bất kỳ hành vi sửa lén dữ liệu trong database. |
| **SD-10** | Huấn luyện lại AI & Canary | `api_core/workflow/ai_learning.py` | Tự động khóa bảo trì Cổng nhân viên; chỉ áp dụng khi vượt qua Bộ test Vàng. |
| **SD-11** | Xuất dữ liệu cá nhân GDPR | `api_core/administration/org_users_rbac.py` | Mã hóa gói xuất PII bằng mật khẩu riêng của người dùng. |
| **SD-12** | Ẩn danh hóa dữ liệu định kỳ | `api_core/administration/org_users_rbac.py` | Ẩn danh hóa định danh PII nhưng bảo toàn chuỗi băm sổ cái kiểm toán. |
| **SD-15** | Thu hồi phê duyệt tự động AI | `api_core/workflow/service.py` | Cung cấp phanh khẩn cấp cho Quản lý can thiệp trong vòng 24 giờ. |
| **SD-16** | Thiết lập ủy quyền khẩn cấp | `api_core/workflow/views.py` | Ngăn chặn vòng lặp ủy quyền chéo và bắt buộc kiểm soát SoD. |
| **SD-17** | Chuyển đổi dự phòng Failover | `docker-compose.yml`, Supabase | Duy trì tính sẵn sàng cao (HA), chuyển Standby sang Master trong < 15 giây. |
| **SD-18** | Phục hồi dữ liệu PITR | Supabase WAL Replay | Khôi phục chính xác về thời điểm trước thảm họa mà không mất mát dữ liệu. |
| **SD-19** | Lưu nháp chống ghi đè | `api_core/workflow/views.py` | Khóa lạc quan `version` chống mất dữ liệu khi sửa đồng thời từ 2 thiết bị. |
| **SD-20** | Yêu cầu bổ sung thông tin | `api_core/workflow/service.py` | Tăng số `revision_number` và bảo toàn toàn bộ lịch sử trao đổi làm rõ. |
| **SD-21** | Báo cáo vướng mắc thi công | `api_core/workflow/service.py` | Chuyển trạng thái BLOCKED và kích hoạt điều chuyển việc của Quản trị viên. |
| **SD-22** | Điều chuyển người xử lý | `api_core/workflow/ops_service.py` | Giải quyết ách tắc khi nhân sự vắng mặt mà vẫn đảm bảo tính tuân thủ SoD. |
| **SD-05 BIZ**| Rút đơn cạnh tranh phê duyệt | `api_core/workflow/service.py` | Phân xử giao dịch nguyên tử theo thứ tự mili-giây, không để phát sinh trạng thái ảo. |
| **SD-12 BIZ**| Tước quyền cạnh tranh ký duyệt| `api_core/authn/service.py` | Thu hồi quyền tức thì qua Kỷ nguyên an ninh, chặn đứng quyết định trái phép. |
