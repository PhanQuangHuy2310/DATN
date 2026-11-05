# Thiết kế schema `eas` v2 và quy tắc duyệt cho lãnh đạo cao nhất (04/11/2026)

Tài liệu đi kèm:

- Báo cáo kiểm toán: [KIEM_TOAN_CODE_DATA_2026-11-04.md](KIEM_TOAN_CODE_DATA_2026-11-04.md)
- Migration 14 (vá bảo mật, thêm bảng): `database/migrations/14_security_hardening_and_schema_v2_expand.sql`. **Đã chạy trên live.**
- Migration 15 (gộp bảng trùng, giữ dữ liệu): `database/migrations/15_schema_v2_consolidate.sql`
- Rollback: `database/migrations/rollback/14_security_hardening_and_schema_v2_expand_rollback.sql`, `database/migrations/rollback/15_schema_v2_consolidate_rollback.sql`
- Lệnh: `python manage.py import_legacy_changelog [--apply]`, `python manage.py repair_workflow_consistency [--apply]`

## 1. Hiện trạng trên Supabase live (đọc trực tiếp ngày 04/11/2026)

Truy vấn chỉ đọc, role `eas_api`.

| Nhóm | Số lượng | Nhận xét |
|---|---|---|
| Bảng trong `eas` | 53 | 49 bảng gốc và 4 bảng của migration 14 |
| View trong `eas` | 9 | Trùng tên với bảng thật. Xem §3.1 |
| Schema `eas_deprecated` | 10 bảng, 2 view | Bảng bản đầu (`users`, `roles`, `requests`, `departments`, `role_permissions`, `request_templates`, `workflow_categories`…), đã cách ly ở migration 11. Role ứng dụng không đọc được |
| Schema `mock_*` | 9 schema | Hệ thống ngoài mô phỏng (HRM, IT, tài sản, CRM…). Xem §3.4 |

## 2. Nguyên tắc

1. **Không mất dữ liệu.** Migration 15 không xoá dữ liệu nào. Phần bị gộp hoặc bỏ khỏi `eas` được dời sang schema `eas_archive`:
   - bảng: dời nguyên bảng;
   - cột: giá trị được lưu theo từng dòng vào `eas_archive.dropped_column_value`.

   Rollback dùng chính kho này để trả lại đúng giá trị cũ.
2. **Mỗi dữ kiện một nơi.** Mỗi dữ kiện có một bảng gốc. Bản chụp theo thời điểm chỉ có khi cố ý, ví dụ trọng số rủi ro lúc gửi đơn.
3. **Giữ lõi đã tốt, không dựng lại DB.** Lõi đã đạt 3NF, có khoá ngoại kép và trigger chỉ-ghi-thêm. Dựng lại database từ đầu sẽ phải chép lại 465 phân quyền, 82 sự kiện audit chuỗi băm và 99 sự kiện quản trị. Chuỗi băm rất dễ hỏng khi chép, nên rủi ro cao hơn lợi ích. Sửa từng chỗ trùng đạt cùng kết quả, an toàn hơn.
4. **Ràng buộc nằm ở DB.** Trigger và CHECK giữ các quy tắc bất biến.
5. **Mặc định từ chối.** Policy RLS chỉ cấp cho role backend. Kho `eas_archive` không cấp quyền cho role ứng dụng nào.

## 3. Danh sách trùng và cách xử lý

### 3.1 Tên trùng: 9 view bí danh

`roles`, `requests`… **không phải bảng thứ hai**. Chúng là view đọc lại bảng thật, do migration 11 và 13 tạo cho code cũ. Không còn code nào dùng chúng. Test `test_schema_v2_consolidation` chặn việc dùng lại các tên này.

| View (bỏ) | Bảng thật (giữ) |
|---|---|
| `roles` | `role` |
| `requests` | `request` |
| `departments` | `department` |
| `role_permissions` | `role_module_permission` |
| `user_roles` | `role_membership` |
| `admins` | `app_user` (`account_type` = `ADMIN`) và `admin_account` |
| `request_templates`, `v_request_templates_full` | `request_type` và `config_release` |
| `v_users_management` | `app_user` |

