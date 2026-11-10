# Enterprise Approval System (EAS)

EAS là hệ thống tiếp nhận và phê duyệt yêu cầu nội bộ doanh nghiệp. Hệ thống gồm:

- cổng web cho nhân viên và cổng web cho quản trị;
- API Django và worker xử lý nền;
- dịch vụ AI (tùy chọn);
- dịch vụ **Mock Systems**, giả lập các hệ thống ngoài: nhân sự, tài sản, toà nhà, IT, tài chính…

Tài liệu này hướng dẫn **chạy hệ thống trên máy Windows**.

## 1. Hệ thống gồm những gì

| Dịch vụ | Địa chỉ sau khi chạy | Bắt buộc |
|---|---|---|
| Mock Systems API | http://127.0.0.1:8100 | Có |
| API (backend) | http://127.0.0.1:8000 | Có |
| Worker nền (thông báo, SLA, tự trả đồ mượn) | — | Có |
| Web nhân viên | http://127.0.0.1:5173 (local dev) / http://127.0.0.1:8080 (Docker Nginx) | Có |
| Web quản trị | http://127.0.0.1:5174 (local dev) / http://127.0.0.1:8081 (Docker Nginx) | Có |
| AI service | http://127.0.0.1:8001 | Không: thiếu AI thì hệ thống dùng quy tắc dự phòng |

Dữ liệu nằm trên **một database Supabase** có sẵn, không cần cài database trên máy.

## 2. Chuẩn bị (một lần)

