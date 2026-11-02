# Enterprise Approval System (EAS)

EAS là hệ thống tiếp nhận và phê duyệt yêu cầu nội bộ. Repository gồm hai cổng web, API Django, dịch vụ AI tùy chọn, worker nền và các gói SQL PostgreSQL/Supabase.

## Khởi động local trên Windows

Yêu cầu: Python 3.12 cho API, Python 3.11 cho AI và Node.js 22.12 trở lên. Kiểm tra runtime Python đã cài bằng `py -0p`. Nếu thiếu phiên bản cần thiết, hãy cài Python trước khi tạo virtual environment; `venv` không thể tự cài runtime. AI là tùy chọn nếu chỉ chạy API và hai cổng web.

1. Sao chép `.env.example` thành `.env` tại thư mục gốc và cấu hình các biến phía server. Không đặt database/Supabase secret vào biến frontend.
2. Tạo môi trường và cài API:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r api_core\requirements.txt
   ```

3. Nếu cần chức năng AI, tạo môi trường và cài AI (có thể bỏ qua nếu chỉ chạy API và web):

   ```powershell
   py -3.11 -m venv ai_service\.venv-ai
   .\ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-local.txt
   ```

4. Cài từng ứng dụng web:

   ```powershell
   cd web_client
   npm ci
   cd ..\web_admin
   npm ci
   cd ..
   ```

5. Mở các terminal riêng tại thư mục gốc và chạy `start_backend_local.cmd`, `start_worker_local.cmd`, `start_frontend_local.cmd`, `start_admin_local.cmd`. Chạy thêm `start_ai_local.cmd` nếu đã cài môi trường AI và muốn bật AI.

Cổng nhân viên: `http://127.0.0.1:5173`; cổng quản trị: `http://127.0.0.1:5174`; API: `http://127.0.0.1:8000`; AI health: `http://127.0.0.1:8001/health`. Hai cổng web dùng chung mã giao diện trong `web_client`.

## Docker Compose

Cấu hình `.env` ở thư mục gốc rồi chạy:

```powershell
docker compose --env-file .env up --build
```

Hai cổng web được expose ở port 8080 và 8081. Compose khởi tạo Redis và kết nối API với AI service. API và worker nên dùng database login riêng; không dùng schema owner hoặc Supabase `service_role` làm runtime login.

## Database và khôi phục tài khoản

Installer baseline, kiểm tra chỉ đọc, seed/regression dành riêng cho development và hướng dẫn migration nằm trong [database/README.md](./database/README.md). Thay đổi production phải dùng migration tăng dần đã review; không chạy lại installer baseline trên database có dữ liệu.

Migration đăng nhập email/reset và migration Gmail aliases [đã được áp dụng và xác minh](./database/EAS_Supabase_SQL/README_VI.md) trên Supabase DATN. 42 tài khoản thử nghiệm hiện dùng alias Gmail riêng, tất cả chuyển về cùng inbox; phiên cũ đã bị vô hiệu hóa. API và hai web portal đã được rebuild local bằng Docker Compose; API báo ready. Gmail đã chấp nhận email thử nghiệm SMTP. Hướng dẫn và giới hạn nằm trong [API Core](./api_core/README.md) và [database migrations](./database/README.md).

## Kiểm thử và mức sẵn sàng

- API: từ thư mục gốc chạy `.\.venv\Scripts\python.exe manage.py test`.
- Web nhân viên: trong `web_client`, chạy `npm run lint`, `npm test`, `npm run build`; kiểm thử trình duyệt hai cổng: `npm run test:portal`.
- Web quản trị: trong `web_admin`, chạy `npm run build`.
- Bộ kiểm thử gốc: `.\.venv\Scripts\python.exe tests\run_tests.py`; lint theo CI: `ruff check api_core manage.py test_logger.py scripts tests` và `ruff format --check api_core manage.py test_logger.py scripts`.
- SQL validation: làm theo [hướng dẫn gói EAS Supabase SQL](./database/EAS_Supabase_SQL/README_VI.md).

Test local pass không đồng nghĩa hệ thống đã sẵn sàng production. Migration Supabase, SMTP, E2E staging, load, backup/restore và kiểm tra triển khai cần được xác minh riêng.

## Hướng dẫn theo phân hệ

Giữ hướng dẫn chi tiết cạnh các phân hệ phức tạp:

