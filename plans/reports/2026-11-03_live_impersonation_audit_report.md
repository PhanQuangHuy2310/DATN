# Báo Cáo Kiểm Thử Toàn Diện: Live Impersonation & E2E Audit 8 Giai Đoạn (Phase 0 -> Phase 7)

| Thuộc tính | Chi tiết |
|---|---|
| **Mã báo cáo** | `EAS-AUDIT-REPORT-2026-11-03-LIVE` |
| **Ngày thực hiện** | 03/11/2026 |
| **Trạng thái** | `PASSED` (100% Pass, 0 Blocking Bugs) |
| **Môi trường** | `http://127.0.0.1:8000` (API), `http://127.0.0.1:5173` (Web Client), `http://127.0.0.1:5174` (Web Admin) |
| **Dữ liệu kiểm thử** | Dữ liệu cập nhật mới nhất từ bản sửa của Quản trị viên (137 tài khoản người dùng, loại bỏ tài khoản `+admin`, hệ thống AI Learning) |

---

## 1. MỤC TIÊU & PHƯƠNG PHÁP KIỂM THỬ

Tiến hành đóng giả trực tiếp (Live Impersonation) các vai trò người dùng thực tế qua trình duyệt web từ bước đăng nhập, kiểm tra toàn bộ luồng chức năng của 8 giai đoạn dự án trên nền tảng mã nguồn và cơ sở dữ liệu mới nhất:

1. **Quản trị viên Hệ thống (`admin@eas.com` / `Password@123456`)**:
   - Đăng nhập Cổng Quản trị `web_admin` (`http://127.0.0.1:5174/`).
   - Kiểm tra Master Layout, Sidebar 5 nhóm & 9 menu chức năng, Header động, Theme Sáng/Tối.
   - Kiểm tra các màn hình: Dashboard KPI, Yêu cầu & Quy trình (Kanban), Sơ đồ công ty, Người dùng (giờ hành chính 08:00 - 17:30 & modal 5 giai đoạn), RBAC (Tab Chức vụ & Tab Người dùng), Quy định (Semantic Versioning), Quản trị AI, Quản lý API (Circuit Breaker) và Phiên bản hệ thống (Diff Viewer).
2. **Nhân viên thông thường (`lan.ngo@eas.com` / `Password@123456`)**:
   - Đăng nhập Cổng Nhân viên `web_client` (`http://127.0.0.1:5173/`).
   - Kiểm tra giao diện Workspace, danh mục yêu cầu cá nhân, tạo yêu cầu mới.
3. **Người phê duyệt (`an.pham@eas.com` / `Password@123456`)**:
   - Đăng nhập Cổng Nhân viên `web_client` (`http://127.0.0.1:5173/`).
   - Kiểm tra danh sách hàng đợi "Chờ phê duyệt".
4. **Người thi hành (`an.do@eas.com` / `Password@123456`)**:
   - Đăng nhập Cổng Nhân viên `web_client` (`http://127.0.0.1:5173/`).
   - Kiểm tra danh sách hàng đợi "Công việc thực hiện".
5. **Kiểm tra Ranh giới Bảo mật (Security Separation & Negative Access Control)**:
   - Nhân viên thường cố tình đăng nhập Cổng Quản trị `web_admin` (`5174`) -> Bị chặn tức thì với thông báo "Không có quyền quản trị".
   - Quản trị viên đăng nhập Cổng Nhân viên `web_client` (`5173`) -> Nhận màn hình phân tách chuyên biệt "Tài khoản quản trị sử dụng cổng quản trị hệ thống riêng".

---

## 2. KẾT QUẢ KIỂM THỬ CHI TIẾT THEO 8 GIAI ĐOẠN

### Phase 0: Audit Dự Án, Sửa Lỗi Nền Tảng & Đồng Bộ Plans
- **Kết quả:** `PASSED`
- Backend Django API phản hồi CSRF và session `/api/v1/auth/csrf` với mã trạng thái 200 (`status: "ok"`).
- Cơ sở dữ liệu sạch: Toàn bộ các tài khoản giả lập `+admin` đã được xóa sạch. Tổng số tài khoản nhân sự hoạt động thực tế là 137 người dùng trải đều 8 phòng ban. Mọi tài khoản đồng bộ hash mật khẩu chuẩn `Password@123456`.

### Phase 1: Database Migration Supabase
- **Kết quả:** `PASSED`
- Toàn bộ các bảng nghiệp vụ nâng cấp (`user_leave_and_trips`, `mock_apis`, `system_versions_changelog`, `role_module_permission`, `user_permissions`) hoạt động ổn định và nhất quán giữa Supabase và PostgreSQL local.

### Phase 2: Master Layout, Design System, Sidebar & Header
- **Kết quả:** `PASSED`
- Đăng nhập thành công với tài khoản Admin `admin@eas.com`.
- **Sidebar:** Hiển thị chuẩn xác 5 nhóm và 9 chức năng:
  - GIÁM SÁT: *Tổng quan*
  - LUỒNG CÔNG VIỆC: *Yêu cầu & Quy trình*
  - TỔ CHỨC & NHÂN SỰ: *Sơ đồ công ty*, *Người dùng*, *Phân quyền*
  - TRI THỨC & AI: *Quy định*, *Quản trị AI*
  - HỆ THỐNG: *Quản lý API*, *Phiên bản hệ thống*
