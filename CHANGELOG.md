# Lịch sử thay đổi

Gộp từ thư mục `changelogs/` và `docs/CHANGELOG_ENTERPRISE_STANDARDS.md` (16/11/2026), mục mới nhất ở trên. Thay đổi sau ngày 05/11/2026 xem mô tả các Pull Request và `PROGRESS.md`.

## Kiểm thử E2E trên giao diện thật (05/11/2026)

### Môi trường

Kiểm thử chạy trên bản sao local `m17test` (container `eas-pg-e2e`, cổng `127.0.0.1:55432`), không chạm Supabase live. Stack gồm:

- API Django: cổng 8000;
- Mock Systems API: cổng 8100;
- worker;
- AI service: cổng 8001;
- `web_client` (Vite): cổng 5173;
- `web_admin` (Vite): cổng 8081.

Mọi thao tác chạy bằng Playwright, đăng nhập bằng phiên thật của từng vai trò.

### Kết quả

| Nhóm | Kết quả |
|---|---|
| Hai cổng cùng template | Đạt. Cùng khung (sidebar, topbar, user pill), cùng token `--ds-*`, cùng font, cùng kiểu menu |
| RBAC | Đạt. Menu khác nhau theo vai trò. Nhân viên không đăng nhập được cổng quản trị. API trả 403 cho nhân viên ở các route `admin/*` và `ops/*`. Nhân viên không đọc được hồ sơ của người khác (404) |
| Tạo yêu cầu qua giao diện | Đạt. Menu có 12 nhóm và 61 biểu mẫu. Biểu mẫu WFH hiện đúng nhãn. Có hộp thoại xác nhận trước khi gửi |
| Quy trình C xen kẽ | Đạt. Chuỗi: yêu cầu bổ sung → gửi lại (2 phiên bản) → duyệt cấp 1 → duyệt cấp 2 → nhận việc → nộp kết quả (bắt buộc minh chứng) → yêu cầu làm lại → nhận lại việc → nộp lần 2 → nghiệm thu → hoàn tất. Chuỗi hash audit kiểm tra PASS (14 sự kiện) |
| Tranh chấp đồng thời | Đạt. Rút đơn và duyệt cùng lúc: chỉ 1 bên thắng. Duyệt 2 lần cùng `Idempotency-Key`: chỉ ghi 1 quyết định |
| Mượn tài nguyên | Đạt. Đơn được duyệt trước thắng; đơn sau tự bị từ chối, kèm thông báo lý do. Gửi khi phòng đã có người giữ: 409 `RESOURCE_UNAVAILABLE`. BGĐ được ưu tiên: người đang giữ phòng bị thu hồi |
| AI | Đạt. Trợ lý trong biểu mẫu trả kết quả phân loại và điểm rủi ro. Đơn WFH (rủi ro 1) được AI tự duyệt (`ai.system`) |
| Quy định → AI học lại | Đạt. Admin thêm quy định "WFH phải duyệt thủ công" → AI học 4 bước (SYNCING → LEARNING → APPLYING → COMPLETED), khoá cổng nhân viên trong lúc học, gửi thông báo. Đơn WFH mới chờ quản lý duyệt thủ công. Gỡ quy định → AI học lại → WFH lại được tự duyệt |

### Lỗi phát hiện và đã sửa

1. **Danh sách và chi tiết hồ sơ trả 500.**
   - Nguyên nhân: `api_core/workflow/views.py` đọc `r.amount_vnd`, nhưng bảng `eas.request` không có cột này.
   - Sửa: đổi thành `COALESCE(v.amount_vnd, r.draft_amount_vnd)`.
2. **101 trường biểu mẫu (35 loại) hiện cùng nhãn "Thông tin bổ sung".**
   - Nguyên nhân: `resolve_field_labels` dùng chuỗi `a or b`, nên mục trong `catalog_v2` (không có `field_labels`) che mất nhãn ở `plan_types.json`.
   - Sửa: gộp nhãn từ mọi nguồn; thêm nhãn cho `leave_kind`.
   - Test: `FieldLabelTests`.
3. **Trợ lý AI tự đổi loại biểu mẫu và xoá dữ liệu đã nhập.**
   - Biểu hiện: bấm "Gợi ý & đánh giá rủi ro" thì biểu mẫu WFH bị đổi sang ACCESS.
   - Sửa: AI chỉ gợi ý; người dùng bấm "Chuyển sang biểu mẫu này" mới đổi. Điểm rủi ro nay dùng quy trình và trọng số thật của loại yêu cầu, không còn gán cứng.
   - Test: thêm vào `e2e/client-refactor.test.mjs`.
4. **Modal quản trị không có CSS.**
   - Biểu hiện: ở các trang Quy định, Quản lý API và Phiên bản hệ thống, modal hiện trơn giữa trang.
   - Nguyên nhân: lớp `eas-modal-*` chưa từng có CSS.
   - Sửa: thêm CSS vào `design-system.css`, dùng token sẵn có.
5. **Tải lại trang trong lúc AI học báo "Không thể kết nối hệ thống".**
   - Sửa: mã `SYSTEM_UNDER_MAINTENANCE` đưa người dùng về trang đăng nhập; trang này đã có thanh tiến độ học.

### Điểm cần chủ dự án xử lý (chưa sửa)

- **Lãnh đạo cao nhất không gửi được loại chỉ có bước `DIRECT_MANAGER`** (ví dụ `ROOM_BOOKING`, `WFH_REQ`).
  - Hệ thống trả 409 `ROUTE_CONFIGURATION_INVALID`. Đây là hành vi đúng theo thiết kế (`docs/THIET_KE_SCHEMA_EAS_V2.md` §5.4).
  - Cần chạy `database/data_fixes/2026-11-04_top_level_approver_binding.sql` trên live để khai báo người duyệt thay.
- **Cổng quản trị chỉ cho đúng email `admin@eas.com`** (`api_core/authn/views.py`, hàm `login`).
  - Người có vai trò OPS_ADMIN, POLICY_ADMIN hoặc AUDITOR khác không vào được cổng quản trị. Ngược lại, admin không vào được cổng nhân viên.
  - API vẫn kiểm vai trò, nên đây không phải lỗ hổng. Tuy vậy, quyền nên dựa trên vai trò thay vì email.
- **Không ai giữ vai trò AUDITOR**, nên không ai kiểm được chuỗi audit từ giao diện. Việc kiểm phải chạy bằng lệnh `manage.py audit_verify`.
- **Lỗi trải nghiệm nhỏ:**
  - mở lại đúng hồ sơ đang xem thì trang không tải lại dữ liệu;
  - đánh dấu thông báo đã đọc vẫn bật toast "Thao tác thành công";
  - menu hiện chữ thô `khi days_gt 2`;
  - gợi ý "đính kèm báo giá / hóa đơn" xuất hiện ở mọi biểu mẫu.

### Ghi chú môi trường

- Bản sao `m17test` thiếu quyền `USAGE`/bảng cho `eas_worker`. Đã cấp lại trên bản sao theo đúng `00_eas_supabase_schema.sql` và các migration.
- Mật khẩu `admin@eas.com` trên bản sao bị đổi trong khoảng 09:53–10:32. Không xác định được nguồn; đã đặt lại, chỉ trên bản sao.

## Changelog 04/11/2026: sửa lỗi kiểm toán và schema `eas` v2

Báo cáo: [docs/KIEM_TOAN_CODE_DATA_2026-11-04.md](docs/KIEM_TOAN_CODE_DATA_2026-11-04.md) §7.
Thiết kế: [docs/THIET_KE_SCHEMA_EAS_V2.md](docs/THIET_KE_SCHEMA_EAS_V2.md).

### Backend

