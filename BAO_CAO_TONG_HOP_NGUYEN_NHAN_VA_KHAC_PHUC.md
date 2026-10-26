# BÁO CÁO TỔNG HỢP NGUYÊN NHÂN GỐC RỄ & CÁC LỖI ĐÃ KHẮC PHỤC
## Hệ thống Phê duyệt Doanh nghiệp (Enterprise Approval System - EAS)

---

## 1. Bảng Tổng Hợp Nguyên Nhân Gốc Rễ và Giải Pháp Đã Khắc Phục

| STT | Nhóm lỗi | Nguyên nhân gốc rễ trong mã nguồn cũ | Giải pháp đã áp dụng |
|:---:|---|---|---|
| **1** | **Hai lỗi 401 (Unauthorized) tại `:5173/api/v1/auth/me` khi mở trang hoặc sau đăng nhập** | 1. Khi mở `:5173` lúc chưa đăng nhập, `App.jsx` gọi `GET /api/v1/auth/me` trong `useEffect`. Do `<StrictMode>` trong `main.jsx` mount component 2 lần ở chế độ development, trình duyệt bắn 2 request liên tiếp nhận 2 lỗi 401 đỏ trên Console.<br>2. Khi chạy local không có Redis (`LocMemCache`), mỗi lần Django runserver tự reload sẽ xóa bộ nhớ RAM chứa key `eas:session:<id>`, làm `load_actor_from_session` từ chối cookie hợp lệ và trả 401.<br>3. `api.js` dùng `credentials: "same-origin"` và `CSRF_TRUSTED_ORIGINS` thiếu một số cổng local (`localhost` vs `127.0.0.1`). | - Gộp (deduplicate) lời gọi khởi tạo phiên trong `web_client/src/App.jsx` và gửi kèm header `X-Auth-Optional: 1` để `api_core/authn/service.py` trả về `200 {"user": null, "authenticated": false}` thay vì báo lỗi 401 khi chưa đăng nhập.<br>- Cho phép `load_actor_from_session` tự khôi phục phiên từ PostgreSQL (`eas.app_user.auth_version`) khi chạy `LocMemCache` ở môi trường development, đồng thời đánh dấu `eas:session:revoked:<id>` khi đăng xuất.<br>- Đổi sang `credentials: "include"` trong `web_client/src/api.js` và bổ sung đầy đủ các cổng local vào `CSRF_TRUSTED_ORIGINS` trong `api_core/config/settings.py`. |
| **2** | **Lỗi 404 (Not Found) khi tải trang / gọi API** | 1. `web_client/index.html` chưa khai báo icon và thư mục `web_client/public/` không có `favicon.ico` / `favicon.svg`.<br>2. `api_core/config/urls.py` chưa có route gốc `/` và `/favicon.ico`.<br>3. `web_client/vite.config.js` chỉ proxy `/api` và `/health`, thiếu `/ai`. | - Tạo mới `web_client/public/favicon.svg` và `web_client/public/favicon.ico`, đồng thời gắn thẻ `<link rel="icon">` vào `web_client/index.html`.<br>- Bổ sung route `/` (trỏ về `health_views.live`) và `/favicon.ico` (204 No Content) vào `api_core/config/urls.py`.<br>- Bổ sung proxy `/ai` sang `http://127.0.0.1:8001` trong `web_client/vite.config.js`. |
| **3** | **Lỗi không đăng nhập được 42 tài khoản mẫu (401 INVALID_CREDENTIALS) & lỗi đổi mật khẩu (400)** | `database/seed.sql` và `database/schema.sql` lưu chuỗi giả lập `'pbkdf2_sha256$600000$seed$TempHashForDevOnly00000000000000000000000000000='` thay vì mã băm PBKDF2-SHA256 thật của mật khẩu `Admin@123456`, khiến `check_password()` luôn trả về `False`. | - Thay thế toàn bộ chuỗi hash giả lập trong `database/seed.sql`, `database/schema.sql` và `database/migrations/init.sql` bằng mã băm PBKDF2-SHA256 thật của `Admin@123456`.<br>- Bổ sung cơ chế xác thực mật khẩu trong môi trường development (tự động nhận diện hash mẫu hoặc kiểm tra linh hoạt giúp đăng nhập và đổi mật khẩu ngay cả khi chưa chạy lại seed), kèm script kiểm tra `verify_admin_password_local.py`. |
| **4** | **Lỗi SQL 500 DATABASE_QUERY_FAILED do lệch cột Schema (SQLSTATE 42703)** | - `api_core/workflow/config_service.py` cập nhật cột `updated_at` trên bảng `eas.config_release` và `eas.request_type` (2 bảng này không có cột `updated_at`).<br>- `api_core/workflow/reporting.py` lọc `WHERE scope_key = 'ADMIN'` trên `eas.admin_event` (bảng này không có cột `scope_key`).<br>- `api_core/management/commands/privacy_case.py` truy vấn và cập nhật cột `email` trên `eas.app_user` (bảng không có cột `email`). | - Xóa `updated_at = statement_timestamp()` khỏi các câu UPDATE `eas.config_release` và UPDATE `eas.request_type` trong `config_service.py`, đồng thời chuẩn hóa cấu trúc mặc định của `actor_bindings`, `route_rules` và `sla_profile` cho cả 3 lifecycle A, B, C.<br>- Bỏ điều kiện `WHERE scope_key = 'ADMIN'` trong `reporting.py` và bỏ cột `email` trong `privacy_case.py`.<br>- Bổ sung đầy đủ các hàm PL/pgSQL (`eas.lock_security`, `eas.lock_audit_head`, `eas.next_request_code`, `eas.initialize_request_head`, `eas.advance_audit_head`) vào `database/schema.sql`. |
| **5** | **Lỗi SQL 500 do tham số NULL không định kiểu (42P18) và bộ lọc rỗng (22P02 / 22007)** | - `api_core/workflow/service.py` (`report_execution_issue`) và `api_core/worker.py` (`acknowledge_outbox`) dùng `%s IS NULL` với cột UUID mà không ép kiểu `%s::uuid`.<br>- `api_core/workflow/views.py` (`request_list`) truyền chuỗi rỗng `""` hoặc UUID/ngày không hợp lệ thẳng vào PostgreSQL; nhánh `dangduy` dùng `DISTINCT` gây xung đột biểu thức với `ORDER BY` (42P10). | - Ép kiểu tường minh `%s::uuid IS NULL`, `%s::text`, `%s::timestamptz` và `%s::boolean` trong `views.py`, `reporting.py`, `ops_service.py`, `service.py` và `worker.py`.<br>- Chuẩn hóa các tham số lọc rỗng `""` về `None`, loại bỏ `DISTINCT` không cần thiết, kiểm tra hợp lệ `department_id` (UUID), `created_from / created_to` (ISO datetime) để trả về mã lỗi 400 rõ ràng thay vì 500. |
| **6** | **Lỗi xác thực nội bộ Django ↔ AI Service (401) & lỗi tóm tắt AI (503) khi thiếu GEMINI_API_KEY** | - `.env.database.example` và `ai_service/.env.example` đặt 2 chuỗi mẫu khác nhau cho `EAS_AI_INTERNAL_SECRET` và `INTERNAL_API_SECRET`.<br>- `ai_service/routers/summarize.py` trả lỗi 503 khi chưa điền `GEMINI_API_KEY`. | - Đồng bộ secret nội bộ giữa `.env.database`, `ai_service/.env`, `ai_service/config.py` và `api_core/ai_client.py` (tự động đọc chéo từ `.env.database` với `utf-8-sig`).<br>- Bổ sung bộ tóm tắt trích xuất tiếng Việt nội bộ (`_local_extractive_summarize`) trong `ai_service/routers/summarize.py` hoạt động độc lập khi chưa cấu hình `GEMINI_API_KEY`. |
| **7** | **Lỗi kết nối Worker ProgrammingError (EAS-004)** | `.env.worker` chứa chuỗi mẫu `YOUR_PROJECT_REF` / `YOUR_POOLER_HOST` hoặc mật khẩu chứa ký tự đặc biệt chưa được URL-encode. | - Cập nhật `run_worker_local.py` và `check_eas_connections_local.py` để tự nhận diện giá trị mẫu, tự động URL-encode mật khẩu có ký tự đặc biệt, và hỗ trợ khai báo `WORKER_DB_USER` + `WORKER_DB_PASSWORD`. |

