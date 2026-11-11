# 2.1. PHÂN TÍCH YÊU CẦU HỆ THỐNG

## 2.1.1. Xác định các tác nhân của hệ thống

EAS phục vụ nhiều nhóm người dùng có trách nhiệm tách biệt. Hệ thống quản lý vai trò theo hai nguyên tắc:

1. **Vai trò có phạm vi.** Mỗi vai trò gắn với:
   - phạm vi toàn công ty hoặc một phòng ban;
   - toàn bộ loại yêu cầu hoặc một loại cụ thể;
   - thời gian hiệu lực.
2. **Tách tài khoản quản trị khỏi tài khoản nghiệp vụ.** Một tài khoản không được đồng thời giữ vai trò quản trị (POLICY_ADMIN, OPS_ADMIN, AUDITOR) và vai trò nghiệp vụ. Ràng buộc này do trigger CSDL cưỡng chế.

**Bảng 2.1. Danh sách tác nhân và trách nhiệm**

| Mã | Tác nhân | Trách nhiệm chính | Phạm vi |
|---|---|---|---|
| REQUESTER | Người yêu cầu | Soạn nháp, đính kèm chứng từ, gửi, bổ sung, rút đơn; theo dõi tiến độ | Nhân viên được cấp quyền tạo theo phòng ban / loại đơn |
| APPROVER | Người phê duyệt | Duyệt, từ chối hoặc yêu cầu bổ sung ở bước được giao; chỉ định người thực hiện ở bước cuối (mẫu B/C); ủy quyền khi vắng; thu hồi quyết định tự duyệt của AI trong 24 giờ (không áp dụng cho đơn của chính mình) | Theo ma trận thẩm quyền và phạm vi phòng ban |
| EXECUTOR | Người thực hiện | Nhận việc, báo không thể nhận / báo vướng, nộp kết quả và bằng chứng | Bộ phận chuyên môn (CNTT, Mua sắm, Kế toán, Hành chính…) |
| ACCEPTOR | Người nghiệm thu | Chấp nhận kết quả hoặc yêu cầu làm lại (mẫu C); bắt buộc khác người thực hiện | Theo quy chế từng loại: chính người yêu cầu, quản lý trực tiếp, CTO, Pháp chế hoặc Quản lý dự án |
| POLICY_ADMIN | Quản trị quy chế | Soạn, kiểm tra, ban hành phiên bản quy chế (biểu mẫu, luật định tuyến, SLA); quản lý quy định công ty | Toàn công ty; chỉ tài khoản quản trị |
| OPS_ADMIN | Quản trị vận hành | Điều chuyển người xử lý; gửi lại sự kiện lỗi; quản lý người dùng, phân quyền, tích hợp, bảo trì | Toàn công ty; chỉ tài khoản quản trị |
| AUDITOR | Kiểm toán nội bộ | Tra cứu hồ sơ theo phạm vi; kiểm chứng chuỗi băm; xem báo cáo | Toàn công ty hoặc phòng ban; tài khoản kiểm soát riêng |
| SYSTEM_WORKER | Tác nhân nền | Quét SLA, gửi thông báo, chạy phiên học quy định, gọi động cơ tự duyệt | Tiến trình `run_outbox_worker` |
| AI_SYSTEM | Tài khoản AI hệ thống | Ký duyệt các bước đủ điều kiện tự duyệt; không thể đăng nhập | Chỉ bước của mẫu A, trọng số ≤ 2 |

Ngoài ra còn hai tác nhân thao tác qua dòng lệnh có kiểm soát:
- **Identity Operator**: nạp danh sách nhân sự.
- **Privacy Operator**: xử lý yêu cầu về dữ liệu cá nhân.

Cả hai thuộc tổ quản trị.

## 2.1.2. Xác định phạm vi và các phân hệ chức năng

EAS P0 gồm **8 phân hệ**:

| # | Phân hệ | Chức năng chính | Module mã nguồn |
|---|---|---|---|
| 1 | Quản lý yêu cầu | Danh mục 58 loại yêu cầu hoạt động theo **12 nhóm lớn** (`eas.request_group`) với **61 mục chọn trên menu** (`eas.request_menu_item`); biểu mẫu động theo quy chế; nháp có khoá lạc quan; đính kèm an toàn; xem trước tuyến duyệt | `api_core/workflow/service.py`, `attachments.py`, `api_core/catalog/` |
| 2 | Phê duyệt đa cấp | Chuỗi 1–5 cấp tuần tự; duyệt / từ chối / bổ sung; ủy quyền; tự thay người duyệt vắng mặt | `service.decide_approval`, `delegation.py` |
| 3 | Thực hiện & nghiệm thu | Nhận việc, báo vướng, nộp kết quả, nghiệm thu, làm lại | `service.start_execution`, `submit_execution`, `decide_acceptance` |
| 4 | Luật nghiệp vụ & cấu hình quy chế | Luật định tuyến có cấu trúc; phiên bản quy chế bất biến; kiểm tra trước khi ban hành | `api_core/domain/routing.py`, `workflow/config_service.py` |
| 5 | SLA & thông báo | Chặng SLA cho từng bước; nhắc ở 50%; ghi vi phạm ở 100%; hàng đợi outbox có thử lại | `api_core/worker.py` |
| 6 | Kiểm toán & báo cáo | Chuỗi băm RFC 8785 + SHA-256; kiểm chứng; báo cáo theo phạm vi | `api_core/audit.py`, `workflow/reporting.py` |
| 7 | Trí tuệ nhân tạo | Gợi ý loại, rủi ro tham khảo, tự duyệt có kiểm soát, tóm tắt, học quy định | `ai_service/`, `workflow/auto_approval.py`, `workflow/ai_learning.py` |
| 8 | Quản trị hệ thống | Tổ chức, người dùng, vai trò, quyền module; quy định công ty; tích hợp; phiên bản hệ thống; bảo trì; thông báo toàn hệ thống | `api_core/administration/`, `api_core/maintenance.py` |

Hệ thống tích hợp với **8 hệ thống nghiệp vụ ngoài mô phỏng** (`mock_*`, Bảng 1.4) thông qua dịch vụ độc lập **Mock Systems API** (`mock_systems :8100`, role CSDL `eas_mock`, xác thực nội bộ bằng `X-Integration-Secret`). EAS hoàn toàn không đọc/ghi trực tiếp bảng `mock_*` bằng SQL mà chỉ gọi qua client tích hợp `api_core/integrations/client.py` (tôn trọng công tắc Circuit Breaker trong `eas.mock_apis`).

## 2.1.3. Yêu cầu chức năng

**Bảng 2.2. Danh mục ca sử dụng**

