# Changelog 04/11/2026: sửa lỗi kiểm toán và schema `eas` v2

Báo cáo: [docs/KIEM_TOAN_CODE_DATA_2026-11-04.md](../docs/KIEM_TOAN_CODE_DATA_2026-11-04.md) §7.
Thiết kế: [docs/THIET_KE_SCHEMA_EAS_V2.md](../docs/THIET_KE_SCHEMA_EAS_V2.md).

## Backend

- **S1**: `administration/workflows.py`. Sửa hoặc xoá cấu hình loại yêu cầu cần vai trò `POLICY_ADMIN` cùng quyền module `requests_workflows`.
- **L1**: `workflow/auto_approval.py`. Khi AI tiếp quản bước mà DB báo xung đột, hệ thống ghi `STEP_TAKEOVER_CONFLICT` và bỏ qua, không trả lỗi 500.
- **L2**: `workflow/service.py`. Nháp và gửi đơn đọc `risk_weight`/`approval_level` từ `eas.request_type`, không đọc tệp JSON. Giá trị được chụp vào `request_revision`. `workflow_instance` không còn ghi hai cột này.
- **L3, L4**: `domain/routing.py`. Bộ định tuyến xử lý người không có quản lý, người gửi trùng người duyệt, và hai bước trùng người. Lý do điều chỉnh được ghi vào audit `REQUEST_SUBMITTED.details.route_adjustments`. Tuyến rỗng thì bị từ chối với `ROUTE_CONFIGURATION_INVALID`.
- **M1**: chưa có bảng chấm công thì phát hiện vắng mặt dùng đơn nghỉ đã duyệt (`user_leave_and_trips`).
- Nhật ký thay đổi hệ thống ghi vào `admin_event` (có chuỗi băm) qua `record_system_change`, thay cho `system_versions_changelog`. Lệnh mới `python manage.py import_legacy_changelog [--apply]` chép dữ liệu cũ.
- Trọng số rủi ro chỉ đọc từ bản chụp `request_revision`. Trước đây AI tự duyệt đọc giá trị lúc tạo nháp.
- Mobile: đăng nhập gửi `email`. Trước đây gửi `username`, API từ chối.
- Lệnh mới `python manage.py repair_workflow_consistency [--apply]`. Lệnh sửa hồ sơ không còn bước ACTIVE và đóng phần thừa của hồ sơ đã kết thúc. Mỗi hồ sơ được sửa có audit `DATA_REPAIR_*`.

## Database (bạn chạy thủ công trên Supabase SQL Editor)

- `14_security_hardening_and_schema_v2_expand.sql` (EXPAND, chạy ngay):
  - xoá policy cấp cho `anon`/`authenticated`/`public` (S2);
  - cố định `search_path` của hàm SECURITY DEFINER (S3);
  - thu hồi quyền cấu hình của vai trò nghiệp vụ (S1);
  - thay `UNIQUE(instance_id, assignee_id)` bằng trigger chỉ áp cho người thật (L1);
  - thêm 4 bảng `privacy_case_approval`, `sla_escalation_policy`, `work_handover`, `business_holiday`;
  - thêm chỉ mục khoá ngoại.
- `15_schema_v2_consolidate.sql`: gộp bảng trùng, **không xoá dữ liệu**.
  - Bỏ 9 view bí danh (`roles`, `requests`, `departments`…).
  - `workflow_categories`, `system_versions_changelog`, `work_handover` và schema `eas_deprecated` dời sang schema `eas_archive`.
  - `work_handover` gộp vào `approval_delegation`.
  - Bỏ 7 cột trùng; giá trị lưu ở `eas_archive.dropped_column_value`.
  - Bỏ trigger `trg_after_mock_api_toggle` (ghi nhật ký đúp).
- Cả hai migration đều có rollback trong `database/migrations/rollback/`.
- `data_fixes/2026-11-04_top_level_approver_binding.sql`: khai báo người duyệt thay cho lãnh đạo cao nhất.

