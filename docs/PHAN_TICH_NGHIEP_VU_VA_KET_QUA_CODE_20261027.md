# Phân tích nghiệp vụ, truy vết và kết quả triển khai DATN

**Ngày kiểm tra:** 27/10/2026. **Sản phẩm:** Enterprise Approval System (EAS). **Nguyên tắc:** không đồng nhất báo cáo mô tả mong muốn, thiết kế P0 và tính năng đã được kiểm chứng thực tế.

## 1. Tài liệu đã rà soát

| Tài liệu gốc | Vai trò | Kết luận sử dụng |
|---|---|---|
| `docs/source_materials/Report_DATN_CNTT_Nhom07_v1.0.docx` (bản tải lên trong ZIP thứ hai) | Báo cáo đồ án; UC, RBAC, R01–R07, nhu cầu đa ứng dụng | Căn cứ **phạm vi mục tiêu**, không phải chứng cứ nghiệm thu. SHA256 bản tải lên `afa6de52170d73eb41a39f93a5d5b5a8a513d8b5cfac101f3f47b8091186c50a`. |
| `docs/00_Pham_vi_va_ke_hoach_v2.docx`, `docs/01_SRS_v2.docx` | Yêu cầu kiểm chứng, ranh giới P0/P1, quyền và NFR | Baseline vận hành P0. Các thông số nghiệp vụ vẫn **chờ ký KD01–KD08**. |
| `docs/02_Phan_tich_thiet_ke_v2.docx`, `docs/03_Du_lieu_va_API_v2.docx` | State machine, SoD, snapshot revision, API command/read, bảng dữ liệu | Contract triển khai chi tiết; backend phải chặn sai trạng thái/không đúng quyền. |
| `docs/04_Ke_hoach_va_ca_kiem_thu_v2.docx` | TC001–TC100/UAT | Tiêu chuẩn cần chạy thực tế, không phải các ca đã PASS. |
| `docs/PLAN_REQUEST_TYPES_18.json` và tài liệu `plan.docx` trong ZIP nguồn | 18 mã biểu mẫu và tuyến đề xuất theo nghiệp vụ các phòng ban | Các **đề xuất cho danh mục mở rộng**, không phải 18 luồng đã phát hành/hoạt động. |
| `docs/APPROVAL_MENU_POLICY_DRAFTS.json` | Mẫu cấu hình có thể làm bản nháp | Phải có POLICY_ADMIN xác minh/validate/publish và OPS cấp quyền REQUESTER. |

**Sai khác provenance cần lưu ý:** `docs/REPORT_V1_SOURCE_MATRIX.json` của dự án gốc lưu SHA256 `856124e…` cho một bản báo cáo trước; báo cáo Word được tải lên lần này có SHA256 `afa6de…`. Không sửa âm thầm hash lịch sử. Các UC/R01–R07 chính nhìn chung tương ứng nhưng vẫn phải kiểm chi tiết phiên bản trước khi coi ma trận cũ là bằng chứng nguyên bản.

## 2. Phạm vi nghiệp vụ thực tế

**7 vai trò (theo SRS v2):** REQUESTER (tạo, sửa, gửi, bổ sung, rút đơn), APPROVER (quyết định từng cấp được giao), EXECUTOR (nhận việc, báo vướng mắc, nộp kết quả), ACCEPTOR (nghiệm thu hoặc yêu cầu làm lại), POLICY_ADMIN (soạn/kiểm/công bố quy chế), OPS_ADMIN (điều phối/SLA và riêng OPS GLOBAL+ALL được quản trị danh tính), AUDITOR (đọc/audit theo scope). Identity operator và Worker là actor hệ thống/biến thể quyền, không tự tạo hai quyền toàn năng mới. Người nhiều role vẫn chịu phân tách nhiệm vụ **SoD**.

**3 lifecycle baseline:** `LEAVE`/A: duyệt đủ → `COMPLETED`. `ACCESS`/B: duyệt đủ → `READY_FOR_EXECUTION` → nhận việc `IN_PROGRESS` → nộp kết quả → `COMPLETED`. `EQUIPMENT`/C: duyệt đủ → thực hiện → `WAITING_FOR_ACCEPTANCE` → `ACCEPT` mới `COMPLETED`; `REWORK` tạo attempt mới, không tái sử dụng attempt cũ. Các trạng thái yêu cầu: `DRAFT`, `PENDING_APPROVAL`, `NEEDS_INFO`, `REJECTED`, `CANCELLED`, `READY_FOR_EXECUTION`, `IN_PROGRESS`, `WAITING_FOR_ACCEPTANCE`, `COMPLETED`. Route chỉ có **1–3 bước tuần tự** theo SRS; không tự động bỏ cấp/duyệt thay.

