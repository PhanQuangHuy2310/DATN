# 01 — Phân tích yêu cầu hệ thống (DOCX 2.1)

> Phạm vi: 2.1.1 (tác nhân), 2.1.2 (phân hệ), 2.1.3 (yêu cầu chức năng / Bảng 2.2) và 2.1.4 (yêu cầu phi chức năng / Bảng 2.3).
> Bằng chứng lấy từ code, lược đồ DB và DB live đọc ngày 04/11/2026.

## 1. Tác nhân (Bảng 2.1)

| Mã | DOCX | Hiện thực | Lệch | Phán quyết |
|---|---|---|---|---|
| REQUESTER | Toàn bộ nhân viên | Vai trò có trong `eas.role` và `role_membership.role`. Live có **136** membership còn hiệu lực | — | KHỚP |
| APPROVER | Trưởng phòng, Giám đốc khối, Ban Giám đốc; xem điểm rủi ro AI | Live có **46** membership. Màn hình duyệt hiển thị gợi ý AI qua `AiAssist`, nhưng điểm này **không phải đầu ra XGBoost** (xem tệp 11) | Nguồn của "điểm rủi ro AI" không đúng như mô tả | LỆCH NHẸ |
| EXECUTOR | IT, Mua sắm, Kế toán | Live có **97** membership. Định tuyến qua 11 slot `EXECUTOR_*` (`api_core/domain/routing.py:28-40`) | — | KHỚP |
| ACCEPTOR | Người đề xuất **hoặc** bộ phận QC độc lập | Live có **177** membership. Slot gồm `REQUESTER`, `DIRECT_MANAGER`, `CTO`, `LEGAL`, `PROJECT_MANAGER` (`routing.py:41-47`). Ràng buộc acceptor ≠ executor (`routing.py:258`) | Bảng 1.2 DOCX viết "C có người nghiệm thu **độc lập**". Thực tế nhiều loại C để chính người tạo nghiệm thu (vd `EQUIPMENT`, `VEHICLE_BOOKING`) | LỆCH NGHIỆP VỤ nhẹ. Theo COSO, người tạo được nghiệm thu khi họ là người thụ hưởng; acceptor chỉ cần **khác executor**. **Giữ code**, sửa câu chữ ở DOCX |
| POLICY_ADMIN | Ban Pháp chế & Nhân sự | Chỉ `admin@eas.com` giữ vai trò này, theo migration 11 (tách tài khoản quản trị) và trigger chặn trộn vai trò | DOCX ngụ ý có nhiều người | LỆCH NHẸ. Đây là quyết định bảo mật đã chốt; ghi vào DOCX |
| OPS_ADMIN | Phòng CNTT | Như trên: 1 membership | Như trên | LỆCH NHẸ |
| AUDITOR | Ban Kiểm soát | Vai trò tồn tại, nhưng live có **0** membership còn hiệu lực. Migration 11 đã thu hồi vai trò này khỏi mọi tài khoản không phải admin | Không ai đọc được báo cáo kiểm toán theo scope AUDITOR | **THIẾU HIỆN THỰC (dữ liệu).** Cần gán AUDITOR cho ít nhất một tài khoản kiểm soát, nằm ngoài tài khoản admin để giữ SoD |
| SYSTEM_WORKER | Celery Worker | Không có Celery. Có tiến trình `run_outbox_worker` (`api_core/management/commands/run_outbox_worker.py`), poll 2 giây, gộp SLA + outbox + AI learning job. AI tự duyệt dưới tài khoản hệ thống không đăng nhập `ai.system@eas.com` (`api_core/workflow/auto_approval.py:56`) | Sai công nghệ | LỆCH NHẸ. **Giữ code**: không cần thêm broker Redis/Celery |

**Tác nhân có trong hệ thống nhưng DOCX không liệt kê:**
- **AI hệ thống**, actor `HUMAN/SYSTEM` trong audit. Tác nhân này ký duyệt bước có rủi ro thấp.
- **Identity operator / Privacy operator**: có trong ảnh UC-CTL-01 và UC-ADM-01, nhưng Bảng 2.1 bỏ sót.
- **Người được ủy quyền (delegate)**, lấy từ `eas.approval_delegation`.