| Mã | Ca sử dụng | Tác nhân chính | Mô tả | API chính |
|---|---|---|---|---|
| UC01 | Đăng nhập và quản lý phiên | Mọi người dùng | Xác thực, chống dò mật khẩu, đổi mật khẩu bắt buộc lần đầu, đăng xuất | `POST /api/v1/auth/login`, `/logout`, `/password` |
| UC02 | Ban hành quy chế | POLICY_ADMIN | Tạo / sao chép bản nháp, sửa, kiểm tra, ban hành phiên bản bất biến | `/api/v1/config-releases`, `/{id}/validate`, `/{id}/publish` |
| UC03 | Soạn nháp và đính kèm | REQUESTER | Tạo nháp, lưu với khoá lạc quan, tải tệp PDF/PNG/JPEG ≤ 10 MB đã quét mã độc | `/api/v1/request-drafts`, `/request-drafts/{id}/attachments` |
| UC04 | Gửi yêu cầu | REQUESTER | Kiểm dữ liệu, chụp phiên bản quy chế, định tuyến, kiểm tách nhiệm, khởi động quy trình | `POST /api/v1/requests/{id}/submit`, `/requests/route-preview` |
| UC05 | Xem hồ sơ | Mọi người tham gia, AUDITOR | Chỉ chủ hồ sơ, người tham gia và kiểm toán theo phạm vi mới xem được; ngoài phạm vi trả 404 | `GET /api/v1/requests/{id}`, `/history`, `/revisions` |
| UC06 | Quyết định phê duyệt | APPROVER | Duyệt / từ chối / yêu cầu bổ sung; hai lựa chọn sau bắt buộc lý do 10–2000 ký tự | `POST /api/v1/requests/{id}/approval-decisions` |
| UC07 | Bổ sung và nộp lại | REQUESTER | Sửa hồ sơ bị trả về, nộp lại thành phiên bản mới | `PATCH /request-drafts/{id}`, `POST /requests/{id}/submit` |
| UC08 | Rút đơn | REQUESTER | Huỷ khi chưa có quyết định duyệt cuối | `POST /api/v1/requests/{id}/withdraw` |
| UC09 | Điều chuyển người xử lý | OPS_ADMIN | Đổi người duyệt, người thực hiện, người nghiệm thu; bắt buộc lý do; giữ hạn SLA | `POST /api/v1/requests/{id}/reassign` |
| UC10 | Nhận việc | EXECUTOR | Nhận hồ sơ đã duyệt; hoặc báo không thể nhận | `POST /api/v1/requests/{id}/claim`, `/issues` |
| UC11 | Báo vướng và nộp kết quả | EXECUTOR | Báo vướng; nộp ghi chú (10–4000 ký tự), mã tham chiếu và tệp bằng chứng | `/requests/{id}/execution/issues`, `/execution/submit`, `/execution/attachments` |
| UC12 | Nghiệm thu | ACCEPTOR | Chấp nhận hoặc yêu cầu làm lại (bắt buộc lý do) | `POST /api/v1/requests/{id}/acceptance-decisions` |
| UC13 | Thông báo | Mọi người dùng | Xem và đánh dấu đã đọc; nội dung luôn kiểm lại quyền | `/api/v1/notifications`, `/{id}/read` |
| UC14 | Giám sát SLA | SYSTEM_WORKER | Nhắc khi qua 50% thời hạn; ghi vi phạm khi quá hạn; thông báo người đang giữ việc | `worker.process_sla_batch` |
| UC15 | Kiểm toán và báo cáo | AUDITOR, OPS_ADMIN | Xem nhật ký, kiểm chứng chuỗi băm, báo cáo theo phạm vi | `/requests/{id}/audit`, `/audit/verify`, `/reports/requests`, `/admin-events` |
| UC16 | Ủy quyền phê duyệt | APPROVER | Giao quyền duyệt cho người khác trong khoảng thời gian; thu hồi | `/api/v1/delegations`, `/{id}/revoke` |
| UC17 | Danh tính và phân quyền | OPS_ADMIN, Identity Operator | Nạp nhân sự (chạy thử / áp dụng), quản lý người dùng và vai trò | `manage.py identity_import`, `/api/v1/admin/users-management` |
| UC18 | AI tự duyệt và thu hồi | AI_SYSTEM, APPROVER | Tự duyệt bước đủ điều kiện; thu hồi trong 24 giờ | `/internal/requests/{id}/auto-approve`, `/requests/{id}/ai-approval/revoke` |
| UC19 | Quy định công ty và học quy định | POLICY_ADMIN, SYSTEM_WORKER | Quản lý văn bản quy định; biên dịch thành bộ luật; khoá cổng nhân viên trong lúc học | `/api/v1/admin/…` (`regulations_ai.py`), `ai_learning_job` |
| UC20 | Thông báo hệ thống | Mọi người dùng | Đọc thông báo thay đổi quy định / phiên bản | `/api/v1/announcements`, `/{id}/read` |
| UC21 | Bảo trì hệ thống | OPS_ADMIN | Chặn thao tác ghi khi nâng cấp | `/api/v1/system/maintenance/{start,complete}` |
| UC22 | Phân quyền module | OPS_ADMIN | Ma trận vai trò × module, quyền riêng từng người | `/api/v1/admin/rbac/*`, `/api/v1/auth/permissions/me` |
| UC23 | Quên mật khẩu | Mọi người dùng, OPS_ADMIN | Người dùng gửi yêu cầu; OPS_ADMIN được báo qua email, xét duyệt; hệ thống gửi mật khẩu tạm thời và bắt đổi ở lần đăng nhập kế tiếp | `/api/v1/auth/password-reset/request`, `/password-reset/requests/{id}/approve` |
| UC24 | Tích hợp & tra cứu dữ liệu hệ thống ngoài | Người dùng theo quyền, Hệ thống | Lấy danh mục chọn (phòng, xe, thiết bị, ứng dụng, loại chi phí) và kiểm tra/ghi nhận quỹ phép, giữ chỗ tài nguyên, ngân sách qua Mock Systems API (`/mock-api/v1/*` nội bộ kèm `X-Integration-Secret`) | `/api/v1/integrations/options`, `api_core/integrations/client.py` |

