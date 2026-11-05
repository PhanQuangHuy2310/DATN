# HỒ SƠ THIẾT KẾ KIẾN TRÚC VÀ LUỒNG DỮ LIỆU PHÂN TÁN (ARCHITECTURE & DFD)
## DỰ ÁN: HỆ THỐNG TỰ ĐỘNG HÓA QUY TRÌNH XỬ LÝ YÊU CẦU NỘI BỘ ĐA CẤP (EAS)
### HỘI ĐỒNG THẨM ĐỊNH IT 15 NĂM KINH NGHIỆM: BA, PM, DEV, UI/UX, AI, QA, PO

---

## 1. NGUYÊN TẮC THIẾT KẾ KIẾN TRÚC HỆ THỐNG PHÂN TÁN (DISTRIBUTED SYSTEMS ARCHITECTURE)

Theo tiêu chuẩn IEEE/ISO/IEC 42010 về Kiến trúc Phần mềm và mô hình C4 (Context, Container, Component, Code), hệ thống EAS được kiến trúc dựa trên các nguyên tắc phòng thủ đa tầng và khả năng chịu tải cao:
1. **Ranh giới tin cậy nghiêm ngặt (Zero-Trust Boundaries):** Không có thành phần nào mặc định tin tưởng thành phần khác. Mọi giao tiếp giữa Web/Mobile và Backend đều phải qua Gateway có kiểm tra Rate-limit, WAF, xác thực danh tính và CSRF protection.
2. **Cách ly phân hệ Quản trị và Cổng Nhân viên (Dual-Portal Port Separation):**
   - **Cổng Nhân viên (Web Client):** Chạy trên cổng `8080` (hoặc `5173` môi trường dev), chỉ phục vụ cán bộ nhân viên tác nghiệp tạo đơn, duyệt đơn, thi công, nghiệm thu.
   - **Cổng Quản trị (Web Admin):** Chạy trên cổng `8081`, chỉ cho phép tài khoản Quản trị viên tối cao (`admin@eas.com` / `ADMIN_ROLES`) truy cập các tính năng cấu hình quy chế, phân quyền, quản lý API và vận hành hệ thống.
3. **Mô hình Dữ liệu Bất đồng bộ Tin cậy (Transactional Outbox Pattern):** Ngăn chặn hiện tượng phân rã dữ liệu (Dual-write problem) khi vừa cập nhật CSDL vừa gửi tin nhắn qua RabbitMQ/Redis/SMTP. Toàn bộ sự kiện phát tán được ghi vào bảng `eas.outbox_event` cùng transaction nghiệp vụ.
4. **Cơ chế Ngắt mạch và Tự phục hồi (Circuit Breaker & Self-Healing):** Giám sát trạng thái 8 Mock API nội bộ; khi một kết nối bị ngắt, hệ thống tự động khóa tạm ngưng các mẫu đơn liên quan để bảo vệ trải nghiệm người dùng và ngăn ngừa dữ liệu rác.

---

## 2. DANH MỤC TẤT CẢ 9 SƠ ĐỒ KIẾN TRÚC VÀ LUỒNG DỮ LIỆU (AR-01 ĐẾN DFD-01)

---

### SƠ ĐỒ 1: HÌNH 2.14 - SƠ ĐỒ NGỮ CẢNH KIẾN TRÚC HỆ THỐNG TỔNG THỂ (C4 CONTEXT - AR-01)
*Vị trí của hệ thống EAS trong toàn cảnh hệ sinh thái công nghệ doanh nghiệp.*