- **Header:** Tiêu đề động tự động thay đổi chuẩn xác 100% theo từng màn hình đang kích hoạt (`Tổng quan vận hành`, `Yêu cầu & Quy trình`, `SƠ ĐỒ TỔ CHỨC CÔNG TY`, `Quản lý Người dùng & Trạng thái làm việc`, `Ma trận Phân quyền (RBAC Matrix)`, `Quy định công ty & Semantic Versioning`, `Quản trị AI Engine & Giám sát Huấn luyện`, `Quản lý API & Circuit Breaker`, `Phiên bản hệ thống & Nhật ký kiểm toán`).
- **Design System:** Nút chuyển đổi Dark/Light mode hoạt động mượt mà, lưu trạng thái vào `localStorage` và áp dụng tức thì.

### Phase 3: Module "Tổng Quan" & "Yêu Cầu & Quy Trình"
- **Kết quả:** `PASSED`
- **Tổng quan (Dashboard):** Hiển thị hàng thẻ KPI, 4 nút lọc thời gian (Theo Ngày / Theo Tuần / Theo Tháng / Theo Năm) chuyển đổi linh hoạt, biểu đồ xu hướng và bảng xếp hạng phòng ban/cá nhân.
- **Yêu cầu & Quy trình:** Hiển thị danh mục loại yêu cầu A/B/C và bảng Kanban 5 giai đoạn giám sát tiến độ trực quan.

### Phase 4: "Sơ Đồ Công Ty", "Người Dùng" & "Ma Trận Phân Quyền RBAC"
- **Kết quả:** `PASSED`
- **Sơ đồ công ty:** Cây phân cấp trực quan từ Ban Giám đốc xuống 8 phòng ban nghiệp vụ với số lượng nhân sự hiển thị rõ ràng.
- **Người dùng:** Hiển thị danh sách 137 nhân sự; thuật toán tính toán trạng thái thời gian thực chuẩn theo khung giờ 08:00 - 17:30, T2-T6 (Đang làm, Nghỉ làm, Công tác). Click vào số lượng yêu cầu mở modal xem chi tiết 5 giai đoạn (Tiếp nhận, Đang kiểm tra, Chờ phê duyệt, Đang thực hiện, Hoàn thành).
- **Phân quyền RBAC:** Hỗ trợ đầy đủ 2 Tab (Phân quyền theo Chức vụ và Phân quyền riêng theo Người dùng). Các công tắc quyền CRUD và `show_on_sidebar` hoạt động mượt mà.

### Phase 5: "Quy Định" & "Quản Trị AI" (Auto-Lock & Đồng Bộ AI Service)
- **Kết quả:** `PASSED`
- **Quy định:** Quản lý danh mục quy định với cơ chế đánh số Semantic Versioning tự động (Sửa quy định -> tăng Minor; Thêm/Xóa -> tăng Major).
- **Quản trị AI:** Trạng thái AI Engine kết nối chặt chẽ với cơ chế bảo vệ hệ thống. Khi AI đang học, Cổng Nhân viên tự động khóa bảo vệ với thông báo rõ ràng; khi hoàn tất, hệ thống tự động mở khóa và người dùng tiếp tục thao tác bình thường.

### Phase 6: "Quản Lý API" & "Phiên Bản Hệ Thống"
- **Kết quả:** `PASSED`
- **Quản lý API:** Hiển thị đầy đủ danh sách APIs tích hợp từ các hệ thống nội bộ (HR, Finance, IT, CRM, Assets, Procurement...). Cơ chế Circuit Breaker cho phép Bật/Tắt kết nối; popup xem trước mẫu dữ liệu JSON hoạt động nhanh chóng.
- **Phiên bản hệ thống:** Nhật ký lịch sử phiên bản hiển thị chi tiết các thay đổi; hỗ trợ Diff Viewer so sánh trực quan và xuất snapshot JSON sao lưu cấu hình.

### Phase 7: Kiểm Thử Đóng Giả Người Dùng (Impersonation) & Ranh Giới Bảo Mật
- **Kết quả:** `PASSED`
- **Nhân viên (`lan.ngo@eas.com`):** Đăng nhập thành công vào Cổng Client (`5173`), hiển thị đúng menu cá nhân và form gửi yêu cầu.
- **Người phê duyệt (`an.pham@eas.com`):** Đăng nhập thành công, truy cập đúng danh sách duyệt.
- **Người thi hành (`an.do@eas.com`):** Đăng nhập thành công, truy cập đúng danh sách công việc.
- **Kiểm soát phân quyền:**
  - `lan.ngo@eas.com` truy cập Cổng Admin (`5174`) -> Bị chặn 100% với thông báo: *"Không có quyền quản trị - Tài khoản không được cấp quyền sử dụng trung tâm quản trị"*.
  - `admin@eas.com` truy cập Cổng Client (`5173`) -> Hệ thống phân tách rõ ràng: *"Tài khoản quản trị sử dụng cổng quản trị hệ thống riêng; không tạo hoặc xử lý yêu cầu trên cổng nhân viên"*.

---

## 3. KẾT LUẬN & ĐỀ XUẤT
Hệ thống Enterprise Approval System (EAS) đã hoàn thành xuất sắc toàn bộ 8 giai đoạn phát triển theo đúng kế hoạch và đạt 100% tiêu chí nghiệm thu (Definition of Done). Mọi kế hoạch trong `plans/active/` đã sẵn sàng chuyển sang `plans/completed/`.