## 2. Phân hệ chức năng (2.1.2)

| # | Phân hệ (DOCX) | Module code | Đánh giá |
|---|---|---|---|
| 1 | Quản lý yêu cầu | `api_core/workflow/service.py` (create/update draft, submit), `api_core/catalog/*`; **66** loại đơn live (`eas.request_type`), 58 đang hoạt động, chia **12 nhóm lớn** (`eas.request_group`) với **61 mục chọn trên menu** (`eas.request_menu_item`) | KHỚP |
| 2 | Phê duyệt đa cấp | `service.decide_approval`, `delegation.py`, `_substitute_approver` (`service.py:1652`) | KHỚP. Code còn có ủy quyền và thay người vắng mặt mà DOCX chỉ nhắc qua |
| 3 | Thực thi & Nghiệm thu | `service.start_execution`, `submit_execution`, `decide_acceptance`, `report_execution_issue` | KHỚP |
| 4 | BRE & Cấu hình quy chế | `domain/routing.py`, `workflow/config_service.py`, `eas.config_release` (78 bản live) | KHỚP |
| 5 | SLA & Thông báo | `api_core/worker.py` (`process_sla_batch`, `run_outbox_batch`) | KHỚP về cơ chế. Khác ngưỡng (tệp 02 §5) |
| 6 | Sổ cái kiểm toán & Báo cáo | `api_core/audit.py` (RFC 8785), `workflow/reporting.py`, `requests/{id}/audit/verify` | KHỚP một phần. **Không có checkpoint ra kho ngoài** (live `audit_checkpoint` = 0 dòng) |
| 7 | AI Microservice | `ai_service/routers/{classify,risk,auto_approve,ocr,summarize,policy,mock_context}.py` | KHỚP về API. Mức sử dụng thực tế xem tệp 11 |
| — | *(không có trong DOCX)* Quản trị hệ thống | `api_core/administration/*`: tổ chức/người dùng/RBAC, quyền module, quy định công ty và học quy định AI, phiên bản hệ thống, thông báo toàn hệ thống, bảo trì | **DOCX thiếu.** Bổ sung phân hệ 8 "Quản trị & cấu hình hệ thống" |
| — | *(không có trong DOCX)* Tích hợp hệ thống ngoài mô phỏng | `api_core/integrations/*`, dịch vụ độc lập `mock_systems` (`:8100`, role CSDL `eas_mock`, `/mock-api/v1/*`, header `X-Integration-Secret`), 8 schema `mock_*` | Bổ sung vào 2.1.2 dưới dạng "tích hợp hệ thống ngoài qua Mock Systems API" (EAS không đọc bảng `mock_*` trực tiếp) |

## 3. Yêu cầu chức năng (Bảng 2.2)

DOCX viết "16 ca sử dụng" nhưng bảng chỉ có 15 dòng: UC01–UC15 và UC17, **không có UC16**. Ảnh UC-CTX-01 cũng không có UC16.