Migration 15 bỏ 9 view này. View không chứa dữ liệu nên không mất gì.

### 3.2 Bảng khác tên, cùng chức năng

**`workflow_categories` (3 dòng) trùng `lifecycle` (3 dòng).**

- Cả hai định nghĩa nhóm A/B/C.
- Giữ `lifecycle` vì có khoá ngoại từ `request_type`, `config_release` và `workflow_instance`.
- `workflow_categories` không có khoá ngoại, và SLA 4h/24h/72h trong đó **sai** quy chế.
- Dữ liệu cũ: dời sang `eas_archive.workflow_categories_eas`.

**`system_versions_changelog` (29 dòng) trùng `admin_event` (99 dòng).**

- Cả hai là nhật ký thay đổi của quản trị.
- Giữ `admin_event` vì có chuỗi băm chống sửa và khoá ngoại tới người thực hiện.
- Bảng changelog còn bị **ghi đúp**: mỗi lần bật/tắt API, cả code lẫn trigger `trg_after_mock_api_toggle` cùng ghi.
- Dữ liệu cũ: lệnh `import_legacy_changelog` chép từng dòng sang `admin_event`, giữ thời điểm gốc và id cũ (`details.legacy_changelog_id`). Bảng gốc dời sang `eas_archive`. Trigger ghi đúp bị bỏ.

**`work_handover` (0 dòng) trùng `approval_delegation` (0 dòng).**

- Cùng nghĩa: giao việc cho người khác trong một khoảng thời gian.
- Giữ `approval_delegation` vì đã có code và API.
- `work_handover` do migration 14 thêm. Đây là sai sót của bản thiết kế trước, nay sửa.
- Dữ liệu cũ: `approval_delegation` thêm 4 cột (`scope`, `source`, `source_request_id`, `created_by`) rồi nhận mọi dòng. Bảng cũ dời sang `eas_archive`.

**`eas_deprecated.*` (10 bảng) trùng `app_user`, `role`, `request`…**

- Các bảng thật trong `eas` đã thay thế chúng từ migration 11.
- Dữ liệu cũ: schema được đổi tên thành `eas_archive`, dữ liệu giữ nguyên.

### 3.3 Cột trùng

| Cột (bỏ) | Nguồn duy nhất | Ghi chú |
|---|---|---|
| `request.risk_weight`, `request.approval_level` | `request_revision` (bản chụp lúc gửi). Đơn nháp đọc `request_type` | Trước đây AI tự duyệt đọc cột này, tức giá trị lúc tạo nháp. Nay AI đọc bản chụp lúc gửi |
| `workflow_instance.risk_weight`, `.approval_level` | `request_revision` | Mỗi phiên trỏ tới đúng một revision |
| `config_release.risk_weight`, `.approval_level` | `request_type` | Bản phát hành PUBLISHED bất biến, không thể là nơi chỉnh trọng số |
| `app_user.username` | `email` | 138/138 dòng bằng đúng phần trước `@` của email. Đăng nhập chỉ dùng email |

Mọi giá trị của các cột bị bỏ được lưu ở `eas_archive.dropped_column_value`.

### 3.4 Có vẻ trùng nhưng **giữ**, kèm lý do

