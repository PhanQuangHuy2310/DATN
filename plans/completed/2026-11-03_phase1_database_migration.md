# Kế hoạch Triển khai: Giai đoạn 1 (Phase 1) — Thiết Kế File SQL Migration Supabase

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-1` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | `supabase/migrations/`, `database/` |
| **Mục tiêu** | Thiết kế SQL Migration an toàn tuyệt đối với `IF NOT EXISTS` và seed data tiếng Việt |

---

## 1. MỤC TIÊU & PHẠM VI
- Tạo file SQL migration mới tại `supabase/migrations/20261103_admin_full_upgrade.sql`.
- Tuân thủ nguyên tắc Zero-Destruction: không dùng `DROP TABLE`, không `TRUNCATE`, sử dụng `ON CONFLICT DO NOTHING`.

## 2. CẤU TRÚC BẢNG & TRƯỜNG DỮ LIỆU
1. **Bảng Tổ chức & Phòng ban (`eas.department`)**:
   - `id`, `code`, `name`, `parent_id`, `manager_id`, `description`, `created_at`.
2. **Bảng Người dùng & Chấm công (`eas.app_user`, `eas.user_leave_and_trips`)**:
   - Thêm cột `avatar_url`, `role_id`, `department_id`.
   - Bảng `user_leave_and_trips` lưu loại đơn (`LEAVE`, `BUSINESS_TRIP`, `OVERTIME`), thời gian bắt đầu, kết thúc, lý do, trạng thái.
3. **Bảng Phân quyền RBAC (`eas.role_module_permission`, `eas.user_permissions`)**:
   - Cấp quyền CRUD theo chức vụ và quyền ghi đè tùy biến theo từng nhân viên.
4. **Bảng Quy định & AI (`eas.company_regulations`, `eas.ai_system_state`, `eas.regulation_versions`)**:
   - Lưu trữ văn bản quy chế, chỉ số phiên bản và thông tin mô hình AI.
5. **Bảng Quản lý API & Changelog (`eas.mock_apis`, `eas.system_versions_changelog`)**:
   - Quản lý 8 API mock nội bộ, cờ `is_enabled`, lịch sử kiểm toán trước/sau (`old_value`, `new_value`).