**Quy tắc chung:** release `PUBLISHED` bất biến, mỗi lần submit ghim snapshot release + rule + resolved route; revision khác nhau không dùng lại quyết định; upload phải là PDF/JPEG/PNG và trạng thái scanner `CLEAN`; mọi command phải có idempotency key và expected_version (theo từng contract). Read ACL theo owner/participant/auditor có scope, không dựa trên việc UI ẩn nút. Không dùng `OPS_ADMIN` để mặc nhiên đọc toàn bộ payload. Nhật ký/audit/outbox phải gắn với transaction; worker SLA không trực tiếp đổi trạng thái request. Nhân sự rời quyền hoặc xử lý lại phải kiểm SoD ở backend.

## 3. Ma trận truy vết UC → hiện trạng source code

| UC | Yêu cầu nghiệp vụ | Thành phần code | Tình trạng ở thời điểm giao |
|---|---|---|---|
| UC01 | Login, session, logout, đổi mật khẩu | `api_core/authn/`, Web Login/Profile; `mobile_app/lib/` | Có code; bổ sung idle 30 phút, giới hạn 5/tài khoản và 30/IP; **chưa chạy Django+Redis thực tế** |
| UC02 | DRAFT/VALIDATE/PUBLISH quy chế | `workflow/config_service.py`, `components/Admin.jsx` (workspace cấu hình) | Có code, vẫn phải cấu hình bindings và phát hành bằng người có quyền |
| UC03 | Nháp và tệp | `workflow/service.py`, `views.py`, `storage.py`, `RequestEditor.jsx` | Có code; ClamAV/object storage chưa nghiệm chứng |
| UC04 | Submit, route snapshot, SoD | `domain/routing.py`, `workflow/service.py` | Có code; phải chạy DB/UAT |
| UC05 | List/detail/history/file có scope | `workflow/views.py`, `history_views.py` | Sửa tab worklist theo revision hiện hành, trạng thái và scope; SQL chưa chạy DB thực |
| UC06 | APPROVE/REJECT/NEEDS_INFO đúng step | `workflow/service.py`, `components/RequestDetail.jsx` | Sửa payload quyết định APPROVE có `reason:null`, bổ sung test |
| UC07 | Bổ sung, resubmit revision mới | `service.py`, `RequestEditor.jsx` | Có code; cần chạy E2E cạnh tranh phiên |
| UC08 | Rút/hủy trước duyệt cuối | `cancel_request`, `RequestDetail.jsx` | Có code; kiểm `expected_version`, reason |
| UC09 | OPS reassign chưa quyết định | `workflow/ops_service.py`, `components/Admin.jsx` | Có code, phải test SoD/scope và race |
| UC10 | Claim công việc | `start_execution`, Web/Mobile | Có code; mobile mới là P1 chưa build |
| UC11 | Báo vướng mắc, kết quả và chứng từ | `report_execution_issue`, `submit_execution`, Web | Có code; chưa chạy scan và nộp tệp E2E |
| UC12 | ACCEPT/REWORK | `decide_acceptance`, Web/Mobile | Sửa payload ACCEPT có `reason:null`; test logic, thiếu E2E DB |
| UC13 | Notifications/read | `workflow/views.py`, `Notifications.jsx`, Mobile | Có code; outbox delivery chưa kiểm chứng thật |
| UC14 | SLA/reminder/breach và retry outbox | `api_core/worker.py`, `management/commands/` | Có code; chưa chứng minh ngưỡng thời gian, số lần retry và xử lý DEAD trên môi trường thật |
| UC15 | Audit/report/verify | `api_core/audit.py`, `workflow/reporting.py`, `AuditorWorkspace.jsx` | Có code; chưa chạy verification hash-chain/permission trên DB thật |
| UC17 | User, department, role membership, type | `api_core/administration`, `IdentityAdmin.jsx` | Có code; chỉ OPS có GLOBAL+ALL; kiểm CRUD/đồng thời thực tế chưa chạy |
| UC16 | AI tóm tắt | `ai_service`/AI client | **P1**, không tính là đã đạt acceptance P0 |

**Không được coi toàn bộ UC ở cột "Có code" là "đã hoàn thành/đạt UAT".** Phần lớn đã có backend/UI từ project đầu vào; bản này duy trì và gia cố các đoạn có thể đối chiếu trực tiếp.

