# EAS — Cập nhật sửa truy vấn + giao diện theo Stitch (26/10/2026)

## Nguồn
- Mã nguồn nền: `DATN_EAS_Ban_Sua_Ket_Noi_Local.zip` (được sửa từ `DATN(3).zip`).
- Chuẩn tham chiếu: `stitch_enterprise_approval_system_ui (1).zip`, tập trung dashboard, My Requests, mẫu sidebar, bảng, chức năng Admin.
- **Giữ nguyên** nghiệp vụ phê duyệt, phân quyền, idempotency, audit và schema 30 bảng. Không tự migrate hay can thiệp dữ liệu.

## Những thay đổi thực sự có trong mã
1. **Lỗi 500 nghi do SQL nullable params:** Ép kiểu PostgreSQL tường minh `::text`, `::uuid`, `::timestamptz`, `::boolean` trong danh sách yêu cầu, vận hành, báo cáo, cấu hình và thông báo. Số placeholder đã kiểm tra bằng AST: Requests 26/26, Operations 11/11. Trên Supabase có thể còn lỗi SQL khác; kiểm tra traceback nếu 500 vẫn xảy ra.
2. **Tìm kiếm server-side:** `GET /api/v1/requests?q=...` và `GET /api/v1/ops/requests?q=...` tìm mã hồ sơ (không chỉ trang đầu), debounce 300ms, reset offset khi đổi từ khóa.
3. **Phân trang:** Nút đầu/trước/sau, chỉ số trang, 10/20/50 dòng cho My Requests, Notifications, Identity Admin, Admin Events, và Policy; Operations dùng phân trang chung phía API. Không dựng tổng trang ảo vì API không trả tổng số.
4. **Responsive theo mẫu:** Sidebar phân nhóm theo quyền, card thống kê cho các trạng thái *trên trang hiện tại*, dashboard hồ sơ mới, thao tác nhanh, mobile sidebar overlay, bảng responsive dạng card trên mobile, giữ panel chi tiết nghiệp vụ.
5. **UX chuyển chức năng:** Thay trang, mở hồ sơ mới/chỉnh sửa, chọn phiên bản Policy, bấm tab chi tiết hoặc đổi trang danh sách sẽ tự cuộn đến khu vực cần thao tác. Có tiêu điểm bàn phím, hỗ trợ reduced motion.
6. **Mật khẩu:** Dùng `PasswordField` chung ở Login, Profile, Identity Admin; có nút Hiện/Ẩn, aria-label; đổi mật khẩu kiểm tra độ dài/nhóm ký tự, thông báo chi tiết hơn khi bị 400/401.
7. **Git:** `.gitignore` bổ sung `.venv-ai/` và `logs/` để ngăn commit lại DLL >100MB và thông tin log nhạy cảm. Quy tắc mới **không loại DLL khỏi các commit đã tạo trước đây**.

## Các lệnh Windows (CMD)

Sao lưu thư mục DATN hiện tại (nhất là các chỉnh sửa riêng), rồi dùng bản full mới hoặc chỉ chép các file từ bản patch. **Không sao chép đè** `.env`, `.env.database`, `.env.worker` đang chạy ổn định và không chép `.git` từ ZIP.

Ở `D:\Đồ án\DATN`:

```cmd
.\.venv\Scripts\python.exe -m unittest discover -s connection_tests -p "test_*.py" -v
.\.venv\Scripts\python.exe connect_database.py
start_backend_local.cmd
```

Terminal Frontend riêng:

```cmd
cd /d "D:\Đồ án\DATN\web_client"
npm ci
npm run build
npm run dev -- --host 127.0.0.1
```

AI chạy Terminal thứ ba bằng `start_ai_local.cmd` (sau khi tạo virtualenv Python tương thích). Kiểm thử chung: `check_local.cmd`.

### Kiểm thử bằng trình duyệt
1. Sau đăng nhập hợp lệ, mở các menu Requester, Approver, Executor, Acceptor, Policy và Ops (nếu được cấp vai trò).
2. Trong My Requests, lọc trạng thái, tìm mã REQ (kể cả hồ sơ ở trang xa), đổi số dòng, chuyển trang và kiểm tra tự cuộn đến danh sách.
3. Trong Identity Admin, phân trang 10/20/50, mở modal xem/sửa/vô hiệu hóa; thử hiện/ẩn mật khẩu tạm khi tạo User (chỉ trong môi trường test và có quyền).
4. Login và Profile: nút Hiện/Ẩn đúng, lỗi đổi mật khẩu hiển thị rõ, mật khẩu không bị đưa lên URL.
5. `GET /api/v1/requests?limit=20&offset=0&tab=mine` và `GET /api/v1/notifications?limit=20&offset=0&unread=false` **không còn 500**. Nếu còn 500, gửi traceback đã che secret và mã SQLSTATE.
6. Kiểm tra màn hình hẹp 375px, tablet 768px, desktop 1440px. Bảng danh sách trở thành thẻ trên điện thoại; không mất nút hành động.

## Các mục chưa xác nhận / chưa tự động sửa
- Không thể chạy kết nối DB/Supabase trên máy bạn: SQL nullable-cast là bản vá dựa trên code, **không bảo đảm đã xóa 100% nguyên nhân lỗi 500** nếu thiếu quyền/schema/RLS.
- Worker `ProgrammingError`: xác thực DSN `eas_worker_login`, mật khẩu và role trên máy bạn; không thể tái hiện khi không có credentials. Dùng `check_local.cmd` rồi đọc lỗi gốc.
- Django ↔ AI auth `401`: vẫn cần secret của 2 file trùng nhau **và khởi động lại server**; không nhúng secret vào source.
- Supabase Storage, ClamAV, Redis, OCR/Gemini, workflow gọi AI: chưa thể coi là E2E PASS; `EAS_REQUIRE_STORAGE=false` chỉ bỏ readiness của Storage.
- GitHub GH001 DLL 169MB: `.gitignore` không xóa file khỏi lịch sử commit. Cần làm sạch **commit chưa push** trên nhánh `dangduy` rồi push; không dùng `--force` bừa bãi, không đẩy `.env`.
- Phần frontend chưa có build Vite / Playwright thực nghiệm trong môi trường đóng gói do thiếu gói npm; cần chạy `npm ci && npm run build` trên Windows.

## Ghi chú Git branch `dangduy`

Đứng tại nhánh `dangduy`: `git status`, xem các file mã nguồn patch, `git diff --cached --name-only` trước commit. Nếu ghép code từ ZIP, chỉ add những file code, không add `.env` hay `.venv-ai`. Vì bạn từng commit `xgboost.dll`, hãy làm sạch lịch sử commit *chưa push* trước khi push, không chỉ xóa thư mục rồi tạo commit mới. Sao lưu nhánh trước khi sửa lịch sử.

## Thiết kế
Các màn hình trong bản Stitch có dữ liệu mẫu và nhiều chức năng P1 vượt ngoài API P0; bản này giữ giao diện thực tế/đầy đủ của mã nguồn và nâng bố cục/UX có căn cứ API, thay vì hiển thị số liệu/vai trò giả. Để pixel-perfect toàn bộ màn hình Stitch cần thiết kế lại từng component sau khi xác nhận dữ liệu API tương ứng.
