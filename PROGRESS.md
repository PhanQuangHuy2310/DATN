# PROGRESS — nhánh `dat`

Phiên sau đọc file này để làm tiếp. Mỗi mục xong: test → commit riêng → push `origin/dat`.

## Đã xong
- [x] 1.1 Quy tắc cổng: admin thuần chỉ dùng cổng quản trị; admin có APPROVER/EXECUTOR dùng cả hai (`rolePolicy.canUsePortal`)
- [x] Mốc nền (6101da8): AI tự duyệt, giao việc xuống cấp dưới, thay người vắng, nạp quy định AI, migration 07/08/mock 004

## Đang làm
- [ ] 1.2 Proxy & gateway chặn admin/ops/internal

## Chưa làm
- [ ] 1.3 Mật khẩu admin đọc từ biến môi trường
- [ ] 1.4 Quy định AI lưu DB
- [ ] 1.5 Hoàn tác AI tự duyệt trong 24h
- [ ] 2.1 Migration 10 nhóm + ngưng 8 loại trùng
- [ ] 2.2 Migration 13 loại mới
- [ ] 2.3 IT_SUPPORT người thực hiện IT
- [ ] 2.4 Code nhóm/nhãn/JSON danh mục
- [ ] 2.5 Test danh mục
- [ ] 3.1 Lazy-load màn hình quản trị
- [ ] 4.1 Cờ is_system_account cho EAS AI
- [ ] 4.2 Xóa ingest_policy / toggle_maintenance cũ
- [ ] 4.3 Giao diện nạp bộ luật POLICY_ADMIN
- [ ] 4.4 Ủy quyền duyệt
- [ ] 4.5 Chấm công khớp mã nhân viên
- [ ] 4.6 Dockerfile ai-service multi-stage
- [ ] 4.7 Smoke test OCR trong CI
- [ ] 5.1 Menu tự cập nhật /me
- [ ] 5.2 Test secret-policy cô lập .env
- [ ] 5.3 Cổng Redis từ biến môi trường
- [ ] 6.x Test toàn bộ, PR_DESCRIPTION.md

## Quyết định cần tôi xác nhận
(chưa có)

## Việc tôi phải làm thủ công
- Chạy trên Supabase SQL Editor theo thứ tự: `database/migrations/07_dev_restore_eas_emails.sql` (đã chạy), `08_ai_system_account.sql`, `database/mock_enterprise_sql/migrations/004_hrm_attendance.sql`
