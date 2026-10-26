# Cách chạy bản EAS P0 theo 7 vai trò

Không chạy Docker trong giai đoạn kiểm tra Local. Sao lưu dự án cũ và **không ghi đè các file `.env*` có secret thật**.

Mở CMD tại `D:\Đồ án\DATN` (thay đường dẫn theo máy):

**Terminal 1 — Backend**
```
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe connect_database.py
start_backend_local.cmd
```

**Terminal 2 — Frontend/Web Admin**
```
cd /d "D:\Đồ án\DATN\web_client"
npm ci
npm test
npm run build
npm run dev -- --host 127.0.0.1
```

**Terminal 3 — AI, tùy chọn P1**
```
cd /d "D:\Đồ án\DATN"
start_ai_local.cmd
```

**Terminal 4 — Kiểm tra không ghi Database**
```
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m compileall -q api_core
check_local.cmd
```

**Không chạy `manage.py test` trên cấu hình trỏ vào Supabase Cloud thực tế.** Django test runner có thể tạo hoặc thay đổi test database; chỉ chạy integration test trong một Postgres dùng riêng cho test (đã cô lập, có quyền hợp lệ). Test UI pure JS có thể chạy bằng `npm test` mà không đụng Database.

Dùng trình duyệt http://127.0.0.1:5173, đăng nhập người dùng thật và test theo vai trò. `/auth/me` trả 401 trước đăng nhập là bình thường. Tài khoản OPS_ADMIN có membership GLOBAL và type_scope ALL mới thấy menu Danh tính. Các role khác vẫn được Backend kiểm tra theo từng request.

**Lưu ý**: `DJANGO_SECRET_KEY`, `EAS_AI_INTERNAL_SECRET`, `INTERNAL_API_SECRET`, Supabase Secret và password Database là các khóa khác nhau; giữ ngoài Git. Nếu đã lộ cần rotate.

**Git**: `.venv/`, `.venv-ai/`, `node_modules/`, `.env`, `logs/` phải bỏ khỏi commit; lịch sử từng commit DLL lớn cần xóa khỏi các commit chưa push trước khi push lại branch `dangduy`.