## Kiểm thử

- Test mới: `test_audit_fixes_2026_11_04.py`, `test_repair_workflow_consistency.py`, `test_schema_v2_consolidation.py`, cùng 1 test vắng mặt theo đơn nghỉ.
- `manage.py test api_core`: 315/315 đạt.
- `tests/run_tests.py`: 153 ca đạt, 1 bỏ qua.
- `ruff`: sạch.
- Bản sao local (`eas-pg-e2e`) đã chạy:
  - chuỗi 14 → rollback → 14 → 15 → rollback → 15;
  - kiểm hành vi trigger;
  - lệnh sửa dữ liệu (4 hồ sơ; quét lại báo 0);
  - smoke gửi đơn cho nhân viên và giám đốc, trước và sau khi khai báo người duyệt thay.

## Kiểm tra sau migration 15 trên live (04/11/2026)

- Chỉ đọc trên live:
  - biên dịch (`PREPARE`) 382 câu SQL tĩnh và 21 câu SQL động của backend bằng role `eas_api`;
  - biên dịch 51 câu SQL của worker bằng role `eas_worker_login`;
  - gọi 154 endpoint GET với 5 vai trò, mỗi lần gọi đều rollback.
- Kết quả: không lỗi bảng hoặc cột nào sau migration 15.
- Phát hiện lỗi quyền của worker:
  - `_table_readable` gọi `to_regclass('mock_hr.attendance')`. Với role không có quyền `USAGE` trên `mock_hr`, lệnh này báo lỗi thay vì trả NULL, làm hỏng cả giao dịch khi worker kích hoạt bước kế tiếp. Đã sửa: kiểm tra quyền schema trước.
  - Worker không đọc được `approval_delegation`, nên uỷ quyền bị bỏ qua. Migration `16_worker_read_delegation.sql` cấp quyền SELECT.
- `manage.py test api_core`: 316/316.

## Chấm công ảo, giờ làm việc, mượn tài nguyên (04/11/2026)

- Bỏ hoàn toàn việc đọc `mock_hr.attendance`. Vắng mặt chỉ tính khi có đơn nghỉ hoặc công tác đã duyệt (`user_leave_and_trips`).
- `16_worker_delegation_and_working_hours.sql`:
  - cho worker đọc uỷ quyền;
  - hàm `get_user_working_status` theo giờ làm 08:00–12:00, 13:30–17:30 (T2–T6), thêm trạng thái `NGOAI_GIO` (nghỉ trưa / ngoài giờ).
  - UI hiển thị trạng thái mới.
- (Đã thay bằng bản dưới) `17_resource_allocation.sql` ghi thẳng vào mock — huỷ, chưa chạy live:
  - đặt phòng, mượn xe và mượn thiết bị gắn với dữ liệu mock;
  - ai được duyệt trước thì được cấp trước, hết hạn thì worker tự trả lại;
  - Ban Giám đốc được ưu tiên: thu hồi phần đã cấp cho nhân viên, chuyển đơn đó sang REJECTED và thông báo.
- Endpoint `GET /api/v1/mock/borrow-options` trả tên phòng, xe và nhóm thiết bị cho biểu mẫu.
- Kiểm thử:
  - `api_core` 325/325, `run_tests` 153, web 64/64;
  - kịch bản đầu-cuối trên bản sao local đạt: được duyệt trước thì được trước; gửi trùng khung giờ bị 409; vượt sức chứa bị chặn; BGĐ thu hồi phòng và laptop; worker trả lại khi hết hạn.

## Hệ thống ngoài chỉ qua API; phân loại yêu cầu theo nhóm (04/11/2026)

Tài liệu được viết trước: `docs/TICH_HOP_HE_THONG_NGOAI.md`, `docs/PHAN_LOAI_YEU_CAU.md`. Code được sửa theo tài liệu.

