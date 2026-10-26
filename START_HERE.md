# EAS — bản tích hợp backend, kết nối database và giao diện

Bản cập nhật 24/10/2026, dựa trên DATN(3).zip vừa cung cấp. Giữ các dịch vụ Django, AI, worker, gateway và bộ SQL gốc; thay frontend theo bố cục mẫu Stitch, bổ sung API quản trị và lịch sử.

## Khởi động trên Windows

Cần Python 3.12+, Node >=22.12, database PostgreSQL/Supabase đã có schema EAS. Không cần cài database mới nếu đã có hệ thống.

1. Giải nén, mở terminal tại DATN.
2. Chạy `python -m venv .venv`, rồi `.\.venv\Scripts\python.exe -m pip install -r api_core/requirements.txt`.
3. Chép `.env.database.example` thành `.env.database`; điền host, port, tên database, tài khoản runtime và mật khẩu.
4. Chạy `.\.venv\Scripts\python.exe connect_database.py` để kiểm tra kết nối và 30 bảng.
5. Chạy `.\.venv\Scripts\python.exe connect_database.py --runserver`.
6. Terminal thứ hai: `cd web_client`, `npm ci`, `npm run dev -- --host 127.0.0.1`.
7. Mở địa chỉ Vite in ra. Tài khoản đăng nhập là tài khoản EAS trong eas.app_user, không phải tài khoản PostgreSQL.

Có thể dùng `start_backend.ps1 -Install` và `start_frontend.ps1 -Install`. Script backend tạo mẫu môi trường nếu chưa có, sau đó dừng để bạn điền thông tin. Không có thông tin đăng nhập thật trong gói mã.

Backend dùng cache bộ nhớ khi chạy development không có Redis. Upload cần Supabase Storage và ClamAV đúng cấu hình; worker cần chạy để gửi thông báo/SLA. Xem `.env.example`, `api_core/.env.example`, `docker-compose.yml` và DATABASE_CONNECTION.md. Không bỏ qua antivirus hoặc giả lập upload thành công khi thiếu dịch vụ.

## Database

`dtb.txt` là mô tả schema, không dùng làm migration. Bộ SQL cài mới nằm trong `database/EAS_Supabase_SQL`; chỉ dùng cho database mới theo README của thư mục. Không chạy installer/seed trên database đang sử dụng để thử kết nối.

Tài khoản backend cần quyền runtime `eas_api` theo bộ schema và cấu hình deploy gốc. DSN/API key không được đưa vào web_client. Kết nối tắt prepared statements và server-side cursors để phù hợp endpoint pooler; chọn host/port/username đúng cấu hình dự án.

## Các chức năng tích hợp

- Requester: tạo, xem, sửa bản nháp/bổ sung, lưu, gửi lại, hủy có lý do, tải tệp, bỏ liên kết tệp khỏi bản nháp, xem các phiên bản.
- Approver: duyệt/từ chối/yêu cầu bổ sung đúng người và bước được giao.
- Executor: nhận việc, nộp kết quả và minh chứng, báo vướng mắc, xem các lần thực hiện.
- Acceptor: đối chiếu, chấp nhận/yêu cầu làm lại; xem kết quả và phản hồi từng lần.
- Policy Admin: tạo/sao chép/sửa cấu hình JSON, kiểm tra, công bố; phiên bản đã công bố bất biến.
- Ops Admin: theo dõi metadata/SLA, điều chuyển, replay outbox DEAD; quản lý danh tính theo quyền bên dưới.
- Auditor: tra cứu hồ sơ, quyết định, phiên bản, lần thực hiện/nghiệm thu, nhật ký và xác minh audit.
- Dùng chung: đăng nhập/đăng xuất, đổi mật khẩu, bắt buộc đổi mật khẩu tạm, thông báo, dashboard 30 ngày, 9 trạng thái, phân trang, lỗi và hộp thoại.

## CRUD quản trị và chính sách quyền

Menu Danh tính & phân quyền gọi `/api/v1/admin/{users|departments|memberships|request-types}`.

Chỉ OPS_ADMIN đang hiệu lực với scope_kind=GLOBAL và type_scope=ALL được dùng các API này. Ops Admin theo phòng/loại vẫn dùng chức năng vận hành theo phạm vi cũ. Đây là chính sách quản trị mới được triển khai cho phạm vi đồ án, không phải mặc định cấp mọi Ops Admin quyền toàn hệ thống.

- Users: POST tạo, GET danh sách/chi tiết qua dòng, PATCH sửa/reset mật khẩu tạm, DELETE vô hiệu hóa.
- Departments: tạo/xem/sửa/vô hiệu hóa; chặn vòng lặp và chặn vô hiệu hóa khi còn nhân viên/phòng con hoạt động.
- Memberships: cấp/xem/sửa thời hạn/phạm vi, DELETE thu hồi; không đổi chủ sở hữu, không mở lại quyền đã thu hồi (cấp bản ghi mới).
- Request types: xem, bật/tắt. Ba mã LEAVE/ACCESS/EQUIPMENT cố định theo validator, không tạo tùy ý loại mới chưa có hợp đồng nghiệp vụ.
- Không cho admin tự đổi tài khoản hoặc quyền của mình qua API quản trị này. Thay đổi người dùng/quyền làm phiên cũ hết hiệu lực.
- PATCH/DELETE gửi expected_revision để chống ghi đè; mutation yêu cầu Idempotency-Key và lý do; audit không chứa mật khẩu/hash mật khẩu.
- Xóa nghiệp vụ là vô hiệu hóa/thu hồi/hủy; không xóa vật lý hồ sơ đã gửi hoặc audit. Việc xóa vì retention/privacy tiếp tục qua quy trình riêng của dự án.

## Phần còn ở mức kỹ thuật / giới hạn

Giao diện quản trị cấu hình sử dụng JSON có kiểm tra; một số trường tham chiếu quản trị/điều chuyển dùng UUID. Đây chưa phải trình thiết kế workflow kéo thả hay danh bạ autocomplete hoàn chỉnh. Lưu nháp kết quả thực hiện, xuất biên bản ký số, tích hợp nghiệp vụ bên ngoài ghi dữ liệu, app mobile chưa được bổ sung trong bản này. Không có nút giả cho các phần đó. Tìm mã trên danh sách chỉ lọc trang hiện tại, nhãn đã thể hiện rõ.

Chưa kiểm thử Supabase/storage/Redis/ClamAV thật vì chưa có môi trường và thông tin truy cập. Kết quả unit tests, browser fixtures và SQL WASM không thay thế nghiệm thu E2E. Xem VALIDATION_24_10.md.
