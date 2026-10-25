# Chạy DATN EAS bằng Windows CMD (không dùng Docker)

## Bắt đầu

Mở thư mục DATN bằng VS Code, rồi tạo 3–5 CMD Terminal riêng.
**Không sao chép lại các mật khẩu/secret trong file ZIP cũ**; hãy thay mới những khóa từng bị chia sẻ.

1. **Sao chép cấu hình:** Tại `D:\Đồ án\DATN`, chạy `setup_local.cmd`.
2. **Sửa `DATN/.env.database`**: Sao chép Host, Port, User (role `eas_backend_login.PROJECT_REF`) và mật khẩu mới từ cấu hình Supabase. Giữ `DB_SSLMODE=require`. Đặt `DJANGO_SECRET_KEY` ngẫu nhiên, `EAS_AI_INTERNAL_SECRET` ngẫu nhiên. Tạm giữ `EAS_REQUIRE_STORAGE=false` khi chỉ kiểm tra đăng nhập (chưa chạy upload).
3. **Sửa `DATN/ai_service/.env`**: điền `INTERNAL_API_SECRET` **giống hệt** `EAS_AI_INTERNAL_SECRET`. `GEMINI_API_KEY` chỉ cần khi test LLM. Không cần Supabase key trong AI/Frontend để chạy các model hiện có.
4. **Cài backend** (Terminal CMD tại `DATN`):
   ```cmd
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r api_core\requirements.txt
   start_backend_local.cmd
   ```
5. **Cài và chạy Frontend/Web Admin** (CMD khác tại `DATN`):
   ```cmd
   start_frontend_local.cmd
   ```
   Mở `http://127.0.0.1:5173`. Lần đầu cần `npm ci` (script tự cài).
6. **Cài và chạy AI** (CMD tại `DATN`):
   ```cmd
   cd ai_service
   py -3.11 -m venv .venv-ai
   .\.venv-ai\Scripts\python.exe -m pip install -r requirements-local.txt
   cd ..
   start_ai_local.cmd
   ```
   Truy cập `http://127.0.0.1:8001/health`, `/docs`. `requirements-local.txt` KHÔNG gồm PaddleOCR; OCR thật cần cài riêng theo nền tảng và kiểm tra lại.
7. **Kiểm tra local** (CMD tại `DATN`):
   ```cmd
   check_local.cmd --config-only
   check_local.cmd
   ```
   Script chỉ đọc, không thử mật khẩu đăng nhập, không ghi DB, không upload.
8. **Kiểm tra tài khoản Admin** (nếu login trả 401):
   ```cmd
   .\.venv\Scripts\python.exe verify_admin_password_local.py admin
   ```
   Nhập mật khẩu ở dấu nhắc ẩn. `PASSWORD_MATCH: False` cần quy trình reset có kiểm toán/ủy quyền; không tự chỉnh password_hash bằng SQL.
9. **Worker tùy chọn**: Sửa `DATN/.env.worker` theo role riêng `eas_worker_login.PROJECT_REF`, mật khẩu mã hóa URL. Sau đó `start_worker_local.cmd --once` để thử, `start_worker_local.cmd` để chạy liên tục.

## Kiểm tra endpoint

| Component | URL/cách thử | Điều kiện |
| --- | --- | --- |
| Django | `http://127.0.0.1:8000/health/live` | HTTP 200 |
| Readiness | `http://127.0.0.1:8000/health/ready` | `status=ready` (Storage có thể đang được miễn kiểm tra cho development) |
| CSRF | `http://127.0.0.1:8000/api/v1/auth/csrf` | HTTP 200 |
| React / Admin | `http://127.0.0.1:5173` | Trang đăng nhập |
| AI | `http://127.0.0.1:8001/health` | HTTP 200 |
| AI Auth | Dùng `check_local.cmd` | Secret trùng, probe qua middleware |
| PostgreSQL | `python connect_database.py` (qua `.venv`) | 30 bảng schema eas |

`GET /api/v1/auth/me` trả 401 trước khi đăng nhập là bình thường. `POST /api/v1/auth/login` trả 401 là lỗi xác thực người dùng EAS, **không phải** sai mật khẩu PostgreSQL. Web Admin là phần của `web_client`, không mở Terminal riêng.

## Khi muốn kiểm thử upload thật

1. Tạo Supabase Storage bucket private `eas-private`.
2. Điền `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (key đã đổi mới) trong `.env.database`.
3. Cài ClamAV Windows có `clamd` và database nhận diện mã độc, mở daemon tại `127.0.0.1:3310`, thử phản hồi `PONG`.
4. Đổi `EAS_REQUIRE_STORAGE=true`, khởi động lại Django.
5. Chạy `check_local.cmd`, sau đó thử upload, download, và test mẫu EICAR trong môi trường kiểm thử có kiểm soát. Không gọi readiness 200 là bằng chứng cho upload E2E.

## Chưa được coi là hoàn thành

Các mô hình AI hiện có chưa được nối mặc định vào mọi bước nghiệp vụ Django; cần kiểm tra riêng việc gọi AI trong workflow trước khi sử dụng quyết định AI. Các dịch vụ Cloud, Worker, OCR/Gemini, upload, login thực tế và E2E phải được thử trên máy bạn. **Không chạy `manage.py migrate` lên Supabase chỉ để xóa cảnh báo khi chưa soát kế hoạch migration.**
