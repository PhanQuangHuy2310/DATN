# EAS – Hotfix tải dữ liệu HTTP 500 / INVALID_RESPONSE

## Nguyên nhân đã xác định

Trong `api_core/workflow/views.py`, danh sách Requests có `SELECT DISTINCT r.id::text ... ORDER BY r.id`: PostgreSQL 42P10, do r.id::text khác biểu thức r.id. Bản sửa bỏ DISTINCT; các JOIN tại đây nối theo khóa chính. Đây là nguyên nhân ở API Requests trong bản ZIP làm chuẩn, chưa xác nhận là toàn bộ nguyên nhân trên máy của người dùng.

## Tác dụng của patch

1. Sửa danh sách yêu cầu: loại DISTINCT không cần thiết.
2. Khi PostgreSQL gặp lỗi, Django `/api/v1/` trả JSON có mã `DATABASE_QUERY_FAILED` và `correlation_id` thay vì debug HTML. Ghi lại SQLSTATE và đường dẫn API trong log mà không ghi SQL hoặc mật khẩu.
3. Frontend hiện lỗi HTTP 500 bằng tiếng Việt thay vì `INVALID_RESPONSE`. Có nút "Thử lại" sẵn có.
4. Có script chẩn đoán riêng Requests/Notifications/Reports, chỉ chạy SELECT trong transaction READ ONLY.

## Cập nhật

1. Sao lưu dự án `D:\Đồ án\DATN` và dùng nhánh Git hiện tại. Giải nén **patch** vào `D:\Đồ án\` (có thư mục `DATN` trong ZIP). Không chép file .env từ nguồn không tin cậy.
2. Terminal Backend: `cd /d "D:\Đồ án\DATN"` rồi `start_backend_local.cmd` (dừng tiến trình cũ bằng Ctrl+C trước).
3. Terminal Frontend: `cd /d "D:\Đồ án\DATN\web_client"` rồi `npm run dev -- --host 127.0.0.1` (Vite sẽ tự reload bản frontend mới).
4. Mở lại trang dashboard, requests, notifications. Lưu ý `GET /auth/me` 401 khi chưa đăng nhập là bình thường.
5. Chạy `cd /d "D:\Đồ án\DATN"` rồi `.\.venv\Scripts\python.exe diagnose_eas_lists_readonly.py` trên Terminal khác.
6. Nếu NOTIFICATIONS hoặc REPORTS vẫn FAIL, gửi 3 dòng `[REQUESTS_MINE]`, `[NOTIFICATIONS]`, `[REPORTS_REQUESTS]` và mã SQLSTATE, KHÔNG gửi mật khẩu, .env hoặc cookie.

## Giới hạn

Không có kết nối Database Supabase thật từ phiên đóng gói, nên chưa kiểm chứng ba endpoint 200 trên máy của bạn. Không sửa schema, quyền, RLS hay dữ liệu. Không chạy `migrate` hoặc SQL ALTER chỉ để chữa HTTP 500 chưa rõ nguyên nhân.