- [API Core](./api_core/README.md) · [AI service](./ai_service/README.md) · [API Gateway](./api_gateway/README.md)
- [Database](./database/README.md) · [Triển khai](./deploy/README.md) · [Kiểm thử](./tests/README.md)
- [Web](./web_client/README.md) · [Ứng dụng mobile](./mobile_app/README.md)
- [Sơ đồ kỹ thuật](./docs/README.md)

- Cổng nhân viên và cổng quản trị đều có menu **Sơ đồ luồng** (chỉ đọc); gồm 9 sơ đồ: tạo/gửi, vòng đời A/B/C, bổ sung/gửi lại, hủy/rút, quản trị, AI, đồng bộ UI. Có tìm kiếm, lọc, xem lớn, phóng to/thu nhỏ, tải ảnh WebP; không gọi API hay thao tác thay đổi dữ liệu.
- Trong **chi tiết hồ sơ**, tab **Sơ đồ luồng** nằm cạnh **Tiến trình**, tự chọn vòng đời A/B/C từ `request.workflow.lifecycle` trả về bởi Django. Nếu hồ sơ chưa có workflow, fallback theo đúng 18 mã trong `api_core/catalog/plan_types.json`; không phỏng đoán vòng đời nếu thiếu thông tin. Thư viện chung vẫn hiển thị.
- Tệp ảnh được tối ưu tại `web_client/public/flow-diagrams/`. `web_admin/vite.config.js` dùng `web_client/public` làm nguồn public chung để hai app dùng một bộ ảnh. Mọi sơ đồ chỉ là **hình minh họa tổng quan**, không thay thế chính sách đã công bố hoặc trạng thái xử lý hiện thời từ Supabase.
- Kiểm tra sau khi giải nén: `cd web_client && npm ci && npm run build && npm test`, sau đó `cd ..\web_admin && npm ci && npm run build`; mở một hồ sơ, chuyển sang **Sơ đồ luồng**, thử phóng to và tải ảnh.

## 02/11/2026 — Hệ thống thiết kế thống nhất cho hai cổng web

**Hệ thống thiết kế**

- `web_client/src/design-system.css` được nạp **sau cùng** ở cả hai cổng: biến màu (xanh navy chủ đạo; xanh lá/cam/đỏ/xám theo ngữ nghĩa), khoảng cách bội số 8px, bo góc 8–12px, chuyển động 150–250ms, hỗ trợ `prefers-reduced-motion`, viền focus rõ ràng. Các file CSS cũ vẫn giữ để không vỡ trang chưa chuyển hết; quy tắc mới ghi đè có chủ đích.
- Thành phần dùng chung trong `components/design.jsx`: `PageHeader`, `PageTabs`, `StatCard`, `StatusBadge`, `EmptyState`, `Skeleton`, `ConfirmDialog`, `WorkflowTimeline`, `SearchInput`. `ClientPageHeader`/`ClientStatCard` cũ trỏ về cùng thành phần. Trạng thái tải dùng skeleton thay vì vòng xoay.
- Khung ứng dụng: header dính (breadcrumb, tìm kiếm hồ sơ theo **mã hoặc tiêu đề** trong đúng phạm vi quyền, chuông thông báo có số chưa đọc và danh sách 6 thông báo mới — bấm để mở hồ sơ và đánh dấu đã đọc), sidebar theo nhóm có thể thu gọn nhóm và thu gọn cả thanh (ghi nhớ trên trình duyệt), ngăn kéo trên di động có nút đóng và phím Esc. Trang quản trị (người dùng, tổ chức, vận hành…) được tách gói tải riêng, nhân viên không phải tải.

**Điều hướng**

| Cổng nhân viên | Cổng quản trị |
|---|---|
| Không gian cá nhân: Tổng quan, Yêu cầu của tôi | Tổng quan: Tổng quan hệ thống, Theo dõi vận hành |
| Công việc được giao: Chờ phê duyệt, Công việc thực hiện, Chờ nghiệm thu | Người dùng & tổ chức: Quản lý người dùng, Phòng ban, Ma trận phân quyền, Sơ đồ tổ chức |
| Quản lý phòng ban (APPROVER/AUDITOR): Tổng quan phòng ban, Nhân viên phòng ban | Cấu hình nghiệp vụ: Danh mục yêu cầu, Quy chế & quy trình (phiên bản quy chế, 18 mẫu, sơ đồ luồng), SLA & thông báo |
| Tổ chức & công cụ: Sơ đồ tổ chức, Sơ đồ luồng, Quy trình AI | Giám sát & kiểm toán: Quy trình AI, Nhật ký kiểm toán (hồ sơ + quản trị), Báo cáo phòng ban |
| Tài khoản: Tài khoản cá nhân | Hệ thống: Cấu hình hệ thống (bảo trì, API & tích hợp) |

