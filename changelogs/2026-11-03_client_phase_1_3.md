# Changelog 03/11/2026 — Cổng nhân viên Phase 1–3: giao diện theo quyền module do admin cấp

Kế hoạch: [EAS-PLAN-2026-11-03-03](../plans/active/2026-11-03_client_phase_1_3_module_permissions.md) · Tài liệu: [docs/CHUC_NANG_UI_VA_PHAN_QUYEN.md](../docs/CHUC_NANG_UI_VA_PHAN_QUYEN.md) mục 14

## Backend
- `api_core/authn/module_access.py`: `can()`, `require_module()`; 4 module hệ thống không bao giờ cho nhân viên.
- `api_core/administration/workspace.py`: `/api/v1/workspace/*` (analytics theo phạm vi, sơ đồ tổ chức, phòng ban, người dùng, quy định, danh mục mẫu kèm trạng thái tích hợp, bảng 5 giai đoạn, cấu hình mẫu) dùng lại logic quản trị; ghi qua `service.mutate(authorizer=...)`, có nhật ký.
- `users` được admin cấp cho nhân viên; nhân viên không gán được vai trò Người phê duyệt; khoá/mở tài khoản cần quyền Xoá.
- `/auth/me`: mã NV, chức danh, phòng ban, trạng thái làm việc (cùng một truy vấn).
- `api_core/workflow/leave_sync.py`: duyệt xong nghỉ phép/công tác/đi muộn/về sớm → `user_leave_and_trips`.
- Nhãn tiếng Việt cho mọi mã người duyệt trong luồng.

## Frontend
- Menu nhân viên theo 5 module (hiện khi có quyền Xem), header trạng thái làm việc + chức danh + phòng ban, khung tiến trình AI ở màn đăng nhập, đếm ngược 3 giây, quyền tự làm mới 15 giây.
- Trang "Yêu cầu & Quy trình" (`ClientRequestsHub.jsx`); Tổng quan, Sơ đồ tổ chức, Người dùng, Quy định dùng chung màn hình admin qua `apiBase.js`.
- Nút theo quyền ở Quy định, Cấu hình mẫu; `ClientPermissionGuard`; sửa lỗi nhân viên không thấy nút Sửa/Huỷ hồ sơ của mình.

## Kiểm thử
- 5 kịch bản liên thông trên trình duyệt (bản sao live): 21/21. Luồng nghỉ phép → "Nghỉ làm": đạt. Live chỉ đọc: 48/48.
- Django 448 OK, `npm test` 64, ESLint/ruff sạch, build 2 cổng, kiểm tra bundle đạt.