1. Cài **Python 3.12** (https://www.python.org, chọn "Add python.exe to PATH") và **Node.js 22.12 trở lên** (https://nodejs.org). Muốn dùng AI thì cài thêm **Python 3.11**.
2. Giải nén dự án. Mở **PowerShell** tại thư mục dự án (thư mục chứa file này).
3. Nhận file **`.env`** từ chủ dự án và đặt vào thư mục dự án.

   > **Bảo mật:** `.env` chứa mật khẩu database và các khoá bí mật. Không gửi qua kênh công khai, không đưa lên GitHub, không chia sẻ ảnh chụp nội dung file. Repository đã có sẵn `.gitignore` cho `.env`.

4. Cài thư viện:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r api_core\requirements.txt
   cd web_client; npm ci; cd ..
   cd web_admin;  npm ci; cd ..
   ```

   Nếu dùng AI (và OCR hóa đơn tiếng Việt bằng PaddleOCR):

   ```powershell
   py -3.11 -m venv ai_service\.venv-ai
   .\ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-local.txt
   .\ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-paddle.txt
   ```

5. Kiểm tra kết nối database: `.\check_local.cmd`.

## 3. Chạy hệ thống (mỗi lần dùng)

Mở **mỗi lệnh dưới đây trong một cửa sổ PowerShell riêng**, tại thư mục dự án, theo đúng thứ tự. Mỗi cửa sổ phải giữ mở trong lúc dùng hệ thống.

Trước tiên mở Docker Desktop, rồi bật Redis (bộ nhớ đệm dùng chung cho chống dò mật khẩu, giới hạn truy cập và khoá khi AI học). Chỉ cần chạy một lần; Redis chạy nền cho đến khi tắt Docker:

```powershell
docker compose up -d redis
```

| # | Lệnh | Dịch vụ |
|---|---|---|
| 1 | `.\start_mock_local.cmd` | Mock Systems API |
| 2 | `.\start_backend_local.cmd` | API backend |
| 3 | `.\start_worker_local.cmd` | Worker nền |
| 4 | `.\start_ai_local.cmd` | AI (bỏ qua nếu không dùng) |
| 5 | `.\start_frontend_local.cmd` | Web nhân viên |
| 6 | `.\start_admin_local.cmd` | Web quản trị |

Sau đó mở trình duyệt:

- **Web nhân viên:** http://127.0.0.1:5173
- **Web quản trị:** http://127.0.0.1:5174

Đăng nhập bằng email và mật khẩu do chủ dự án cung cấp. Lần đầu đăng nhập bằng mật khẩu tạm, hệ thống yêu cầu đổi mật khẩu.

Tắt hệ thống: bấm `Ctrl+C` trong từng cửa sổ.

## 4. Kiểm tra hệ thống đã chạy đúng

Mở http://127.0.0.1:8000/health/ready. Kết quả đúng có `"status": "ready"`, trong đó:

- `mock_systems_api_reachable` là `true`;
- `eas_role_has_no_mock_table_access` là `true`;
- `shared_security_cache` là `true` (Redis đang chạy).

## 5. Cách khác: chạy bằng Docker

Cần Docker Desktop. Đặt file `.env` vào thư mục dự án rồi chạy:

```powershell
docker compose --env-file .env up --build
```

Web nhân viên mở ở http://127.0.0.1:8080, web quản trị ở http://127.0.0.1:8081. Tắt bằng `docker compose down`.

## 6. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Báo thiếu `.venv` hoặc `node_modules` | Chưa làm bước 2.4 |
| `Copy .env.example to .env…` hoặc `Missing EAS_MOCK_DATABASE_URL` | Chưa có file `.env` đúng ở thư mục dự án (bước 2.3) |
| Gửi đơn mượn phòng/xe/thiết bị, nghỉ phép, mua sắm, cấp quyền báo `INTEGRATION_UNAVAILABLE` | Cửa sổ `start_mock_local.cmd` chưa chạy hoặc đã tắt |
| Đăng nhập báo "Hệ thống bảo mật tạm thời gián đoạn" (`CACHE_UNAVAILABLE`) | Redis chưa chạy: mở Docker Desktop rồi chạy `docker compose up -d redis` |
| Báo `INTEGRATION_DISABLED` | Quản trị đã tắt kết nối hệ thống đó: vào web quản trị → Cấu hình hệ thống → API & tích hợp |
| Cổng 8000 / 8100 / 5173 / 5174 đã bị dùng | Tắt chương trình đang chiếm cổng, hoặc cửa sổ cũ của chính hệ thống này |
| Quên mật khẩu quản trị | `.\.venv\Scripts\python.exe set_temporary_admin_password.py` để tạo mật khẩu tạm (bắt buộc đổi khi đăng nhập) |
| Thông báo, nhắc hạn, trả đồ mượn không chạy | Cửa sổ `start_worker_local.cmd` chưa chạy |

## 7. Tài liệu thêm

<<<<<<< HEAD
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

- **Sidebar:** bỏ "Hồ sơ liên quan" và mọi mục quản trị hệ thống khỏi cổng nhân viên; giữ Tổng quan, Yêu cầu của tôi, các hàng đợi theo quyền, Sơ đồ tổ chức theo phòng ban, Sơ đồ luồng, Quy trình AI và tài khoản. Web Admin vẫn tách riêng tại cổng 8081 khi chạy local.
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


## 03/11/2026 — An toàn phân tuyến R07, xác thực cổng và giảm polling

- **Đăng nhập theo quyền, không theo email cố định:** Cổng quản trị chấp nhận tài khoản có grant `OPS_ADMIN`, `POLICY_ADMIN` hoặc `AUDITOR` còn hiệu lực (kiểm tra phía Django **sau khi xác nhận mật khẩu**). Tài khoản có bất kỳ vai trò quản trị đang hoạt động không được đăng nhập cổng nhân viên, ngay cả khi vẫn có grant Requester cũ. Portal khai báo ở header và body phải khớp nhau; mọi API nghiệp vụ vẫn kiểm tra quyền và phạm vi độc lập. Không đặt mật khẩu hoặc email quản trị cố định trong code.
- **Tối ưu Supabase khi gửi đơn:** xác thực grant APPROVER/EXECUTOR/ACCEPTOR theo phạm vi dùng một truy vấn gộp (thay vì 1 truy vấn cho mỗi cấp duyệt), sau bước kiểm tra tài khoản còn hoạt động và không phải Admin; có regression test đảm bảo vẫn từ chối thiếu quyền. Đây là tối ưu số round-trip, **chưa đo độ trễ trên Supabase thật**.
- **R07 — chống tự phê duyệt:** Khi quy tắc quy định người tạo đơn là người duyệt, Backend truy ngược chuỗi `manager_id` tới tối đa 20 cấp, chỉ chọn cấp trên có grant `APPROVER` hợp lệ theo phòng ban/loại đơn, còn hoạt động, không có vai trò quản trị và không giữ bước khác trong cùng tuyến hoặc vai trò thực thi. Nếu không có người hợp lệ, trả `ROUTE_SOD_ESCALATION_UNRESOLVED` (409), không lưu đơn sai hoặc tự chọn đại. Cả xem trước tuyến và gửi đơn dùng chung bộ giải quyết này; sự kiện chuyển cấp được ghi vào audit chain với ứng viên bị bỏ qua và lý do.
- **AI human-in-the-loop:** `EAS_AI_AUTO_APPROVE_ENABLED=false` mặc định và cờ phê duyệt độc lập `EAS_AI_AUTO_APPROVAL_POLICY_APPROVED=false` (cả hai phải bật mới cho phép auto-approve). Cấu hình cũ có `EAS_AI_AUTO_APPROVE_ENABLED=true` **không đủ** để AI ký đơn. Hai cờ này chỉ là điều kiện kỹ thuật, không thay thế phiên bản quy chế đã được ban hành và nghiệm thu. Đã bổ sung kiểm thử hành vi chặn AI ký khi thiếu một cờ.
- **Giảm polling:** Giao diện kiểm tra trạng thái bảo trì AI mỗi 15 giây khi hệ thống bình thường, 2 giây khi đang khóa bảo trì, 30 giây khi tab bị ẩn; chỉ giữ một request đang chạy và hủy lịch khi rời trang. Đây là giảm lưu lượng **không phải** chứng nhận Supabase hết timeout.
- **Cổng local hiện tại:** `start_frontend_local.cmd` → `http://127.0.0.1:5173`; `start_admin_local.cmd` → `http://127.0.0.1:8081`; Docker dùng cổng khác theo Compose. `.env.example` được đồng bộ với hai cổng local; không thay đổi `.env` thực.
- **Kiểm tra an toàn:** `python tests/run_tests.py`, `cd web_client && npm test`; bổ sung test cho role/portal và R07. Mã Python đã được biên dịch cú pháp, nhưng không chạy được Django tests hoặc build Vite trên môi trường thiếu dependencies. Không có migration SQL, seed, reset mật khẩu hoặc thao tác ghi Supabase nào được thực hiện.

**Các vấn đề cần tiếp tục xác minh:** ma trận hạn mức A3, nguồn số dư chính thức C2, migration và vận hành SLA/ủy quyền trên staging, xử lý các hồ sơ bị kẹt của live database, bản build Vite và E2E qua Supabase/AI. Các thay đổi quy chế và sửa dữ liệu production phải được phê duyệt riêng.

### Trạng thái CSDL trên dashboard

`GET /health/ready` trả `checks.database=true` khi các truy vấn kiểm tra PostgreSQL/Supabase thực thi thành công, ngay cả khi một điều kiện readiness khác chưa đạt (Redis, quyền runtime, bản quy chế, nguồn mock hoặc Storage). Khi mất kết nối database, endpoint trả HTTP 503 với `checks.database=false`; frontend vẫn đọc phần JSON chẩn đoán và hiển thị đúng lý do thay vì đồng nhất tất cả lỗi 503 với mất Backend.

Kiểm tra bằng trình duyệt hoặc PowerShell: `http://127.0.0.1:8000/health/live` để xác định API sống, và `http://127.0.0.1:8000/health/ready` để xem trường `checks`. Nếu trạng thái tổng thể là `not_ready` nhưng `checks.database=true`, kiểm tra các trường `false` khác, không đổi password Supabase hay tăng timeout tùy tiện. Sau khi cập nhật code hãy khởi động lại Backend và frontend.


## 03/11/2026 — Xử lý nhiều lỗi HTTP 503 trên Web Admin (Docker :8081)

- Admin Docker ở `http://127.0.0.1:8081` dùng Nginx chuyển tiếp `/api/` tới container `api:8000`. Nếu **nhiều API cùng báo 503**, kiểm tra Backend/Supabase trước; đừng nhầm đây là lỗi của từng trang.
- `/health/live`: tiến trình Django còn phục vụ HTTP (không truy vấn DB).
- **Mới:** `/health/db`: một truy vấn `SELECT 1` tới PostgreSQL, chỉ báo kết nối và nhóm lỗi đã loại bỏ thông tin nhạy cảm; không kiểm tra quyền hay migration.
- `/health/ready`: kiểm tra nghiệp vụ/role/catalog/Redis/storage, có thể là 503 **ngay cả khi** `database=true`. Đọc `checks` để biết điều kiện không đạt. Không tắt các kiểm tra này để làm UI chuyển xanh.
- Docker healthcheck dùng `/health/db` với thời gian chờ rộng hơn; không dùng `/health/ready` nhiều truy vấn để đánh giá liệu container có sống hay không.
- Web Client/Admin dùng chung API helper: tối đa 5 GET đồng thời; giảm số request khi kết nối Backend/Supabase thất bại, chỉ áp dụng circuit-backoff đối với lỗi kết nối chung, không ảnh hưởng lỗi quyền hay AI cụ thể. Không tự gửi lại các lệnh POST/PATCH/DELETE.
- Polling `ai-status` giảm tần suất, tăng khoảng cách gọi lại theo số lần lỗi, tạm dừng hợp lý khi ẩn tab và hủy request khi unmount. Đây không phải tính năng chạy AI tự động.

**Kiểm tra trên Windows / PowerShell (không chia sẻ file `.env` hoặc mật khẩu):**

```powershell
# Từ thư mục gốc, nếu chạy Docker
 docker compose --env-file .env ps
 docker compose --env-file .env logs --tail 120 api
# Bỏ -i nếu chỉ muốn JSON; mã 503 là trạng thái đúng khi phụ thuộc không đạt
 curl.exe -i http://127.0.0.1:8000/health/live
 curl.exe -i http://127.0.0.1:8000/health/db
 curl.exe -i http://127.0.0.1:8000/health/ready
```

Nếu `/health/live` lỗi: kiểm tra container API và log. Nếu `live=200, db=503`: xác minh `EAS_API_DATABASE_URL`/SSL/mạng Supabase/pooler và xem SQLSTATE trong log đã được che thông tin nhạy cảm. Nếu `db=200, ready=503`: sửa **đúng check false**, không đổi password hoặc database bừa. Nếu cả ba trả 200 nhưng API Admin còn 503: lấy mã lỗi + correlation ID của response và log API để tìm endpoint cụ thể. Thực hiện restart/rebuild container sau khi cập nhật code; frontend cũ vẫn có thể tiếp tục polling cho đến khi thay bản build mới.
=======
- Phân loại yêu cầu (12 nhóm): [docs/PHAN_LOAI_YEU_CAU.md](./docs/PHAN_LOAI_YEU_CAU.md)
- Tích hợp hệ thống ngoài (Mock Systems): [docs/TICH_HOP_HE_THONG_NGOAI.md](./docs/TICH_HOP_HE_THONG_NGOAI.md)
- Thiết kế cơ sở dữ liệu: [docs/THIET_KE_SCHEMA_EAS_V2.md](./docs/THIET_KE_SCHEMA_EAS_V2.md). Dựng database mới: [database/README.md](./database/README.md)
- Theo phân hệ: [API](./api_core/README.md) · [AI](./ai_service/README.md) · [Web](./web_client/README.md) · [Mobile](./mobile_app/README.md) · [Kiểm thử](./tests/README.md) · [Triển khai](./deploy/README.md)
- Lịch sử thay đổi: thư mục [changelogs/](./changelogs/)
>>>>>>> origin/main


## Cập nhật UI/UX và kịch bản duyệt hồ sơ — 08/11/2026

### Phạm vi sửa

- Chỉ thay đổi frontend `web_client` và ghi thông tin vào README gốc; không sửa Django, PostgreSQL, AI Service, Docker hoặc các quy tắc phê duyệt.
- Ở cổng Client, không còn điều hướng chung tới trang quản lý người dùng của Admin. Sơ đồ tổ chức chỉ mở tra cứu nhân viên khi tài khoản có nhân viên **báo cáo trực tiếp** trong cùng phòng ban; không coi mọi APPROVER mặc nhiên là trưởng phòng. Trưởng phòng chỉ mở được danh sách phòng ban của mình, Admin vẫn giữ chức năng hiện tại. Nhân viên thông thường chỉ xem cấu trúc phòng ban.
- Popup **Nộp kết quả thực hiện**: bắt buộc chọn minh chứng PDF/JPG/PNG tối đa 10 MB; chờ API tải lên xác nhận tệp `CLEAN` trước khi submit. Giữ thông tin biểu mẫu và biên nhận tải lên nếu lệnh submit thất bại; không tải lại cùng tệp khi thử lại. Thành công mới đóng popup, cập nhật chi tiết hồ sơ.
- **Giới hạn bảo mật:** Ẩn chức năng bằng frontend không ngăn truy vấn API trực tiếp. Hiện `workspace/org-chart-tree` do backend kiểm soát quyền theo module, chưa cấp quyền đọc theo quan hệ quản lý từng phòng ban. Trước khi triển khai production bắt buộc cập nhật phân quyền và lọc dữ liệu tại API, và kiểm thử không rò rỉ email/nhân viên ngoài phạm vi.
- **Giới hạn gửi minh chứng:** endpoint tải lên minh chứng hiện chưa có cơ chế idempotency thực thi trong backend (header không đủ để chống tạo tệp trùng). UI chỉ tránh gửi lại khi đã nhận biên nhận upload thành công; nếu kết nối đứt trước khi nhận biên nhận, phải kiểm tra lịch sử tệp/attempt trước khi gửi lại để tránh tải trùng.
- **Lỗi minh chứng từ ảnh:** mã nghiệp vụ như `EXECUTION_EVIDENCE_REQUIRED` có nghĩa là backend chưa xác nhận tệp cho lần thực hiện. Nếu đã tải thành công nhưng submit vẫn trả 409, cần đối chiếu `X-Correlation-ID`, bản ghi `eas.execution_attachment` theo execution attempt, kết nối Storage và ClamAV; không bỏ qua kiểm tra minh chứng.

### Kịch bản E2E kiểm thử phê duyệt trên môi trường thử nghiệm

Chuẩn bị: Redis `PONG`, Django `/health/ready` phản hồi đúng, AI/mock/worker nếu loại hồ sơ phụ thuộc tích hợp; tài khoản test REQUESTER, APPROVER khác requester, EXECUTOR, ACCEPTOR, AUDITOR; tài khoản quản lý phòng ban có nhân viên cùng phòng báo cáo trực tiếp. Dùng các hồ sơ **thử nghiệm**, không dùng dữ liệu thực. Trong tab Network bật Preserve log và ghi `X-Correlation-ID` + status của API lỗi.

| Mã | Luồng thao tác | Kết quả cần xác nhận |
| --- | --- | --- |
| E2E-01 | REQUESTER đăng nhập → tạo nháp → nhập dữ liệu → lưu → gửi duyệt | Hiển thị mã hồ sơ, lưu không F5, có tuyến duyệt và lịch sử |
| E2E-02 | APPROVER đăng nhập → mở hàng chờ → phê duyệt từng cấp | Chỉ đúng hồ sơ có lượt duyệt, mỗi cấp chỉ 1 quyết định, trạng thái/notification cập nhật |
| E2E-03 | EXECUTOR nhận việc → nhập kết quả và mã bàn giao → chọn PDF/JPG/PNG → xác nhận | 1 lượt upload minh chứng `CLEAN`, 1 lượt submit, đóng popup chỉ khi thành công; vòng đời B có thể hoàn tất, C chuyển nghiệm thu |
| E2E-04 | ACCEPTOR mở hồ sơ đang chờ → xác nhận nghiệm thu | Chỉ người có quyền thực hiện, trạng thái COMPLETED, timeline và requester cập nhật |
| E2E-05 | APPROVER từ chối kèm lý do ≥10 ký tự | Chuyển trạng thái REJECTED, requester đọc được lý do; không tạo tác vụ thực thi |
| E2E-06 | APPROVER yêu cầu bổ sung → REQUESTER sửa → gửi lại | Mở lại phiên duyệt đúng bản sửa, không tạo hồ sơ trùng |
| E2E-07 | EXECUTOR nộp kết quả thiếu file / file sai loại / quá 10 MB | Validate ngay trong popup, không gọi submit; form giữ nguyên, không đóng giả thành công |
| E2E-08 | EXECUTOR upload file thành công, buộc API submit thất bại có kiểm soát rồi thử lại | Không tải trùng file, popup còn giá trị nhập; nếu server chưa xác nhận được tệp phải hiển thị lỗi; không tạo 2 execution records |
| E2E-09 | ACCEPTOR yêu cầu làm lại → EXECUTOR nộp lại minh chứng | Tạo lượt xử lý đúng theo nghiệp vụ, timeline có lịch sử, nghiệm thu lại đúng |
| E2E-10 | REQUESTER thử tự duyệt và user khác không được phân công thử duyệt | Button không hiển thị/không thực thi; gọi API trực tiếp cũng bị từ chối theo quy tắc SoD |
| E2E-11 | Trưởng phòng mở Sơ đồ tổ chức, tìm nhân viên thuộc phòng mình → thử phòng khác | Cho phép tra cứu trong phòng mình, không mở danh sách phòng khác ở frontend |
| E2E-12 | Nhân viên thường mở Sơ đồ tổ chức → thử tìm tên hoặc mở danh sách nhân viên | Không có ô tìm nhân sự, không mở được danh sách qua nút; **kiểm tra riêng API** có chặn truy vấn trực tiếp hay chưa |
| E2E-13 | Double-click các nút Gửi / Duyệt / Nộp kết quả, làm mới danh sách | Chỉ 1 quyết định nghiệp vụ, không trùng thông báo, không cần F5 |
| E2E-14 | Ngắt Redis hoặc mạng trong môi trường test, thử thao tác rồi khôi phục | Không báo thành công giả, có retry phù hợp, log xác định request/status/correlation |

**Định nghĩa hoàn thành:** Không xem là PASS nếu chỉ có toast. Cần đồng thời: API trả trạng thái hợp lệ, dữ liệu được ghi, UI hiển thị bước tiếp theo, tài khoản vai trò tiếp theo nhìn thấy hồ sơ và không có thao tác trùng.