Cổng quản trị không có chức năng tạo yêu cầu. Theo UC05, quản trị vận hành chỉ xem **thông tin điều phối**: tìm kiếm và thông báo dẫn tới bảng vận hành; chỉ kiểm toán viên mở được chi tiết hồ sơ.

**Màn hình**

- **Chi tiết hồ sơ:** khối tình trạng (giai đoạn, người đang xử lý, bước kế tiếp, hạn/quá hạn, lý do quyết định) và các tab Thông tin · Tiến trình xử lý (dòng thời gian) · Người phê duyệt · Tệp đính kèm · Đánh giá AI · Lịch sử hoạt động · Sơ đồ luồng. Nhật ký hoạt động hiển thị bằng tiếng Việt, không còn bảng kỹ thuật (hash, mã định danh).
- **Tạo yêu cầu:** hộp xác nhận trước khi gửi phê duyệt; dữ liệu đã nhập được giữ nguyên nếu hủy hoặc lỗi.
- **Tổng quan hệ thống:** lọc theo thời gian, phòng ban, loại yêu cầu, trạng thái; KPI (tổng, chờ duyệt, đang thực hiện, hoàn thành, từ chối/hủy, quá hạn, người dùng hoạt động); so sánh phòng ban; tình trạng API, cơ sở dữ liệu, bộ nhớ đệm, dịch vụ AI và hàng đợi thông báo.
- **Theo dõi vận hành:** bảng Hồ sơ | Người tạo | Người đang xử lý | Phòng ban | Giai đoạn | Hạn | Quá hạn | Trạng thái | Thao tác; dòng quá hạn được tô viền đỏ. Điều chuyển chọn người nhận từ danh sách tài khoản đang hoạt động có đúng vai trò — không còn ô nhập mã định danh.
- **SLA & thông báo:** số bước đang tính hạn/quá hạn, nhắc hạn 24 giờ, trạng thái hàng đợi; danh sách thông báo gửi lỗi kèm nút gửi lại (bắt buộc lý do).
- Thông báo kết quả (toast) nêu rõ thao tác: điều chuyển, gửi lại, gửi yêu cầu, lưu nháp, bảo trì…

**API bổ sung (chỉ đọc)**

- `GET /api/v1/admin/overview`: thêm bộ lọc `department_id`, `type_code`, `status`; thêm `by_department`, `users` (đang hoạt động/tổng). Một truy vấn nhóm duy nhất.
- `GET /api/v1/admin/diagnostics` (OPS_ADMIN GLOBAL): số sự kiện outbox theo trạng thái, độ trễ hàng đợi, 20 sự kiện gửi lỗi, số bước SLA mở/quá hạn, nhắc hạn 24 giờ, kiểm tra dịch vụ AI (tối đa 3 giây). `worker.backlog_ok` chỉ cho biết **không có tồn đọng quá 5 phút**, không khẳng định worker đang chạy.
- `GET /api/v1/requests` và `GET /api/v1/ops/requests`: `q` tìm cả tiêu đề; danh sách vận hành trả thêm `requester_name`, `department_name`.

**Kiểm tra**

- `npm run lint`, `npm test` (51 bài), `npm run build` ở `web_client`; `npm run build` ở `web_admin`; `manage.py test` (284 bài, 5 bỏ qua); `tests/run_tests.py`; ruff và secret gate đều đạt.
- Kiểm thử trình duyệt mới, API giả lập, chạy cả hai cổng: `cd web_client && npm run test:portal` (đặt `EAS_CHROMIUM_PATH` tới Chrome/Edge nếu chưa cài trình duyệt của Playwright). 15/15 đạt trên Chrome: không tràn ngang và header không che tiêu đề ở 1440/1024/768/375px; điều hướng theo cổng; tìm kiếm; chuông thông báo; đủ 7 tab chi tiết; từ chối bắt buộc lý do; điều chuyển gửi đúng bước và phiên bản; không có lỗi trợ năng mức *critical* (axe). Đặt `EAS_SHOTS=1` để lưu ảnh chụp.
- `npm run test:ui` (`e2e/ui.spec.js`) là bộ kiểm thử cũ viết cho giao diện trước các đợt thiết kế lại (ví dụ chờ tiêu đề "Tổng quan xử lý yêu cầu" không còn tồn tại từ trước phiên này) và đang thất bại 17/18; bộ `test:portal` thay thế cho giao diện hiện tại.
- Chưa kiểm chứng trên dữ liệu thật qua trình duyệt (cần mật khẩu tài khoản thử nghiệm), chưa kiểm thử Safari/Firefox và thiết bị di động thật.

