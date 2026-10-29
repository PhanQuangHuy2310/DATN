# EAS — đối chiếu code với đặc tả v2 (26/10/2026)

**Nguồn ưu tiên:** `01_SRS_v2.docx` → `02_Phan_tich_thiet_ke_v2.docx` → `03_Du_lieu_va_API_v2.docx` → `diagram/02_USE_CASE/01_use_case.md` và `diagram/04_STATE_MACHINE/01_state_machine.md`.

**Phạm vi triển khai:** P0 chỉ có LEAVE (A), ACCESS (B), EQUIPMENT (C). AI tự phê duyệt, OCR/risk tự quyết định, Android và workflow builder tổng quát không được tính là yêu cầu P0 đã hoàn thiện.

## UC ↔ Backend ↔ UI ↔ Role

| UC | Actor/soát quyền | API / triển khai | Giao diện có trong bản này | Xác minh |
|---|---|---|---|---|
| UC01 | Mọi tài khoản được cấp | `authn/views.py`: csrf/login/logout/me/password | Login, Profile, Hiện/Ẩn mật khẩu | API phải kiểm tra bằng cookie/CSRF, không có public signup |
| UC02 | POLICY_ADMIN có scope | `/config-releases` (create/patch/validate/publish) | Policy: bản nháp, validate, công bố | Publish bất biến, lạc version 409 |
| UC03/04 | REQUESTER owner/type/department | `/request-drafts`, `/requests/submit`, `/attachments` | RequestEditor + RequestList | Scan CLEAN, config release, expected_version |
| UC05 | Owner, participant, AUDITOR scoped | `/requests`, detail, revisions, history, download | History, RequestDetail, AuditorWorkspace | DRAFT chỉ owner; auditor không xem ngoài scope |
| UC06 | APPROVER đúng step ACTIVE | `/approval-decisions` | RequestDetail → duyệt/từ chối/bổ sung | Backend enforce role, step, SoD |
| UC07/08 | REQUESTER, đúng trạng thái | `/request-drafts/:id`, `/requests/:id/cancel` | RequestEditor, RequestDetail | Resubmit instance/revision mới; terminal không reopen |
| UC09 | OPS_ADMIN đúng scope | `/ops/requests`, `/requests/:id/reassign` | Operations | Metadata-only, khóa version, actor mới đúng quyền |
| UC10/11 | EXECUTOR đúng attempt | `/execution/start`, `/issues`, `/execution/submit` | RequestDetail execution | READY→RUNNING; B→COMPLETED; C→WAITING_FOR_ACCEPTANCE |
| UC12 | ACCEPTOR đúng lifecycle C/attempt | `/acceptance-decisions` | RequestDetail acceptance | Rework tạo attempt READY mới, không tái mở cũ |
| UC13 | Recipient | `/notifications`, `/:id/read` | Notifications, phân trang | Chỉ thông báo của chính người nhận |
| UC14 | Worker | `run_outbox_worker` và SLA | OPS metadata + Notifications | Cần chạy Worker/Redis/Storage để kiểm thử E2E |
| UC15 | AUDITOR, scope riêng | `/requests/:id/audit`, `audit/verify`, `/admin-events`, `/reports/requests` | AuditorWorkspace, AdminEvents, Dashboard | Verify PASS/FAIL/UNKNOWN thực từ API; không tạo số liệu giả |
| UC17 | Identity operator: OPS GLOBAL+ALL | `/admin/users`, `/departments`, `/memberships`, `/request-types` | IdentityAdmin chỉ hiện khi `/auth/me` trả `capabilities.identity_manage=true` | Backend vẫn chặn ngoài scope và ghi audit |

## Bản vá triển khai này