- **Mock Systems API**: dịch vụ riêng (`EAS_SERVICE=mock`, compose `mock_systems`) với role DB `eas_mock`. Mọi API ghi đều chống trùng theo `source_request_id`. Nhóm API:
  - HRM: phòng ban, nhân viên, quỹ phép, ghi ngày nghỉ;
  - tài sản / toà nhà: danh mục, tình trạng trống, giữ chỗ, huỷ, trả;
  - ITSM: ứng dụng, vai trò, cấp quyền;
  - ERP: loại chi phí, ngân sách, cam kết;
  - danh mục CRM, mua sắm, công tác.
- **EAS** gọi qua `api_core/integrations/client.py`. Thay đổi:
  - bỏ mọi SQL vào `mock_*`, bỏ route `/api/v1/mock/*`;
  - thêm `/api/v1/integrations/options` cho biểu mẫu.
- **Luật nghiệp vụ** (`integrations/requests.py`):
  - mã phải có trong hệ thống ngoài: phòng, xe, nhóm thiết bị, ứng dụng, vai trò, loại chi phí;
  - kiểm tra quỹ phép HRM, ngân sách ERP, hạn mức chi theo ngày;
  - duyệt xong thì ghi ngày nghỉ và cam kết ngân sách; đơn cấp quyền hoàn tất thì cấp quyền trong ITSM.
- **Mượn tài nguyên** viết lại theo API. Worker trả lại khi hết hạn và huỷ phần giữ chỗ "mồ côi" (sau 10 phút).
- **AI**: bỏ bản chụp JSON `ai_service/data/mock` (ngân sách trong đó sai 100 lần); AI tra quỹ phép, phòng, ngân sách qua API. Bỏ tra phòng cứng "PH-01".
- **Dữ liệu mock**:
  - `005_align_with_eas.sql`: 136 nhân viên HRM khớp tài khoản EAS, 8 phòng ban khớp mã, quỹ phép 2026;
  - xoá `004_hrm_attendance.sql`;
  - `sync_employee_codes` đọc HRM qua API.
- **Phân loại**:
  - 12 nhóm theo bản chất, 61 loại nhỏ (`request_group`, `request_menu_item`), lựa chọn đặt sẵn Đi muộn / Về sớm / Quên chấm công / Nghỉ có lương / Nghỉ không lương;
  - giao diện chọn nhóm trước, rồi loại.
- **Health**: kiểm Mock API phản hồi và **EAS không có quyền** vào `mock_*`.
- **Kiểm thử**: `api_core` 338/338, `run_tests` 153, web 64/64; e2e hai tiến trình trên bản sao đạt (tài liệu tích hợp §6).

## Rà soát bảo mật 05/11/2026

- **Quét tự động:** quét bí mật trong repo PASS; `pip-audit` API 0 lỗ hổng; `npm audit` hai web 0 lỗ hổng.
- **S4, S5:** giới hạn tần suất và header bảo mật cho cả hai cổng web, đã kiểm bằng `nginx -t`.
- **S6:** gateway không mở AI và mock ra ngoài.
- **S7:** nâng PaddleOCR lên 3.x (`paddlepaddle 3.3.1`, `paddleocr 3.7.0`, `protobuf 5.29.6`, bỏ `imgaug`); `pip-audit` sạch; OCR kiểm thật trong container. Mã `ai_service/routers/ocr.py` đổi sang API `predict()`; model lưu ở `~/.paddlex` (volume `ai_ocr_models`).
- **S8a:** OCR URL chống DNS rebinding và giới hạn kích thước.
- **S8b:** thoát ký tự `LIKE` trong tìm kiếm quản trị.
- **S8c:** ghim phiên bản thư viện mobile.
- **S8d:** gỡ thư viện Supabase khỏi trình duyệt.
- **S8e:** gỡ Elasticsearch.
- **S8f:** worker dọn `idempotency_record`.
- **Code mới:** mã phòng / xe / thiết bị được mã hoá khi ghép vào URL gọi Mock Systems API.
- **Test:** `api_core` 340/340, `run_tests` 153, web 64/64, build hai web đạt.