## 02/11/2026 — Rà soát toàn hệ thống: tiến trình hồ sơ, AI lưu vết, báo cáo phòng ban

**Lỗi gốc đã sửa**

- **Cổng nhân viên chạy sai chế độ:** `web_client/src/main.jsx` không truyền `portal`, nên ứng dụng rơi về chế độ "unified" — bảng tổng quan cá nhân, Kanban "Yêu cầu của tôi", tìm nhanh và chặn tài khoản quản trị không hoạt động. Nay cố định `portal="client"`.
- **Tài khoản quản trị chỉ dùng cho hệ thống (theo quyết định nghiệp vụ):** API vẫn từ chối tài khoản OPS_ADMIN/POLICY_ADMIN/AUDITOR ở endpoint nghiệp vụ. Bổ sung phía định tuyến: khi gửi yêu cầu, chuyển bước, nghiệm thu hoặc điều phối lại, hệ thống **không giao việc cho tài khoản quản trị** (trả `ROUTE_ACTOR_INACTIVE` / `ASSIGNEE_INVALID`) thay vì tạo bước mà không ai xử lý được.
- **Mật khẩu mặc định ẩn:** `verify_user_password` từng chấp nhận `Admin@123456` cho tài khoản seed/`!UNUSABLE_DEMO_` khi `EAS_ENV=development`, trái với [README SQL](./database/EAS_Supabase_SQL/README_VI.md) ("không có mật khẩu mặc định"). Đã bỏ; xóa `fix_seed_passwords_local.py` (ghi hash mật khẩu công khai vào mọi tài khoản placeholder). Khôi phục mật khẩu dùng `recover_admin_password_interactive.py` hoặc lệnh `account_reset`. Không script khởi động nào ghi mật khẩu.
- **Kết nối Supabase:** mặc định `EAS_DB_CONN_MAX_AGE` trong code là `0` (mâu thuẫn chú thích "60"), khiến mỗi request mở kết nối TLS mới (~2,3 giây đo từ máy dev). Nay mặc định 60 giây, giữ `CONN_HEALTH_CHECKS`.
- **Dữ liệu giả trên trang quản trị:** bỏ số cứng 42 tài khoản / 8 phòng ban / "ISO 27001" / "2.0 LTS"; dùng `GET /api/v1/admin/overview` thật. Endpoint `/api/v1/meta/org-chart` (trước đây 404) đã có.
- **AI không trung thực khi dự phòng:** bộ phân loại trả độ tin cậy cố định 0,75 khi dùng quy tắc từ khóa; nay trả `method="keyword_heuristic"`, `fallback_used=true`, độ tin cậy 0. Lỗi `SyncAIServiceClient._run` gọi lại coroutine đã dùng cũng được sửa.
- Vite không còn proxy thẳng `/ai` tới dịch vụ AI nội bộ; test cấu hình production không còn phụ thuộc `.env` của máy dev (`EAS_DISABLE_DOTENV=true`).

**API mới (chỉ đọc, trừ đánh giá AI)**

| Endpoint | Mục đích | Phạm vi |
|---|---|---|
| `GET /api/v1/requests/{id}` → `request.progress` | Giai đoạn, người đang xử lý + vai trò, bước kế tiếp, hạn và thời gian còn lại, mọi quyết định kèm lý do | Như chi tiết hồ sơ |
| `GET /api/v1/requests` | Thêm `current_assignee_name`, `due_at`, `overdue`, `requester_name`, lọc `requester_id` | Như danh sách |
| `POST /api/v1/requests/route-preview` | Xem trước người duyệt/thực hiện/nghiệm thu bằng đúng bộ định tuyến khi gửi; không ghi dữ liệu | REQUESTER |
| `GET /api/v1/reports/requests` | Thêm `avg_completion_hours`, `avg_approval_hours` (tính từ lần gửi đầu) | Như cũ |
| `GET /api/v1/reports/team` | Phòng ban → nhân viên: tổng, chờ duyệt, đang làm, quá hạn, hoàn thành, thời gian TB | APPROVER/AUDITOR; chỉ hồ sơ người dùng tham gia hoặc thuộc phạm vi AUDITOR, không gồm hồ sơ của chính họ |
| `GET /api/v1/meta/org-chart` | Phòng ban + quan hệ `manager_id` | Toàn tổ chức cho OPS_ADMIN/AUDITOR GLOBAL; người khác: phòng mình + chuỗi quản lý |
| `GET/POST /api/v1/requests/{id}/ai-assessments` | Chạy và xem lịch sử đánh giá AI theo hồ sơ (kiểm tra dữ liệu thiếu, phân loại, rủi ro, tuyến duyệt, khuyến nghị) | Đọc: người xem được hồ sơ; chạy: vai trò nghiệp vụ |

