# Kế hoạch Triển khai: Giai đoạn 4 (Phase 4) — "Sơ Đồ Công Ty", "Người Dùng" & "Ma Trận Phân Quyền RBAC"

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-4` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | `web_admin/src/pages/OrgChart/`, `web_admin/src/pages/Users/`, `web_admin/src/pages/RBAC/`, `api_core/` |
| **Mục tiêu** | Triển khai sơ đồ cây tổ chức, quản lý người dùng với trạng thái giờ làm việc thực tế & modal 5 giai đoạn, ma trận RBAC động theo chức vụ & cá nhân |

---

## 1. MỤC TIÊU & PHẠM VI

### 1.1 Chức năng 3: Sơ đồ công ty (Company Org Chart)
- Thống kê toàn công ty: Tổng số phòng ban (8 phòng ban), tổng số lượng nhân sự (137 nhân sự).
- Sơ đồ cây phân cấp trực quan (Visual Org Chart Tree) từ Ban Giám đốc xuống các Phòng ban nghiệp vụ (Kỹ thuật, Tài chính, Nhân sự, Kinh doanh, Marketing, Vận hành, Pháp chế, Hành chính).
- Mỗi khối Phòng ban thể hiện rõ: Tên phòng ban, Trưởng phòng, Số lượng nhân viên hiện có. Bấm vào phòng ban để xem danh sách nhân sự thuộc phòng ban đó.

### 1.2 Chức năng 4: Người dùng & Trạng thái làm việc thực tế (User Management)
- Bảng danh sách người dùng đầy đủ: Họ tên, Email, Chức vụ, Phòng ban, Trạng thái, Tổng số yêu cầu, thao tác Thêm/Sửa/Khóa người dùng.
- **Thuật toán tính Trạng thái làm việc chính xác theo thời gian thực:**
  - Khung giờ chuẩn: **08:00 - 17:30, Thứ Hai đến Thứ Sáu** (Nghỉ Thứ 7, Chủ nhật).
  - Đối chiếu tự động với bảng `user_leave_and_trips` (các đơn được `APPROVED`):
    - **Đang làm (Xanh lá):** Trong khung giờ làm việc và không có lịch nghỉ/công tác.
    - **Nghỉ làm (Xám/Đỏ nhạt):** Đang trong thời gian nghỉ phép hoặc ngoài giờ làm việc chuẩn.
    - **Công tác (Xanh dương/Tím):** Đang trong thời gian công tác hợp lệ.
- **Modal chi tiết 5 giai đoạn:** Bấm vào số lượng yêu cầu của bất kỳ người dùng nào để xem popup chia nhỏ yêu cầu theo 5 giai đoạn:
  1. Mới tiếp nhận (Received)
  2. Đang kiểm tra / AI đánh giá (Evaluating)
  3. Chờ phê duyệt (Approving)
  4. Đang thực hiện (Executing)
  5. Hoàn thành (Completed)

### 1.3 Chức năng 5: Ma trận Phân quyền RBAC (Role-Based Access Control)
- Thiết kế 2 Tab:
  - **Tab 1: Phân quyền theo Chức vụ (Role-based):** Áp dụng quyền mặc định cho từng vai trò (`ADMIN`, `DIRECTOR`, `MANAGER`, `LEADER`, `SENIOR_SPECIALIST`, `SPECIALIST`, `STAFF`, `INTERN`).
  - **Tab 2: Phân quyền riêng theo Người dùng (User-specific override):** Cho phép ghi đè quyền cụ thể cho từng tài khoản mà không làm thay đổi vai trò gốc.
- Ma trận phân quyền động 4 hành động (Xem, Tạo, Sửa, Xóa) cho toàn bộ các module chức năng.
- Cột cấu hình **Hiển thị trên Sidebar (`show_on_sidebar`)**: Quyết định menu chức năng có xuất hiện trên thanh điều hướng bên trái hay không.
- Lưu trữ qua RPC `eas.update_role_module_permission` và `eas.upsert_user_module_permission`. Khi thay đổi, cập nhật ngay lập tức UI mà không cần tải lại trang.

---

## 2. KẾT QUẢ THỰC HIỆN
- Xây dựng `OrgChartPage.jsx`, `UsersPage.jsx`, `RBACPage.jsx` trong `web_admin`.
- Xây dựng modal `UserStageDetailsModal.jsx` xem chi tiết 5 giai đoạn yêu cầu.
- Đồng bộ hàm tính toán trạng thái người dùng trong `api_core/users/` và frontend.
- Cập nhật database với dữ liệu chuẩn 137 tài khoản người dùng, loại bỏ tài khoản `+admin` ảo.