```mermaid
flowchart TD
    subgraph USERS["NGƯỜI DÙNG DOANH NGHIỆP"]
        STAFF["Cán bộ Nhân viên\n(Tạo đơn, theo dõi)"]
        MANAGERS["Cấp Quản lý & Giám đốc\n(Phê duyệt, thẩm định)"]
        SPECIALISTS["Bộ phận Chuyên trách\n(IT, Mua sắm, Kế toán)"]
        ADMINS["Ban Quản trị & Kiểm toán\n(Policy Admin, Ops, Auditor)"]
    end

    subgraph EAS_SYSTEM["ENTERPRISE APPROVAL SYSTEM (EAS) - PHẦN MỀM LÕI"]
        EAS_CORE["Hệ thống Tự động hóa Quy trình Xử lý Yêu cầu Nội bộ (EAS)\n- Tự động hóa phê duyệt đa cấp theo thẩm quyền\n- Phân hệ AI chấm điểm rủi ro và bóc tách hóa đơn\n- Giám sát cam kết thời gian SLA thời gian thực\n- Sổ cái kiểm toán mật mã học Hash-chain bất biến"]
    end

    subgraph ENTERPRISE_ECOSYSTEM["HỆ THỐNG NGOẠI VI DOANH NGHIỆP (8 MOCK APIS)"]
        EXT_HR["Hệ thống Nhân sự & Chấm công (HRIS / HRM)"]
        EXT_FIN["Hệ thống Tài chính & Ngân sách (ERP Finance)"]
        EXT_IT["Hệ thống Hạ tầng & Cấp quyền IT (ITSM / IAM)"]
        EXT_PROC["Hệ thống Mua sắm & Chuỗi cung ứng (Procurement)"]
        EXT_ASSETS["Hệ thống Quản lý Tài sản Doanh nghiệp (EAM)"]
        EXT_FAC["Hệ thống Cơ sở vật chất & Phòng họp (Facilities)"]
        EXT_TRAV["Hệ thống Định mức Công tác phí (Travel Per Diem)"]
        EXT_CRM["Hệ thống Quản hệ Khách hàng (CRM)"]
    end

    subgraph CLOUD_SERVICES["DỊCH VỤ ĐÁM MÂY & BÊN THỨ BA"]
        CLOUD_FCM["Firebase Cloud Messaging (FCM Push)"]
        CLOUD_SMTP["Enterprise Mail Gateway (SMTP)"]
        CLOUD_GEMINI["Google Gemini 2.5 Flash API (LLM)"]
    end

    STAFF -->|HTTPS / Trình duyệt Web| EAS_SYSTEM
    MANAGERS -->|HTTPS / Web & Mobile App| EAS_SYSTEM
    SPECIALISTS -->|HTTPS / Trình duyệt Web| EAS_SYSTEM
    ADMINS -->|HTTPS / Cổng Quản trị :8081| EAS_SYSTEM

    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_HR
    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_FIN
    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_IT
    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_PROC
    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_ASSETS
    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_FAC
    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_TRAV
    EAS_SYSTEM <-->|REST API JSON + HMAC Token| EXT_CRM

    EAS_SYSTEM -->|Push Notification| CLOUD_FCM
    EAS_SYSTEM -->|Email Alert| CLOUD_SMTP
    EAS_SYSTEM <-->|Tóm tắt & Trích xuất quy định| CLOUD_GEMINI
```

---

### SƠ ĐỒ 2: HÌNH 2.15 - SƠ ĐỒ CÁC CONTAINER LOGIC TRONG HỆ THỐNG (C4 CONTAINER - AR-02)
*Phân rã các khối thực thi (Containers), công nghệ nền tảng và giao thức kết nối nội bộ.*