| UC | Tên | Endpoint / bằng chứng | Trạng thái |
|---|---|---|---|
| UC01 | Đăng nhập & phiên | `api/v1/auth/{csrf,login,logout,me,password}`, `authn/login_throttle.py`, Argon2 (`settings.py:129`), signed-cookie 8 giờ + Redis idle key | KHỚP |
| UC02 | Ban hành quy chế | `config-releases`, `/{id}/validate`, `/{id}/publish` | KHỚP |
| UC03 | Nháp & tệp | `request-drafts`, `request-drafts/{id}/attachments` (10MB, magic bytes, ClamAV) | KHỚP. Quét đồng bộ, không QUEUED (tệp 05 SD-02) |
| UC04 | Submit | `requests/submit`, `requests/{id}/submit`, `requests/route-preview` | KHỚP |
| UC05 | Xem hồ sơ chống IDOR | `requests/{id}`: owner / participant / AUDITOR theo scope; trả 404 khi ngoài scope (`workflow/views.py:476-497`) | KHỚP với ảnh SD-10. Text PL-16 cho "quản lý cùng phòng" xem, code **không cho** → giữ code (least privilege) |
| UC06 | Quyết định duyệt | `requests/{id}/approval-decisions` | KHỚP |
| UC07 | Bổ sung & nộp lại | trạng thái `NEEDS_INFO` → `submit` tạo revision mới | LỆCH NHẸ (tên trạng thái; xem tệp 02) |
| UC08 | Rút đơn | `requests/{id}/withdraw`, `requests/{id}/cancel` | KHỚP |
| UC09 | Reassign | `requests/{id}/reassign`, `target_kind ∈ {APPROVAL_STEP, EXECUTOR, ACCEPTOR, PLANNED_EXECUTOR}` (`ops_service.py:522`) | KHỚP. URL khác text PL-28 |
| UC10 | Claim | `requests/{id}/claim`, `execution/start` | KHỚP |
| UC11 | Tiến độ & nộp kết quả | `execution/issues`, `execution/submit`, `execution/attachments` | KHỚP |
| UC12 | Nghiệm thu | `acceptance-decisions` | KHỚP |
| UC13 | Thông báo | `notifications`, `notifications/{id}/read` | KHỚP |
| UC14 | SLA | `worker.process_sla_batch` | KHỚP cơ chế. Khác ngưỡng; không gửi cho cấp quản lý (chỉ gửi người đang giữ việc) |
| UC15 | Kiểm toán & báo cáo | `requests/{id}/audit`, `audit/verify`, `reports/requests`, `reports/team`, `admin-events`, lệnh `audit_verify` | KHỚP một phần (thiếu checkpoint) |
| UC16 | — | — | **DOCX thiếu.** Đề xuất: **UC16 "Ủy quyền phê duyệt (Delegation)"**. Chức năng đã hiện thực (`delegations`, `delegations/{id}/revoke`, `approval_delegation`) |
| UC17 | Danh tính & phân quyền | Lệnh `identity_import` (dry-run/apply), `administration/org_users_rbac.py` | KHỚP |

**Chức năng đã hiện thực nhưng chưa có UC trong DOCX.** Cần bổ sung vào Bảng 2.2 dưới dạng UC18–UC24:

| Đề xuất | Chức năng | Bằng chứng |
|---|---|---|
| UC18 | AI tự duyệt rủi ro thấp và thu hồi trong 24 giờ | `internal/requests/{id}/auto-approve`, `requests/{id}/ai-approval/revoke` |
| UC19 | Quản lý quy định công ty và học quy định AI (khoá cổng nhân viên khi đang học) | `administration/regulations_ai.py`, `workflow/ai_learning.py`, migration 12 |
| UC20 | Thông báo hệ thống / cập nhật phiên bản | `announcements`, `system_announcement`, `eas.admin_event` (29 dòng từ `system_versions_changelog` đã gộp vào chuỗi băm `admin_event` ở Migration 15) |
| UC21 | Bảo trì hệ thống (chặn ghi khi nâng cấp) | `system/maintenance/{start,complete}`, `api_core/maintenance.py` |
| UC22 | Phân quyền module theo vai trò và theo người dùng | `role_module_permission`, `user_permissions`, `auth/permissions/me` |
| UC23 | Quên / đặt lại mật khẩu | migration 05, `password_reset_request` |
| UC24 | Tích hợp & tra cứu dữ liệu hệ thống ngoài (quỹ phép, ngân sách, giữ chỗ phòng/xe/thiết bị, cấp quyền IT…) | `/api/v1/integrations/options`, `api_core/integrations/client.py` gọi dịch vụ `mock_systems` (`/mock-api/v1/*`, `X-Integration-Secret`, role `eas_mock`) |

## 4. Yêu cầu phi chức năng (2.1.4, Bảng 2.3)

