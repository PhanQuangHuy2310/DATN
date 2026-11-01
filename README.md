# Enterprise Approval System (EAS)

Hệ thống phê duyệt yêu cầu nội bộ, gồm **web_client** (nhân viên), **web_admin** (quản trị), **api_core** (Django + Supabase PostgreSQL), **ai_service** (FastAPI AI) và worker. Các API nghiệp vụ, schema dữ liệu và hồ sơ lịch sử hiện có được giữ nguyên. Các cấu hình và thao tác triển khai tập trung trong README này; tài liệu thiết kế nghiệp vụ vẫn thuộc thư mục `docs/`.

## Khởi động trên Windows (không dùng Docker)

Yêu cầu: Python 3.12 cho Django, Python 3.11 cho AI, Node.js 22.12+, PostgreSQL/Supabase đã thiết lập schema và runtime role, Redis nếu muốn kiểm tra sát môi trường production.

1. Tại thư mục gốc DATN: `copy .env.example .env`; chỉnh **một file `.env` duy nhất**. Truy cập trực tiếp Supabase từ `EAS_API_DATABASE_URL`, `EAS_WORKER_DATABASE_URL` (nên là hai PostgreSQL login phân quyền khác nhau), sử dụng pooler endpoint/port của đúng project, `sslmode=require`. Đặt `EAS_DJANGO_SECRET_KEY`, `INTERNAL_API_SECRET` ngẫu nhiên và giống nhau giữa API/AI. Cấu hình `EAS_SUPABASE_URL`, `EAS_SUPABASE_SECRET_KEY` chỉ trên server nếu cần Storage. Không đặt secret trong `VITE_*`.
2. Cài backend: `py -3.12 -m venv .venv`, rồi `.venv\Scripts\python.exe -m pip install -r api_core\requirements.txt`.
3. Cài AI: `py -3.11 -m venv ai_service\.venv-ai`, rồi `ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-local.txt`.
4. Cài frontend: `cd web_client && npm ci`; tiếp đó `cd ..\web_admin && npm ci`.
5. Mở **năm terminal** tại thư mục gốc và chạy: `start_backend_local.cmd`, `start_ai_local.cmd`, `start_worker_local.cmd`, `start_frontend_local.cmd`, `start_admin_local.cmd`. Worker chạy riêng để xử lý outbox/thông báo.
6. Cổng nhân viên: http://127.0.0.1:5173; quản trị riêng: http://127.0.0.1:5174; API: http://127.0.0.1:8000; AI health: http://127.0.0.1:8001/health.

**Lưu ý Windows:** nếu cài AI trên Python 3.11 không thành công vì các thư viện ML/OCR, phải xử lý yêu cầu hệ điều hành, đúng wheel và phiên bản của `requirements-local.txt` trước khi chạy. Không được đánh dấu AI sẵn sàng khi thiếu model. Nếu kết nối Supabase báo `AUTH_FAILED`, kiểm tra lại mật khẩu, user pooler, host/port, reset credential và xác nhận runtime role có quyền; chỉ sửa timeout không thể chữa sai mật khẩu.

## Docker Compose

Cùng một file `.env` gốc: `docker compose --env-file .env up --build`. Web nhân viên tại http://127.0.0.1:8080; quản trị tại http://127.0.0.1:8081. Docker dùng `EAS_API_DATABASE_URL` và `EAS_WORKER_DATABASE_URL` tách quyền truy cập. Django tự chọn URL AI mặc định theo cách chạy: `127.0.0.1:8001` khi chạy local; Docker Compose truyền `http://ai-service:8001` cho API. Không cần thay `.env` khi chuyển giữa hai cách chạy (trừ khi bạn tự định nghĩa `EAS_AI_SERVICE_URL` để override). Cả hai dùng duy nhất `.env` gốc. `REDIS_URL` được Compose cấp trực tiếp cho backend và worker.

## Phản hồi và đồng bộ dữ liệu