| Cặp | Lý do giữ cả hai |
|---|---|
| `role_module_permission` và `user_permissions` | Khác khoá: quyền mặc định theo vai trò, và quyền riêng của từng người. Gộp lại cần cột "vai trò hoặc người", tức là phi chuẩn |
| `role` và `role_membership` | Danh mục vai trò, và việc gán vai trò cho người |
| `company_regulations` và `regulation_versions` | Bản hiện hành, và lịch sử phiên bản |
| `notification` và `system_announcement`, `announcement_receipt` | Thông báo theo hồ sơ cho từng người, và thông báo chung kèm trạng thái đã đọc |
| `audit_event` và `admin_event` | Hai chuỗi băm riêng: nghiệp vụ theo từng hồ sơ, và quản trị |
| `attachment` và `draft_attachment`, `revision_attachment`, `execution_attachment` | Một bảng tệp và ba bảng liên kết theo giai đoạn. Không lặp dữ liệu tệp |
| `ai_policy_version`, `ai_learning_job`, `ai_system_state` | Bộ luật, công việc học, trạng thái máy. `ai_policy_version` là nguồn bộ luật |
| `eas.department`, `eas.app_user` và `mock_hr.department`, `mock_hr.employee` | `mock_hr` mô phỏng **hệ thống HRM bên ngoài**; EAS đồng bộ từ đó. Ngoài đời đây là hai hệ thống, hai database. Gộp sẽ phá kiến trúc tích hợp đã mô tả trong báo cáo |
| `eas.mock_apis` và các schema `mock_*` | `mock_apis` là danh mục cổng tích hợp (bật/tắt, circuit breaker). `mock_*` là dữ liệu của hệ thống ngoài |

### 3.5 Kết quả

| | Trước 15 | Sau 15 |
|---|---|---|
| Bảng trong `eas` | 53 | 50 |
| View trong `eas` | 9 | 0 |
| Schema `eas_deprecated` | có | không (đổi tên thành `eas_archive`) |
| Nhật ký thay đổi quản trị | 2 bảng | 1 (`admin_event`) |
| Nơi lưu trọng số rủi ro | 5 bảng | `request_type`, bản chụp ở `request_revision` |

## 4. Thứ tự chạy trên live

1. **Sao lưu** (Supabase → Database → Backups).
2. **Triển khai bản code mới.** Code mới không đọc hay ghi tên cũ, và vẫn chạy được trên schema trước 15.
3. **Chép nhật ký:** chạy `python manage.py import_legacy_changelog` để xem trước, rồi chạy lại với `--apply`. Chạy lại an toàn: dòng đã chép được bỏ qua.
4. **Chạy migration 15** trong SQL Editor. File tự dừng nếu bước 3 chưa xong.
5. **Sửa hồ sơ kẹt:** chạy `python manage.py repair_workflow_consistency`, rồi chạy lại với `--apply`.
6. **Gán vai trò AUDITOR** cho một tài khoản kiểm soát riêng.
7. **Bỏ qua** `database/migrations/scheduled/2026-11-17_drop_eas_deprecated_after_11.sql`. Sau bước 4, schema `eas_deprecated` đã đổi tên, nên file đó chỉ báo "không có schema".

Đã kiểm tra trên bản sao local. Bản sao được dựng lại đúng hiện trạng live: 9 view, `eas_deprecated`, 49 dòng changelog, 1 dòng bàn giao. Kết quả:

- Migration 15 từ chối chạy khi chưa chép nhật ký.
- Import chép 49 dòng; lần chạy thứ hai chép 0. `audit_verify --scope ADMIN`: PASS, 220 sự kiện.
- 15 chạy 2 lần đều OK. Còn 50 bảng, 0 view, 6 bảng trong kho.
- Rollback chạy 2 lần. Checksum trọng số của `request` và `workflow_instance`, và checksum `username`, khớp **trước và sau**. Dòng bàn giao trở về bảng cũ. Trigger bất biến được bật lại.
- Chạy lại 15, rồi smoke test:
  - gửi đơn của nhân viên và của giám đốc đúng;
  - truy vấn ngữ cảnh AI chạy được;
  - màn hình nhật ký đọc đủ 49 dòng từ `admin_event`.

## 5. Quy tắc duyệt cho người không có quản lý trực tiếp

### 5.1 Vấn đề

Giám đốc hoặc người đứng đầu không có `manager_id`. Trước đây, loại yêu cầu có bước `DIRECT_MANAGER` thì người này không gửi được (L3). Ngoài ra, khi người gửi trùng người duyệt, hệ thống chặn hẳn thay vì leo thang (L4).