- **S1**: `administration/workflows.py`. Sửa hoặc xoá cấu hình loại yêu cầu cần vai trò `POLICY_ADMIN` cùng quyền module `requests_workflows`.
- **L1**: `workflow/auto_approval.py`. Khi AI tiếp quản bước mà DB báo xung đột, hệ thống ghi `STEP_TAKEOVER_CONFLICT` và bỏ qua, không trả lỗi 500.
- **L2**: `workflow/service.py`. Nháp và gửi đơn đọc `risk_weight`/`approval_level` từ `eas.request_type`, không đọc tệp JSON. Giá trị được chụp vào `request_revision`. `workflow_instance` không còn ghi hai cột này.
- **L3, L4**: `domain/routing.py`. Bộ định tuyến xử lý người không có quản lý, người gửi trùng người duyệt, và hai bước trùng người. Lý do điều chỉnh được ghi vào audit `REQUEST_SUBMITTED.details.route_adjustments`. Tuyến rỗng thì bị từ chối với `ROUTE_CONFIGURATION_INVALID`.
- **M1**: chưa có bảng chấm công thì phát hiện vắng mặt dùng đơn nghỉ đã duyệt (`user_leave_and_trips`).
- Nhật ký thay đổi hệ thống ghi vào `admin_event` (có chuỗi băm) qua `record_system_change`, thay cho `system_versions_changelog`. Lệnh mới `python manage.py import_legacy_changelog [--apply]` chép dữ liệu cũ.
- Trọng số rủi ro chỉ đọc từ bản chụp `request_revision`. Trước đây AI tự duyệt đọc giá trị lúc tạo nháp.
- Mobile: đăng nhập gửi `email`. Trước đây gửi `username`, API từ chối.
- Lệnh mới `python manage.py repair_workflow_consistency [--apply]`. Lệnh sửa hồ sơ không còn bước ACTIVE và đóng phần thừa của hồ sơ đã kết thúc. Mỗi hồ sơ được sửa có audit `DATA_REPAIR_*`.

### Database (bạn chạy thủ công trên Supabase SQL Editor)

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

### Kiểm thử

- Test mới: `test_audit_fixes_2026_11_04.py`, `test_repair_workflow_consistency.py`, `test_schema_v2_consolidation.py`, cùng 1 test vắng mặt theo đơn nghỉ.
- `manage.py test api_core`: 315/315 đạt.
- `tests/run_tests.py`: 153 ca đạt, 1 bỏ qua.
- `ruff`: sạch.
- Bản sao local (`eas-pg-e2e`) đã chạy:
  - chuỗi 14 → rollback → 14 → 15 → rollback → 15;
  - kiểm hành vi trigger;
  - lệnh sửa dữ liệu (4 hồ sơ; quét lại báo 0);
  - smoke gửi đơn cho nhân viên và giám đốc, trước và sau khi khai báo người duyệt thay.

### Kiểm tra sau migration 15 trên live (04/11/2026)

- Chỉ đọc trên live:
  - biên dịch (`PREPARE`) 382 câu SQL tĩnh và 21 câu SQL động của backend bằng role `eas_api`;
  - biên dịch 51 câu SQL của worker bằng role `eas_worker_login`;
  - gọi 154 endpoint GET với 5 vai trò, mỗi lần gọi đều rollback.
- Kết quả: không lỗi bảng hoặc cột nào sau migration 15.
- Phát hiện lỗi quyền của worker:
  - `_table_readable` gọi `to_regclass('mock_hr.attendance')`. Với role không có quyền `USAGE` trên `mock_hr`, lệnh này báo lỗi thay vì trả NULL, làm hỏng cả giao dịch khi worker kích hoạt bước kế tiếp. Đã sửa: kiểm tra quyền schema trước.
  - Worker không đọc được `approval_delegation`, nên uỷ quyền bị bỏ qua. Migration `16_worker_read_delegation.sql` cấp quyền SELECT.
- `manage.py test api_core`: 316/316.

### Chấm công ảo, giờ làm việc, mượn tài nguyên (04/11/2026)

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

### Hệ thống ngoài chỉ qua API; phân loại yêu cầu theo nhóm (04/11/2026)

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

### Rà soát bảo mật 05/11/2026

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

## Changelog 03/11/2026 — Dọn bảng trùng chức năng và tách tài khoản quản trị

Kế hoạch: [EAS-PLAN-2026-11-03-01](plans/active/2026-11-03_db_cleanup_admin_split.md)

### Database (migration 11, chạy thủ công trên Supabase SQL Editor)

- Chuyển 7 bảng trùng chức năng (`users`, `departments`, `requests`, `roles`, `role_permissions`, `request_templates`, `workflow_categories`), 2 view và 4 function chỉ phục vụ chúng sang schema cách ly `eas_deprecated`. Dữ liệu giữ nguyên; xoá hẳn sau 14 ngày.
- Quyền module gắn với danh tính lõi: bảng mới `eas.role_module_permission` (theo `eas.role`); `user_permissions`, `user_leave_and_trips` trỏ khóa ngoại sang `eas.app_user`; viết lại `eas.get_effective_user_permissions`.
- Tách quản trị: cột `app_user.account_type` (`EMPLOYEE` | `ADMIN`), bảng `eas.admin_account`. **Chỉ `admin@eas.com` là tài khoản quản trị**; mọi tài khoản khác bị thu hồi OPS_ADMIN/POLICY_ADMIN/AUDITOR. Tài khoản `<tên>+admin@eas.com` do bản đầu tạo bị thu hồi vai trò và khoá.
- Trigger `b_account_role_type`, `b_account_type_change` chặn trộn vai trò quản trị và nghiệp vụ trên cùng tài khoản (SQLSTATE 23514).
- Bảo mật: thu hồi mọi quyền của `anon`/`authenticated` trên schema `eas` và default privilege tương ứng; mọi object trong `eas` thuộc `eas_migration`.

### Backend

- `api_core/authn/views.py`: `/me` lấy quyền module bằng id `app_user` (bỏ tra cứu `eas.users`); nếu DB chưa cấp quyền xem nào hoặc lỗi DB thì dùng ma trận theo vai trò. Chỉ bắt `DatabaseError`.
- Test mới: `api_core/tests/test_actor_permissions.py` (3 test). Toàn bộ 426 test PASS.

### Cách chạy

1. Supabase Dashboard → Database → Backups: tạo bản sao lưu.
2. SQL Editor → dán toàn bộ `database/migrations/11_cleanup_duplicates_and_admin_split.sql` → Run. Kết quả cuối là danh sách tài khoản quản trị.
3. Quay lại nếu cần: `database/migrations/rollback/11_cleanup_duplicates_and_admin_split_rollback.sql`.
4. Từ 17/11/2026: `database/migrations/scheduled/2026-11-17_drop_eas_deprecated_after_11.sql`.

### Data fix (sau migration 11)

- `database/data_fixes/2026-11-03_delete_plus_admin_accounts.sql`: xoá hẳn 4 tài khoản `hung.nguyen`/`thang.ngo`/`tri.tran`/`tuan.pham` `+admin@eas.com` (đã khoá, chỉ có dòng `role_membership` đã thu hồi và `admin_account`; không có request/audit). Script dừng nếu phát hiện tham chiếu khác. Sau khi chạy, `eas.admin_account` chỉ còn `admin@eas.com`.

- `database/data_fixes/2026-11-03_org_structure_and_passwords.sql`: bổ sung cơ cấu tổ chức (BOD: giám đốc `hung.nguyen`, phó giám đốc `ngoc.tran`; 7 phòng ban x 1 trưởng phòng + 3 trưởng nhóm + 15 nhân viên), giữ người đã có và chỉ tạo phần thiếu; trưởng nhóm có APPROVER phạm vi phòng (luồng DIRECT_MANAGER), nhân viên mới có EXECUTOR phạm vi phòng. Đặt mật khẩu theo yêu cầu chủ dự án cho admin@eas.com và mọi tài khoản còn lại (Argon2, đăng xuất phiên cũ). Kiểm thử trên bản sao live: 137 tài khoản hoạt động, chạy lại không tạo thêm.

## Changelog 03/11/2026 — Cổng nhân viên Phase 1–3: giao diện theo quyền module do admin cấp

Kế hoạch: [EAS-PLAN-2026-11-03-03](plans/active/2026-11-03_client_phase_1_3_module_permissions.md) · Tài liệu: [docs/CHUC_NANG_UI_VA_PHAN_QUYEN.md](docs/CHUC_NANG_UI_VA_PHAN_QUYEN.md) mục 14