Đánh giá AI được ghi vào chuỗi `audit_event` (hành động `AI_ASSESSMENT_RECORDED`) — **không cần migration**. Mỗi bước ghi rõ `DONE / FALLBACK / NOT_APPLICABLE`; khuyến nghị duyệt là quy tắc nghiệp vụ (`method="rule_based"`), chỉ mang tính tham khảo, người có thẩm quyền vẫn quyết định. OCR được ghi "chưa chạy" khi có tệp vì luồng này chưa gửi tệp tới OCR. Nếu cả phân loại và rủi ro đều dự phòng, hệ thống không gọi thêm bước khuyến nghị để không vượt timeout 30 giây của gunicorn.

**Giao diện**

- Chi tiết hồ sơ: khối tình trạng (giai đoạn, người đang xử lý, bước kế tiếp, hạn/quá hạn, lý do từ chối/bổ sung) và bảng "Đánh giá AI" có lịch sử.
- Tạo yêu cầu: "Tuyến xử lý dự kiến" trước khi gửi; cảnh báo nếu tuyến có người chưa đủ quyền. Gửi yêu cầu dùng một idempotency key cho mỗi phiên bản nháp; nếu hết thời gian chờ, client đọc lại trạng thái thật trước khi báo lỗi.
- Mới: **Bảng điều khiển phòng ban** (Tổ chức → Phòng ban → Nhân viên → Hồ sơ); **Sơ đồ tổ chức** dạng cây có tìm kiếm, lọc phòng ban, mở/thu gọn. Auditor xem báo cáo phòng ban trong cổng quản trị.
- "Yêu cầu của tôi": thẻ/bảng hiển thị người đang xử lý và hạn; phân trang 5/20/50. Tổng quan cá nhân hiển thị thời gian hoàn thành/phê duyệt trung bình thật.

**Việc cần quản trị/DBA xử lý (không tự sửa dữ liệu)**

1. Slot `DIRECTOR` đang gán cho tài khoản có AUDITOR, và một số người duyệt (ví dụ `tuan.pham`, có OPS_ADMIN) đang giữ bước ACTIVE. Theo quy tắc "quản trị chỉ dùng cho hệ thống", các yêu cầu có bước DIRECTOR sẽ bị từ chối khi gửi cho đến khi cấu hình `actor_bindings` trỏ tới người duyệt không có vai trò quản trị, hoặc tách vai trò quản trị sang tài khoản riêng. Các bước đang treo cần OPS điều phối lại sang người duyệt hợp lệ.
2. Ba hồ sơ `PENDING_APPROVAL` không có bước ACTIVE (REQ-2026-0002, -0009, -0026; dữ liệu seed). Kiểm tra chỉ đọc:
   `SELECT r.code FROM eas.request r WHERE r.status='PENDING_APPROVAL' AND NOT EXISTS (SELECT 1 FROM eas.approval_step s JOIN eas.workflow_instance w ON w.id=s.instance_id WHERE s.request_id=r.id AND s.state='ACTIVE' AND w.revision_id=r.current_revision_id);`

**Kết quả kiểm tra (02/11/2026, máy dev Windows)**

- `manage.py test`: 279 bài đạt (5 bỏ qua); `tests/run_tests.py`: 98 đạt; `web_client` `npm test`: 44 đạt; `npm run lint` sạch; build `web_client`/`web_admin` thành công; ruff, secret gate, env/docs gate đạt.
- Truy vấn mới chạy thử trên Supabase DATN trong phiên `READ ONLY` qua toàn bộ stack Django (không ghi dữ liệu, không đăng nhập bằng mật khẩu). Độ trễ đo từ máy dev (RTT tới pooler ~390 ms/lượt): danh sách p50 0,76 s / p95 1,6 s; chi tiết p50 0,99 s / p95 1,6 s; sơ đồ tổ chức ~0,37 s; báo cáo ~0,45 s. Số liệu bị chi phối bởi khoảng cách mạng; **chưa đo tải trên hạ tầng triển khai cùng vùng**, nên chưa khẳng định đạt mục tiêu p95.
- Chưa chạy: E2E ghi dữ liệu (gửi/duyệt/từ chối/nghiệm thu) trên Supabase, worker trên DB dùng chung, AI service thật, Playwright và kiểm thử tải. `npm audit` còn 7 cảnh báo mức moderate trong công cụ ESLint (dev).

