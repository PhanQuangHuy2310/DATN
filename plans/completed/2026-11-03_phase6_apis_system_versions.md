# Kế hoạch Triển khai: Giai đoạn 6 (Phase 6) — Xây Dựng Module "Quản Lý API" & "Phiên Bản Hệ Thống"

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-6` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | `web_admin/src/pages/APIs/`, `web_admin/src/pages/SystemVersions/`, `web_client/`, `api_core/` |
| **Mục tiêu** | Quản lý Mock API & cơ chế Circuit Breaker chặn luồng tức thì, quản lý phiên bản hệ thống với Diff so sánh trực quan |

---

## 1. MỤC TIÊU & PHẠM VI

### 1.1 Chức năng 8: Quản lý API & Circuit Breaker (Ngắt kết nối khẩn cấp)
- Hiển thị danh mục toàn bộ các API tích hợp từ hệ thống nội bộ (HR, Finance, IT, CRM, Assets, Facilities, Procurement, Travel...) từ bảng `mock_apis`.
- Mỗi API cung cấp thông tin chi tiết:
  - Tên API & Endpoint (ví dụ: `/mock/hr/leave-balance`, `/mock/finance/budget-check`).
  - Hệ thống nguồn (`source_system`).
  - Dữ liệu cung cấp (`data_provided`) kèm nút xem trước dữ liệu mẫu (JSON sample modal).
  - Danh sách các mẫu yêu cầu phụ thuộc vào API này.
  - Công tắc chuyển đổi Bật / Tắt kết nối (`is_enabled`).
- **Cơ chế Circuit Breaker (Ngắt kết nối an toàn):**
  - Khi Admin tắt một API (`is_enabled = false`), backend cập nhật trạng thái ngay lập tức.
  - Phía `web_client` và `web_admin`: Mọi mẫu yêu cầu phụ thuộc vào API đó lập tức chuyển sang trạng thái **Tạm ngưng** với cảnh báo: *"Yêu cầu này hiện không thể sử dụng do hệ thống [Tên API] đang tạm ngắt kết nối"*. Nút gửi yêu cầu bị vô hiệu hóa kèm tooltip giải thích.
  - Khi Admin bật lại API (`is_enabled = true`), các mẫu yêu cầu tự động mở khóa tức thì mà không cần reload trang.

### 1.2 Chức năng 9: Phiên bản hệ thống & Nhật ký thay đổi (System Versions & Diff Viewer)
- Bảng nhật ký phiên bản hệ thống (`system_versions_changelog`): Số phiên bản (ví dụ `v1.0.0`, `v1.1.0`), Phân loại thay đổi (Tính năng mới, Sửa lỗi, Cập nhật quy định, Bảo mật), Người thực hiện, Thời gian áp dụng.
- **Tính năng So sánh Phiên bản Trực quan (Diff Viewer Modal):**
  - Cho phép người dùng bấm "Xem chi tiết thay đổi" để xem modal so sánh nội dung cũ và mới dạng trực quan (Side-by-side hoặc Unified Diff với màu xanh lá cho phần thêm và đỏ cho phần xóa).
- **Sao lưu & Phục hồi:**
  - Nút "Xuất cấu hình phiên bản" (JSON snapshot) tải về máy bản sao lưu cấu hình toàn bộ hệ thống.
  - Hỗ trợ lưu trữ snapshot an toàn phục vụ truy vết và đối soát kiểm toán (Audit Trail).

---

## 2. KẾT QUẢ THỰC HIỆN
- Xây dựng `APIsPage.jsx` và `SystemVersionsPage.jsx` trên `web_admin`.
- Xây dựng modal `JsonPreviewModal.jsx` và `DiffViewerModal.jsx`.
- Tích hợp kiểm tra Circuit Breaker vào `RequestCreateModal.jsx` trên `web_client`.
- Kiểm thử thành công luồng bật/tắt API và xác nhận thông báo chặn hiển thị chính xác trên `web_client`.