### Backend
- `api_core/authn/module_access.py`: `can()`, `require_module()`; 4 module hệ thống không bao giờ cho nhân viên.
- `api_core/administration/workspace.py`: `/api/v1/workspace/*` (analytics theo phạm vi, sơ đồ tổ chức, phòng ban, người dùng, quy định, danh mục mẫu kèm trạng thái tích hợp, bảng 5 giai đoạn, cấu hình mẫu) dùng lại logic quản trị; ghi qua `service.mutate(authorizer=...)`, có nhật ký.
- `users` được admin cấp cho nhân viên; nhân viên không gán được vai trò Người phê duyệt; khoá/mở tài khoản cần quyền Xoá.
- `/auth/me`: mã NV, chức danh, phòng ban, trạng thái làm việc (cùng một truy vấn).
- `api_core/workflow/leave_sync.py`: duyệt xong nghỉ phép/công tác/đi muộn/về sớm → `user_leave_and_trips`.
- Nhãn tiếng Việt cho mọi mã người duyệt trong luồng.

### Frontend
- Menu nhân viên theo 5 module (hiện khi có quyền Xem), header trạng thái làm việc + chức danh + phòng ban, khung tiến trình AI ở màn đăng nhập, đếm ngược 3 giây, quyền tự làm mới 15 giây.
- Trang "Yêu cầu & Quy trình" (`ClientRequestsHub.jsx`); Tổng quan, Sơ đồ tổ chức, Người dùng, Quy định dùng chung màn hình admin qua `apiBase.js`.
- Nút theo quyền ở Quy định, Cấu hình mẫu; `ClientPermissionGuard`; sửa lỗi nhân viên không thấy nút Sửa/Huỷ hồ sơ của mình.

### Kiểm thử
- 5 kịch bản liên thông trên trình duyệt (bản sao live): 21/21. Luồng nghỉ phép → "Nghỉ làm": đạt. Live chỉ đọc: 48/48.
- Django 448 OK, `npm test` 64, ESLint/ruff sạch, build 2 cổng, kiểm tra bundle đạt.

## Changelog 03/11/2026 — AI học quy định có kiểm chứng, thông báo cập nhật, khắc phục phase 0–7

Kế hoạch: [EAS-PLAN-2026-11-03-02](plans/completed/2026-11-03_ai_learning_and_admin_remediation.md)

### Database (migration 12, chạy thủ công trên Supabase SQL Editor)

- `eas.ai_learning_job` (QUEUED → RUNNING → APPLIED | FAILED, có lease, tối đa 3 lần thử). Khoá đăng nhập suy ra từ job đang mở, không còn cờ boolean có thể kẹt.
- `eas.system_announcement` + `eas.announcement_receipt`: thông báo "Hệ thống đã cập nhật" kèm thay đổi và hướng dẫn thao tác.
- `ai_system_state`: thêm `applied_policy`, `applied_snapshot`, `applied_at`, `applied_job_id`; chuẩn hoá bộ đếm phiên bản theo phiên bản lớn nhất thực có (live đang có target "2.1" nhưng bộ đếm 1.0 → trước đây lần sửa tiếp theo bị lùi số).
- Trigger `fn_after_regulation_versioning` chỉ ghi lịch sử và phiên bản; bỏ tự bật khoá.
- Gỡ khoá đang kẹt trên live (APPLYING 75%) bằng một job học lại.
- Rollback: `database/migrations/rollback/12_ai_learning_jobs_and_announcements_rollback.sql`.

### Backend

- `api_core/workflow/ai_learning.py`: trích luật tất định từ văn bản quy định tiếng Việt (ngưỡng tiền, số ngày, "bắt buộc duyệt thủ công", phạm vi loại yêu cầu), đẩy sang ai_service, đọc lại xác nhận phiên bản và chạy ca kiểm thử vàng; chỉ khi AI áp dụng đúng mới mở khoá và gửi thông báo. AI lỗi → thử lại 15s/45s/120s → giữ luật cũ, mở khoá, chỉ báo quản trị viên.
- API mới: `GET /api/v1/announcements`, `POST /api/v1/announcements/<id>/read`, `POST /api/v1/admin/ai-engine/test` (hỏi AI thật với loại yêu cầu/số tiền/số ngày).
- Module quản trị viết lại trên bảng lõi (`org_users_rbac.py`, `workflows.py`, `analytics.py`): tạo/sửa/khoá người dùng qua kiểm tra chung, mật khẩu Argon2, idempotency, audit `admin_event`; AUDITOR chỉ đọc; analytics bỏ số liệu giả.
- Circuit breaker API tích hợp: chặn tạo/gửi yêu cầu phía server (`409 INTEGRATION_UNAVAILABLE`), ánh xạ theo nhóm catalog v2 thật (trước đây 4/8 API không khoá gì), bật/tắt có transaction + audit.
- Sửa lỗi có sẵn: tạo nháp không tiêu đề → 500 (NULL vào cột NOT NULL); `service.SELECT_BY_ID_SQL` đọc cột không tồn tại/sai thứ tự (500 khi sửa phòng ban, loại yêu cầu, vai trò).
- `supabase/migrations/20261103_admin_full_upgrade.sql`: bỏ `GRANT ALL` cho `anon`/`authenticated` (live đã sạch).

### AI service (không đổi chi phí)

- Endpoint CPU/mạng chạy trong threadpool thay vì chặn event loop (`classify`, `risk`, `summarize` — Gemini trước đây chặn toàn service vài giây mỗi lần gọi).
- Nạp sẵn model NLP + 4 model rủi ro khi khởi động.
- Cache tóm tắt Gemini theo nội dung (LRU 512): yêu cầu giống hệt không gọi Gemini lần nữa, giảm chi phí.

### Frontend

- Hộp "Hệ thống đã cập nhật quy định vX" sau đăng nhập (thay đổi + hướng dẫn), xem lại ở Thông báo.
- Overlay khoá chỉ theo khoá thật (trước đây trạng thái ERROR khoá nhân viên vĩnh viễn).
- Khôi phục menu bị mất sau redesign: Theo dõi vận hành, Thông báo SLA, Báo cáo phòng ban, Nhật ký kiểm toán; thêm Danh tính & phạm vi quyền, Phiên bản cấu hình quy trình, Luật AI thủ công. Nhân viên có lại "Quy trình AI", trưởng phòng có lại "Nhân viên phòng ban".
- Mobile: sidebar không còn che toàn màn hình (không mở/đóng được menu); dashboard admin không tràn ngang ở 1024px.
- Trang Quản trị AI gọi AI thật, hiện lịch sử các lượt học. ESLint 89 → 0 lỗi.

### Kiểm thử

- Django 444 OK; `tests/run_tests.py` 153 OK; `npm test` 64 OK; Playwright portal 15/15; ruff, ESLint, secret, docs, env gate PASS; build client + admin OK.
- E2E API phase 0–7 trên stack cục bộ (Postgres bản sao live + Django + ai_service): 45/45 (`%TEMP%/claude/e2e_all.py`).
- Trình duyệt thật: `web_client/e2e/live_stack_walk.mjs` (mọi trang 2 cổng, không lỗi 5xx/console ngoài `/health/ready` do bản sao thiếu schema `mock_hr`), `web_client/e2e/live_maintenance_lock.mjs` (khoá → tự đăng xuất → chặn đăng nhập → AI lỗi → mở khoá sau 62s, nhân viên không thấy cảnh báo lỗi).
- Có từ trước phase 0–5, chưa sửa: `e2e/ui.spec.js` (17/18 fail) và `e2e/smoke.spec.js` (1/3 fail) đã lỗi thời từ commit `86172e9`.

### Chạy trên live (thứ tự)

1. Supabase → Backups: tạo bản sao lưu.
2. SQL Editor lần lượt: `08_ai_auto_approval.sql` → `09_request_catalog_v2.sql` → `10_approval_delegation_and_employee_code.sql` → `12_ai_learning_jobs_and_announcements.sql`.
3. Khởi động ai_service, backend và worker (`start_worker_local.cmd`); job học lại sẽ chạy và mở khoá.

### Bổ sung sau khi chạy 08 → 12 trên live