### 5.2 Phương án đã chọn và cài đặt

Bộ định tuyến (`api_core/domain/routing.py`) xử lý theo thứ tự sau:

| Tình huống | Hành vi | Mã ghi audit |
|---|---|---|
| Bước `DIRECT_MANAGER`, người gửi có quản lý | Quản lý duyệt như bình thường | — |
| Bước `DIRECT_MANAGER`, người gửi không có quản lý, phòng ban có khai báo `TOP_LEVEL_APPROVER` | Người được khai báo duyệt thay | `TOP_LEVEL_FALLBACK` |
| Như trên nhưng không khai báo | Bỏ qua bước này; các bước chuyên môn khác (FINANCE, LEGAL, …) vẫn giữ | `TOP_LEVEL_SKIPPED` |
| Người gửi trùng người duyệt của một bước | Chuyển bước lên quản lý của người gửi | `SOD_ESCALATED` |
| Như trên nhưng người gửi không có quản lý | Bỏ qua bước | `SOD_SKIPPED` |
| Hai bước liền ra cùng một người | Gộp thành một bước | `DUPLICATE_SKIPPED` |
| Sau các điều chỉnh, tuyến **không còn bước nào** | Từ chối gửi: `ROUTE_CONFIGURATION_INVALID` (409) | — |
| Người nghiệm thu `DIRECT_MANAGER`, người gửi không có quản lý | Dùng `TOP_LEVEL_APPROVER`; nếu không có, người gửi tự nghiệm thu | — |

Mọi điều chỉnh được ghi vào `details.route_adjustments` của sự kiện audit `REQUEST_SUBMITTED`. Kiểm toán viên thấy rõ bước nào bị bỏ hoặc đổi người, và vì sao.

### 5.3 Lý do chọn

- **Không ai tự duyệt đơn của mình.** Tuyến rỗng thì bị từ chối, không tự động thông qua. Đây là nguyên tắc tách biệt nhiệm vụ (SoD) cốt lõi.
- **Không cấu hình ẩn.** Không tự chọn "người có chức danh cao nhất" bằng heuristic. Người duyệt thay phải được khai báo rõ.
- **Không chặn công việc thường ngày.** Đơn có bước chuyên môn (chi phí qua FINANCE, hợp đồng qua LEGAL) vẫn qua kiểm soát chuyên môn. Chỉ bỏ bước "quản lý trực tiếp" vốn không tồn tại.
- **Truy vết đầy đủ.** Mỗi lần bỏ hoặc đổi người đều có mã lý do trong audit chuỗi băm.

### 5.4 Việc cần làm để giám đốc gửi được loại chỉ có bước `DIRECT_MANAGER`

Ví dụ: làm việc từ xa (`WFH_REQ`). Nếu chưa khai báo người duyệt thay, đơn của giám đốc bị từ chối với `ROUTE_CONFIGURATION_INVALID`. Đây là hành vi đúng; smoke test trên bản sao đã xác nhận.

Cách khai báo: dùng script `database/data_fixes/2026-11-04_top_level_approver_binding.sql`.

1. Chọn người duyệt thay, ví dụ thành viên hội đồng quản trị hoặc phó giám đốc được uỷ quyền. Script từ chối nếu người này chính là lãnh đạo cao nhất của phòng.
2. Sửa 2 tham số đầu script: `dept_code` (mặc định `BOD`) và `approver_email`.
3. Dán toàn bộ vào Supabase SQL Editor → Run.

Script làm những việc sau:

- Với mỗi loại yêu cầu đang hoạt động có dùng `DIRECT_MANAGER`, script phát hành một bản cấu hình mới. Bản mới thêm khoá `TOP_LEVEL_APPROVER` vào `actor_bindings.departments.<id phòng ban>`. Khoá theo **id** phòng ban, không theo mã.
- Bản PUBLISHED cũ không bị sửa. Hồ sơ đã gửi giữ cấu hình cũ.
- Chạy lại an toàn: loại nào đã có đúng khai báo thì bỏ qua.