| Chỉ tiêu | DOCX | Thực tế | Phán quyết |
|---|---|---|---|
| Hiệu năng | Đọc < 200ms; ký duyệt < 500ms; AI < 300ms | Chưa có kết quả đo trong repo. DB đặt ở Sydney, client ở VN nên RTT riêng đã khoảng 150–200ms. Pool kết nối có cấu hình (`settings.py:80-100`) | **Chưa kiểm chứng.** Đổi thành chỉ tiêu đo p95 tại gateway, có test hiệu năng kèm báo cáo. Đặt ngưỡng thực tế: đọc p95 ≤ 800ms, ghi p95 ≤ 1.500ms do vị trí DB |
| Bảo mật | "Chặn 100% OWASP Top 10"; Argon2/PBKDF2 | Argon2 là hasher duy nhất. CSRF, cookie HttpOnly/SameSite=Lax, Secure khi production. Throttle 5 lần/tài khoản và 30 lần/IP mỗi 15 phút (`settings.py:151-153`). Nginx giới hạn login 5 request/phút. CSP và HSTS ở gateway | "100%" không đo được → đổi thành **OWASP ASVS 4.0.3 Level 2**. Bỏ "PBKDF2" (code chỉ dùng Argon2) |
| Toàn vẹn | RFC 8785 + SHA-256 + checkpoint | RFC 8785 dùng thư viện `rfc8785` (`api_core/audit.py:7`). Có `lock_audit_head`, verify API. **Checkpoint: không có** | THIẾU HIỆN THỰC (checkpoint) |
| Sẵn sàng | 99.9% uptime; AI sập vẫn duyệt thủ công | AI sập → `escalate_to_human` (fallback). Không có số đo uptime | Giữ "AI fail-safe". 99.9% phải dựa trên SLA của Supabase và nền tảng host → ghi là "mục tiêu", kèm cách đo |
| Chống trùng | Idempotency-Key + Outbox + Celery | `_execute_idempotent` (`service.py:290`), `idempotency_record`, outbox `dedupe_key`. **Không có Celery** | KHỚP về cơ chế; sửa tên công nghệ |
| Khả dụng trên di động | 1.4.2: Flutter, FCM, sinh trắc học | `mobile_app/lib` có 482 dòng: đăng nhập, danh sách, chi tiết, thông báo, đổi mật khẩu. **Không có FCM, sinh trắc học, nút duyệt** | THIẾU HIỆN THỰC. Thu hẹp mô tả DOCX về đúng phạm vi P0: chỉ theo dõi và thông báo kéo về |

## 5. Ma trận truy vết đề xuất (giữ mã của ảnh sơ đồ)

Các ảnh SD đều có dòng "Trace: UCxx, FRxx, NFRxx, BRxx · Tests: TCxxx". DOCX nên có thêm **Bảng 2.x Ma trận truy vết UC ↔ FR ↔ sơ đồ ↔ test** để giảng viên kiểm tra được độ phủ:

| UC | Sơ đồ | Test (theo ảnh) | Test tự động hiện có trong repo |
|---|---|---|---|
| UC01 | SD-01 | TC001–006, TC071–072 | `api_core/tests/test_authn.py`, `test_security_middleware.py` |
| UC02 | SD-09, AD-07 | TC010–012, TC029, TC075, TC097 | `test_ops_and_config.py` |
| UC03 | SD-02 | TC014–020, TC050, TC076, TC079 | `test_request_workflow_scenarios.py` |
| UC04/07 | SD-03, SD-20, AD-02 | — | `test_workflow_service.py`, `test_workflow_api.py` |
| UC05 | SD-10 | TC023–026, TC068–069 | `test_history_views.py`, `test_role_scope_alignment.py` |
| UC06 | SD-04, AD-03 | TC031–042, TC057–060 | `test_request_workflow_scenarios.py`, `test_approval_delegation.py` |
| UC08 | SD-05 | TC037–038, TC057, TC060 | idem |
| UC09 | SD-07, SD-22, AD-05 | TC039–041, TC046, TC051, TC055, TC057 | `test_ops_and_config.py` |
| UC10–12 | SD-06, SD-21, AD-04 | TC043–055 | `test_request_workflow_scenarios.py` |
| UC13 | SD-15 | TC068–069 | — |
| UC14 | SD-08, AD-06 | TC061–070, TC087 | `test_maintenance.py`, worker tests |
| UC15 | SD-13, SD-16 | TC028, TC082, TC093, TC096 | `test_reporting_and_cli.py`, `test_insights.py` |
| UC17 | SD-11, AD-08 | TC005–009, TC042, TC073 | `test_reporting_and_cli.py` |
| Privacy | SD-14, AD-09 | TC083–085, TC089 | — |
| Vận hành | SD-17, SD-18, AD-10 | TC088–092, TC100 | — |