```mermaid
flowchart TD
    subgraph CLIENT_TIER["LỚP ỨNG DỤNG CLIENT (CLIENT TIER)"]
        SPA_CLIENT["Web Client Application\nReact 19 + Vite (:8080)\nDành cho Nhân viên tác nghiệp"]
        SPA_ADMIN["Web Admin Application\nReact 19 + Vite (:8081)\nDành cho Ban Quản trị & Điều hành"]
        APP_MOBILE["Mobile Application\nReact Native / Expo (:8082)\nPhê duyệt nhanh On-the-go"]
    end

    subgraph GATEWAY_TIER["LỚP CỔNG VÀ ĐIỀU PHỐI (GATEWAY TIER)"]
        NGINX_GW["Reverse Proxy & API Gateway (Nginx)\n- SSL Termination (HTTPS)\n- Rate Limiting & DDOS Mitigation\n- Phân luồng Cổng :8080 vs :8081\n- Gắn Security Headers (CSP, HSTS, X-Frame)"]
    end

    subgraph BACKEND_TIER["LỚP DỊCH VỤ XỬ LÝ BACKEND (BACKEND TIER)"]
        DJANGO_API["API Core Service (Django 5 REST :8000)\n- Authentication & RBAC Middleware\n- State Machine & Workflow Engine\n- Business Rule Engine (BRE)\n- Transactional Outbox Generator\n- Cryptographic Hash-Chain Ledger"]
        CELERY_WORKER["Background Task Workers (Celery / Worker)\n- Dispatcher phân phối Outbox Event\n- SLA Scanner & Escalation Engine\n- ClamAV Antivirus File Scanner\n- Privacy Data Anonymizer Task"]
        FASTAPI_AI["AI Engine Microservice (FastAPI :8001)\n- TF-IDF + SGD Request Classifier\n- Gradient Boosting Risk Pipeline\n- PaddleOCR Vietnamese VAT Extractor\n- Gemini 2.5 Flash Summarizer\n- Rule Extraction & Semantic Versioning"]
    end

    subgraph STORAGE_TIER["LỚP LƯU TRỮ DỮ LIỆU & BỘ ĐỆM (PERSISTENCE TIER)"]
        PG_DB["PostgreSQL 15+ (Supabase Dedicated Schema eas)\n- Bảng nghiệp vụ phân quyền RLS\n- Chuỗi khối băm kiểm toán `audit_log`\n- Hàng đợi sự kiện `outbox_event`\n- 8 Schemas Mock Enterprise APIs"]
        REDIS_CACHE["Redis In-memory Database (:6379)\n- Session Cache & Security Epoch\n- Distributed Claim Locks\n- Rate Limit Tokens Bucket\n- Celery Message Broker"]
        OBJ_VAULT["Encrypted File Vault / S3 Compatible\n- Lưu trữ tệp đính kèm hóa đơn/chứng từ\n- Cách ly tệp nhiễm mã độc"]
    end

    SPA_CLIENT -->|HTTPS / Cookie HttpOnly| NGINX_GW
    SPA_ADMIN -->|HTTPS / Admin Session Cookie| NGINX_GW
    APP_MOBILE -->|HTTPS / Bearer JWT| NGINX_GW

    NGINX_GW -->|Reverse Proxy /api/v1/*| DJANGO_API
    
    DJANGO_API <-->|Async HTTP /ai/*| FASTAPI_AI
    DJANGO_API <-->|TCP Socket / Psycopg3 Pool| PG_DB
    DJANGO_API <-->|TCP Socket / Redis Protocol| REDIS_CACHE
    DJANGO_API <-->|S3 API / Presigned URLs| OBJ_VAULT

    CELERY_WORKER <-->|Message Queue Task| REDIS_CACHE
    CELERY_WORKER <-->|Direct SQL Worker Connection| PG_DB
    CELERY_WORKER <-->|Quét tệp đính kèm| OBJ_VAULT
```

---

### SƠ ĐỒ 3: HÌNH 2.20 - KIẾN TRÚC HẠ TẦNG VÀ RANH GIỚI TIN CẬY (AR-03)
*Mô hình phân vùng mạng an ninh (DMZ, Application Zone, Secure Data Zone) và Zero-Trust.*

```mermaid
flowchart TD
    subgraph PUBLIC_INTERNET["VÙNG INTERNET CÔNG CỘNG (UNTRUSTED ZONE)"]
        CLIENT_BROWSERS["Trình duyệt Web Người dùng (Client Browsers)"]
        MOBILE_DEVICES["Thiết bị Di động Nhân viên (Mobile Devices)"]
    end

    subgraph DMZ_ZONE["PHÂN VÙNG PHÒNG THỦ BIÊN GIỚI (DMZ ZONE)"]
        WAF["Web Application Firewall (WAF) / Cloudflare\n- Chặn SQL Injection, XSS, Path Traversal\n- Rate limiting theo dải IP"]
        NGINX_EDGE["Nginx Edge Ingress Controller\n- Chứng chỉ số SSL/TLS 1.3\n- Chặn toàn bộ IP nội bộ riêng tư (Anti-SSRF)"]
    end

    subgraph APP_ZONE["VÙNG ỨNG DỤNG NỘI BỘ (PRIVATE APPLICATION ZONE)"]
        API_CLUSTER["Django REST API Cluster (Docker Containers)\n- Chỉ mở cổng nội bộ 8000\n- Không truy cập trực tiếp từ Internet"]
        AI_CLUSTER["FastAPI AI Engine Cluster (Docker Containers)\n- Chỉ mở cổng nội bộ 8001\n- Giao tiếp bảo mật với API Cluster"]
        WORKER_CLUSTER["Celery Worker Farm (Docker Containers)\n- Xử lý ngầm các tác vụ nền"]
    end

    subgraph SECURE_DATA_ZONE["VÙNG DỮ LIỆU TỐI MẬT (ISOLATED SECURE DATA ZONE)"]
        DB_PRIMARY["PostgreSQL Master (Port 5432 Internal Only)\n- Row Level Security (RLS) cưỡng chế mức bảng\n- Quyền truy cập gán theo Role: eas_api, eas_worker"]
        REDIS_SECURE["Redis Cluster (Port 6379 Password-Protected)\n- Tắt lệnh nguy hiểm (FLUSHALL, CONFIG)"]
        S3_STORAGE["Encrypted Object Storage (KMS Key-Protected)\n- Phân quyền theo Bucket Policy độc quyền"]
    end

    CLIENT_BROWSERS -->|HTTPS :443| WAF
    MOBILE_DEVICES -->|HTTPS :443| WAF
    WAF --> NGINX_EDGE
    
    NGINX_EDGE -->|Private VPC Network| API_CLUSTER
    
    API_CLUSTER <-->|Internal Docker Bridge| AI_CLUSTER
    API_CLUSTER <-->|Unix Domain Socket / TCP| DB_PRIMARY
    API_CLUSTER <-->|TCP Auth| REDIS_SECURE
    API_CLUSTER <-->|IAM Role Token| S3_STORAGE

    WORKER_CLUSTER <-->|Task Broker| REDIS_SECURE
    WORKER_CLUSTER <-->|SQL Connection| DB_PRIMARY
    WORKER_CLUSTER <-->|S3 API| S3_STORAGE
```

