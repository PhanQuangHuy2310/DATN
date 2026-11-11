# Sửa kết nối, tải dữ liệu và tự phục hồi API (05/11/2026)

## Phạm vi sửa

- `web_client/src/api.js`: bỏ hành vi từ chối GET hàng loạt chỉ vì một lần mất kết nối. Vẫn giới hạn tối đa 5 yêu cầu dữ liệu đồng thời, giữ cơ chế retry tối đa một lần đối với GET khi bị gián đoạn tạm thời, dùng thời hạn chung cho chuỗi thử lại, thông báo lỗi mạng/timeout rõ ràng, không retry POST/PATCH/DELETE, ưu tiên endpoint phiên đăng nhập và health. API vẫn có thể trả lỗi nếu backend/DB thật sự ngừng hoạt động.
- `web_client/src/components/ui.jsx`: tự tải lại GET bị lỗi tạm thời với giới hạn số lần và backoff, không làm mất dữ liệu trước đó khi màn hình có cache; thử lại khi quay lại tab hoặc mạng khôi phục.
- `web_client/src/App.jsx`: xử lý `/auth/me` HTTP 200 + `user:null` thành phiên đã hết hạn, không để frontend tiếp tục gọi các endpoint riêng tư bằng phiên hết hạn; tự thử kết nối lại ở màn khởi tạo khi lỗi thoáng qua, đặt timeout cho poll AI.
- `web_client/src/components/RequestEditor.jsx`: chuyển vòng poll trạng thái API sang chạy tuần tự, có timeout/backoff, không xếp chồng các yêu cầu khi mạng chậm hoặc tab bị ẩn.
- `api_core/config/database.py`, `api_core/config/settings.py`: giữ health-check cho kết nối PostgreSQL tái sử dụng, thêm TCP keepalive cho Supabase pooler, kiểm tra kết nối trong nhánh dùng psycopg pool.
- `web_client/vite.config.js`, `web_admin/vite.config.js`: timeout chuyển tiếp Django được đặt rõ ràng 45 giây cho môi trường phát triển.
- Giải quyết các conflict Git chưa được resolve trong `App.jsx`, `domain.js`, `api_core/domain/routing.py` và `api_core/tests/test_health.py`. Phần routing giữ cả metadata `adjustments` mới và các trường sự kiện SoD cũ để tránh crash khi gọi luồng nghiệp vụ.
- `web_client/e2e/connection-recovery.test.mjs`: test chống GET stampede, GET tự phục hồi, auth ưu tiên, timeout, và POST không bị gửi lại tự động.

## Cách cập nhật trên máy Windows

1. Sao lưu toàn bộ thư mục DATN hiện tại và file `.env` (không đưa mật khẩu vào Git).
2. Giải nén thư mục `DATN-dangduy` trong file mới, sao chép `.env` cũ sang thư mục gốc project. Đừng ghi đè `.env` thật bằng `.env.example`.
3. Mở terminal lần lượt tại thư mục DATN:

```bat
cd /d "D:\Đồ án\DATN"
start_backend_local.cmd
```

   Ở terminal khác:

```bat
cd /d "D:\Đồ án\DATN"
start_frontend_local.cmd
```

   Nếu dùng cổng quản trị, mở terminal thứ ba:

```bat
cd /d "D:\Đồ án\DATN"
start_admin_local.cmd
```

   Nếu dùng chức năng AI, chạy AI service trong terminal riêng:

```bat
cd /d "D:\Đồ án\DATN"
start_ai_local.cmd
```

4. Mở `http://127.0.0.1:5173` (nhân viên) hoặc `http://127.0.0.1:8081` (quản trị). Dùng `Ctrl+Shift+R` sau khi khởi động lại Vite.
5. Trong `.env`, cấu hình URL Supabase đúng role ứng dụng, SSL `require`. `EAS_DB_CONN_MAX_AGE=60` là cấu hình đang hỗ trợ. Không tự ý đưa `EAS_DB_CONN_MAX_AGE=0` khi không cần pool; nếu chọn pool, cần cài `psycopg[pool]` theo requirements.
6. Test cục bộ (không cần DB) trong `web_client`: `node --test e2e/connection-recovery.test.mjs e2e/session-refresh.test.mjs`; thử `npm ci` nếu chưa cài dependencies và `npm run build` sau đó. Kiểm tra Django bằng `\.venv\Scripts\python.exe manage.py check` và `\.venv\Scripts\python.exe check_eas_connections_local.py` khi có môi trường đúng.

## Cách nhận diện lỗi còn lại

- `401 AUTHENTICATION_REQUIRED`: phiên hết hạn hoặc cookie không hợp lệ, đăng nhập lại. Khác lỗi mạng.
- `429 RATE_LIMIT_EXCEEDED`: giới hạn truy cập API; kiểm tra số tab đang mở và các client đang poll, không tăng rate limit để che lỗi.
- `502/503/504`, `REQUEST_TIMED_OUT`, `NETWORK_UNAVAILABLE`: service/DB bị gián đoạn hoặc chậm; các GET có thể tự thử lại. Nếu liên tục thất bại, xem log Django tương ứng và kiểm tra `/health/live`, `/health/db`, `/health/ready` (health/ready còn kiểm tra điều kiện vận hành khác DB).
- `DATABASE_QUERY_FAILED` HTTP 500: vấn đề câu SQL/schema hoặc quyền trong DB; sửa SQL/schema gốc, không thể chỉ xử lý bằng retry frontend.
- `AI_SERVICE_UNAVAILABLE`: kiểm tra service 8001 và cặp khóa `EAS_AI_INTERNAL_SECRET`/`INTERNAL_API_SECRET` tương ứng; lỗi riêng của AI không có nghĩa toàn bộ DB hỏng.

## Kiểm thử trong môi trường xử lý ZIP

- Đã chạy **8/8** test Node `connection-recovery.test.mjs` + `session-refresh.test.mjs` thành công.
- Đã chạy **9/9** test Python `tests/test_connection.py` thành công; compile Python backend thành công.
- `tests/test_sod_r07_contract.py`: **3/4** test đạt; một test cũ yêu cầu từ chối tự duyệt nếu không có người duyệt dự phòng đã xác minh, trong khi logic mới từ nhánh `origin/main` cho phép tự động chuyển tuyến tới quản lý. Đây là bất đồng quy tắc nghiệp vụ từ các nhánh Git, cần thống nhất theo đặc tả trước khi phát hành production; chưa khẳng định bộ test nghiệp vụ đã đạt hết.
- Không thể chạy `npm run build` trong môi trường này vì `npm ci` bị lỗi DNS `EAI_AGAIN` khi tải dependencies từ registry.npmjs.org. Các kiểm tra cú pháp JS thông thường đã hoàn thành, nhưng chưa thể xác minh JSX bằng Vite.
- Không thể kiểm tra giao tiếp live với Supabase hoặc AI server thật vì ZIP không chứa kết nối/khóa vận hành tương ứng. Chưa thể cam kết 100% hết lỗi truy vấn, tải dữ liệu hoặc cấu hình cụ thể của môi trường người dùng.