## 01/11/2026 — Bố trí lại không gian làm việc và giám sát vận hành

- **Tổng quan nhân viên:** bộ lọc hôm nay / 7 ngày / 30 ngày / 12 tháng và chọn khoảng ngày; phân bố trạng thái và 10 loại yêu cầu thường xử lý. Thống kê chỉ trên hồ sơ mà người dùng có quyền xem; loại nháp không nằm trong báo cáo nghiệp vụ đã gửi.
- **Tổng quan quản trị:** API đọc `GET /api/v1/admin/overview?created_from=...&created_to=...` tổng hợp theo SQL `GROUP BY`, giới hạn 366 ngày và kiểm tra quyền OPS_ADMIN GLOBAL+ALL; biểu đồ trạng thái, nhóm yêu cầu, số trường hợp quá hạn và tình trạng endpoint `/health/ready`. Không gán nhãn "toàn hệ thống" cho dữ liệu ngoài phạm vi quyền.
- **Sidebar riêng:** nhân viên có công việc cá nhân, hồ sơ, quy trình AI; admin có vận hành, quản lý người dùng, vai trò/phân quyền, danh mục và kiểm toán. Cổng admin không hiện mục hồ sơ cá nhân; luồng buộc đổi mật khẩu vẫn được giữ khi mật khẩu tạm.
- **Người dùng & vai trò:** các API `admin/users`, `admin/memberships` có sẵn được đặt ở khu vực tương ứng, thêm/sửa/vô hiệu hóa user (xóa mềm), cấp/sửa/thu hồi role theo phòng ban và loại yêu cầu. Tại trang phân quyền, chọn dòng vai trò từ ma trận API để lọc và cấp role cho nhân viên. Ma trận mô tả *khả năng* role, không cho sửa hợp đồng API; quyền thực tế do backend kiểm tra.
- **Danh mục yêu cầu:** menu "Quản lý loại yêu cầu" cho phép nhập tên, nhóm, mức rủi ro, cấp phê duyệt và trạng thái với API có sẵn. **Bước triển khai bắt buộc:** chỉ đặt `EAS_ALLOW_REPORT_CATALOG_EXPANSION=true` trong `.env` gốc **sau khi** DBA xác nhận đã áp dụng migration mở rộng danh mục trên Supabase. Loại mới cần quy chế công bố và role phù hợp mới có thể gửi đơn. Không bật cờ này trên schema chưa tương thích.
- **Vận hành:** `GET /api/v1/ops/requests` trả thêm tên người phụ trách bước đang hoạt động, giai đoạn xử lý, loại yêu cầu, hạn và cờ quá hạn; hỗ trợ lọc theo ngày. Worker định tuyến `SLA_REMINDER`/`SLA_BREACH` tới người đang phụ trách phê duyệt/thực hiện/nghiệm thu, đồng thời chống trùng theo stage/kind/outbox. Khởi động `start_worker_local.cmd` để xử lý thông báo, không phụ thuộc trang web có mở hay không.
- **Quy trình AI:** thêm menu tra cứu luồng và giải thích bước xử lý. Khi chạy AI tại hồ sơ, nhãn "đang chạy / hoàn thành / lỗi / dự phòng" dựa trên phản hồi API; trang hướng dẫn không giả lập tiến trình trực tiếp. Người có thẩm quyền vẫn thực hiện approve/reject.
- **Chuẩn UI:** header dính trên màn hình khi cuộn, bảng có tiêu đề cố định trong vùng cuộn, nhãn nghiệp vụ tiếng Việt, hỗ trợ màn hình nhỏ, focus/aria cơ bản và giảm animation theo `prefers-reduced-motion`. Backend không trả dữ liệu ngoài scope chỉ vì frontend hiển thị nút.
- **Tối ưu:** báo cáo user nhóm SQL thay vì lấy tối đa 100.000 hàng rồi đếm bằng Python; cảnh báo SLA loại bỏ những stage đã có alert; GET thử lại an toàn, lệnh ghi không tự gửi lại khi timeout (30 giây chờ). Khi lỗi timeout ghi, cần truy vấn trạng thái theo idempotency trước khi thử lại.