- Live đã chạy 08, 09, 10, 12: job học lại APPLIED (v1.0), mở khoá; test API trên live 48/48, đi qua mọi trang 2 cổng không lỗi.
- Migration 13 `database/migrations/13_lock_client_roles_and_batch1_objects.sql` (+ rollback): script batch1 chạy trực tiếp trên live đã cấp lại `USAGE` schema `eas` và default privilege cho `anon`/`authenticated`, tạo `eas.workflow_categories` không RLS, 9 view và 3 function thuộc `postgres`. Bản 13 chuyển mọi object về `eas_migration`, view chạy `security_invoker`, bật RLS + policy backend, thu hồi quyền và default privilege của `anon`/`authenticated`, kiểm tra sau cùng rồi mới commit. Đã kiểm thử trên bản sao: chạy 2 lần, rollback, chạy lại đều sạch; bảng tạo sau đó `anon` không đọc được.
- Frontend: đăng nhập không còn gọi RPC Supabase từ trình duyệt (backend đã chặn sai cổng); `web_client/src/supabase.js` bỏ key ghi cứng và không được import; `@supabase/supabase-js` ghim `2.118.0`. Cổng nhân viên chặn lại mọi tài khoản có vai trò quản trị (không chỉ `admin@eas.com`).
- Test: `e2e/batch1_audit.test.mjs` đổi tên `batch1_audit.spec.js` (là test Playwright, `npm test` chạy nhầm); `portal.spec.js` theo menu admin 9 mục và quy tắc chỉ `admin@eas.com` vào cổng admin. Playwright portal 15/15, batch1 4/4, `npm test` 64, Django 444 OK.

### Kiểm tra tách quyền quản trị (live)

- DB live: chỉ `admin@eas.com` có OPS_ADMIN/POLICY_ADMIN, `account_type = ADMIN` và dòng `eas.admin_account`; vai trò nhân viên không có quyền module quản trị; không có quyền riêng.
- Kiểm thử từng tài khoản trên live (`%TEMP%/claude/e2e_admin_isolation.py`): admin vào cổng admin, bị từ chối ở cổng nhân viên, không gửi được yêu cầu nghiệp vụ; 136/136 tài khoản còn lại vào được cổng nhân viên, bị từ chối ở cổng admin, `/auth/me` không có vai trò/module quản trị, 11 API quản trị (đọc) và 2 API ghi đều 403.
- Chặn thêm: không thể cấp module chỉ-dành-cho-admin (`users`, `permissions`, `ai_engine`, `api_management`, `system_versions`) cho vai trò nhân viên hay quyền riêng của nhân viên (`422 ADMIN_MODULE_NOT_GRANTABLE`); trang Phân quyền khoá các công tắc đó.

## Nhật ký phát triển trước đây (chuyển từ README.md ngày 05/11/2026)

Nội dung gốc, giữ nguyên để tra cứu.

### 02/11/2026 — Hệ thống thiết kế thống nhất cho hai cổng web

**Hệ thống thiết kế**

- `web_client/src/design-system.css` được nạp **sau cùng** ở cả hai cổng: biến màu (xanh navy chủ đạo; xanh lá/cam/đỏ/xám theo ngữ nghĩa), khoảng cách bội số 8px, bo góc 8–12px, chuyển động 150–250ms, hỗ trợ `prefers-reduced-motion`, viền focus rõ ràng. Các file CSS cũ vẫn giữ để không vỡ trang chưa chuyển hết; quy tắc mới ghi đè có chủ đích.
- Thành phần dùng chung trong `components/design.jsx`: `PageHeader`, `PageTabs`, `StatCard`, `StatusBadge`, `EmptyState`, `Skeleton`, `ConfirmDialog`, `WorkflowTimeline`, `SearchInput`. `ClientPageHeader`/`ClientStatCard` cũ trỏ về cùng thành phần. Trạng thái tải dùng skeleton thay vì vòng xoay.
- Khung ứng dụng: header dính (breadcrumb, tìm kiếm hồ sơ theo **mã hoặc tiêu đề** trong đúng phạm vi quyền, chuông thông báo có số chưa đọc và danh sách 6 thông báo mới — bấm để mở hồ sơ và đánh dấu đã đọc), sidebar theo nhóm có thể thu gọn nhóm và thu gọn cả thanh (ghi nhớ trên trình duyệt), ngăn kéo trên di động có nút đóng và phím Esc. Trang quản trị (người dùng, tổ chức, vận hành…) được tách gói tải riêng, nhân viên không phải tải.

**Điều hướng**

| Cổng nhân viên | Cổng quản trị |
|---|---|
| Không gian cá nhân: Tổng quan, Yêu cầu của tôi | Tổng quan: Tổng quan hệ thống, Theo dõi vận hành |
| Công việc được giao: Chờ phê duyệt, Công việc thực hiện, Chờ nghiệm thu | Người dùng & tổ chức: Quản lý người dùng, Phòng ban, Ma trận phân quyền, Sơ đồ tổ chức |
| Quản lý phòng ban (APPROVER/AUDITOR): Tổng quan phòng ban, Nhân viên phòng ban | Cấu hình nghiệp vụ: Danh mục yêu cầu, Quy chế & quy trình (phiên bản quy chế, 18 mẫu, sơ đồ luồng), SLA & thông báo |
| Tổ chức & công cụ: Sơ đồ tổ chức, Sơ đồ luồng, Quy trình AI | Giám sát & kiểm toán: Quy trình AI, Nhật ký kiểm toán (hồ sơ + quản trị), Báo cáo phòng ban |
| Tài khoản: Tài khoản cá nhân | Hệ thống: Cấu hình hệ thống (bảo trì, API & tích hợp) |

Cổng quản trị không có chức năng tạo yêu cầu. Theo UC05, quản trị vận hành chỉ xem **thông tin điều phối**: tìm kiếm và thông báo dẫn tới bảng vận hành; chỉ kiểm toán viên mở được chi tiết hồ sơ.

**Màn hình**

- **Chi tiết hồ sơ:** khối tình trạng (giai đoạn, người đang xử lý, bước kế tiếp, hạn/quá hạn, lý do quyết định) và các tab Thông tin · Tiến trình xử lý (dòng thời gian) · Người phê duyệt · Tệp đính kèm · Đánh giá AI · Lịch sử hoạt động · Sơ đồ luồng. Nhật ký hoạt động hiển thị bằng tiếng Việt, không còn bảng kỹ thuật (hash, mã định danh).
- **Tạo yêu cầu:** hộp xác nhận trước khi gửi phê duyệt; dữ liệu đã nhập được giữ nguyên nếu hủy hoặc lỗi.
- **Tổng quan hệ thống:** lọc theo thời gian, phòng ban, loại yêu cầu, trạng thái; KPI (tổng, chờ duyệt, đang thực hiện, hoàn thành, từ chối/hủy, quá hạn, người dùng hoạt động); so sánh phòng ban; tình trạng API, cơ sở dữ liệu, bộ nhớ đệm, dịch vụ AI và hàng đợi thông báo.
- **Theo dõi vận hành:** bảng Hồ sơ | Người tạo | Người đang xử lý | Phòng ban | Giai đoạn | Hạn | Quá hạn | Trạng thái | Thao tác; dòng quá hạn được tô viền đỏ. Điều chuyển chọn người nhận từ danh sách tài khoản đang hoạt động có đúng vai trò — không còn ô nhập mã định danh.
- **SLA & thông báo:** số bước đang tính hạn/quá hạn, nhắc hạn 24 giờ, trạng thái hàng đợi; danh sách thông báo gửi lỗi kèm nút gửi lại (bắt buộc lý do).
- Thông báo kết quả (toast) nêu rõ thao tác: điều chuyển, gửi lại, gửi yêu cầu, lưu nháp, bảo trì…

**API bổ sung (chỉ đọc)**

- `GET /api/v1/admin/overview`: thêm bộ lọc `department_id`, `type_code`, `status`; thêm `by_department`, `users` (đang hoạt động/tổng). Một truy vấn nhóm duy nhất.
- `GET /api/v1/admin/diagnostics` (OPS_ADMIN GLOBAL): số sự kiện outbox theo trạng thái, độ trễ hàng đợi, 20 sự kiện gửi lỗi, số bước SLA mở/quá hạn, nhắc hạn 24 giờ, kiểm tra dịch vụ AI (tối đa 3 giây). `worker.backlog_ok` chỉ cho biết **không có tồn đọng quá 5 phút**, không khẳng định worker đang chạy.
- `GET /api/v1/requests` và `GET /api/v1/ops/requests`: `q` tìm cả tiêu đề; danh sách vận hành trả thêm `requester_name`, `department_name`.

