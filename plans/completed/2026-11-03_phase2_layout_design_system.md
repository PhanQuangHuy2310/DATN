# Kế hoạch Triển khai: Giai đoạn 2 (Phase 2) — Master Layout, Sidebar & Header Đồng Bộ

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-2` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | `web_admin/`, `web_client/` |
| **Mục tiêu** | Thiết kế Design System, Sidebar 2 trạng thái, Header đồng bộ 100% giữa Admin và Client |

---

## 1. MỤC TIÊU & PHẠM VI
- Đồng nhất hoàn toàn ngôn ngữ thiết kế giữa cổng Quản trị (`web_admin`) và cổng Nhân viên (`web_client`).
- Hỗ trợ chế độ Sáng / Tối (Dark / Light Mode) mượt mà với `theme-toggle-btn`.
- Typography chuẩn hóa: Roboto cho body text, Montserrat cho tiêu đề & số liệu.

## 2. HẠNG MỤC THỰC HIỆN
1. **Sidebar Điều hướng 2 Trạng thái**:
   - Trạng thái Mở rộng (Expanded): đầy đủ icon, nhãn nhóm, tên chức năng.
   - Trạng thái Thu gọn (Collapsed): chỉ hiển thị icon thu nhỏ kèm tooltip, ghi nhớ vào `localStorage`.
   - Phân chia 5 nhóm rõ ràng: Giám sát, Luồng công việc, Tổ chức & Nhân sự, Tri thức & AI, Hệ thống.
2. **Header Thông minh**:
   - Tiêu đề trang (`.topbar-page-title`) đổi đúng theo trang đang mở.
   - Thanh tìm kiếm toàn cục (Global Search) hỗ trợ tìm nhanh trang điều hướng và tìm mã yêu cầu.
   - Chuông thông báo (Notification Bell), Avatar người dùng, chức vụ, nút Đăng xuất.