## 4. Phân biệt 16 loại trong báo cáo và 18 loại trong plan

Báo cáo Nhóm 07 mô tả **mục tiêu 16 loại** trên 3 template; file plan kèm theo có danh mục **18 mã**, không phải chứng cứ rằng cùng một danh mục đã được phê duyệt. Bản mã hiện có `PLAN_REQUEST_TYPES_18.json` gồm:

- **A / phê duyệt:** `LEAVE_ANNUAL`, `LEAVE_LONG`, `WFH_REQ`.
- **B / phê duyệt rồi thực hiện:** `OVERTIME_REQ`, `ROOM_VEHICLE`, `ADVANCE_SMALL`, `ADVANCE_MEDIUM`, `ADVANCE_LARGE`, `REIMBURSEMENT`, `SOFTWARE_ACCESS`, `OFFICE_SUPPLIES`.
- **C / có nghiệm thu:** `RESIGNATION`, `VENDOR_PAYMENT`, `LAPTOP_PROVISION`, `PROD_DATA_ACCESS`, `SAAS_LICENSE_BUY`, `ASSET_PURCHASE`, `FACILITY_REPAIR`.

Các bản nháp công bố/biểu mẫu động đã có code; **không tự thêm 18 loại, cấp quyền rộng hoặc công bố 18 release** vì mã loại trong Supabase, actor bindings, yêu cầu bắt buộc và chính sách duyệt thực tế chưa được người quản trị xác nhận. `RESIGNATION` theo plan đòi 4 executor song song — engine hiện chỉ hỗ trợ một executor/attempt nên **không đúng quy trình, phải chặn phát hành**. Hai mẫu auto-approval theo plan cũng **không được tự động duyệt bằng AI** khi P0 không cho phép.

## 5. Những chỗ tài liệu bất đồng — chưa được tự ý hợp nhất

| Nghiệp vụ | Báo cáo/plan | SRS/P0 và thiết kế hiện tại | Quyết định kỹ thuật an toàn |
|---|---|---|---|
| R01 nghỉ phép ít ngày, điểm rủi ro thấp | AI có thể duyệt ngay, **0 bước duyệt** | Không auto approve; 1–3 bước duyệt, AI P1 | Giữ chặn tự duyệt; chờ quyết định chính sách và nghiệm thu AI |
| R03–R05 mức chi | Báo cáo: <5 triệu, 5–50 triệu, >50 triệu | SRS EQUIPMENT: <10 triệu, 10–50 triệu, >50 triệu | Không âm thầm thay route/phiên bản đã ghim; admin chốt theo từng loại và phát hành release mới |
| R06 quyền IT admin/root | Phải duyệt 2 cấp IT/CISO | ACCESS baseline có route theo loại quyền | Chốt policy actor bindings đủ hai cấp, kiểm SoD bằng test trên DB |
| R07 trùng requester/approver | Tự động chuyển cấp trên | SRS chặn `SOD_VIOLATION`/`ROUTE_UNRESOLVED`, không tự bỏ bước | Fail closed và báo OPS/Policy Admin xử lý quyền/tuyến hợp lệ |
| SLA | Báo cáo nhắc 80% và escalation 100/150% | SRS nhắc 50%, breach 100%; không tự reassign | Giữ baseline 50/100 trừ khi có change request + migration + test |
| Quyền đọc | Một số bảng tổng quan ghi “tất cả” | Scoped RBAC, owner/participant/auditor; DRAFT chỉ owner | Ưu tiên riêng tư và SRS; không mở toàn bộ đơn cho admin |
| Mobile/AI | Mục tiêu ứng dụng đầy đủ, push/biometrics/OCR | FR20/FR21 P1, P0 không yêu cầu | Bổ sung Flutter nhanh nhưng chưa có platform wrapper/build, FCM, OCR, tạo đơn trên mobile |
| Trạng thái | Báo cáo có tên tóm tắt khác FSM kỹ thuật | `PENDING_APPROVAL`, `WAITING_FOR_ACCEPTANCE`... | API/trạng thái tuân FSM SRS v2 |

## 6. Các thay đổi mã nguồn trong gói này

