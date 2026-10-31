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
