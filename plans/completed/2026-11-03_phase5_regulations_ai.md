# Kế hoạch Triển khai: Giai đoạn 5 (Phase 5) — Xây Dựng Module "Quy Định" & "Quản Trị AI" (Auto-Lock & Đồng Bộ AI Service)

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-5` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | `web_admin/src/pages/Regulations/`, `web_admin/src/pages/AIEngine/`, `web_client/`, `api_core/workflow/` |
| **Mục tiêu** | Quản lý quy định với Semantic Versioning tự động, đồng bộ học máy AI Service và cơ chế Auto-Lock bảo vệ toàn diện trên Web Client |

---

## 1. MỤC TIÊU & PHẠM VI

### 1.1 Chức năng 6: Quy định công ty & Semantic Versioning
- Quản lý danh mục Quy định công ty, liên kết điều khoản chính sách với nhãn phiên bản hiện tại (ví dụ: `v1.0`, `v1.1`, `v2.0`).
- Cho phép Thêm quy định mới, Chỉnh sửa nội dung quy định, Xóa quy định.
- **Quy tắc Đánh số Phiên bản Tự động (Semantic Versioning):**
  - **Sửa đổi nội dung quy định hiện có:** Tự động tăng phiên bản nhỏ (**Minor Version**, ví dụ `v1.0` -> `v1.1`, `v2.3` -> `v2.4`).
  - **Thêm mới hoặc Xóa một quy định:** Tự động tăng phiên bản lớn (**Major Version**, ví dụ `v1.4` -> `v2.0`).
  - Ghi nhận đầy đủ biến động vào bảng nhật ký lịch sử `system_versions_changelog`.

### 1.2 Chức năng 7: Quản trị AI Engine & Cơ chế Auto-Lock Bảo vệ Hệ thống
- Tự động kích hoạt luồng đồng bộ sang `ai_service` ngay khi quy định có sự thay đổi.
- **Cơ chế Khóa tự động (Auto-Lock / Freeze Screen):**
  - Trong quá trình AI tiến hành học/retrain quy định mới:
    - Tại `web_admin`: Hiển thị trạng thái học tập (Job Queue / Status: `LEARNING` / `PROCESSING`), thanh tiến trình và thông báo thời gian dự kiến.
    - Tại `web_client`: Tự động kích hoạt màn hình khóa bảo vệ hệ thống với thông điệp: *"Hệ thống AI đang cập nhật quy định mới. Mọi chức năng tạo và xử lý yêu cầu tạm dừng để đảm bảo tính chuẩn xác."*
  - Khi AI hoàn tất học tập (Status: `READY` / `IDLE`), `web_client` tự động mở khóa và người dùng tiếp tục thao tác bình thường.
  - Cung cấp nút **Mở khóa khẩn cấp (Emergency Force Unlock)** cho Quản trị viên can thiệp xử lý khi cần thiết.

---

## 2. KẾT QUẢ THỰC HIỆN
- Xây dựng `RegulationsPage.jsx` và `AIEnginePage.jsx` trên `web_admin`.
- Xây dựng component `MaintenanceOverlay.jsx` và hook kiểm tra trạng thái khóa trên `web_client`.
- Cập nhật backend `api_core/workflow/ai_learning.py` và `api_core/maintenance.py` hỗ trợ queue học quy định và đồng bộ trạng thái khóa `ai_system_state`.
- Đảm bảo 100% test coverage cho module `test_ai_learning` (11/11 tests pass).
