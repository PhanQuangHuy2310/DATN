# PROGRESS — nhánh `dat`

Phiên sau đọc file này để làm tiếp. Mỗi mục xong: test → commit riêng → push `origin/dat`.

## Đã xong
- [x] 4.3 Trang 'Bộ luật quy định AI' (khu quản trị, chỉ POLICY_ADMIN): tải tệp JSON, danh sách phiên bản, kích hoạt/khôi phục; dùng API lưu DB của 1.4; lazy-load, không có trong bundle cổng nhân viên
- [x] 4.2 Đã xóa ingest_policy, toggle_maintenance, maintenance_status, _trigger_ai_retraining (grep xác nhận không còn nơi gọi, không gắn URL); có test chặn quay lại
- [x] 4.1 Cờ is_system_account (migration 14 + rollback); API admin ẩn tài khoản hệ thống mặc định (include_system=true để xem), từ chối sửa/vô hiệu hóa/đổi quyền (403 SYSTEM_ACCOUNT_LOCKED); UI có ô 'Hiện tài khoản hệ thống', nhãn và khóa nút. Hoạt động cả trước khi chạy migration 14 (nhận diện qua EAS_AI_SYSTEM_USER_ID)
- [x] 3.1 Màn hình quản trị lazy-load qua adminScreens.jsx, chỉ entry web_admin truyền vào App (AdminScreensContext). Đã build kiểm tra: bundle cổng nhân viên 0/7 dấu hiệu màn hình quản trị, cổng quản trị đủ 7/7; scripts/check_client_bundle.py chạy trong CI
- [x] 2.5 tests/test_request_catalog_v2.py (13 test): 10 nhóm/58/13/8, mọi loại có cấu hình hợp lệ và nhóm hợp lệ, số cấp = số cấp tối đa của luồng, mọi loại (kể cả 13 loại mới) tạo được route cho 8 phòng (fixture bindings ẩn danh), migration 11/12/13 khớp danh mục, có rollback, catalogV2.js đồng bộ
- [x] 2.4 Code dùng catalog_v2.json: REQUEST_TYPE_CATEGORIES = 10 nhóm; menu tạo yêu cầu, trọng số/số cấp, nhãn trường, tên loại lấy từ catalog_v2; web_client/src/catalogV2.js sinh bằng scripts/generate_catalog_js.py; IdentityAdmin 10 nhóm; PlanCatalog chế độ 'Danh mục 10 nhóm (58 loại)'
- [x] 2.3 IT_SUPPORT: migration 13 + rollback công bố release mới với executor EXECUTOR_IT (release cũ bất biến, rollback trỏ lại bản cũ)
- [x] 2.2 Migration 12 + rollback: 13 loại mới, mỗi loại 1 release PUBLISHED (form/route/SLA), bindings gộp từ release hiện có; đã chạy thử phần đọc trên DB thật và kiểm cấu hình bằng validate_config_release_payload
- [x] 2.1 Migration 11 + rollback: 10 nhóm (FINANCE, RESOURCE, FACILITY, WORK, HR, TIME, IT, LEGAL, SALES, ADMIN), trọng số/số cấp/tên theo api_core/catalog/catalog_v2.json, ngưng 8 loại trùng
- [x] 1.5 Hoàn tác AI tự duyệt trong 24h: POST /requests/<id>/ai-approval/revoke (APPROVER trong phạm vi, không phải người tạo), tạo revision mới giao người duyệt gốc, audit AI_AUTO_APPROVE_REVOKED, AI không duyệt lại; nút ẩn sau 24h; migration 10 + rollback. Sửa kèm lỗi idempotency key không phải UUID khiến AI tự duyệt luôn thất bại
- [x] 1.4 Quy định AI lưu DB (eas.ai_policy_version, migration 09 + rollback); API đẩy bản ACTIVE sang AI, AI cache trống thì kéo từ /api/v1/internal/ai-policy/active; lệnh import_ai_policy_file chuyển file cũ
- [x] 1.3 Bỏ mật khẩu mặc định Admin@123456: EAS_DEV_DEFAULT_PASSWORD không có default; fix_seed_passwords_local.py đọc EAS_SEED_PASSWORD, hash Argon2, buộc đổi khi đăng nhập
- [x] 1.2 Proxy: cổng nhân viên chặn /api/v1/admin|ops|internal (404); cổng quản trị có nginx.conf riêng, chặn internal; gateway trả 404 cho /api/v1/internal/
- [x] 1.1 Quy tắc cổng: admin thuần chỉ dùng cổng quản trị; admin có APPROVER/EXECUTOR dùng cả hai (`rolePolicy.canUsePortal`)
- [x] Mốc nền (6101da8): AI tự duyệt, giao việc xuống cấp dưới, thay người vắng, nạp quy định AI, migration 07/08/mock 004

## Đang làm
- [ ] 4.4 Ủy quyền duyệt

## Chưa làm
- [ ] 4.5 Chấm công khớp mã nhân viên
- [ ] 4.6 Dockerfile ai-service multi-stage
- [ ] 4.7 Smoke test OCR trong CI
- [ ] 5.1 Menu tự cập nhật /me
- [ ] 5.2 Test secret-policy cô lập .env
- [ ] 5.3 Cổng Redis từ biến môi trường
- [ ] 6.x Test toàn bộ, PR_DESCRIPTION.md

## Quyết định cần tôi xác nhận
- 4.2: `api_core/workflow/maintenance.py` không còn nơi gọi sau khi xóa các hàm cũ (khác `api_core/maintenance.py` đang dùng). Giữ lại vì ngoài phạm vi; có thể xóa nếu bạn đồng ý.
- 1.5: hàm DB `eas.ai_revocable` ghi cứng id tài khoản AI `00000002-0000-4000-8000-0000000000a1` (khớp migration 08 và mặc định `EAS_AI_SYSTEM_USER_ID`). Nếu đổi biến này phải sửa hàm.
- 1.5: chỉ hoàn tác được hồ sơ vòng đời A đã COMPLETED (AI chỉ tự duyệt vòng đời A). Bất kỳ APPROVER trong phạm vi phòng/loại (trừ người tạo) đều thu hồi được, không chỉ người duyệt gốc.

## Việc tôi phải làm thủ công
- Chạy trên Supabase SQL Editor theo thứ tự: `database/migrations/07_dev_restore_eas_emails.sql` (đã chạy), `08_ai_system_account.sql`, `database/mock_enterprise_sql/migrations/004_hrm_attendance.sql`, `09_ai_policy_store.sql`, `10_ai_auto_approve_revoke.sql`, `11_request_category_regroup.sql`, `12_request_types_new.sql`, `13_it_support_executor.sql`, `14_system_account_flag.sql`
- Sau migration 09, nếu container AI đang có file quy định cũ: `python manage.py import_ai_policy_file ai_service/data/active_enterprise_policy.json --operator <email POLICY_ADMIN>`
- Rollback: `database/migrations/rollback/`