## 2.1.4. Yêu cầu phi chức năng

**Bảng 2.3. Yêu cầu phi chức năng và cách đáp ứng**

| Nhóm (ISO/IEC 25010) | Yêu cầu | Giải pháp | Cách kiểm chứng |
|---|---|---|---|
| Bảo mật | Đạt các yêu cầu OWASP ASVS 4.0.3 mức 2 cho xác thực, phiên, kiểm soát truy cập, xử lý tệp | Argon2; cookie HttpOnly / SameSite=Lax / Secure; CSRF; chống dò mật khẩu theo tài khoản và IP; kiểm quyền đối tượng (404 khi ngoài phạm vi); kiểm định dạng tệp bằng magic bytes; quét ClamAV; header bảo mật ở cổng | Kiểm thử tự động `test_authn.py`, `test_security_middleware.py`; e2e `portal.spec.js` |
| Toàn vẹn | Lịch sử phê duyệt không thể sửa / xoá mà không bị phát hiện | Bảng chỉ-ghi-thêm (trigger); chuỗi băm RFC 8785 + SHA-256; API kiểm chứng | `audit/verify`; lệnh `audit_verify` |
| Đúng đắn nghiệp vụ | Không có chuyển trạng thái sai; không vi phạm tách nhiệm | Máy trạng thái hai lớp (dịch vụ + trigger); kiểm tra SoD khi định tuyến và khi điều chuyển | `03_database_regression_DEV_ONLY.sql`; `test_request_workflow_scenarios.py` |
| Tin cậy | Không gửi trùng, không mất thông báo | Khoá Idempotency-Key; transactional outbox có lease, thử lại, DEAD và gửi lại | `test_ops_and_config.py` |
| Đồng thời | Hai người thao tác cùng lúc không ghi đè nhau | Khoá dòng `FOR UPDATE`; `lock_version` (trả 409 khi lệch); khoá `security_epoch` khi đổi quyền | Kịch bản SD-05, SD-12, SD-19 |
| Sẵn sàng | Lõi nghiệp vụ hoạt động khi dịch vụ AI lỗi | Gọi AI ngoài giao dịch, có thời gian chờ; lỗi thì chuyển người duyệt | `test_ai_auto_approve_revoke.py` |
| Hiệu năng | Mục tiêu p95 tại cổng: đọc ≤ 800 ms, ghi ≤ 1.500 ms (CSDL đặt ở Sydney); AI phân loại ≤ 300 ms | Pool kết nối; chỉ mục; lưu đệm tóm tắt AI | Đo trong Chương 3.3.4 |
| Khả dụng | Giao diện tiếng Việt, lỗi dễ hiểu, dùng được trên điện thoại | Hệ thiết kế dùng chung; thông báo lỗi kèm mã tra cứu; bố cục co giãn | `design-system.test.mjs`, `ui.spec.js` |
| Bảo trì | Thay đổi quy trình không cần sửa mã | Quy chế dạng dữ liệu có phiên bản; migration có kịch bản rollback | Migration 08–13 kèm `rollback/` |
| Bảo vệ dữ liệu cá nhân (Nghị định 13/2023) | Tối thiểu hoá; xử lý yêu cầu của chủ thể dữ liệu; không xoá khi đang bị phong toả pháp lý | View đã lọc PII cho dữ liệu tích hợp; `privacy_case`, `retention_hold`; lọc nội dung trước khi gửi Gemini | Lệnh `privacy_case` |