---

### SƠ ĐỒ 4: HÌNH 2.21 - PHÂN RÃ CÁC THÀNH PHẦN XỬ LÝ BACKEND (AR-04)
*Cấu trúc module hóa phân tầng trong `api_core` bảo đảm tính phân tách độc lập (Separation of Concerns).*

```mermaid
flowchart TD
    subgraph HTTP_LAYER["1. TẦNG GIAO TIẾP HTTP & MIDDLEWARE"]
        MW_AUTH["Authentication Middleware\n(Trích xuất Actor từ Cookie/Header)"]
        MW_CSRF["CSRF Protection Middleware\n(Kiểm tra SameSite=Lax & CSRF Token)"]
        MW_SEC_HEADERS["Security Headers Middleware\n(CSP, HSTS, X-Frame-Options)"]
        ROUTERS["API Routers & URL Dispatchers\n(/auth/*, /requests/*, /admin/*, /ai/*)"]
    end

    subgraph SERVICE_LAYER["2. TẦNG NGHIỆP VỤ LÕI (CORE BUSINESS LOGIC)"]
        AUTH_SVC["Auth & Identity Service\n(Xác thực, phân quyền RBAC, Security Epoch)"]
        WF_SVC["Workflow Engine Service\n(Chuyển trạng thái FSM, tính toán lộ trình duyệt)"]
        BRE_SVC["Business Rule Engine (BRE)\n(Kiểm tra hạn mức ngân sách, ngày phép, chính sách)"]
        EXE_SVC["Execution & Acceptance Service\n(Tiếp nhận việc Lease, xử lý vướng mắc, nghiệm thu)"]
        CONF_SVC["Config & Versioning Service\n(Quản lý mẫu đơn, phát hành Release bất biến)"]
    end

    subgraph INTEGRATION_LAYER["3. TẦNG TÍCH HỢP & GIAO TIẾP NGOẠI VI"]
        AI_CLIENT["AI Service Client\n(HTTP Pool, Warm-up, Circuit Breaker Fallback)"]
        MOCK_INTEGRATOR["Enterprise Systems Integrator\n(Giao tiếp 8 Mock APIs với cơ chế Circuit Breaker)"]
        OUTBOX_EMITTER["Transactional Outbox Emitter\n(Đóng gói sự kiện đồng thời với giao dịch)"]
        AUDIT_RECORDER["Cryptographic Audit Recorder\n(Tính mã băm SHA-256 xâu chuỗi bản ghi)"]
    end

    subgraph DATA_ACCESS_LAYER["4. TẦNG TRUY XUẤT DỮ LIỆU (PERSISTENCE REPOSITORY)"]
        REPO_USER["User & Role Repository (`eas.app_user`, `role_membership`)"]
        REPO_REQ["Request & Revision Repository (`eas.request`, `request_revision`)"]
        REPO_STEP["Approval Step Repository (`eas.approval_step`, `step_decision`)"]
        REPO_ATTEMPT["Execution Repository (`eas.execution_attempt`, `acceptance_record`)"]
        REPO_AUDIT["Audit Ledger Repository (`eas.audit_log`, `audit_head`)"]
    end

    HTTP_LAYER --> SERVICE_LAYER
    SERVICE_LAYER --> INTEGRATION_LAYER
    SERVICE_LAYER --> DATA_ACCESS_LAYER
    INTEGRATION_LAYER --> DATA_ACCESS_LAYER
```