**Kiểm tra bản vá:** `node --test web_client/e2e/*.test.mjs` (31 bài đạt); `python -m compileall -q api_core`; `tsc --allowJs --checkJs false --jsx preserve --noEmit --noResolve --target es2022 --module esnext --skipLibCheck web_client/src/App.jsx web_client/src/components/*.jsx`. Chưa có Supabase thực, Redis và Django dependencies trong môi trường kiểm thử này; **chưa xác nhận UAT hoặc thời gian phản hồi production**. Việc cài `npm ci` và build Vite cần thực hiện trên máy có mạng; chỉ triển khai sau khi cả `web_client` và `web_admin` build thành công, đồng thời chạy test theo 7 role.

## 01/11/2026 — Chuẩn hóa Web Client theo yêu cầu UI/UX

Đã cập nhật trực tiếp giao diện `web_client/`, không thay mẫu biểu hay tác vụ nghiệp vụ đã công bố:

- **Sidebar:** bỏ "Hồ sơ liên quan" và mọi mục quản trị hệ thống khỏi cổng nhân viên; giữ Tổng quan, Yêu cầu của tôi, các hàng đợi theo quyền, Sơ đồ tổ chức theo phòng ban, Sơ đồ luồng, Quy trình AI và tài khoản. Web Admin vẫn tách riêng tại cổng 5174.
- **Header:** thanh tìm nhanh **mã yêu cầu**, chuông hiển thị số thông báo chưa đọc từ API, tên + biểu tượng người dùng, biểu tượng đăng xuất, header cố định khi cuộn. Cỡ màn hình nhỏ tự bố trí lại, mọi thao tác có nhãn accessibility.
- **Tổng quan nhân viên:** báo cáo có lọc thời gian, thẻ KPI, biểu đồ phân bố trạng thái và loại yêu cầu thường gặp, hồ sơ gần đây. `GET /api/v1/reports/requests?scope=mine` mới chỉ tổng hợp hồ sơ *do chính người đăng nhập tạo*, không lẫn hồ sơ họ được mời xem. Thống kê không đếm nháp; tần suất là ước tính theo 30 ngày. Khi chưa có dữ liệu đo thời gian hoàn thành trung bình, hiển thị dấu gạch ngang thay vì số giả.
- **Tổng quan theo vai trò:** tài khoản chỉ có quyền APPROVER/EXECUTOR/ACCEPTOR nhận dashboard công việc được phân công từ API, không tự động được xem các hồ sơ khác trong phòng ban.
- **Yêu cầu của tôi:** sáu tab Yêu cầu của tôi / Phê duyệt / Thực hiện / Nghiệm thu / Hoàn thành / Nháp (chỉ hiện tab thuộc quyền), với Kanban hoặc bảng, giữ nguyên bộ lọc khi đổi kiểu xem; tìm mã, lọc loại/trạng thái/ngày tạo, sắp xếp theo ngày và phân trang từ API. Các trạng thái bị từ chối/đã hủy có nhóm riêng trong Kanban. Kéo thả không sửa trạng thái giả; approve/reject/thực hiện/nghiệm thu vẫn chỉ qua nút xác nhận trên chi tiết hồ sơ.
- **Tạo yêu cầu:** danh mục mẫu từ API được hiển thị dạng thẻ responsive, giữ nguyên tất cả mẫu hiện có, validation, tệp và logic lưu nháp/gửi đơn. Có mục "Tạo yêu cầu khác" **chỉ hoạt động khi quản trị đã công bố mẫu linh hoạt có mã thuộc nhóm được hỗ trợ**; khi chưa có mẫu, hiển thị giải thích và không tạo nút giả. Form tùy ý chưa có API/schema không được ghi vào Supabase.
- **Sơ đồ tổ chức của nhân viên:** lấy danh bạ đồng nghiệp cùng phòng từ `/api/v1/meta/colleagues` (chỉ tài khoản REQUESTER, không hiển thị email/role/quyền hoặc dữ liệu phòng ban khác). Chưa thể hiển thị hệ phân cấp quản lý khi API chưa trả `manager_id` an toàn.
- **Hệ thống giao diện:** bổ sung thành phần dùng chung `ClientPageHeader`, `ClientStatCard`, `ClientFilterSection`, CSS `client-refactor.css` với cùng màu, khoảng cách, form, bảng, thẻ; hỗ trợ desktop/tablet/mobile, focus và giảm chuyển động.
- **Chính xác về phạm vi:** `GET /api/v1/requests` hiện chỉ tìm theo **mã hồ sơ** bằng `q`, không tìm tiêu đề trong payload; cổng client không quảng cáo tìm theo tiêu đề khi backend chưa hỗ trợ. Sắp xếp trên trang đang tải, không giả làm thứ tự trên toàn bộ dữ liệu.

