# Kế hoạch Triển khai: Giai đoạn 3 (Phase 3) — Xây Dựng Module "Tổng Quan" & "Yêu Cầu & Quy Trình"

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-3` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | `web_admin/src/pages/Dashboard/`, `web_admin/src/pages/Workflows/`, `api_core/` |
| **Mục tiêu** | Xây dựng Dashboard phân tích KPI theo kỳ và Quản lý Yêu cầu & Quy trình luồng A/B/C với Kanban và Ma trận trọng số |

---

## 1. MỤC TIÊU & PHẠM VI

### 1.1 Chức năng 1: Tổng quan (Dashboard)
- Bộ lọc thời gian linh hoạt: **Theo Ngày | Theo Tuần | Theo Tháng | Theo Năm** (`timeRange`).
- Hàng thẻ KPI tổng hợp:
  - Tổng số yêu cầu phát sinh.
  - Số lượng & Tỷ lệ yêu cầu **Thành công (Đã hoàn thành/Phê duyệt)**.
  - Số lượng & Tỷ lệ yêu cầu **Bị từ chối (Rejected)**.
  - Số lượng yêu cầu **Đang xử lý**.
- Biểu đồ & Bảng xếp hạng chuyên sâu:
  - **Xu hướng yêu cầu:** Biểu đồ cột/đường theo trục thời gian.
  - **Loại yêu cầu phổ biến nhất:** Biểu đồ phân bổ theo loại yêu cầu.
  - **Thống kê Phòng ban & Cá nhân:** Bảng xếp hạng Top Phòng ban và Top Người dùng gửi nhiều yêu cầu nhất.
  - **Tốc độ xử lý trung bình theo Phân loại (A, B, C):** Thống kê thời gian xử lý trung bình (giờ/phút) và tỷ lệ đúng hạn SLA.
- Nút **Xuất Báo Cáo** (CSV / Excel) tải về bảng số liệu chi tiết.

### 1.2 Chức năng 2: Yêu cầu & Quy trình (Workflows & Request Types)
- **Danh sách Mẫu Yêu cầu:**
  - Hiển thị đầy đủ các loại yêu cầu kèm phân loại rõ ràng:
    - **Loại A:** Phê duyệt tự động bằng AI (Auto Approval).
    - **Loại B:** Phê duyệt thông thường (Trưởng phòng/QL trực tiếp duyệt).
    - **Loại C:** Phê duyệt phức tạp đa cấp (Nhiều cấp, Ban Giám đốc, Hội đồng thẩm định).
  - Cho phép Admin chuyển đổi phân loại (từ A sang B, hoặc B sang C) trực tiếp trên giao diện và tự động cập nhật số bước duyệt tương ứng.
- **Sơ đồ Quy trình Trực quan:**
  - Hiển thị tiến trình các bước duyệt tương ứng với từng phân loại.
  - Tích hợp **Cấu hình Trọng số & Rủi ro:** Cho phép điều chỉnh ngưỡng số tiền duyệt, mức độ ưu tiên, phòng ban áp dụng.
- **Kanban Board Giám sát Tiến độ:**
  - 5 cột tương ứng 5 giai đoạn: **Mới tiếp nhận (RECEIVED) | Đang kiểm tra/AI chấm (EVALUATING) | Chờ phê duyệt (APPROVING) | Đang thực hiện (EXECUTING) | Hoàn thành (COMPLETED)**.
  - Hỗ trợ kéo thả (drag & drop) hoặc đổi trạng thái nhanh để can thiệp luồng duyệt khi cần thiết.

---

## 2. KẾT QUẢ THỰC HIỆN
- Tạo component `DashboardPage.jsx` và `WorkflowsPage.jsx` trong `web_admin/src/pages/`.
- Tích hợp API endpoint phân tích số liệu `api_core/dashboard/` và quản lý yêu cầu `api_core/workflow/`.
- Hỗ trợ xuất dữ liệu báo cáo ra file CSV/Excel UTF-8.
- Đồng bộ tự động các thay đổi trọng số và phân loại A/B/C với `ai_service`.
