# EAS Portal — giao diện theo mẫu Stitch

Bản triển khai ngày 24/10/2026. Giao diện nằm trong `web_client`; các trang quản trị được tích hợp cùng ứng dụng theo role, không cần chạy thêm `web_admin`.

## Chạy cùng backend hiện có

Yêu cầu Node >=22.12 và Django/API/database đã cấu hình theo README gốc.

```bash
cd web_client
npm ci
npm run dev -- --host 127.0.0.1
```

Vite chuyển `/api` đến Django tại `127.0.0.1:8000`. Dùng tài khoản được cấp trong database; không có tài khoản giả hoặc chế độ bỏ qua xác thực. Production dùng gateway cùng origin theo cấu hình gốc. `npm run preview` chỉ phục vụ build tĩnh, không thay thế gateway/API.

## Các chức năng đã nối API

- Đăng nhập, đăng xuất, hồ sơ, đổi mật khẩu.
- Dashboard thống kê kỳ 30 ngày; số liệu theo phạm vi quyền từ API.
- Requester: danh sách, bộ lọc 9 trạng thái, loại, thời gian, phân trang; tạo/sửa/lưu nháp/gửi/gửi lại; upload và kiểm tra trạng thái tệp; hủy có lý do.
- Approver: hàng đợi cá nhân, nội dung, tiến trình, duyệt/từ chối/yêu cầu bổ sung.
- Executor: công việc được giao, nhận việc, nộp kết quả và minh chứng, báo không thể nhận/bị cản trở.
- Acceptor: xem kết quả đang nộp; chấp nhận hoặc yêu cầu làm lại.
- Policy Admin: danh sách, tạo/sao chép, xem/sửa JSON cấu hình nháp, validate và publish. Đây là editor cấu hình kỹ thuật, chưa phải trình dựng biểu mẫu trực quan.
- Ops Admin: metadata yêu cầu, trạng thái/SLA, điều chuyển với ID đối tượng và ID người nhận; replay sự kiện DEAD bằng ID.
- Auditor: tra cứu, xem các phiên bản, nhật ký, kiểm tra tính toàn vẹn, nhật ký quản trị.
- Thông báo: đọc, đánh dấu đã đọc, phân trang; tài liệu lịch sử tải qua endpoint có kiểm tra quyền.

Trạng thái tổng: DRAFT, PENDING_APPROVAL, NEEDS_INFO, READY_FOR_EXECUTION, IN_PROGRESS, WAITING_FOR_ACCEPTANCE, COMPLETED, REJECTED, CANCELLED.

## Phạm vi CRUD và giới hạn

Create/Read/Update yêu cầu dùng API hiện có. Hủy là chuyển trạng thái có lịch sử, không xóa dữ liệu. Không thêm quyền xóa hồ sơ đã gửi, quyết định hoặc audit. Cấu hình đã công bố bất biến.

Đã bổ sung CRUD tài khoản, phòng ban, cấp/sửa/thu hồi phân quyền; xem và bật/tắt ba loại yêu cầu cố định. API quản trị chỉ dành cho OPS_ADMIN toàn hệ thống. Đã bổ sung lịch sử quyết định và từng lần thực hiện/nghiệm thu, bỏ tệp khỏi bản nháp và bắt buộc đổi mật khẩu tạm.

Các trường tham chiếu còn dùng UUID; cấu hình quy trình dùng JSON. Chưa bổ sung lưu nháp kết quả trên server, xuất biên bản ký số, trình thiết kế kéo thả hoặc tích hợp ghi dữ liệu ra hệ thống bên ngoài. Xem `../START_HERE.md` để biết phạm vi và chính sách quyền đầy đủ.

## Kiểm tra

```bash
npm run lint
npm run build
npm test
npx playwright install chromium
npm run test:ui
```

`test:ui` chạy Chromium với API fixtures, không ghi vào database thật. Có thể dùng `EAS_CHROMIUM_PATH` để trỏ đến Chromium cài sẵn. `npm run e2e` là suite gốc dùng môi trường tích hợp thật (cần API/gateway và fixture tài khoản).

Xem `UI_VALIDATION.md` để biết kết quả thực chạy. Không suy ra nghiệm thu E2E thật từ build hoặc kiểm thử mock.