**Kiểm tra**

- `npm run lint`, `npm test` (51 bài), `npm run build` ở `web_client`; `npm run build` ở `web_admin`; `manage.py test` (284 bài, 5 bỏ qua); `tests/run_tests.py`; ruff và secret gate đều đạt.
- Kiểm thử trình duyệt mới, API giả lập, chạy cả hai cổng: `cd web_client && npm run test:portal` (đặt `EAS_CHROMIUM_PATH` tới Chrome/Edge nếu chưa cài trình duyệt của Playwright). 15/15 đạt trên Chrome: không tràn ngang và header không che tiêu đề ở 1440/1024/768/375px; điều hướng theo cổng; tìm kiếm; chuông thông báo; đủ 7 tab chi tiết; từ chối bắt buộc lý do; điều chuyển gửi đúng bước và phiên bản; không có lỗi trợ năng mức *critical* (axe). Đặt `EAS_SHOTS=1` để lưu ảnh chụp.
- `npm run test:ui` (`e2e/ui.spec.js`) là bộ kiểm thử cũ viết cho giao diện trước các đợt thiết kế lại (ví dụ chờ tiêu đề "Tổng quan xử lý yêu cầu" không còn tồn tại từ trước phiên này) và đang thất bại 17/18; bộ `test:portal` thay thế cho giao diện hiện tại.
- Chưa kiểm chứng trên dữ liệu thật qua trình duyệt (cần mật khẩu tài khoản thử nghiệm), chưa kiểm thử Safari/Firefox và thiết bị di động thật.

### 02/11/2026 — Rà soát toàn hệ thống: tiến trình hồ sơ, AI lưu vết, báo cáo phòng ban

**Lỗi gốc đã sửa**

- **Cổng nhân viên chạy sai chế độ:** `web_client/src/main.jsx` không truyền `portal`, nên ứng dụng rơi về chế độ "unified" — bảng tổng quan cá nhân, Kanban "Yêu cầu của tôi", tìm nhanh và chặn tài khoản quản trị không hoạt động. Nay cố định `portal="client"`.
- **Tài khoản quản trị chỉ dùng cho hệ thống (theo quyết định nghiệp vụ):** API vẫn từ chối tài khoản OPS_ADMIN/POLICY_ADMIN/AUDITOR ở endpoint nghiệp vụ. Bổ sung phía định tuyến: khi gửi yêu cầu, chuyển bước, nghiệm thu hoặc điều phối lại, hệ thống **không giao việc cho tài khoản quản trị** (trả `ROUTE_ACTOR_INACTIVE` / `ASSIGNEE_INVALID`) thay vì tạo bước mà không ai xử lý được.
- **Mật khẩu mặc định ẩn:** `verify_user_password` từng chấp nhận `Admin@123456` cho tài khoản seed/`!UNUSABLE_DEMO_` khi `EAS_ENV=development`, trái với [README SQL](database/EAS_Supabase_SQL/README_VI.md) ("không có mật khẩu mặc định"). Đã bỏ; xóa `fix_seed_passwords_local.py` (ghi hash mật khẩu công khai vào mọi tài khoản placeholder). Khôi phục mật khẩu dùng `recover_admin_password_interactive.py` hoặc lệnh `account_reset`. Không script khởi động nào ghi mật khẩu.
- **Kết nối Supabase:** mặc định `EAS_DB_CONN_MAX_AGE` trong code là `0` (mâu thuẫn chú thích "60"), khiến mỗi request mở kết nối TLS mới (~2,3 giây đo từ máy dev). Nay mặc định 60 giây, giữ `CONN_HEALTH_CHECKS`.
- **Dữ liệu giả trên trang quản trị:** bỏ số cứng 42 tài khoản / 8 phòng ban / "ISO 27001" / "2.0 LTS"; dùng `GET /api/v1/admin/overview` thật. Endpoint `/api/v1/meta/org-chart` (trước đây 404) đã có.
- **AI không trung thực khi dự phòng:** bộ phân loại trả độ tin cậy cố định 0,75 khi dùng quy tắc từ khóa; nay trả `method="keyword_heuristic"`, `fallback_used=true`, độ tin cậy 0. Lỗi `SyncAIServiceClient._run` gọi lại coroutine đã dùng cũng được sửa.
- Vite không còn proxy thẳng `/ai` tới dịch vụ AI nội bộ; test cấu hình production không còn phụ thuộc `.env` của máy dev (`EAS_DISABLE_DOTENV=true`).

**API mới (chỉ đọc, trừ đánh giá AI)**

| Endpoint | Mục đích | Phạm vi |
|---|---|---|
| `GET /api/v1/requests/{id}` → `request.progress` | Giai đoạn, người đang xử lý + vai trò, bước kế tiếp, hạn và thời gian còn lại, mọi quyết định kèm lý do | Như chi tiết hồ sơ |
| `GET /api/v1/requests` | Thêm `current_assignee_name`, `due_at`, `overdue`, `requester_name`, lọc `requester_id` | Như danh sách |
| `POST /api/v1/requests/route-preview` | Xem trước người duyệt/thực hiện/nghiệm thu bằng đúng bộ định tuyến khi gửi; không ghi dữ liệu | REQUESTER |
| `GET /api/v1/reports/requests` | Thêm `avg_completion_hours`, `avg_approval_hours` (tính từ lần gửi đầu) | Như cũ |
| `GET /api/v1/reports/team` | Phòng ban → nhân viên: tổng, chờ duyệt, đang làm, quá hạn, hoàn thành, thời gian TB | APPROVER/AUDITOR; chỉ hồ sơ người dùng tham gia hoặc thuộc phạm vi AUDITOR, không gồm hồ sơ của chính họ |
| `GET /api/v1/meta/org-chart` | Phòng ban + quan hệ `manager_id` | Toàn tổ chức cho OPS_ADMIN/AUDITOR GLOBAL; người khác: phòng mình + chuỗi quản lý |
| `GET/POST /api/v1/requests/{id}/ai-assessments` | Chạy và xem lịch sử đánh giá AI theo hồ sơ (kiểm tra dữ liệu thiếu, phân loại, rủi ro, tuyến duyệt, khuyến nghị) | Đọc: người xem được hồ sơ; chạy: vai trò nghiệp vụ |

Đánh giá AI được ghi vào chuỗi `audit_event` (hành động `AI_ASSESSMENT_RECORDED`) — **không cần migration**. Mỗi bước ghi rõ `DONE / FALLBACK / NOT_APPLICABLE`; khuyến nghị duyệt là quy tắc nghiệp vụ (`method="rule_based"`), chỉ mang tính tham khảo, người có thẩm quyền vẫn quyết định. OCR được ghi "chưa chạy" khi có tệp vì luồng này chưa gửi tệp tới OCR. Nếu cả phân loại và rủi ro đều dự phòng, hệ thống không gọi thêm bước khuyến nghị để không vượt timeout 30 giây của gunicorn.

**Giao diện**

- Chi tiết hồ sơ: khối tình trạng (giai đoạn, người đang xử lý, bước kế tiếp, hạn/quá hạn, lý do từ chối/bổ sung) và bảng "Đánh giá AI" có lịch sử.
- Tạo yêu cầu: "Tuyến xử lý dự kiến" trước khi gửi; cảnh báo nếu tuyến có người chưa đủ quyền. Gửi yêu cầu dùng một idempotency key cho mỗi phiên bản nháp; nếu hết thời gian chờ, client đọc lại trạng thái thật trước khi báo lỗi.
- Mới: **Bảng điều khiển phòng ban** (Tổ chức → Phòng ban → Nhân viên → Hồ sơ); **Sơ đồ tổ chức** dạng cây có tìm kiếm, lọc phòng ban, mở/thu gọn. Auditor xem báo cáo phòng ban trong cổng quản trị.
- "Yêu cầu của tôi": thẻ/bảng hiển thị người đang xử lý và hạn; phân trang 5/20/50. Tổng quan cá nhân hiển thị thời gian hoàn thành/phê duyệt trung bình thật.

**Việc cần quản trị/DBA xử lý (không tự sửa dữ liệu)**