---

## 2. Hướng Dẫn Chạy Lại Dự Án Sau Khi Giải Nén / Cập Nhật

### Bước 1: Chuẩn bị và kiểm tra cấu hình môi trường (.env)
1. Giữ nguyên file `.env.database` ở thư mục gốc chứa kết nối Supabase thật của bạn:
   - Các tham số kết nối PostgreSQL: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE=require`.
   - Khóa bí mật nội bộ: `INTERNAL_API_SECRET` và `EAS_AI_INTERNAL_SECRET` phải có cùng giá trị.
   - Địa chỉ AI Service: `EAS_AI_SERVICE_URL=http://127.0.0.1:8001`.
   - Chế độ Storage: `EAS_REQUIRE_STORAGE=false` (cho giai đoạn kiểm thử phát triển chưa bật ClamAV/S3).
2. Kiểm tra file `ai_service/.env`:
   - Đảm bảo `INTERNAL_API_SECRET` trùng khớp với secret bên Django.
   - `GEMINI_API_KEY`: Có thể để trống; hệ thống sẽ tự động dùng bộ tóm tắt trích xuất tiếng Việt offline.

### Bước 2: Kiểm tra kết nối và tài khoản
1. Chạy lệnh kiểm toán kết nối (chế độ chỉ đọc, an toàn 100%):
   ```cmd
   check_local.cmd
   ```
   *Kết quả mong đợi: Đạt `PASS=26` hoặc tương đương, `0 FAIL`.*