Đã kiểm tra trên bản sao:

- Giám đốc gửi `EXPENSE_CLAIM` khi chưa khai báo → tuyến chỉ còn bước FINANCE, trạng thái `PENDING_APPROVAL`.
- Giám đốc gửi `WFH_REQ` khi chưa khai báo → 409.
- Chạy script: 53 loại được phát hành bản mới; lần chạy thứ hai: 0. Sau đó giám đốc gửi `WFH_REQ` được; bước 1 giao cho người duyệt thay, kèm mã `TOP_LEVEL_FALLBACK`.

## 6. Còn mở (không thuộc đợt này)

| Mã | Việc |
|---|---|
| M6 | Job xuất `audit_checkpoint` ra nơi lưu ngoài |
| S8f | Job dọn `idempotency_record` hết hạn |
| — | Worker SLA và bộ phân công đọc `sla_escalation_policy`, `business_holiday` và `approval_delegation.scope` (bàn giao thực hiện/nghiệm thu). Bảng và dữ liệu mặc định đã có; code chưa dùng |

## 7. Chấm công và giờ làm việc (migration 16)

Chủ dự án chốt: dữ liệu chấm công là dữ liệu ảo. Không có bảng chấm công nào được đọc; trạng thái của nhân viên suy ra từ đơn đã duyệt.

| Thời điểm (giờ Việt Nam) | Có đơn nghỉ/công tác ĐÃ DUYỆT trùng giờ | Không có đơn |
|---|---|---|
| T2–T6, 08:00–12:00 và 13:30–17:30 | Nghỉ làm / Công tác | **Đang làm** (`DANG_LAM`) |
| T2–T6, 12:00–13:30 | Nghỉ làm / Công tác | **Nghỉ trưa** (`NGOAI_GIO`) |
| Ngoài khung trên, T7, CN | Nghỉ làm / Công tác | **Ngoài giờ làm việc** (`NGOAI_GIO`) |

- Hàm `eas.get_user_working_status` trả về các trạng thái này. Màn hình nhân sự và sơ đồ tổ chức hiển thị thêm trạng thái "Nghỉ trưa / Ngoài giờ".
- Phân công:
  - người duyệt đang **nghỉ phép** → chuyển sang người được uỷ quyền, nếu không có thì lên quản lý;
  - người duyệt đang **công tác** → vẫn duyệt được (quyết định D2: duyệt từ xa trên web hoặc điện thoại);
  - người thực hiện đang nghỉ hoặc công tác → giao cho đồng nghiệp cùng phòng có vai trò thực hiện.
- Ngoài giờ hoặc giờ nghỉ trưa không làm đổi người được giao; việc được xử lý vào giờ làm kế tiếp.
- Thứ 7 và Chủ nhật được tính là ngoài giờ, theo giả định T2–T6.

## 8. Mượn phòng, xe, thiết bị và hệ thống ngoài

Đã chuyển sang tài liệu riêng: [TICH_HOP_HE_THONG_NGOAI.md](TICH_HOP_HE_THONG_NGOAI.md).

Bản đầu của migration 17 ghi thẳng SQL vào `mock_assets` và `mock_facilities`. Bản đó **đã bị huỷ, chưa từng chạy trên live**. Lý do: các schema `mock_*` là hệ thống ngoài, nên EAS chỉ được gọi API của chúng.

Quy tắc nghiệp vụ giữ nguyên:

- ai được duyệt trước thì được trước;
- hết hạn thì trả lại;
- Ban Giám đốc được ưu tiên: thu hồi phần của nhân viên, chuyển đơn đó sang REJECTED và báo cho nhân viên.

Thực hiện qua migration `17_external_systems_via_api.sql` và module `api_core/workflow/resource_allocation.py`, gọi qua `api_core/integrations/client.py`.

Phân loại yêu cầu theo nhóm: [PHAN_LOAI_YEU_CAU.md](PHAN_LOAI_YEU_CAU.md).
