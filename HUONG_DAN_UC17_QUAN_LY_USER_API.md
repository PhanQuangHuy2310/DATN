# CÁCH CHẠY — EAS USER / ROLE MATRIX / API MANAGER

1. Sao lưu `D:\Đồ án\DATN` và kiểm tra `git switch dangduy`, `git status`.
2. Giải nén ZIP PATCH **vào `D:\Đồ án\`** (ZIP có `DATN/`), tránh ghi đè `.env`, `.git`, DB.
3. Terminal CMD Backend:

   ```cmd
   cd /d "D:\Đồ án\DATN"
   start_backend_local.cmd
   ```

4. Terminal Frontend:

   ```cmd
   cd /d "D:\Đồ án\DATN\web_client"
   npm ci
   npm test
   npm run build
   npm run dev -- --host 127.0.0.1
   ```

5. Xem ở `http://127.0.0.1:5173`. Đăng nhập bằng tài khoản active **OPS_ADMIN có membership GLOBAL + ALL**, không phải chỉ có tên role OPS_ADMIN theo phòng. Sidebar sẽ hiện **Danh tính & phân quyền** và **Quản lý API**.
6. API trực tiếp: `/api/v1/admin/users?limit=20&offset=0`, `/api/v1/admin/access-matrix`, `/api/v1/admin/api-catalog`. Cả ba yêu cầu session hợp lệ và quyền GLOBAL+ALL.
7. Kiểm thử nhanh không cần DB:

   ```cmd
   cd /d "D:\Đồ án\DATN"
   .\.venv\Scripts\python.exe verify_uc17_static.py
   cd web_client
   npm test
   ```

8. Kiểm thử Django cần máy đã cài thư viện:

   ```cmd
   cd /d "D:\Đồ án\DATN"
   .\.venv\Scripts\python.exe -m django test api_core.tests.test_administration --settings=api_core.config.settings
   ```

   Nếu đang dùng câu lệnh `manage.py` trước đây, có thể dùng `python manage.py test api_core.tests.test_administration`. Chỉ chạy trên DB kiểm thử; không áp dụng migration hoặc reset dữ liệu sản xuất.

**Ghi chú:** Quản lý API P0 là danh mục hợp đồng API + role matrix + readiness theo tài liệu. Hệ thống *không* hỗ trợ tạo API key và bật/tắt endpoint từ UI vì đó là quyền cấu hình có rủi ro, chưa được đặc tả và thiết kế audit/migration trong SRS v2.