---

### SƠ ĐỒ 5: HÌNH 2.22 - SƠ ĐỒ LUỒNG DỮ LIỆU PHÂN TÁN VÀ KIẾN TRÚC OUTBOX (AR-05)
*Mô hình Transactional Outbox Pattern bảo đảm tính "At-least-once Delivery" không mất mát sự kiện.*

```mermaid
sequenceDiagram
    autonumber
    actor User as "Người dùng (Web/Mobile)"
    participant API as "API Core (Django)"
    participant DB as "PostgreSQL (ACID DB)"
    participant Poller as "Outbox Dispatcher Worker"
    participant Redis as "Redis Pub/Sub"
    participant PushSrv as "Notification Delivery Service"
    actor Recipient as "Người nhận (Cấp quản lý / Cán bộ)"

    User->>API: Gửi đơn / Ký duyệt / Nghiệm thu
    API->>DB: BEGIN TRANSACTION (Nguyên tử)
    API->>DB: 1. Cập nhật bảng nghiệp vụ (`eas.request`, `approval_step`)
    API->>DB: 2. Ghi bản ghi kiểm toán (`eas.audit_log`)
    API->>DB: 3. GHI SỰ KIỆN OUTBOX (`eas.outbox_event` status='PENDING')
    API->>DB: COMMIT TRANSACTION (Hoàn tất 100%)
    DB-->>API: Giao dịch lưu trữ thành công
    API-->>User: 200 OK (Thao tác thành công tức thì)

    Note over DB,Poller: TIẾN TRÌNH QUÉT BẤT ĐỒNG BỘ ĐỘC LẬP
    loop Quét định kỳ mỗi 5 giây (Hoặc nhận Notify từ Postgres Listen)
        Poller->>DB: SELECT * FROM eas.outbox_event WHERE status = 'PENDING' FOR UPDATE SKIP LOCKED LIMIT 50
        DB-->>Poller: Trả về danh sách sự kiện cần phát tán
        loop Duyệt qua từng sự kiện
            Poller->>Redis: Đẩy thông điệp vào Redis Stream / Queue
            Redis->>PushSrv: Worker nhận thông điệp phát tán
            par Gửi Email SMTP
                PushSrv->>Recipient: Gửi email thông báo định dạng HTML chuẩn
            and Gửi Push Mobile
                PushSrv->>Recipient: Gửi thông báo đẩy lên thiết bị điện thoại
            end
            PushSrv-->>Poller: Xác nhận đã gửi thành công
            Poller->>DB: UPDATE eas.outbox_event SET status = 'DISPATCHED', delivered_at = now() WHERE id = %s
        end
    end
```

---

### SƠ ĐỒ 6: BỔ SUNG CHƯƠNG 2 - MÔ HÌNH BẢO MẬT PHÒNG THỦ ĐA TẦNG (SEC-01)
*Kiến trúc Zero-Trust: 7 lớp bảo vệ chống tấn công mạng và rò rỉ dữ liệu.*

