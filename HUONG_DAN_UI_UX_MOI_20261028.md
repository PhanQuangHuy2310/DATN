# Cập nhật UI/UX DATN — 28/10/2026

## Phạm vi thay đổi

1. **Tạo yêu cầu mới** (REQUESTER): thanh lọc theo nhóm nằm ngang có thể cuộn, tìm kiếm theo tên/mã/mô tả, lọc trạng thái, danh sách biểu mẫu dạng xổ xuống, chọn biểu mẫu hợp lệ. Loại chưa công bố/cấp quyền không thể chọn. Nguồn trạng thái: `/api/v1/meta/request-type-forms`.
2. **Danh mục loại yêu cầu** (POLICY_ADMIN/OPS_ADMIN): nhóm nghiệp vụ nằm ngang, bộ lọc từ khóa và tình trạng release, danh sách dạng hàng, chi tiết JSON Schema giữ nguyên. Nguồn: `/api/v1/meta/plan-request-types`, `/api/v1/request-types`.
3. **Quản lý API & ma trận quyền** (OPS_ADMIN GLOBAL+ALL): heatmap 7 vai trò × nhóm nghiệp vụ, phân màu ô có GET/chỉ thao tác/cả hai/chưa có khai báo trực tiếp, bộ lọc theo vai trò và nhóm, nhấn ô xem danh sách endpoint. Nguồn dữ liệu chỉ đọc: `/api/v1/admin/access-matrix`, `/api/v1/admin/api-catalog`.
4. **Người dùng & phân quyền** (OPS_ADMIN GLOBAL+ALL): biểu đồ ngang trạng thái role membership **chỉ theo trang hiện tại** do API phân trang; chi tiết quyền theo bảng thay vì card. Không mở rộng scope.

## Cần lưu ý về bảo mật / diễn giải biểu đồ

- Heatmap mô tả **endpoint có khai báo trực tiếp role trong catalog**, **không phải quyết định cho phép truy cập**. Alias `PARTICIPANT` và `AUTHENTICATED` được giữ nguyên, không giả lập thành cấp quyền cụ thể. Ô trống nghĩa là catalog không khai báo trực tiếp cặp role/domain, không mặc nhiên là `DENY`.
- Quyền thực tế phụ thuộc phiên, role membership hiệu lực, phòng ban, loại yêu cầu, actor, trạng thái, revision và SoD. Mọi kiểm tra vẫn do Backend Django thực hiện.
- Biểu đồ membership chỉ tổng hợp các bản ghi hiện tại trong trang, không dùng để báo cáo tổng số quyền toàn tổ chức.
- Không thêm API, không sửa schema Supabase, không thay quyền người dùng hoặc trạng thái công bố.

## Chạy giao diện mới trên Windows

Mở CMD tại thư mục `D:\Đồ án\DATN`:

```cmd
start_backend_local.cmd
```

Trong terminal khác:

```cmd
cd /d "D:\Đồ án\DATN\web_client"
npm ci
npm run dev
```

Truy cập http://127.0.0.1:5173, đăng nhập đúng role rồi xem **Tạo yêu cầu mới**, **Danh mục loại yêu cầu**, **Quản lý API & ma trận quyền** và **Danh tính & phân quyền**.

## Kiểm thử

```cmd
cd /d "D:\Đồ án\DATN\web_client"
npm test
npm run build
```

Đã chạy kiểm thử logic Node.js **24/24** và kiểm tra cú pháp JSX/CSS trong môi trường chỉnh sửa. `npm ci` ở môi trường tạo bản này không hoàn tất do tải thư viện bị timeout; vì thế không khẳng định Vite build hoặc trình duyệt đã được nghiệm thu trong môi trường đó. Hãy chạy `npm ci && npm run build` ở máy Windows có kết nối mạng và báo lại log nếu có lỗi.
