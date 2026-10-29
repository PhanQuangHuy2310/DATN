# DATN — Sửa lỗi 503 gián đoạn kết nối Supabase (28/10/2026)

## Kết luận từ log do người dùng gửi

- `start_backend_local.cmd` kết nối PostgreSQL thành công, 30 bảng `eas` được tìm thấy.
- Đăng nhập, lấy danh sách và báo cáo trả HTTP 200 trong một khoảng thời gian.
- Sau đó, `/api/v1/request-types`, `/api/v1/ops/requests`, `/api/v1/admin/users`, `/api/v1/auth/me`, và `/health/ready` đồng loạt trả 503. Backend phân loại `OperationalError`, `SQLSTATE=unknown`, `category=connection`.
- Mã lỗi đối chiếu: `517010d7-8992-47c2-8194-055a8bd0a397` tại `/api/v1/auth/me`.
- **Đây là sự cố kết nối/tài nguyên pooler hoặc hạ tầng mạng, chưa đủ bằng chứng để kết luận một câu SQL cụ thể bị chậm.** Không sửa schema hoặc cấp quyền khi chưa xác định nguyên nhân.

## Các thay đổi trong bản cập nhật

1. Trong môi trường `EAS_ENV=development`, Django mặc định `CONN_MAX_AGE=0` để đóng kết nối sau request, tránh phát sinh nhiều session do `runserver` tạo luồng mới. Production vẫn mặc định 60 giây. Biến `EAS_DB_CONN_MAX_AGE` có thể ghi đè.
2. Bật TCP keepalive ở psycopg; tiếp tục giữ `CONN_HEALTH_CHECKS=True`, `connect_timeout=10`, `prepare_threshold=None` (phù hợp pooler). Không đổi DB host, port, SSL, username, quyền DB.
3. Frontend chỉ tự retry **tối đa 1 lần** với GET/HEAD nếu gặp HTTP 502/503/504, tôn trọng `Retry-After` (tối đa 4 giây); POST/PATCH/DELETE, nhất là tạo/duyệt/hủy yêu cầu, tuyệt đối không retry.
4. Giảm request bị gọi hai lần bởi React StrictMode trong chế độ phát triển. Muốn bật lại để debug component, đặt `VITE_REACT_STRICT_MODE=true` trong môi trường Vite.
5. Thêm `diagnose_db_latency.py` để đo tách biệt thời gian mở một kết nối mới và thời gian `SELECT 1`, chạy chỉ đọc và không in DSN hoặc mật khẩu.
6. `EAS_DB_TRACE_ENABLED=true` là chế độ tùy chọn để log **số lần query, tổng ms, max ms theo endpoint**, không lưu nội dung SQL hoặc tham số. Mặc định `false`.
7. Thêm đề xuất index cho màn hình OPS dưới dạng SQL **chỉ để DBA review**, chưa áp dụng lên Supabase; tránh tạo index thiếu cơ sở.

## Cách áp dụng trên Windows mà không mất .env

1. Sao lưu `D:\Đồ án\DATN` hoặc các file `.env.database`, `.env.worker`, `ai_service\.env`.
2. **Nếu đang dùng bản project đầy đủ:** giải nén `DATN_fix_Supabase_503_full_20261028.zip` ra `D:\Đồ án\`, ghép vào thư mục `D:\Đồ án\DATN`, giữ nguyên `.env` đã có. Hoặc dùng ZIP `DATN_fix_Supabase_503_patch_20261028.zip` để chỉ ghi đè các file mã nguồn đã chỉnh.
3. Mở `.env.database` thêm (hoặc sửa nếu có):

```dotenv
EAS_ENV=development
EAS_DB_CONN_MAX_AGE=0
EAS_DB_TRACE_ENABLED=false
```

4. Đóng terminal backend cũ (`Ctrl+C`) rồi mở CMD:

```cmd
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe connect_database.py
.\.venv\Scripts\python.exe diagnose_db_latency.py --samples 8 --interval 1
start_backend_local.cmd
```

5. Terminal khác chạy Frontend:

```cmd
cd /d "D:\Đồ án\DATN\web_client"
npm test
npm run build
npm run dev
```

6. Mở `http://127.0.0.1:5173`. Xem `/health/live`, `/health/ready`, đăng nhập và chuyển qua vài màn hình. Không tự động chạy `manage.py migrate` trên Supabase chỉ vì Django cảnh báo `contenttypes`/`sessions` khi bắt đầu chạy; cơ sở dữ liệu EAS có schema riêng.

## Khi lỗi 503 vẫn còn

- Chạy `diagnose_db_latency.py` trong lúc lỗi xảy ra. **Kết nối mới FAIL**: kiểm tra Supabase Dashboard (project status, pooler/connections, compute), host/port/SSL và mạng tới pooler; không tối ưu index để chữa lỗi này.
- Nếu kết nối mới **OK và SELECT 1 nhanh** nhưng API cụ thể chậm: tạm bật `EAS_DB_TRACE_ENABLED=true` (sau đó khởi động lại backend), so sánh các path có `DB metrics` lớn. Tắt biến sau khi thu thập.
- Kiểm tra Supabase Dashboard → Connect → **Session pooler** (host chính xác, port `5432`, username role có hậu tố `.[PROJECT_REF]`). **Không tự ý chuyển port sang `6543`**: transaction pooler có hạn chế session state và cần xác nhận app phù hợp.
- Khi tải cao và query thực sự chậm: DBA kiểm tra `pg_stat_statements`, `EXPLAIN (ANALYZE, BUFFERS)` với query + scope thực tế, xem `database/verify/ops_request_index_DBA_REVIEW_ONLY.sql`. Không chạy `CREATE INDEX` mù hoặc dùng quyền admin DB cho ứng dụng.
- Nêu kết quả `diagnose_db_latency.py`, endpoint gặp 503, thời gian xảy ra, và correlation ID. Không gửi mật khẩu, `.env`, connection string, token hoặc raw SQL có dữ liệu cá nhân.

## Kết quả kiểm thử trong môi trường tạo bản vá

- `npm test`: **30/30** logic frontend đạt, gồm retry khi 503, không retry POST/PATCH, không retry 401 và kiểm tra hủy request đang chờ.
- `python -m unittest discover -s tests_report -p 'test_*.py' -q`: **21/21** đạt, gồm 6 ca mới cho cấu hình kết nối và đo thời gian.
- Python source files `py_compile`: đạt.
- **Chưa** xác minh live Supabase, build Vite, Django end-to-end do không có `.env.database` và node_modules/DB credentials trong môi trường kiểm thử. Không khẳng định 503 đã được loại bỏ trong hệ thống thật.

## Tài liệu tham khảo

- Django DB persistent connections: https://docs.djangoproject.com/en/5.2/ref/databases/#persistent-connections
- Supabase connection modes: https://supabase.com/docs/guides/database/connecting-to-postgres