```mermaid
flowchart TD
    subgraph LAYER1["LỚP 1: BẢO VỆ MẠNG & CỔNG BIÊN (NETWORK & EDGE)"]
        L1_1["WAF Cloudflare: Chặn IP xấu, chống DDoS"]
        L1_2["Nginx Ingress: Chặn dải IP nội bộ tư nhân (SSRF Prevention)"]
        L1_3["Phân lập cổng vật lý: 8080 (Client) vs 8081 (Admin)"]
    end

    subgraph LAYER2["LỚP 2: BẢO VỆ TRUYỀN DẪN & PHIÊN (TRANSPORT & SESSION)"]
        L2_1["Mã hóa HTTPS TLS 1.3 bắt buộc toàn tuyến"]
        L2_2["Cookie HttpOnly, Secure, SameSite=Lax (Chống XSS đánh cắp Session)"]
        L2_3["Kỷ nguyên An ninh (Security Epoch): Thu hồi phiên tức thì khi đổi quyền"]
    end

    subgraph LAYER3["LỚP 3: BẢO VỆ ĐẦU VÀO & BỘ LỌC DỮ LIỆU (INPUT VALIDATION)"]
        L3_1["Server-side Schema Validation (Pydantic / Django Serializers)"]
        L3_2["Magic Bytes Check & ClamAV Stream Scanner (Chặn mã độc đính kèm)"]
        L3_3["Idempotency-Key Header (Chống nộp đúp mạng lag)"]
    end

    subgraph LAYER4["LỚP 4: PHÂN QUYỀN TRUY CẬP TÀI NGUYÊN (AUTHORIZATION RBAC/ABAC)"]
        L4_1["Authentication Middleware chạy trước mọi Handler"]
        L4_2["Kiểm tra quyền sở hữu tài nguyên: `owner_id == actor.id` (Chống IDOR)"]
        L4_3["Khóa cứng 4 quyền Hệ thống: Chỉ Admin tối cao mới được chạm vào"]
    end

    subgraph LAYER5["LỚP 5: BẢO VỆ TOÀN VẸN NGHIỆP VỤ (BUSINESS LOGIC INTEGRITY)"]
        L5_1["Nguyên tắc Phân tách nhiệm vụ (Separation of Duties - SoD)"]
        L5_2["Cơ chế Bốn mắt (Four-Eyes): Acceptor bắt buộc khác Executor"]
        L5_3["Khóa hàng CSDL `FOR UPDATE` (Triệt tiêu hoàn toàn Race Condition)"]
    end

    subgraph LAYER6["LỚP 6: BẢO VỆ CƠ SỞ DỮ LIỆU (DATABASE DEFENSE)"]
        L6_1["Supabase PostgreSQL: Cưỡng chế Row Level Security (RLS) trên 100% bảng"]
        L6_2["Thu hồi toàn bộ quyền USAGE/GRANT của `anon` và `authenticated`"]
        L6_3["Parameterized Queries: Triệt tiêu 100% nguy cơ SQL Injection"]
    end

    subgraph LAYER7["LỚP 7: KIỂM TOÁN VÀ CHỐNG CHỐI BỎ (AUDIT & NON-REPUDIATION)"]
        L7_1["Sổ cái Kiểm toán Mật mã học: Băm chuỗi SHA-256 nối tiếp liên tục"]
        L7_2["Checkpoint độc lập đối soát tính toàn vẹn hàng ngày"]
        L7_3["Quyền riêng tư GDPR: Ẩn danh PII nhưng bảo toàn chuỗi băm lịch sử"]
    end

    LAYER1 --> LAYER2
    LAYER2 --> LAYER3
    LAYER3 --> LAYER4
    LAYER4 --> LAYER5
    LAYER5 --> LAYER6
    LAYER6 --> LAYER7
```

---

### SƠ ĐỒ 7: SƠ ĐỒ LUỒNG DỮ LIỆU MỨC 0 - CONTEXT DFD (DFD-00)
*Mô tả luồng thông tin vào/ra tổng quát giữa các đối tác bên ngoài và hệ thống EAS.*

```mermaid
flowchart LR
    REQ["Người yêu cầu\n(Requester)"]
    APP["Người phê duyệt\n(Approver)"]
    EXE["Người thực thi\n(Executor)"]
    ACC["Người nghiệm thu\n(Acceptor)"]
    ADM["Ban Quản trị\n(Admin / Auditor)"]
    MOCK["8 Hệ thống Ngoại vi\n(HR, Finance, IT...)"]

    subgraph DFD_EAS["HỆ THỐNG XỬ LÝ YÊU CẦU NỘI BỘ (EAS - MỨC 0)"]
        CORE_PROC["(0.0)\nTIẾN TRÌNH XỬ LÝ\nTRUNG TÂM EAS"]
    end

    REQ -->|1. Biểu mẫu đơn & Chứng từ| CORE_PROC
    CORE_PROC -->|2. Thông báo tiến độ & Quyết định| REQ

    CORE_PROC -->|3. Hồ sơ cần duyệt & Điểm rủi ro AI| APP
    APP -->|4. Phán quyết: Duyệt / Từ chối / Bổ sung| CORE_PROC

    CORE_PROC -->|5. Hồ sơ đã duyệt chờ thi công| EXE
    EXE -->|6. Nhận việc & Báo cáo kết quả| CORE_PROC

    CORE_PROC -->|7. Mời nghiệm thu kết quả bàn giao| ACC
    ACC -->|8. Biên bản nghiệm thu: Đạt / Làm lại| CORE_PROC

    ADM -->|9. Cấu hình quy chế & Phân quyền| CORE_PROC
    CORE_PROC -->|10. Báo cáo Dashboard & Log kiểm toán| ADM

    CORE_PROC <-->|11. Tra cứu hạn mức & Số dư| MOCK
```

