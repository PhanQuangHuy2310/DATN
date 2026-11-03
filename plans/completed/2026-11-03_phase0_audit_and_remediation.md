# Kế hoạch Triển khai: Giai đoạn 0 (Phase 0) — Audit Dự Án, Sửa Lỗi Nền Tảng & Đồng Bộ Plans

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-0` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | `api_core/`, `web_admin/`, `web_client/`, `database/`, `plans/` |
| **Mục tiêu** | Rà soát toàn bộ tài liệu đặc tả SRS, sửa lỗi schema trùng lặp, thiết lập kế hoạch 9 chức năng |

---

## 1. MỤC TIÊU & PHẠM VI
- Kiểm toán toàn diện kiến trúc hệ thống hiện có theo tiêu chuẩn Zero-Destruction.
- Loại bỏ các bảng trung gian thừa, giải quyết xung đột schema giữa các phân hệ.
- Chuẩn hóa cấu trúc tài liệu quản lý tiến độ và kế hoạch theo định dạng chuẩn của dự án.

## 2. HẠNG MỤC THỰC HIỆN
1. **Audit Database**:
   - Phân tích `database/migrations/` và cấu trúc bảng `eas.*`.
   - Lập phương án dọn dẹp các tài khoản quản trị phụ (`+admin@eas.com`) bảo đảm an toàn.
2. **Audit Code-Splitting & Kiến trúc**:
   - Xác định mô hình chia tách frontend: `web_client` (cổng nhân viên, bundle siêu nhẹ ~300KB) và `web_admin` (cổng quản trị, nạp qua lazy chunk `adminScreens.jsx`).
   - Rà soát xác thực cookie bảo mật, RLS Supabase và middleware `require_actor`.
3. **Quy hoạch Kế hoạch 9 Chức năng**:
   - Soạn thảo roadmap chi tiết `plans/active/2026-11-03_admin_9_features_roadmap.md`.
