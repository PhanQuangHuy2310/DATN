# Access Control (IDOR) Fix Plan

Báo cáo: [ACCESS_CONTROL_REPORT.md](../reports/ACCESS_CONTROL_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- Không có thay đổi mã.

## New files

- Không có.

## Verification goals

- [x] Mọi route có ID kiểm tra sở hữu/phạm vi
- [x] Kiểm tra có ở cả GET và PUT/PATCH/DELETE
- [x] Sai sở hữu → 403 (ghi) / 404 (đọc, chủ đích)
- [x] Xác thực và sở hữu tách biệt

## Manual verification (for the human)

- Đăng nhập 2 tài khoản REQUESTER khác phòng ban; dùng ID yêu cầu của người A gọi `/api/v1/requests/{id}` bằng người B: phải nhận 404.
