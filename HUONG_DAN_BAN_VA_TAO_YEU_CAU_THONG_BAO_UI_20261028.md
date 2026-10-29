# DATN — Bản vá tạo yêu cầu, thông báo hoạt động, UI gọn (28/10/2026)

## A. Lỗi tạo yêu cầu được xác định từ mã nguồn

- API `POST /api/v1/request-drafts` nhận `{ "type_code": "LEAVE" }` (không có `title`).
- `create_draft` trước đây truyền `None` vào `eas.request.draft_payload`, mặc dù DB07 có `draft_payload jsonb NOT NULL DEFAULT '{}'::jsonb`.
- **Lưu ý:** giá trị `DEFAULT` của PostgreSQL *không áp dụng khi INSERT cung cấp NULL tường minh*; việc chèn trước đây gây lỗi `NOT NULL` (thông thường SQLSTATE `23502`).
- Bản vá sử dụng `Jsonb(draft_payload or {})`, giữ nguyên logic phân quyền, release đã công bố và idempotency.
- Mã tương quan `7193aded-19d9-4b0e-8546-3200137e826a` chưa được đối chiếu trực tiếp với log Backend. Nếu vẫn lỗi 500 sau bản vá, lấy log ứng với mã đó, **chỉ chia sẻ loại lỗi và SQLSTATE, không gửi mật khẩu/URL DB**.

## B. Thông báo khi có thay đổi hồ sơ

- Sử dụng bảng `eas.audit_event`, `eas.outbox_event` và `eas.notification` hiện có; **không đổi schema**.
- Một hành động nghiệp vụ tạo bản ghi audit và sự kiện `REQUEST_ACTIVITY` **cùng giao dịch**. Idempotent replay không tạo lại sự kiện.
- Worker đẩy thông báo tới người tạo hồ sơ và các participant còn quyền đọc; chủ hồ sơ xem được hoạt động từ bản nháp. Tải file (read-only) không tạo thông báo ồn ào.
- Ngoài các thông báo hoạt động, các thông báo phân công duyệt/thực hiện hiện có vẫn hoạt động.
- Frontend cập nhật số chưa đọc tối đa mỗi 30 giây khi trang hiển thị. Click một thông báo sẽ cố đánh dấu đã đọc và chuyển sang tab **Tiến trình**, nơi có dòng thời gian audit, lịch sử duyệt và thực hiện mở rộng khi cần.
- **Quan trọng:** phải chạy `start_worker_local.cmd` và cấu hình `.env.worker` hợp lệ. Worker không chạy thì sự kiện nằm trong outbox và thông báo chưa xuất hiện. Những sự kiện cũ chưa được tự động phát lại thành thông báo; bản vá áp dụng cho hoạt động mới.

## C. UI/UX

- Bộ thẻ chức năng vai trò chuyển thành các ô nhỏ trong lưới responsive; phần mô tả rút gọn và có tooltip.
- Thanh chọn nhóm loại yêu cầu vẫn ngang nhưng tự xuống dòng khi không đủ chỗ, tránh cuộn ngang.
- Trung tâm thông báo chuyển thành hàng nhấn được, không còn các thẻ lớn; hiển thị chấm chưa đọc.
- Tiến trình: các hoạt động mới nhất ở đầu, chi tiết nâng cao chỉ tải khi người dùng mở mục mở rộng.

## D. Cập nhật trên máy Windows

1. Sao lưu `D:\Đồ án\DATN` và **giữ lại** `.env.database`, `.env.worker`, `ai_service\.env`.
2. Dừng Backend, Frontend và Worker bằng `Ctrl+C`.
3. Giải nén ZIP bản vá có thư mục gốc `DATN/` vào `D:\Đồ án\`, xác nhận ghi đè mã nguồn tương ứng. Không đè thư mục `.venv`, `node_modules`, dữ liệu hay `.env`.
4. Chạy ba terminal CMD:

   Terminal 1 — `cd /d "D:\Đồ án\DATN" && start_backend_local.cmd`

   Terminal 2 — `cd /d "D:\Đồ án\DATN" && start_frontend_local.cmd`

   Terminal 3 — `cd /d "D:\Đồ án\DATN" && start_worker_local.cmd` (cần tài khoản DB worker hợp lệ)

5. Tại `http://127.0.0.1:5173`, thử **Tạo yêu cầu → Chọn loại đã công bố → Lưu nháp → Gửi phê duyệt**. Mở **Thông báo**, kiểm tra mốc tạo nháp và gửi đơn, click mốc để xem **Tiến trình**. Có thể mất thời gian theo chu kỳ chạy Worker.

Không chạy `python manage.py migrate` vào Supabase dùng chung chỉ để áp dụng bản vá này. Không có migration/schema mới.

## E. Kết quả kiểm tra và giới hạn

- 33/33 kiểm thử logic Node frontend đạt.
- 25/25 kiểm thử Python độc lập đạt (không kết nối DB).
- Kiểm tra cú pháp JSX của 7 component bằng TypeScript transpiler: đạt.
- Kiểm tra biên dịch cú pháp 90 tệp Python: đạt.
- Đã thêm kiểm thử tích hợp mô phỏng `create_draft` và tạo thông báo ở `api_core/tests/test_request_creation_notifications.py`; **chưa chạy được bộ Django test suite** trong môi trường đóng gói do chưa có Django/psycopg cài đặt. Chạy trên máy bạn sau khi đã cài dependencies: `.\.venv\Scripts\python.exe manage.py test api_core.tests.test_request_creation_notifications --keepdb` (nếu môi trường test DB được cấu hình riêng). Không chạy test suite có thay đổi dữ liệu trên Supabase thật nếu chưa xác minh isolation.
- Chưa thử tạo đơn thực tế qua kết nối Supabase của người dùng. Nếu 500 vẫn xuất hiện, cần log SQLSTATE của mã mới để chẩn đoán tiếp, không suy diễn đã giải quyết toàn bộ.
