# EAS — 18 loại yêu cầu theo `plan.docx` (26/10/2026)

## Đã triển khai trong bản cập nhật

- Trích xuất đúng 18 mã từ **bốn bảng loại đơn** trong tài liệu nguồn; lưu vào `api_core/catalog/plan_types.json` và `docs/PLAN_REQUEST_TYPES_18.json`.
- Mỗi mẫu chứa tên, nhóm, A/B/C, danh sách trường bắt buộc, schema nhập liệu (profile JSON Schema hiện có), SLA, tuyến duyệt được tài liệu mô tả, executor, acceptor, AI hook và các điểm cần rà soát.
- GET `/api/v1/meta/plan-request-types` cho Policy Admin/Ops Admin, phản hồi `deployment_state=BLUEPRINT_ONLY`.
- Giao diện "Danh mục 18 loại đơn": tìm kiếm, lọc nhóm, phân trang 8 mục/trang, xem chi tiết, sao chép JSON Schema, so sánh trạng thái đăng ký trong database. Trên mobile tự chuyển lưới thành 1 cột.
- Giao diện tạo hồ sơ vẫn bắt buộc loại đơn đang active + phiên bản PUBLISHED + scope của Requester. Dropdown bộ lọc danh sách lấy loại đơn từ API; nhãn trường dựa trên dữ liệu nguồn.
- SQL tùy chọn `database/report_migrations/02_plan_18_type_registration_DBA_REVIEW_ONLY.sql` CHỈ **đăng ký 18 loại ở trạng thái INACTIVE**; KHÔNG thay đổi lịch sử hay tự cấp quyền. Cần chạy sau migration 01, tại DB UAT, bởi DBA được ủy quyền.
- Test không cần database `python -m unittest tests_report.test_plan_18_catalog -v`.

## Không được tự ý bật trên Production

Hiện tại máy trạng thái và policy JSON chỉ giới hạn một số actor slots; chưa bao quát đầy đủ các actor HR, CTO, Security, thủ quỹ, bốn bên song song. Do đó **18 loại chưa thể coi là đã gửi-duyệt-nghiệm thu E2E**.

Các xung đột trong nguồn:

- `ROOM_VEHICLE` và `OFFICE_SUPPLIES` dùng template B, nhưng mô tả AI Auto-Approve: KHÔNG kích hoạt AI tự duyệt trước khi thống nhất lại điều kiện.
- `LEAVE_LONG` thuộc A nhưng có HR ghi nhận và trưởng phòng nghiệm thu; `OVERTIME_REQ`, `ADVANCE_*`, `REIMBURSEMENT` là B nhưng có người nghiệm thu: cần quyết định có mở rộng lifecycle hay tách ghi nhận hậu xử lý.
- `RESIGNATION` yêu cầu bốn bên thực hiện song song; P0 engine hiện chỉ xử lý một executor.
- `PROD_DATA_ACCESS` và một số loại khác cần actor resolver CTO/CISO/Security và quy tắc nhạy cảm riêng.
- Tài liệu báo cáo khác có chỉ tiêu 16 loại. **Bảng mã chuẩn trong plan.docx ghi 18**. Cần chỉnh nhất quán phần thuyết minh.

## Quy trình kích hoạt có kiểm soát

1. Sao lưu DB, đưa 18 mã lên môi trường UAT bằng role migration (không dùng `eas_api`). Kiểm tra SQL đọc-only trước/sau; không xóa LEAVE/ACCESS/EQUIPMENT đang hoạt động.
2. Mở rộng state machine, actor resolvers, role scope và hard guards cho từng nhóm; đối chiếu sơ đồ. Tạo test E2E cho nhánh duyệt/từ chối/needs-info/tái nộp/exec-reject/accept-reject.
3. OPS_ADMIN quản lý user/phòng ban/role, POLICY_ADMIN tạo config release cho mỗi loại; sử dụng mẫu JSON từ màn hình danh mục và cấu hình bộ approver/executor/acceptor/SLA thực tế. Validate rồi công bố bản release.
4. Sau khi từng loại đạt đủ test (scope/SoD/IDOR, hạn mức, attachment scan, audit, idempotency, outbox), mới kích hoạt bằng API quản trị có lý do và audit.
5. Không chạy tự động các file SQL trong `database/report_migrations` và không cố tình tắt guard bảo mật chỉ để demo.

## Chạy bản cập nhật

```cmd
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe -m unittest tests_report.test_plan_18_catalog -v
start_backend_local.cmd
```

Frontend tại Terminal khác:

```cmd
cd /d "D:\Đồ án\DATN\web_client"
npm ci
npm test
npm run build
npm run dev
```

Đăng nhập vai trò POLICY_ADMIN hoặc OPS_ADMIN, mở **Danh mục 18 loại đơn**. Đây là workspace đối chiếu và thiết lập, không phải nơi vượt qua kiểm soát công bố.