1. `web_client/src/rolePolicy.js`: menu/module chuẩn bảy role và trường hợp multi-role.
2. `web_client/src/components/RoleTasks.jsx`: bảng tác vụ theo actor có liên kết chức năng và mã UC.
3. `web_client/src/components/AuditorWorkspace.jsx`: tra cứu kiểm toán riêng, phân trang, tìm kiếm trên API, xác minh lịch sử chỉ đọc.
4. `web_client/src/App.jsx`, `RequestDetail.jsx`: điều hướng role, vào tab audit đúng ngữ cảnh.
5. `web_client/src/domain.js`: UI tuân thủ FSM/SoD, không hiện nút trái trạng thái/phân tách nhiệm vụ (nhưng không thay thế guard Backend).
6. `api_core/workflow/ops_service.py`: sửa lỗi đọc metadata OPS khác phòng ban/loại bằng cách lọc role membership scope trong SQL.
7. `api_core/workflow/views.py`: trang chi tiết chỉ tải bước duyệt thuộc revision hiện tại, không trộn các instance superseded.
8. `api_core/authn/views.py`: trả khả năng quản trị danh tính khi OPS_ADMIN đúng GLOBAL+ALL.
9. `api_core/authn/service.py`, `account_reset.py` và UI password: mật khẩu mới 15–128 ký tự, kiểm tra độ mạnh theo SRS; không đổi yêu cầu xác thực của mật khẩu cũ.
10. Giữ UI Stitch của bản nền: responsive, thẻ trạng thái, sidebar, phân trang server cho request/notification/audit, Hiện/Ẩn mật khẩu, tự cuộn khi điều hướng.

## Chưa xác nhận / không nên tuyên bố hoàn thành

- Không có truy cập trực tiếp tới Supabase của người dùng trong môi trường biên dịch: API E2E / RLS / concurrent requests / audit chain chưa được tái xác nhận.
- Các bài test Python Django cần cài `api_core/requirements.txt` và chạy trên môi trường đã có backend. Không được xem kiểm tra cú pháp là kết quả API integration.
- Build Vite chưa chạy được tại môi trường kiểm thử này do thiếu gói npm offline; phải thực hiện `npm ci && npm run build` trên máy local.
- Storage, ClamAV, Worker, OCR, Redis và AI trong workflow chưa được xác nhận vận hành E2E. Không dùng kết quả health để suy ra các nghiệp vụ đã PASS.
- OPS_READ scope và identity GLOBAL/ALL cần thử với ít nhất hai tài khoản OPS khác phạm vi và một tài khoản AUDITOR.
- Các thiết kế Stitch chưa được xác minh pixel-perfect trên mọi kích thước; cần chạy kiểm thử responsive/axe bằng browser thật.
- Theo SRS v2, cần UAT TC001–TC100 và lưu bằng chứng trước khi gọi hệ thống là hoàn thành.

## Phạm vi chi tiết các kiểm tra quyền bổ sung

- `/auth/me` hiện cung cấp một *gợi ý UI* `capabilities.identity_manage`, dựa trên membership GLOBAL+ALL còn hiệu lực. Nó không cấp quyền; mỗi route `/admin/...` phải kiểm tra lại ở Backend.
- `list_ops_metadata` áp dụng đồng thời role, hiệu lực, phòng ban và `type_scope`, thay vì chỉ kiểm tra có role OPS_ADMIN bất kỳ.
- `list_admin_events` lọc sự kiện theo scope membership còn hiệu lực, tránh gửi metadata quản trị toàn công ty cho người kiểm toán có phạm vi hẹp.
- Nút action ở UI còn xét SoD, current attempt state, lifecycle C; DB kiểm tra lần nữa khi submit, với `expected_version` và idempotency.
- `approval_steps` trong request detail chỉ là step của revision hiện tại. Các step vòng cũ phải xem từ lịch sử request.

## Vùng cần kiểm tra thêm trước nghiệm thu

- Truy vấn SQL `/requests`, `/notifications` và `/reports/requests` đã từng trả HTTP 500 trên môi trường local; không thể khẳng định đã hết lỗi nếu không có traceback và chạy kiểm thử thực tế.
- Việc cấp role/scope phải được kiểm chứng với hai users khác scope, nhất là policy release và OPS reassign.
- Không cấp quyền bằng CSS hoặc front-end state; UI hide/show chỉ nhằm UX.