---

### SƠ ĐỒ 8: SƠ ĐỒ LUỒNG DỮ LIỆU MỨC 1 - SUB-SYSTEM DFD (DFD-01)
*Phân rã luồng dữ liệu chi tiết giữa các phân hệ chức năng và kho dữ liệu.*

```mermaid
flowchart TD
    REQ["Requester"]
    APP["Approver"]
    EXE["Executor"]
    ACC["Acceptor"]
    ADM["Admin"]

    subgraph PROCESSES["CÁC TIẾN TRÌNH XỬ LÝ PHÂN HỆ (DFD MỨC 1)"]
        P1["(1.0) Tiếp nhận & Thẩm định đơn"]
        P2["(2.0) Điều phối & Phê duyệt đa cấp"]
        P3["(3.0) Quản lý Thực thi & Nghiệm thu"]
        P4["(4.0) Giám sát SLA & Cảnh báo"]
        P5["(5.0) Quản trị Cấu hình & Phân quyền"]
        P6["(6.0) Ghi nhận & Kiểm toán Hash-chain"]
    end

    subgraph DATA_STORES["KHO DỮ LIỆU (DATA STORES)"]
        D1[("D1: eas.request & revision")]
        D2[("D2: eas.approval_step")]
        D3[("D3: eas.execution_attempt")]
        D4[("D4: eas.sla_stage")]
        D5[("D5: eas.config_release")]
        D6[("D6: eas.audit_log")]
        D7[("D7: eas.app_user & RBAC")]
        D8[("D8: eas.outbox_event")]
    end

    REQ -->|Nộp hồ sơ| P1
    P1 <-->|Đọc cấu hình mẫu| D5
    P1 -->|Lưu đơn mới| D1
    P1 -->|Tạo sự kiện Outbox| D8
    P1 -->|Khởi tạo bước duyệt| D2
    P1 -->|Kích hoạt đồng hồ SLA| D4
    P1 -->|Ghi log khởi tạo| D6

    APP <-->|Xem & Ký duyệt| P2
    P2 <-->|Đọc/Cập nhật bước duyệt| D2
    P2 -->|Cập nhật trạng thái đơn| D1
    P2 -->|Ghi log phán quyết| D6
    P2 -->|Bàn giao thi công| P3

    EXE <-->|Nhận việc & Nộp kết quả| P3
    P3 <-->|Lưu lượt thi công| D3
    P3 -->|Cập nhật trạng thái| D1
    P3 -->|Ghi log thi công| D6

    ACC <-->|Nghiệm thu bàn giao| P3
    P3 -->|Hoàn thành đơn| D1

    P4 <-->|Quét thời hạn| D4
    P4 -->|Báo động quá hạn| D8

    ADM <-->|Quản trị mẫu đơn & Quyền| P5
    P5 <-->|Cập nhật phân quyền| D7
    P5 <-->|Ban hành cấu hình| D5
    P5 -->|Ghi log quản trị| D6

    P6 <-->|Đọc & Đối soát chuỗi băm| D6
```

---

### SƠ ĐỒ 9: KIẾN TRÚC TRIỂN KHAI CANARY VÀ CIRCUIT BREAKER (CANARY-01)
*Cơ chế tự động cô lập lỗi (Fault Isolation) và phát hành phiên bản an toàn.*