### Cần backend mở rộng nếu muốn nghiệm thu toàn bộ prompt

1. Định nghĩa/được cấp quyền *Trưởng phòng*, *Phó Giám đốc*, *Giám đốc* và endpoint thống kê đọc theo `department_id`/phân cấp được xác minh từ server, kèm danh sách nhân viên, báo cáo riêng, lịch sử xử lý và quyền truy cập chi tiết. **Không dùng API admin/users ở cổng nhân viên**.
2. API báo cáo thời gian hoàn thành trung bình dựa trên mốc bắt đầu/đóng thực, cho từng cấp người dùng; API tra cứu theo tên hồ sơ và lọc ngày xử lý; trả người phụ trách theo từng giai đoạn trong kết quả danh sách.
3. Muốn tạo form tự do ngoài 18 mẫu, cần định nghĩa loại mới, schema/validation phía server, quản lý các trường động, lưu dự thảo, phân tuyến duyệt/permission, migration và chính sách công bố. Nếu không có API này, không cho client tự lưu dữ liệu ngoài quy định.
4. API sơ đồ tổ chức đọc theo role/scope cho phép hiển thị quan hệ cấp trên–cấp dưới mà không lộ thông tin riêng tư.

### Kiểm tra

`cd web_client && npm ci && npm test && npm run build` và `cd ..\web_admin && npm ci && npm run build`; kiểm tra nghiệp vụ tạo nháp/gửi/duyệt/thực hiện/nghiệm thu theo vai trò trên Supabase thật, chức năng điều hướng, bảo mật dữ liệu và responsive. Trong môi trường chỉnh sửa hiện tại **36/36 bài kiểm thử Node đạt**, các file JSX đã được kiểm tra parser TypeScript, Python report biên dịch cú pháp thành công, CSS parse thành công. **Chưa thể xác nhận build Vite**, do `npm ci` không tải đủ dependencies (`ENOTCACHED` và lỗi npm). Chưa có kiểm thử tích hợp với Supabase/AI thật; không coi đây là nghiệm thu production.


## 2026-11-01 — Web Client: bố cục, quy trình AI, sơ đồ phòng ban

- Thanh lọc thời gian trên trang Tổng quan được căn theo cùng chiều cao (44px), các khoảng chọn nhanh xuống hàng hợp lý trên màn hình hẹp.
- Trang **Quy trình AI** không còn hiển thị ảnh tĩnh: dùng dữ liệu từ `/api/v1/requests?tab=mine|approval` và `/api/v1/requests/{id}` để phản ánh trạng thái thật của yêu cầu, người duyệt hiện tại và mức độ hoàn thành. Chọn **Chạy đánh giá AI cho hồ sơ** để gọi `/api/v1/ai/classify`, `/api/v1/ai/risk-score` theo yêu cầu (chỉ phân tích, tuyệt đối không tự phê duyệt); kết quả thuộc phiên hiện tại, không giả lập lịch sử AI. Người duyệt tiếp tục dùng giao diện chi tiết hồ sơ để approve/reject.
- **Sơ đồ phòng ban** hiển thị quan hệ `manager_id` và thành viên từ API `/api/v1/meta/colleagues`. API giữ nguyên `items` theo hợp đồng cũ (chỉ đồng nghiệp và `{id, display_name}` dùng cho form), bổ sung `organization` với các quan hệ trưởng nhóm/nhân viên **chỉ trong phòng ban hiện tại**. Dữ liệu không cấu hình trưởng phòng sẽ hiển thị rõ là chưa gán. Sơ đồ chỉ xem, không tạo thêm quyền phê duyệt.
- Không thay đổi logic gửi/phê duyệt, không sửa schema Supabase. Với dữ liệu tổ chức, Backend cần chạy phiên bản mới để frontend nhận thêm `organization`.
- Kiểm tra bằng `cd web_client && npm test && npm run build`, sau đó thử giao diện thực tế với tài khoản REQUESTER/APPROVER và Supabase của dự án. Việc build cần cài dependencies (`npm ci`).