1. Slot `DIRECTOR` đang gán cho tài khoản có AUDITOR, và một số người duyệt (ví dụ `tuan.pham`, có OPS_ADMIN) đang giữ bước ACTIVE. Theo quy tắc "quản trị chỉ dùng cho hệ thống", các yêu cầu có bước DIRECTOR sẽ bị từ chối khi gửi cho đến khi cấu hình `actor_bindings` trỏ tới người duyệt không có vai trò quản trị, hoặc tách vai trò quản trị sang tài khoản riêng. Các bước đang treo cần OPS điều phối lại sang người duyệt hợp lệ.
2. Ba hồ sơ `PENDING_APPROVAL` không có bước ACTIVE (REQ-2026-0002, -0009, -0026; dữ liệu seed). Kiểm tra chỉ đọc:
   `SELECT r.code FROM eas.request r WHERE r.status='PENDING_APPROVAL' AND NOT EXISTS (SELECT 1 FROM eas.approval_step s JOIN eas.workflow_instance w ON w.id=s.instance_id WHERE s.request_id=r.id AND s.state='ACTIVE' AND w.revision_id=r.current_revision_id);`

**Kết quả kiểm tra (02/11/2026, máy dev Windows)**

- `manage.py test`: 279 bài đạt (5 bỏ qua); `tests/run_tests.py`: 98 đạt; `web_client` `npm test`: 44 đạt; `npm run lint` sạch; build `web_client`/`web_admin` thành công; ruff, secret gate, env/docs gate đạt.
- Truy vấn mới chạy thử trên Supabase DATN trong phiên `READ ONLY` qua toàn bộ stack Django (không ghi dữ liệu, không đăng nhập bằng mật khẩu). Độ trễ đo từ máy dev (RTT tới pooler ~390 ms/lượt): danh sách p50 0,76 s / p95 1,6 s; chi tiết p50 0,99 s / p95 1,6 s; sơ đồ tổ chức ~0,37 s; báo cáo ~0,45 s. Số liệu bị chi phối bởi khoảng cách mạng; **chưa đo tải trên hạ tầng triển khai cùng vùng**, nên chưa khẳng định đạt mục tiêu p95.
- Chưa chạy: E2E ghi dữ liệu (gửi/duyệt/từ chối/nghiệm thu) trên Supabase, worker trên DB dùng chung, AI service thật, Playwright và kiểm thử tải. `npm audit` còn 7 cảnh báo mức moderate trong công cụ ESLint (dev).

### 01/11/2026 — Bố trí lại không gian làm việc và giám sát vận hành

- **Tổng quan nhân viên:** bộ lọc hôm nay / 7 ngày / 30 ngày / 12 tháng và chọn khoảng ngày; phân bố trạng thái và 10 loại yêu cầu thường xử lý. Thống kê chỉ trên hồ sơ mà người dùng có quyền xem; loại nháp không nằm trong báo cáo nghiệp vụ đã gửi.
- **Tổng quan quản trị:** API đọc `GET /api/v1/admin/overview?created_from=...&created_to=...` tổng hợp theo SQL `GROUP BY`, giới hạn 366 ngày và kiểm tra quyền OPS_ADMIN GLOBAL+ALL; biểu đồ trạng thái, nhóm yêu cầu, số trường hợp quá hạn và tình trạng endpoint `/health/ready`. Không gán nhãn "toàn hệ thống" cho dữ liệu ngoài phạm vi quyền.
- **Sidebar riêng:** nhân viên có công việc cá nhân, hồ sơ, quy trình AI; admin có vận hành, quản lý người dùng, vai trò/phân quyền, danh mục và kiểm toán. Cổng admin không hiện mục hồ sơ cá nhân; luồng buộc đổi mật khẩu vẫn được giữ khi mật khẩu tạm.
- **Người dùng & vai trò:** các API `admin/users`, `admin/memberships` có sẵn được đặt ở khu vực tương ứng, thêm/sửa/vô hiệu hóa user (xóa mềm), cấp/sửa/thu hồi role theo phòng ban và loại yêu cầu. Tại trang phân quyền, chọn dòng vai trò từ ma trận API để lọc và cấp role cho nhân viên. Ma trận mô tả *khả năng* role, không cho sửa hợp đồng API; quyền thực tế do backend kiểm tra.
- **Danh mục yêu cầu:** menu "Quản lý loại yêu cầu" cho phép nhập tên, nhóm, mức rủi ro, cấp phê duyệt và trạng thái với API có sẵn. **Bước triển khai bắt buộc:** chỉ đặt `EAS_ALLOW_REPORT_CATALOG_EXPANSION=true` trong `.env` gốc **sau khi** DBA xác nhận đã áp dụng migration mở rộng danh mục trên Supabase. Loại mới cần quy chế công bố và role phù hợp mới có thể gửi đơn. Không bật cờ này trên schema chưa tương thích.
- **Vận hành:** `GET /api/v1/ops/requests` trả thêm tên người phụ trách bước đang hoạt động, giai đoạn xử lý, loại yêu cầu, hạn và cờ quá hạn; hỗ trợ lọc theo ngày. Worker định tuyến `SLA_REMINDER`/`SLA_BREACH` tới người đang phụ trách phê duyệt/thực hiện/nghiệm thu, đồng thời chống trùng theo stage/kind/outbox. Khởi động `start_worker_local.cmd` để xử lý thông báo, không phụ thuộc trang web có mở hay không.
- **Quy trình AI:** thêm menu tra cứu luồng và giải thích bước xử lý. Khi chạy AI tại hồ sơ, nhãn "đang chạy / hoàn thành / lỗi / dự phòng" dựa trên phản hồi API; trang hướng dẫn không giả lập tiến trình trực tiếp. Người có thẩm quyền vẫn thực hiện approve/reject.
- **Chuẩn UI:** header dính trên màn hình khi cuộn, bảng có tiêu đề cố định trong vùng cuộn, nhãn nghiệp vụ tiếng Việt, hỗ trợ màn hình nhỏ, focus/aria cơ bản và giảm animation theo `prefers-reduced-motion`. Backend không trả dữ liệu ngoài scope chỉ vì frontend hiển thị nút.
- **Tối ưu:** báo cáo user nhóm SQL thay vì lấy tối đa 100.000 hàng rồi đếm bằng Python; cảnh báo SLA loại bỏ những stage đã có alert; GET thử lại an toàn, lệnh ghi không tự gửi lại khi timeout (30 giây chờ). Khi lỗi timeout ghi, cần truy vấn trạng thái theo idempotency trước khi thử lại.

**Kiểm tra bản vá:** `node --test web_client/e2e/*.test.mjs` (31 bài đạt); `python -m compileall -q api_core`; `tsc --allowJs --checkJs false --jsx preserve --noEmit --noResolve --target es2022 --module esnext --skipLibCheck web_client/src/App.jsx web_client/src/components/*.jsx`. Chưa có Supabase thực, Redis và Django dependencies trong môi trường kiểm thử này; **chưa xác nhận UAT hoặc thời gian phản hồi production**. Việc cài `npm ci` và build Vite cần thực hiện trên máy có mạng; chỉ triển khai sau khi cả `web_client` và `web_admin` build thành công, đồng thời chạy test theo 7 role.

### 01/11/2026 — Chuẩn hóa Web Client theo yêu cầu UI/UX

Đã cập nhật trực tiếp giao diện `web_client/`, không thay mẫu biểu hay tác vụ nghiệp vụ đã công bố:

- **Sidebar:** bỏ "Hồ sơ liên quan" và mọi mục quản trị hệ thống khỏi cổng nhân viên; giữ Tổng quan, Yêu cầu của tôi, các hàng đợi theo quyền, Sơ đồ tổ chức theo phòng ban, Sơ đồ luồng, Quy trình AI và tài khoản. Web Admin vẫn tách riêng tại cổng 5174.
- **Header:** thanh tìm nhanh **mã yêu cầu**, chuông hiển thị số thông báo chưa đọc từ API, tên + biểu tượng người dùng, biểu tượng đăng xuất, header cố định khi cuộn. Cỡ màn hình nhỏ tự bố trí lại, mọi thao tác có nhãn accessibility.
- **Tổng quan nhân viên:** báo cáo có lọc thời gian, thẻ KPI, biểu đồ phân bố trạng thái và loại yêu cầu thường gặp, hồ sơ gần đây. `GET /api/v1/reports/requests?scope=mine` mới chỉ tổng hợp hồ sơ *do chính người đăng nhập tạo*, không lẫn hồ sơ họ được mời xem. Thống kê không đếm nháp; tần suất là ước tính theo 30 ngày. Khi chưa có dữ liệu đo thời gian hoàn thành trung bình, hiển thị dấu gạch ngang thay vì số giả.
- **Tổng quan theo vai trò:** tài khoản chỉ có quyền APPROVER/EXECUTOR/ACCEPTOR nhận dashboard công việc được phân công từ API, không tự động được xem các hồ sơ khác trong phòng ban.
- **Yêu cầu của tôi:** sáu tab Yêu cầu của tôi / Phê duyệt / Thực hiện / Nghiệm thu / Hoàn thành / Nháp (chỉ hiện tab thuộc quyền), với Kanban hoặc bảng, giữ nguyên bộ lọc khi đổi kiểu xem; tìm mã, lọc loại/trạng thái/ngày tạo, sắp xếp theo ngày và phân trang từ API. Các trạng thái bị từ chối/đã hủy có nhóm riêng trong Kanban. Kéo thả không sửa trạng thái giả; approve/reject/thực hiện/nghiệm thu vẫn chỉ qua nút xác nhận trên chi tiết hồ sơ.
- **Tạo yêu cầu:** danh mục mẫu từ API được hiển thị dạng thẻ responsive, giữ nguyên tất cả mẫu hiện có, validation, tệp và logic lưu nháp/gửi đơn. Có mục "Tạo yêu cầu khác" **chỉ hoạt động khi quản trị đã công bố mẫu linh hoạt có mã thuộc nhóm được hỗ trợ**; khi chưa có mẫu, hiển thị giải thích và không tạo nút giả. Form tùy ý chưa có API/schema không được ghi vào Supabase.
- **Sơ đồ tổ chức của nhân viên:** lấy danh bạ đồng nghiệp cùng phòng từ `/api/v1/meta/colleagues` (chỉ tài khoản REQUESTER, không hiển thị email/role/quyền hoặc dữ liệu phòng ban khác). Chưa thể hiển thị hệ phân cấp quản lý khi API chưa trả `manager_id` an toàn.
- **Hệ thống giao diện:** bổ sung thành phần dùng chung `ClientPageHeader`, `ClientStatCard`, `ClientFilterSection`, CSS `client-refactor.css` với cùng màu, khoảng cách, form, bảng, thẻ; hỗ trợ desktop/tablet/mobile, focus và giảm chuyển động.
- **Chính xác về phạm vi:** `GET /api/v1/requests` hiện chỉ tìm theo **mã hồ sơ** bằng `q`, không tìm tiêu đề trong payload; cổng client không quảng cáo tìm theo tiêu đề khi backend chưa hỗ trợ. Sắp xếp trên trang đang tải, không giả làm thứ tự trên toàn bộ dữ liệu.

#### Cần backend mở rộng nếu muốn nghiệm thu toàn bộ prompt

1. Định nghĩa/được cấp quyền *Trưởng phòng*, *Phó Giám đốc*, *Giám đốc* và endpoint thống kê đọc theo `department_id`/phân cấp được xác minh từ server, kèm danh sách nhân viên, báo cáo riêng, lịch sử xử lý và quyền truy cập chi tiết. **Không dùng API admin/users ở cổng nhân viên**.
2. API báo cáo thời gian hoàn thành trung bình dựa trên mốc bắt đầu/đóng thực, cho từng cấp người dùng; API tra cứu theo tên hồ sơ và lọc ngày xử lý; trả người phụ trách theo từng giai đoạn trong kết quả danh sách.
3. Muốn tạo form tự do ngoài 18 mẫu, cần định nghĩa loại mới, schema/validation phía server, quản lý các trường động, lưu dự thảo, phân tuyến duyệt/permission, migration và chính sách công bố. Nếu không có API này, không cho client tự lưu dữ liệu ngoài quy định.
4. API sơ đồ tổ chức đọc theo role/scope cho phép hiển thị quan hệ cấp trên–cấp dưới mà không lộ thông tin riêng tư.

#### Kiểm tra

`cd web_client && npm ci && npm test && npm run build` và `cd ..\web_admin && npm ci && npm run build`; kiểm tra nghiệp vụ tạo nháp/gửi/duyệt/thực hiện/nghiệm thu theo vai trò trên Supabase thật, chức năng điều hướng, bảo mật dữ liệu và responsive. Trong môi trường chỉnh sửa hiện tại **36/36 bài kiểm thử Node đạt**, các file JSX đã được kiểm tra parser TypeScript, Python report biên dịch cú pháp thành công, CSS parse thành công. **Chưa thể xác nhận build Vite**, do `npm ci` không tải đủ dependencies (`ENOTCACHED` và lỗi npm). Chưa có kiểm thử tích hợp với Supabase/AI thật; không coi đây là nghiệm thu production.


### 2026-11-01 — Web Client: bố cục, quy trình AI, sơ đồ phòng ban

- Thanh lọc thời gian trên trang Tổng quan được căn theo cùng chiều cao (44px), các khoảng chọn nhanh xuống hàng hợp lý trên màn hình hẹp.
- Trang **Quy trình AI** không còn hiển thị ảnh tĩnh: dùng dữ liệu từ `/api/v1/requests?tab=mine|approval` và `/api/v1/requests/{id}` để phản ánh trạng thái thật của yêu cầu, người duyệt hiện tại và mức độ hoàn thành. Chọn **Chạy đánh giá AI cho hồ sơ** để gọi `/api/v1/ai/classify`, `/api/v1/ai/risk-score` theo yêu cầu (chỉ phân tích, tuyệt đối không tự phê duyệt); kết quả thuộc phiên hiện tại, không giả lập lịch sử AI. Người duyệt tiếp tục dùng giao diện chi tiết hồ sơ để approve/reject.
- **Sơ đồ phòng ban** hiển thị quan hệ `manager_id` và thành viên từ API `/api/v1/meta/colleagues`. API giữ nguyên `items` theo hợp đồng cũ (chỉ đồng nghiệp và `{id, display_name}` dùng cho form), bổ sung `organization` với các quan hệ trưởng nhóm/nhân viên **chỉ trong phòng ban hiện tại**. Dữ liệu không cấu hình trưởng phòng sẽ hiển thị rõ là chưa gán. Sơ đồ chỉ xem, không tạo thêm quyền phê duyệt.
- Không thay đổi logic gửi/phê duyệt, không sửa schema Supabase. Với dữ liệu tổ chức, Backend cần chạy phiên bản mới để frontend nhận thêm `organization`.
- Kiểm tra bằng `cd web_client && npm test && npm run build`, sau đó thử giao diện thực tế với tài khoản REQUESTER/APPROVER và Supabase của dự án. Việc build cần cài dependencies (`npm ci`).

## EAS Security & Compliance Changelog

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-CHANGELOG-STD-02 |
| Ngày | 31/10/2026 |
| Phạm vi | Kiểm soát kỹ thuật trong mã nguồn, đối chiếu với các yêu cầu của ISO 9001, CMMI, ISO/IEC 27001, SOC 2, ITIL |
| Trạng thái | Nhật ký thay đổi kỹ thuật. **Không phải chứng nhận và không phải biên bản GO-LIVE** |

### 0. Phạm vi trung thực của tài liệu này

ISO 9001, CMMI, ISO/IEC 27001, SOC 2 và TIER là **chứng nhận hoặc xếp hạng cấp tổ chức/cơ sở hạ tầng**, do bên thứ ba đánh giá trên bằng chứng vận hành theo thời gian. Việc sửa mã nguồn **không thể** tự cấp các chứng nhận này. Tài liệu này chỉ ghi lại các **kiểm soát kỹ thuật** đã triển khai và kiểm chứng bằng test; mục 4 liệt kê những gì còn thiếu.

### 1. Thay đổi đã triển khai

#### 1.1 Bảo mật ứng dụng & Danh tính (ISO 27001 A.8/A.9/A.12, SOC 2 Security & Privacy)