```mermaid
flowchart TD
    subgraph TRAFFIC_INGRESS["LƯU LƯỢNG TRUY CẬP (INGRESS)"]
        USERS["Người dùng toàn hệ thống"]
    end

    subgraph CIRCUIT_BREAKER["BỘ ĐIỀU KHIỂN NGẮT MẠCH (CIRCUIT BREAKER CONTROL)"]
        CB_STATUS{"Trạng thái Kết nối 8 API Nội bộ\n(`eas.mock_apis.is_enabled`)"}
        CB_STATUS -- "BẬT (Enabled)" --> CB_CLOSED["Trạng thái Closed (Bình thường):\nCho phép tải dữ liệu và nộp đơn thông suốt"]
        CB_STATUS -- "TẮT (Disabled)" --> CB_OPEN["Trạng thái Open (Ngắt kết nối):\n- Khóa nút gửi trên Web Client\n- Hiển thị thông báo đỏ cảnh báo người dùng\n- Backend từ chối ngay với mã lỗi 409"]
    end

    subgraph CANARY_DEPLOYMENT["MÔ HÌNH PHÁT HÀNH CANARY (CANARY ROUTING)"]
        ROUTER["Envoy / Nginx Smart Traffic Router"]
        V1_PROD["Production Stable Version (v1.0)\n(90% lưu lượng người dùng)"]
        V2_CANARY["Canary Release Version (v2.0)\n(10% lưu lượng thử nghiệm an toàn)"]
    end

    subgraph MONITORING["GIÁM SÁT VÀ TỰ PHỤC HỒI (SELF-HEALING SENTINEL)"]
        METRICS["Thu thập lỗi thời gian thực (Error Rate, Latency p99)"]
        ROLLBACK_TRIGGER{"Tỷ lệ lỗi Canary > 1%?"}
        ROLLBACK_TRIGGER -- Có lỗi bất thường --> AUTO_DRAIN["Tự động ngắt lưu lượng Canary (0%)\nHoàn trả 100% về phiên bản Stable an toàn"]
        ROLLBACK_TRIGGER -- Hoạt động hoàn hảo --> PROMOTE_PROD["Thăng cấp Canary thành Production chính thức (100%)"]
    end

    USERS --> CB_STATUS
    CB_STATUS --> ROUTER
    ROUTER -->|90% Traffic| V1_PROD
    ROUTER -->|10% Traffic| V2_CANARY

    V2_CANARY --> METRICS
    METRICS --> ROLLBACK_TRIGGER
    ROLLBACK_TRIGGER --> AUTO_DRAIN
    ROLLBACK_TRIGGER --> PROMOTE_PROD
```

---

## 3. BẢNG ĐỐI SOÁT VÀ NÂNG CẤP KIẾN TRÚC THEO CHUẨN IT 15 NĂM

| Tiêu Chí Kiến Trúc | Đặc Tả Ban Đầu Trong DOCX | Hiện Thực Trong Codebase | Nhận Định & Nâng Cấp Chuyên Gia IT 15 Năm |
|:---:|:---|:---|:---|
| **Ranh giới Cổng (Port Isolation)** | DOCX đề cập chung chung Web Application trên cổng chuẩn. | Tách biệt cứng: Web Client chạy cổng `8080`, Web Admin chạy cổng `8081`. | **Tuyệt đối an toàn:** Ngăn chặn việc nhân viên thường mò mẫm vào trang quản trị; Session và Cookie hoàn toàn cô lập. |
| **Giao tiếp Supabase Database** | DOCX mô tả client gọi trực tiếp Supabase qua SDK. | Toàn bộ giao tiếp CSDL đi qua Backend Django REST API; thu hồi toàn bộ quyền của `anon`/`authenticated`. | **Bảo mật tối cao:** Tuân thủ triệt để nguyên tắc `AGENTS.md`. Client không bao giờ giữ chìa khóa Database, chống rò rỉ dữ liệu. |
| **Truyền tin Outbox Pattern** | DOCX mô tả phát thông báo trực tiếp khi duyệt đơn. | Triển khai Transactional Outbox Pattern: Lưu vào bảng `eas.outbox_event` trước khi gửi. | **Chống mất dữ liệu:** Bảo đảm tin nhắn không bao giờ bị mất nếu hạ tầng mạng hoặc Email server bị gián đoạn. |
| **Khóa tranh chấp (Concurrency)** | DOCX chưa đặc tả cơ chế chống nộp đúp mạng lag. | Triển khai `Idempotency-Key` Header và khóa bi quan `FOR UPDATE` mức dòng. | **Nguyên tử hóa:** Chống hoàn toàn tình huống nhân viên bấm nút 2 lần sinh ra 2 đơn hàng hoặc 2 sếp cùng duyệt 1 đơn. |
| **Circuit Breaker** | DOCX chưa đề cập ngắt kết nối ngoại vi. | Bảng `eas.mock_apis` và Circuit Breaker tự động khóa mẫu đơn trên UI khi API tắt. | **Chống phân rã hệ thống:** Bảo vệ tính toàn vẹn nghiệp vụ khi các hệ thống vệ tinh (HR, Finance) bảo trì. |