1. `api_core/authn/login_throttle.py`, `authn/views.py`: chống đoán mật khẩu bằng hai bộ đếm tách biệt theo tài khoản/IP, không dùng `X-Forwarded-For` chưa được xác thực; trả 429 với Retry-After; IP budget không bị reset bằng một lần đăng nhập thành công.
2. `api_core/authn/service.py`, `config/settings.py`, `.env.example`: session idle tối đa 30 phút và absolute 8 giờ; refresh idle không gia hạn absolute; logout/đổi mật khẩu hủy hoặc cập nhật key tương ứng. Khi chạy qua Nginx phải xác minh IP khách được định danh đúng/trusted proxy trước UAT tải.
3. `api_core/workflow/views.py`: phân tab Approval/Execution/Acceptance dựa trên **revision + workflow instance ACTIVE**, state đúng và role membership scope hiệu lực, không hiện tác vụ từ phiên cũ; giữ kiểm tra đọc theo ACL.
4. `web_client/src/actionPayload.js`, `components/RequestDetail.jsx`: sửa hợp đồng nghiêm ngặt của `approval-decisions`/`acceptance-decisions` để luôn gửi `reason:null` khi duyệt/chấp nhận, giữ đúng bộ khóa body mỗi lệnh.
5. `mobile_app/lib/`, `pubspec.yaml`, `README.md`: Flutter P1 quick approval, phiên/cookie + CSRF trong RAM, sửa đăng nhập mật khẩu tạm, danh sách và một số hành động cơ bản. Không chứa credential quản trị; server tiếp tục enforce.
6. Regression tests trong `tests_business`, `connection_tests`, `web_client/e2e` và cập nhật kiểm thử phân loại lỗi DB an toàn, theo file khác module middleware.

## 7. Kết quả kiểm chứng và tiêu chí nghiệm thu chưa đạt

- **Đã chạy thành công:** offline Python unit/static tests, kiểm tra cú pháp Python, frontend Node tests với Node built-in test runner. Chi tiết tại `KIEM_THU_BAN_CAP_NHAT_20261027.md` (ghi số lượng sau khi chạy cuối).
- **Chưa chạy được tại container này:** `manage.py test` với Django thật (chưa tải được dependencies vì không truy cập PyPI), `npm run build` (chưa có `node_modules`/Vite), build Flutter (không có Flutter SDK), kết nối Supabase thật (không dùng credential tải lên để truy cập môi trường người dùng), worker/storage/ClamAV/Redis E2E, TC001–TC100, load/security/backup DR.
- **Yêu cầu khi nghiệm thu P0:** UAT mọi trạng thái A/B/C; 7 role và cặp SoD; 2 người khác scope, file IDOR, race 409/idempotency, replay outbox, audit hash chain, SLA 50/100, scanner CLEAN/INFECTED, chạy toàn bộ TC001–TC100, chốt KD01–KD08 và lưu ảnh/log/bằng chứng.
- **Chưa làm xong so với báo cáo rộng:** 18 luồng mở rộng đầy đủ, 4 executor song song cho RESIGNATION, mobile workflow đầy đủ + FCM/biometric, AI auto-approval + OCR được kiểm chứng, production security/deploy/DR. Không nên gọi gói này là "project đã hoàn thiện 100%".

## 8. Hướng dẫn tiếp tục có kiểm soát

1. Trên Windows ở thư mục project: `py -3.12 -m venv .venv`, `.venv\Scripts\python.exe -m pip install -r api_core/requirements.txt`.
2. Sao chép `.env.database.example` hoặc `.env.example` thành tệp thực tế; dùng tài khoản runtime `eas_api` (không dùng owner `postgres` hay Supabase service-role secret), `DB_SSLMODE=require` và đúng credential Supabase. **Gói này cố ý không chứa file .env thật.**
3. `python connect_database.py` để kiểm tra kết nối, đặt `EAS_ENV=test` và chạy `python manage.py test` trên profile kiểm thử cô lập (không vào DB sản xuất) để chạy Django API tests và `python connect_database.py --runserver` hoặc script trong `START_HERE.md` để chạy local; chạy worker/storage/scanner nếu luồng cần.
4. Terminal frontend: `cd web_client`, `npm ci`, `npm test`, `npm run build`, `npm run dev`.
5. P1 Flutter: `cd mobile_app`, `flutter create --project-name eas_mobile --platforms android,ios .`, `flutter pub get`, `flutter run --dart-define=EAS_API_BASE_URL=http://10.0.2.2:8000` trong emulator debug; production cần HTTPS.
6. POLICY_ADMIN kiểm `GET /api/v1/config-releases/status`, chuẩn bị bindings, validate/publish release sau phê duyệt; OPS GLOBAL+ALL cấp membership đúng scope. **Không chạy `schema.sql`/`seed.sql` vào Supabase đang có dữ liệu.**