- UI có toast cho thao tác thành công/thất bại, animation có hỗ trợ `prefers-reduced-motion`, thanh tải và đồng bộ dữ liệu sau hành động **không cần F5**.
- Các GET được gộp khi trùng nhau, cache tối đa 20 giây để chuyển trang mượt. Mọi lệnh ghi hoàn tất sẽ xóa cache và kích hoạt nạp lại các khối đang hiển thị. Dữ liệu cũ được giữ trên màn hình trong lúc truy vấn. GET có retry giới hạn trên lỗi mạng/503; lệnh ghi **không tự retry** nhằm tránh ghi trùng khi timeout.
- AI hiển thị trạng thái thật theo từng tác vụ: chờ xử lý, phân loại xong, đánh giá rủi ro xong, lỗi hoặc fallback. Chưa có streaming phần trăm từ mô hình; hiển thị các mốc phản hồi thực từ backend thay vì tiến độ giả. AI fallback không được coi là mô hình đã chạy thành công.
- `web_admin` và `web_client` là hai ứng dụng triển khai độc lập, tái sử dụng chung module UI để không sao chép code. Backend chặn lệnh nghiệp vụ dành cho REQUESTER/APPROVER/EXECUTOR/ACCEPTOR nếu phiên đăng nhập đang giữ role quản trị OPS_ADMIN/POLICY_ADMIN/AUDITOR; admin chỉ dùng hệ thống quản lý, kiểm toán và vận hành. Quyền API tiếp tục được kiểm tra tại Django; ẩn menu không thay cho kiểm tra quyền.

## Kiểm tra nhanh và tình trạng nghiệm thu

- `python -m compileall -q api_core ai_service project_env.py manage.py connect_database.py`
- `cd web_client && npm run build && cd ..\web_admin && npm run build`
- `python scripts/validate_env.py --file .env --profile compose`
- `python connect_database.py` kiểm tra Supabase và role; `curl http://127.0.0.1:8000/health/ready` kiểm tra schema, Redis, Storage/scanner theo cấu hình; `curl http://127.0.0.1:8001/health` kiểm tra AI process.
- Bộ regression tests đang nằm trong `api_core/tests`, `tests`, và `connection_tests`; giữ lại vì cần chống lỗi khi triển khai production. Các script test thử nghiệm rời rạc đã được dọn.

**Trạng thái:** đây là bản cập nhật mã nguồn, **chưa được chứng nhận production-ready**. Không có credential Supabase hoặc dịch vụ chạy cùng phiên kiểm tra nên chưa đo p95/p99 query, kiểm tra connection pool, RLS, lỗi auth, worker real-time hay end-to-end qua tất cả vai trò. Trước production cần test UAT, kiểm tra Supabase pooler/SSL/RLS/role, dùng Redis, đảm bảo Storage private + malware scanner, cấu hình HTTPS và secret manager, kiểm tra load test, observability, backup/restore. Không đưa file `.env` có mật khẩu lên Git hoặc trong ZIP.

## Cập nhật lần này

31/10/2026: tách cổng quản trị, thêm toast và cập nhật dữ liệu không reload, hiển thị trạng thái AI có phân biệt fallback, dùng một `.env` gốc cho local/Docker, bổ sung retry GET an toàn và thời gian phản hồi `Server-Timing`, chuẩn hóa script chạy và gộp hướng dẫn trong README. Các tài liệu nghiệp vụ gốc trong `docs` không bị thay thế.

### Tab sơ đồ luồng (cập nhật 31/10/2026)

- Cổng nhân viên và cổng quản trị đều có menu **Sơ đồ luồng** (chỉ đọc); gồm 9 sơ đồ: tạo/gửi, vòng đời A/B/C, bổ sung/gửi lại, hủy/rút, quản trị, AI, đồng bộ UI. Có tìm kiếm, lọc, xem lớn, phóng to/thu nhỏ, tải ảnh WebP; không gọi API hay thao tác thay đổi dữ liệu.
- Trong **chi tiết hồ sơ**, tab **Sơ đồ luồng** nằm cạnh **Tiến trình**, tự chọn vòng đời A/B/C từ `request.workflow.lifecycle` trả về bởi Django. Nếu hồ sơ chưa có workflow, fallback theo đúng 18 mã trong `api_core/catalog/plan_types.json`; không phỏng đoán vòng đời nếu thiếu thông tin. Thư viện chung vẫn hiển thị.
- Tệp ảnh được tối ưu tại `web_client/public/flow-diagrams/`. `web_admin/vite.config.js` dùng `web_client/public` làm nguồn public chung để hai app dùng một bộ ảnh. Mọi sơ đồ chỉ là **hình minh họa tổng quan**, không thay thế chính sách đã công bố hoặc trạng thái xử lý hiện thời từ Supabase.
- Kiểm tra sau khi giải nén: `cd web_client && npm ci && npm run build && npm test`, sau đó `cd ..\web_admin && npm ci && npm run build`; mở một hồ sơ, chuyển sang **Sơ đồ luồng**, thử phóng to và tải ảnh.

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