2. Kiểm tra mật khẩu tài khoản quản trị:
   ```cmd
   python verify_admin_password_local.py admin
   ```
   - Nhập mật khẩu ẩn ở dấu nhắc. Nếu hiển thị `PASSWORD_MATCH: True`, tài khoản đã sẵn sàng đăng nhập.

### Bước 3: Khởi động 3 dịch vụ nền tảng
Mở 3 cửa sổ terminal riêng biệt (hoặc chạy ngầm):

1. **Khởi động AI Microservice (FastAPI)**:
   ```cmd
   start_ai_local.cmd
   ```
   *Hoặc lệnh trực tiếp:*
   ```cmd
   cd ai_service
   python -m uvicorn main:app --host 127.0.0.1 --port 8001
   ```
   - Kiểm tra: Mở [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health) (HTTP 200) và [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs) (Swagger UI).

2. **Khởi động Backend API (Django 5.2)**:
   ```cmd
   start_backend_local.cmd
   ```
   *Hoặc lệnh trực tiếp:*
   ```cmd
   python connect_database.py --runserver
   ```
   - Kiểm tra: Mở [http://127.0.0.1:8000/health/live](http://127.0.0.1:8000/health/live) và [http://127.0.0.1:8000/health/ready](http://127.0.0.1:8000/health/ready) (Cả hai đều trả HTTP 200).

3. **Khởi động Frontend Web Client (React + Vite)**:
   ```cmd
   start_frontend_local.cmd
   ```
   *Hoặc lệnh trực tiếp:*
   ```cmd
   cd web_client
   npm run dev -- --host 127.0.0.1
   ```
   - Kiểm tra: Mở trình duyệt tại [http://127.0.0.1:5173](http://127.0.0.1:5173).

---

## 3. Danh Sách Tài Khoản Mẫu Để Kiểm Thử Nghiệp Vụ

| Tên đăng nhập | Họ và tên | Chức danh / Vai trò | Mật khẩu mặc định |
|---|---|---|---|
| `admin` | System Administrator | Quản trị viên hệ thống (Admin) | `Admin@123456` |
| `hung.nguyen` | Nguyễn Thế Hùng | Ban Giám Đốc (BOD) / Phê duyệt cấp cao | `Admin@123456` |
| `tuan.pham` | Phạm Minh Tuấn | Trưởng phòng Kỹ thuật (Manager) | `Admin@123456` |
| `huy.do` | Đỗ Quang Huy | Nhân viên Kỹ thuật (Employee / Requester) | `Admin@123456` |
| `ngoc.tran` | Trần Thị Bích Ngọc | Trưởng phòng Tài chính - Kế toán | `Admin@123456` |
| `lan.ngo` | Ngô Thị Mai Lan | Kế toán viên / Chuyên viên thẩm định | `Admin@123456` |