| Hạng mục | Thay đổi | File |
|---|---|---|
| Proxy-aware Login Throttle | `login()` dùng `client_ip(request)` thay vì `REMOTE_ADDR`. Sau proxy tin cậy (`EAS_TRUST_PROXY_HEADERS=true`), throttle theo IP thực tế của client từ entry cuối của `X-Forwarded-For`, không còn nguy cơ khóa nhầm toàn bộ công ty. | `api_core/authn/views.py` |
| Ép đổi mật khẩu trước go-live | Tạo lệnh quản trị `enforce_initial_passwords.py` `--operator <user> --approval <ticket>` để bật `must_change_password=True`, tăng `auth_version` hủy toàn bộ session cũ của các tài khoản seed, ghi nhật ký kiểm toán bất biến. | `api_core/management/commands/enforce_initial_passwords.py` |
| Che PII trước khi gửi LLM | `sanitize_prompt_text()` che số thẻ (PAN 16 số), số CCCD (12 số) và bearer token/api keys thành `[REDACTED_*]` trước khi gửi prompt tới Google Gemini. | `ai_service/routers/summarize.py` |
| Giới hạn Payload AI Service | Middleware `limit_request_size` chặn request vượt quá 20MB (HTTP 413 `Payload too large`), phòng ngừa cạn kiệt bộ nhớ (OOM/DoS). | `ai_service/main.py` |
| Loại bỏ Deprecation Warning | Thay `asyncio.get_event_loop()` bằng `asyncio.get_running_loop()`; chuyển Pydantic `example=` sang `examples=[...]`. | `api_core/ai_client.py`, `ai_service/ai_client.py`, `ai_service/routers/classify.py` |
| Header phòng thủ | `ApiSecurityHeadersMiddleware`: CSP (`frame-ancestors 'none'`), Permissions-Policy, nosniff, Referrer-Policy, COOP. Không ghi đè CSP có sẵn. | `api_core/middleware.py` |
| Giới hạn tần suất chung | `ApiRateLimitMiddleware`: 300 req/phút/IP (cấu hình bằng `EAS_API_RATE_LIMIT_PER_MINUTE`), trả 429 + `Retry-After`. | `api_core/middleware.py`, `api_core/config/settings.py` |
| Fail-open có chủ đích | Nếu Redis/cache lỗi, rate limiter ghi cảnh báo và cho request đi qua, ưu tiên tính sẵn sàng. | `api_core/middleware.py` |
| Chính sách secret production | Production **từ chối khởi động** nếu `EAS_AI_INTERNAL_SECRET` rỗng, ngắn hơn 32 ký tự, là placeholder hoặc là chuỗi dev công khai. | `api_core/config/settings.py`, `ai_service/config.py` |
| So sánh secret hằng thời gian | `hmac.compare_digest` cho `X-Internal-Secret`. | `ai_service/main.py` |
| Che dữ liệu nhạy cảm trong log | Che số thẻ 16 chữ số và số CCCD 12 chữ số trong console log. | `api_core/logger.py` |

#### 1.2 Độ tin cậy và vận hành (ITIL, ISO 27001 A.17)

| Hạng mục | Thay đổi | File |
|---|---|---|
| Lỗi 500 luôn là JSON | Catch-all cho `/api/v1/`, ghi log kèm `correlation_id`, không lộ chi tiết. | `api_core/middleware.py` |
| Kết nối DB với pooler | `CONN_MAX_AGE` mặc định `0` để tránh socket cũ với PgBouncer. | `api_core/config/database.py`, `settings.py` |
| Cách ly lỗi giao diện | `ErrorBoundary` cho cả `web_client` và `web_admin`. | `web_client/src/components/ErrorBoundary.jsx` |
| CI | Thêm audit và build cho `web_admin`. | `.github/workflows/ci.yml` |

#### 1.3 Kiểm thử mới (CMMI V&V)

- `api_core/tests/test_authn.py`: thêm test throttle cách ly IP client sau proxy tin cậy.
- `api_core/tests/test_administration.py`: thêm test lệnh quản trị `enforce_initial_passwords`.
- `tests/integration/test_ai_service.py`: thêm test `sanitize_prompt_text` che PII trước khi gửi LLM.
- `api_core/tests/test_security_middleware.py`: 9 test security middleware.
- `api_core/tests/test_production_secret_policy.py`: 3 test production startup policy.
- `test_logger.py`: test che số thẻ/CCCD.
- Toàn bộ test suite: 100% PASS.

### 2. Sự cố và điều chỉnh trong quá trình làm (minh bạch)

1. **Đã xử lý dứt điểm điểm nghẽn proxy**: Cả `ApiRateLimitMiddleware` và `login()` trong `authn/views.py` hiện đều sử dụng chung hàm `client_ip()` xử lý an toàn IP cuối của `X-Forwarded-For` khi bật `EAS_TRUST_PROXY_HEADERS=true`.
2. **Đã có công cụ ép đổi mật khẩu seed**: Lệnh `enforce_initial_passwords` giải quyết triệt để rủi ro mật khẩu mặc định `Password@123456` trước khi bàn giao hệ thống.
3. **Đã bảo vệ PII trước LLM**: Dữ liệu thẻ và CCCD không còn bị gửi nguyên vẹn ra Google Gemini.
4. Script live test không còn chứa mật khẩu hay đường dẫn cá nhân; đọc `EAS_E2E_*` từ môi trường.

### 3. Kết quả kiểm chứng

- Ruff check/format, compileall, secret gate, docs gate: **PASS**.
- `python manage.py test`: **PASS** (chạy trên SQLite in-memory).
- `python tests/run_tests.py`: **12/12 PASS**.
- `npm run build --prefix web_client`: **PASS**.
- `npm run build --prefix web_admin`: **PASS**.

### 4. Những gì CHƯA làm hoặc không thể làm bằng mã nguồn

| # | Khoảng trống | Vì sao quan trọng | Việc cần làm |
|---|---|---|---|
| 1 | **Chưa có chứng nhận nào** (ISO 9001/27001, SOC 2, CMMI, TIER) | Không thể tuyên bố "đạt chuẩn" với khách | Cần ISMS/QMS được tài liệu hóa, chính sách, đào tạo, đánh giá rủi ro, audit nội bộ, rồi tổ chức chứng nhận bên ngoài. SOC 2 Type II cần 3 đến 12 tháng bằng chứng |
| 2 | **TIER là thuộc tính của cơ sở hạ tầng/nhà cung cấp**, không phải của ứng dụng | Compose chạy **một** instance mỗi dịch vụ, không dự phòng | Chọn nhà cung cấp hosting có TIER công bố; thiết kế nhiều instance, load balancer, DB HA. Không nên quảng cáo "TIER III" cho phần mềm |
| 3 | **Chưa chạy load test** | Chưa có số p95/p99, chưa biết sức chịu tải | Chạy k6/Locust trên môi trường giống production trước khi cam kết SLA |
| 4 | **Chưa penetration test độc lập** | Không có bằng chứng bên ngoài về khả năng chống tấn công | Thuê pentest trước khi bán |
| 5 | **Chưa diễn tập backup/restore** | Backup chưa chứng minh được là khôi phục được | Chạy `scripts/rehearse_backup_restore.ps1` và ghi RTO/RPO thực tế |
| 6 | **Tài liệu 08 ghi `.env` từng nằm trong lịch sử Git (F01)** | Mọi credential trong đó phải coi là đã lộ | Xoay vòng DB password và các key Supabase trước khi go-live thương mại |
| 7 | Redis không có mật khẩu/TLS; Elasticsearch (profile tùy chọn) tắt xác thực | Chỉ chấp nhận được khi mạng nội bộ cô lập | Bật xác thực nếu mở rộng ra ngoài mạng nội bộ |
| 8 | KD01–KD08 (quyết định nghiệp vụ) chưa có người ký (tài liệu 08, F10) | Chính sách và SLA chưa có thẩm quyền | PO/khách hàng ký trước pilot dữ liệu thật |
| 9 | SonarCloud còn một số code smell cấp thấp | Không chặn Quality Gate nhưng là nợ kỹ thuật | Xử lý dần theo backlog |

### 5. Điều kiện trước khi bán cho khách

Tối thiểu: (1) chạy `enforce_initial_passwords` trên DB khách, (2) xoay credential Supabase/DB, (3) cấu hình proxy `EAS_TRUST_PROXY_HEADERS=true`, (4) pentest bên thứ 3, (5) diễn tập khôi phục, (6) load test theo SLA cam kết.
