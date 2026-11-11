# Rà soát tài liệu `workspace/` (05/11/2026)

Gửi AI đang viết tài liệu trong `workspace/`. Chủ dự án phân công như sau:

- **AI viết chính:** soạn và sửa nội dung trong `workspace/`.
- **Claude Code (người rà):** đối chiếu tài liệu với mã nguồn và CSDL thật, sửa chỗ sai, bổ sung chỗ thiếu.

Đọc file này trước mỗi đợt viết.

## Cách phối hợp

- Người rà chỉ sửa trực tiếp file đã đứng yên ít nhất 2 phút. Mọi sửa đều ghi vào "Nhật ký" kèm tên file và mục.
- Nếu người rà đang sửa một file, file đó được ghi vào mục "Đang khoá". Đừng sửa file đó cho tới khi khoá được gỡ.
- Câu hỏi về nghiệp vụ hoặc kỹ thuật ghi vào "Hỏi đáp". Người rà trả lời ngay bên dưới.

## Nguồn sự thật (khi tài liệu và nguồn khác nhau, nguồn thắng)

| Chủ đề | Nguồn |
|---|---|
| Bảng, cột, ràng buộc của schema `eas` | `database/migrations/*.sql` (mới nhất: 14–17) |
| Nhóm và loại yêu cầu | `eas.request_group` (12 nhóm), `eas.request_menu_item`, `api_core/catalog/catalog_v2.json` |
| Hệ thống ngoài `mock_*` | Chỉ truy cập qua Mock Systems API (`api_core/mock_sources/service_urls.py`, `api_core/integrations/client.py`). EAS không đọc bảng `mock_*` trực tiếp |
| Vai trò CSDL | `eas_api`, `eas_worker`, `eas_mock` (xem `AGENTS.md`, mục "Project notes") |
| API | `api_core/*/urls.py` |
| Giao diện | `web_client/src` (đã làm lại sáng 05/11), `web_admin` |
| AI và OCR | `ai_service/` (PaddleOCR 3.x từ 05/11) |
| Kiểm toán bảo mật | `docs/KIEM_TOAN_CODE_DATA_2026-11-04.md` |

## Đang khoá

(trống)

## Phát hiện của người rà

Đợt rà 1 (08:55). Tài liệu trong `workspace/` viết ngày 04/11, trước các thay đổi sau:

- schema v2 và migration 14–17;
- danh mục 12 nhóm yêu cầu;
- hệ thống ngoài chỉ truy cập qua API;
- kiểm toán bảo mật S4–S8 và PaddleOCR 3.x;
- giao diện làm lại ngày 05/11.

Dưới đây là các chỗ đã lỗi thời. Cột "Trạng thái" ghi `mở` (chưa ai sửa), `AI viết` (bên viết chính nhận sửa) hoặc `người rà` (người rà đã sửa).

| # | Chỗ sai | File (dòng) | Sự thật hiện nay (nguồn) | Trạng thái |
|---|---|---|---|---|
| W01 | Nhóm yêu cầu cũ `FINANCE, RESOURCE, FACILITY, WORK, HR, TIME, IT, LEGAL, SALES, ADMIN` (CHECK `request_type_category_valid`) | `bao_cao_hoan_chinh/10_CHUONG_2_3_8_THIET_KE_BANG.md:117`, `analysis_design/07_THIET_KE_CO_SO_DU_LIEU.md:111` | Migration 17 bỏ CHECK này. Nay có 12 nhóm trong bảng `eas.request_group`: `ABSENCE, WORKTIME, BORROW, PROVISION, PAYMENT, PROCUREMENT, PEOPLE, SUPPORT, WORK, LEGAL, SALES, ASSET`. Menu 61 mục nằm trong `eas.request_menu_item` (`docs/PHAN_LOAI_YEU_CAU.md`, `catalog_v2.json`) | AI viết (đã sửa) |
| W02 | EAS đọc `mock_*` trực tiếp, hoặc gateway mở `/api/v1/mock/*` | `bao_cao_hoan_chinh/12_CHUONG_3_XAY_DUNG_TRIEN_KHAI.md:55`, `bao_cao_hoan_chinh/03_CHUONG_2_1_PHAN_TICH_YEU_CAU.md:79` (UC24), `phan_tich_thiet_ke/01_PHAN_TICH_YEU_CAU.md:72`, `phan_tich_thiet_ke/09_THIET_KE_CO_SO_DU_LIEU.md:129`, `analysis_design/04_SO_DO_SEQUENCE.md:228`, `analysis_design/07_THIET_KE_CO_SO_DU_LIEU.md:518` | `mock_*` là hệ thống ngoài. EAS chỉ gọi Mock Systems API (`/mock-api/v1/...`, header `X-Integration-Secret`, dịch vụ `mock_systems`, vai trò CSDL `eas_mock`). Vai trò `eas_api`/`eas_worker` không có quyền trên `mock_*`. Gateway không mở mock (`docs/TICH_HOP_HE_THONG_NGOAI.md`) | AI viết (đã sửa) |
| W03 | Gateway chuyển `/ai/*` và Swagger ra ngoài | `bao_cao_hoan_chinh/12_CHUONG_3_XAY_DUNG_TRIEN_KHAI.md:55`, `bao_cao_hoan_chinh/02_CHUONG_1_TONG_QUAN.md:217`, `analysis_design/06_SO_DO_KIEN_TRUC_DU_LIEU_PHAN_TAN.md:110,176` | Đã gỡ (S6). Trình duyệt và mobile gọi AI qua `api_core` (`/api/v1/ai/*`). AI service chỉ nhận lời gọi nội bộ có `X-Internal-Secret` | người rà (đã sửa) |
| W04 | Bảng `mock_hr.attendance` "chưa có trên live", migration mock 004 | `phan_tich_thiet_ke/09_THIET_KE_CO_SO_DU_LIEU.md:130,156`, `phan_tich_thiet_ke/12_SO_LECH_VA_QUYET_DINH.md:102` (E02), `bao_cao_hoan_chinh/06_CHUONG_2_2_9_ACTIVITY.md:118` | Migration `004_hrm_attendance.sql` đã xoá. Trạng thái vắng mặt và giờ làm lấy từ migration 16 (`worker_delegation`, giờ hành chính 08:00–12:00 và 13:30–17:30, trạng thái `DANG_LAM/NGHI_LAM/CONG_TAC/NGOAI_GIO`). Xem `docs/THIET_KE_SCHEMA_EAS_V2.md` §7 | người rà (đã sửa) |
| W05 | Bảng sai lệch G01–G03 (gateway `/ai/`, `@supabase/supabase-js`, Elasticsearch) còn ở trạng thái "cần làm" | `phan_tich_thiet_ke/12_SO_LECH_VA_QUYET_DINH.md:123-125`, `phan_tich_thiet_ke/06_SO_DO_KIEN_TRUC_VA_THANH_PHAN.md:21,165` | Đã xử lý ngày 05/11: gỡ `/ai/` khỏi gateway, xoá `supabase.js` và dependency, xoá Elasticsearch khỏi compose | người rà (đã sửa) |
| W06 | PaddleOCR không ghi phiên bản, và bị xếp "hướng phát triển" | `bao_cao_hoan_chinh/02_CHUONG_1_TONG_QUAN.md:84,119,253`, `bao_cao_hoan_chinh/12_CHUONG_3_XAY_DUNG_TRIEN_KHAI.md:24` | `paddlepaddle 3.3.1`, `paddleocr 3.7.0`, `paddlex 3.7.2`. Mặc định có trong image (`ENABLE_PADDLE_OCR=true`), model lưu ở `~/.paddlex`. Dự phòng: Gemini Vision | người rà (đã sửa) |
| W07 | Thiếu nội dung mới | các chương thiết kế CSDL và thiết kế hệ thống | Nên bổ sung: schema `eas_archive` (lưu giá trị cột trước khi gộp), bảng `eas.request_group` và `eas.request_menu_item`, cơ chế mượn tài nguyên qua API (duyệt trước thắng, BOD ưu tiên), circuit breaker `eas.mock_apis`, dọn `idempotency` | AI viết (đã sửa) |

### Dữ kiện đã kiểm cho W01, W02, W07 (người rà soạn, dùng khi viết)

**W01: danh mục yêu cầu.** Nguồn: migration 17 §4 và `docs/PHAN_LOAI_YEU_CAU.md` §3–4.

- Có 12 nhóm, theo thứ tự `sort_order`:
  1. `ABSENCE` Vắng mặt
  2. `WORKTIME` Chấm công & giờ làm
  3. `BORROW` Mượn & đặt chỗ
  4. `PROVISION` Cấp phát & quyền truy cập
  5. `PAYMENT` Tạm ứng & thanh toán
  6. `PROCUREMENT` Mua sắm & ngân sách
  7. `PEOPLE` Nhân sự & chế độ
  8. `SUPPORT` Hỗ trợ & sự cố
  9. `WORK` Công việc & dự án
  10. `LEGAL` Văn bản & pháp chế
  11. `SALES` Kinh doanh & marketing
  12. `ASSET` Kho & tài sản cố định
- Bảng `eas.request_group(code PK varchar(20), name, description, sort_order)`.
- Bảng `eas.request_menu_item(code PK, group_code FK → request_group, type_code FK → request_type, label, preset jsonb object, sort_order, is_active)`. Có chỉ mục `(group_code, sort_order)`.
- `eas.request_type.category` là khoá ngoại tới `request_group.code`. CHECK `request_type_category_valid` (10 mã cũ) **đã bỏ**. Giá trị cũ được lưu vào `eas_archive.dropped_column_value` với `column_name = 'category_before_17'`.
- Menu có **61 mục**:
  - 56 loại hiện trực tiếp: 58 loại đang hoạt động, trừ `ATTENDANCE_ADJUSTMENT` và `LEAVE`;
  - 5 lựa chọn đặt sẵn: Đi muộn, Về sớm, Quên chấm công, Nghỉ có lương, Nghỉ không lương.
- `LEAVE` có trường `leave_kind` ∈ {`CO_LUONG`, `KHONG_LUONG`}. Chỉ nghỉ có lương bị trừ quỹ phép.
- Một loại có thể nằm ở hai nhóm qua preset. Ví dụ `ATTENDANCE_ADJUSTMENT` vừa ở `ABSENCE` vừa ở `WORKTIME`.

**W02: hệ thống ngoài.** Nguồn: `docs/TICH_HOP_HE_THONG_NGOAI.md` §0, §2, §4; `api_core/integrations/client.py`; `api_core/mock_sources/service_urls.py`.

- Dịch vụ `mock_systems` chạy cùng mã `api_core` với `EAS_SERVICE=mock`, đường dẫn gốc `/mock-api/v1/`. Header `X-Integration-Secret` (`EAS_MOCK_API_SECRET`). Không mở qua gateway.
- Vai trò CSDL: `eas_mock` (NOLOGIN) và `eas_mock_login`. Chỉ hai vai trò này có quyền trên `mock_*`, theo policy RLS `mock_service`. `eas_api` và `eas_worker` không có quyền.
- Kiểm tra sức khoẻ: `mock_systems_api_reachable`, `eas_role_has_no_mock_table_access`.
- Nhóm endpoint:
  - `hr/` (departments, employees, leave-balances, leave-usages);
  - `assets/` (categories, availability, loans);
  - `facilities/` (resources, availability, reservations);
  - `allocations`;
  - `it/` (applications, access-roles, user-access);
  - `finance/` (expense-categories, budgets, commitments);
  - `catalogue/<resource>` (mua sắm, CRM, công tác).
- Luồng mượn và đặt chỗ (§4.2):
  1. Lúc gửi: kiểm tra `availability`.
  2. Duyệt bước cuối: `POST reservations` hoặc `POST loans`, idempotent theo `source_request_id`. **Đơn duyệt trước thắng**; đơn duyệt sau tự động REJECTED; gửi khi đã hết chỗ thì bị 409.
  3. BGĐ được ưu tiên: thu hồi qua `holders` rồi `cancel`. Phía DB dùng GUC `eas.preempt_request_id` trong `guard_request`.
- Ghi ra hệ thống ngoài:
  - ITSM: `POST /it/user-access`, có `expires_at`;
  - ERP: `POST /finance/commitments`; ngân sách còn lại = `approved − committed − spent`, kiểm cả `daily_limit_minor`.

**W07: nội dung cần bổ sung.**

- `eas_archive`: schema chỉ đọc cho DBA (migration 15). Ứng dụng không truy cập. Bảng `eas_archive.dropped_column_value(table_name, row_id, column_name, value jsonb, archived_at)`, khoá chính `(table_name, row_id, column_name)`. Lưu giá trị các cột bị gộp hoặc bỏ để rollback được.
- Circuit breaker: `eas.mock_apis.is_enabled` (admin bật hoặc tắt từng hệ thống). Client kiểm tra trước mọi lời gọi.
- Đối soát của worker, mỗi vòng (§4.4):
  1. Trả lại phần mượn đã hết hạn.
  2. Huỷ giữ chỗ "mồ côi": có `source_request_id` nhưng đơn EAS không ở trạng thái đã duyệt, sau 10 phút.
- Dọn `idempotency`: `process_idempotency_cleanup(batch_size=500)` trong `api_core/worker.py`. Sau `expires_at` thì xoá `response_body`; sau `tombstone_until` thì xoá dòng.
- Trạng thái làm việc: `eas.get_user_working_status` (migration 16), trả `DANG_LAM`, `NGHI_LAM`, `CONG_TAC` hoặc `NGOAI_GIO`.

### Rà đợt 1 của AI viết: `bao_cao_hoan_chinh/10_CHUONG_2_3_8_THIET_KE_BANG.md` (09:00)

**Đạt.** Các điểm sau đúng với migration:

- W01: `request_type.category` là khoá ngoại tới `request_group`; đã bỏ CHECK 10 mã; có mục 2.11.3 `request_group` và 2.11.4 `request_menu_item`.
- 9 view bị gỡ ở migration 15 (dòng 104–112).
- Các cột `risk_weight`/`approval_level` của `request`, `workflow_instance`, `config_release` và cột `app_user.username` đã được lưu vào `eas_archive.dropped_column_value` rồi bỏ (migration 15, dòng 194–207).

**Cần sửa** (file đang do AI viết khoá, nên người rà chỉ ghi lại):

| # | Chỗ | Vấn đề | Sửa |
|---|---|---|---|
| R1 | §2.16.16 `eas.system_versions_changelog`, §2.16.19 `eas.workflow_categories` | Hai bảng này đã chuyển ra khỏi `eas` ở migration 15 (`SET SCHEMA eas_archive`; `workflow_categories` được đổi tên thành `workflow_categories_eas`). Tài liệu vẫn để chúng trong danh sách bảng `eas`, kèm số dòng "live". | Bỏ hai mục khỏi chương bảng `eas`. Chuyển sang mục "Kho lưu trữ `eas_archive`" với tên đúng `eas_archive.system_versions_changelog` và `eas_archive.workflow_categories_eas`. `work_handover` cũng đã sang `eas_archive` (migration 15, dòng 179). |
| R2 | Dòng 4: "**52 bảng hoạt động**" | File có 51 mục `### … eas.…`, trong đó 2 bảng (R1) không còn ở `eas`. Con số không khớp. | Đếm lại sau khi làm R1, hoặc chạy trên bản sao local: `SELECT count(*) FROM information_schema.tables WHERE table_schema='eas' AND table_type='BASE TABLE'`. Container `eas-pg-e2e` hiện đang tắt, nên người rà chưa chạy được. |

### Rà đợt 2 của AI viết: 14 file (09:01–09:09)

**Đạt:**

- Phần người rà đã sửa ở 02, 06, 09, 12 vẫn được giữ nguyên.
- Không còn chỗ nào mô tả EAS đọc thẳng `mock_*`, gateway mở `/api/v1/mock/`, hay danh mục 10 nhóm cũ. Các dòng còn nhắc đến đều đã được ghi là lịch sử hoặc đã xử lý.
- Endpoint Mock Systems API được trích (`hr/leave-balances`, `hr/leave-usages`, `assets/categories`, `facilities/resources`, `allocations`, `it/user-access`, `finance/commitments`) đều có trong `service_urls.py`.
- Tài liệu ghi `allocations/{cancel|return}`, khớp với `allocation_action` (chỉ nhận `cancel` và `return`).
- R1 và R2 (file 10) **vẫn mở**.

**Phát hiện mới.** Người rà đã đối chiếu tự động mọi đường dẫn `/api/v1/...` trong `workspace/*.md` với URLconf Django: 97 đường dẫn, 55 không khớp. Trừ đi các tiền tố và các chỗ đã được ghi chú đúng, còn **44 endpoint không tồn tại**, toàn bộ nằm trong `analysis_design/` (file 01, 04, 08, 10).

| # | Vấn đề | Sửa |
|---|---|---|
| R3 | `analysis_design/01` (dòng 84–90) và `analysis_design/10` (dòng 52–57 trở đi) dùng tiền tố bịa `/api/v1/workflow/...`, có dấu `/` cuối. | Thay theo bảng ánh xạ bên dưới. Code không có tiền tố `workflow/` và không có `/` cuối. |
| R4 | `analysis_design/04_SO_DO_SEQUENCE.md` có 20 đường dẫn sai tên. | Theo bảng ánh xạ. |
| R5 | `analysis_design/08` dòng 99: `/api/v1/system/maintenance-state`. | Đổi thành `GET /api/v1/system/maintenance`. Bật và tắt bảo trì: `POST .../start` và `POST .../complete`. |
| R6 | Thuật ngữ "16 nhóm" dùng cho bộ phân loại NLP (`12_CHUONG_3...:215`, `14_PHU_LUC.md:119`) dễ nhầm với 12 nhóm yêu cầu. | Viết là "16 nhãn phân loại của mô hình NLP" và ghi rõ đây không phải 12 nhóm menu (vấn đề F04 ở `12_SO_LECH`). |

Bảng ánh xạ (nguồn: `api_core/*/urls.py`; đã kiểm bằng `django.urls.resolve`):

| Tài liệu đang ghi | Route thật |
|---|---|
| `/workflow/requests/` (tạo hoặc nộp) | `POST /api/v1/requests` (tạo nháp), `POST /api/v1/requests/{id}/submit` hoặc `POST /api/v1/requests/submit` |
| `/requests/{id}/draft`, `/requests/{id}/resubmit` | `PATCH /api/v1/requests/{id}` (sửa nháp); nộp lại bằng `POST /api/v1/requests/{id}/submit` (tạo revision mới, xem `/revisions`) |
| `/workflow/requests/{id}/approval-decisions/`, `/requests/{id}/decision` | `POST /api/v1/requests/{id}/approval-decisions` |
| `/workflow/requests/{id}/claims/`, `/requests/{id}/claim` | `POST /api/v1/requests/{id}/claim` |
| `/workflow/requests/{id}/execution-submit/`, `/requests/{id}/submit-result` | `POST /api/v1/requests/{id}/execution/start`, rồi `POST .../execution/submit` |
| `/workflow/requests/{id}/acceptance/`, `/requests/{id}/accept` | `POST /api/v1/requests/{id}/acceptance-decisions` (`GET .../acceptance` để xem) |
| `/workflow/requests/{id}/issue-report/`, `/requests/{id}/report-issue` | `POST /api/v1/requests/{id}/execution/issues` (hoặc `.../issues`) |
| `/workflow/requests/{id}/cancellation/` | `POST /api/v1/requests/{id}/cancel` (`/withdraw` là bí danh) |
| `/workflow/requests/{id}/reassign/`, `/admin/requests/{id}/reassign-step` | `POST /api/v1/requests/{id}/reassign` |
| `/workflow/requests/{id}/history/` | `GET /api/v1/requests/{id}/history` |
| `/workflow/attachments/upload/`, `/attachments/upload` | `POST /api/v1/request-drafts/{id}/attachments` (lúc soạn), `POST /api/v1/requests/{id}/attachments`, `POST .../execution/attachments` |
| `/workflow/config/request-types/` | `GET /api/v1/request-types` |
| `/workflow/config/releases/` | `POST /api/v1/config-releases`, rồi `.../{release_id}/validate` và `.../{release_id}/publish` |
| `/workflow/audit/verify/`, `/audit/verify-chain` | `GET /api/v1/requests/{id}/audit/verify` (từng hồ sơ). Kiểm toàn chuỗi: lệnh `python manage.py audit_verify` |
| `/workflow/privacy/purge/`, `/privacy/export-request` | **Không có API.** Dùng lệnh quản trị `python manage.py privacy_case` (có legal hold) |
| `/workflow/ai/revoke-approval/`, `/requests/{id}/revoke-ai-approval` | `POST /api/v1/requests/{id}/ai-approval/revoke` |
| `/admin/operations/blocked-tasks` | `GET /api/v1/ops/requests` (cổng admin); phát lại sự kiện: `POST /api/v1/ops/outbox/{event_id}/replay` |
| `/admin/requests/{id}/resolve-issue` | Không có route riêng. Xử lý sự cố qua `/execution/issues` và `/reassign` |
| `/admin/users/{id}/roles/APPROVER` | `/api/v1/admin/{kind}/{record_id}` (thay đổi chung qua `administration.service.mutate`). Quyền theo module: `/api/v1/admin/rbac/user-permission` |
| `/system/maintenance-state` | `GET /api/v1/system/maintenance` |

Các đường dẫn sau trong `analysis_design/` là **đúng**, giữ nguyên: `auth/login`, `auth/me`, `delegations`, `requests/submit`, `requests/{id}`, `requests/{id}/withdraw`, `admin/rbac/matrix`, `admin/ai-engine/retrain`.

### Rà đợt 3 của AI viết: 7 file (09:13–09:16)

**Đạt.** Người rà đã kiểm từng điểm sau với code:

- Mã `409 INTEGRATION_UNAVAILABLE` có trong `integrations/client.py`.
- `VERSION_CONFLICT` có trong `workflow/constants.py`.
- `TOP_LEVEL_APPROVER` và `TOP_LEVEL_SKIPPED` có trong `domain/routing.py`.
- Gọi `POST /mock-api/v1/hr/leave-usages` cho `LEAVE` có lương: có trong `integrations/requests.py`.
- BGĐ thu hồi chỉ áp dụng cho `READY_FOR_EXECUTION`, `IN_PROGRESS` và `COMPLETED`, khớp `PREEMPTABLE_STATUSES` trong `resource_allocation.py`. Lý do `RESOURCE_PREEMPTED` có trong `worker.py`.
- Các tên test `NoDirectMockAccessTests`, `TaxonomyTests`, `submit_requires_idempotency_key_before_service`, `domain_conflict_uses_stable_error_envelope` đều có thật.
- ERD có `request_group` và `request_menu_item`. Đã ghi `work_handover` được gộp vào `approval_delegation`.

**Cần sửa:**

| # | Chỗ | Vấn đề | Sửa |
|---|---|---|---|
| R7 | `bao_cao_hoan_chinh/04...:169`, `05...:210`, `07...:63`; `phan_tich_thiet_ke/05...:137` | Mã lỗi `STATE_CONFLICT` không đúng với luồng hồ sơ. Code dùng `REQUEST_STATE_CONFLICT` (`workflow/constants.py`: `ERR_STATE_CONFLICT`). `STATE_CONFLICT` chỉ có ở `insights.py:637`, ngoài luồng hồ sơ. | Thay bằng `409 REQUEST_STATE_CONFLICT`. |
| R2 | `bao_cao_hoan_chinh/09_CHUONG_2_3_7_ERD.md:3` | Lặp lại con số "52 bảng (30 lõi + 22 mở rộng)" chưa được kiểm. | Sửa cùng R2 ở file 10. |

### Rà đợt 4 của AI viết: `analysis_design/` 01, 04, 08, 10; `12`, `14_PHU_LUC` (09:20)

- **R3, R4, R5 đã sửa.** Chạy lại bộ đối chiếu: tài liệu nay trích 103 đường dẫn `/api/v1/...`. 11 đường dẫn không khớp route đều không phải lỗi:
  - là tiền tố (`/ai/`, `/internal/`, `/admin/`);
  - là đường dẫn được ghi rõ "đã gỡ" hoặc "không tồn tại" (`/api/v1/mock/`, `reports/sla-compliance`);
  - là đề xuất tương lai (`/api/v1/ai/ocr`, mục A5);
  - là cách viết gộp `maintenance/{start,complete}`.
  Không còn endpoint bịa.
- **R6 đã sửa:** đổi thành "16 nhãn phân loại của mô hình NLP".
- **Còn mở:**
  - ~~R1~~: đã sửa. Hai mục được thay bằng `eas.privacy_case_approval`, `eas.sla_escalation_policy` và `eas.business_holiday`. Người rà đã kiểm: cả ba bảng có ở migration 14.
  - R2: con số 52 nay được giải thích là 50 bảng nghiệp vụ cộng 2 bảng Django (`django_migrations`, `django_session`). Có thể chấp nhận, nhưng còn hai việc:
    - chưa kiểm được trên DB vì bản sao local đang tắt;
    - phải xác nhận hai bảng Django thật sự nằm trong schema `eas`, không phải `public`, bằng `SELECT table_schema FROM information_schema.tables WHERE table_name LIKE 'django_%'`.
  - R7: `STATE_CONFLICT` → `REQUEST_STATE_CONFLICT`, ở 4 chỗ.

### Rà đợt 5 (09:27): R2 đạt, R7 còn 3 chỗ

- **R2 đạt.** Cách tính nay khớp nhau: 49 − 2 (đã dời sang `eas_archive`) + 3 (migration 14) + 2 (migration 17) = 52. File có 51 mục, vì một mục gộp `sla_escalation_policy` và `business_holiday`. Con số gốc 49 chưa đếm được trên DB, vì bản sao local đang tắt.
- **R7 đã sửa ở `04`, `05`, `07:63` và `phan_tich_thiet_ke/05:137`. Còn sót 3 chỗ:**
  - `bao_cao_hoan_chinh/07_CHUONG_2_2_10_SEQUENCE.md` dòng 188 và 189;
  - `phan_tich_thiet_ke/05_SO_DO_SEQUENCE.md` dòng 179.

  Đổi `STATE_CONFLICT` thành `REQUEST_STATE_CONFLICT`.
- Đối chiếu endpoint: 103 đường dẫn, không còn endpoint bịa.

### Nghiệm thu (09:33): ĐẠT

- W01–W07 và R1–R7 đã xử lý xong. Không còn `STATE_CONFLICT` sai.
- Đối chiếu endpoint: 103 đường dẫn, không còn endpoint bịa.
- File 10 có 52 mục `eas.*` và Bảng 2.17 `eas_archive`. Các nội dung W07 đều đã có:
  - `dropped_column_value`;
  - `mock_apis.is_enabled`;
  - dọn `idempotency`;
  - `get_user_working_status`;
  - `source_request_id`;
  - ưu tiên BGĐ;
  - huỷ giữ chỗ "mồ côi".
- ~~Đếm lại số bảng trên DB~~. Chủ dự án đã chạy truy vấn đếm (05/11): schema `eas` có **52** bảng `BASE TABLE`, khớp với tài liệu.

Đề xuất chia việc:

- **AI viết:** nhận W01, W02, W07, vì phải viết lại đoạn văn và sơ đồ.
- **Người rà:** sửa W03, W04, W05, W06, vì là sửa câu hoặc dòng cụ thể.

Nếu AI viết đang mở file nào trong danh sách của người rà, hãy ghi vào "Hỏi đáp". Người rà sẽ chờ.

## Hỏi đáp

(AI viết chính ghi câu hỏi ở đây.)

## Nhật ký

| Thời gian | Ai | File / mục | Việc |
|---|---|---|---|
| 05/11 08:51 | Người rà | `phan_tich_thiet_ke/12_SO_LECH_VA_QUYET_DINH.md` E02, G01–G03 | Đánh dấu đã xử lý 05/11, kèm nguồn |
| 05/11 08:51 | Người rà | `phan_tich_thiet_ke/09_THIET_KE_CO_SO_DU_LIEU.md` §5 (ghi chú Mock Systems API, dòng mock_hr, attendance), §7 L2 | Cập nhật theo migration 16–17 |
| 05/11 08:51 | Người rà | `phan_tich_thiet_ke/06_SO_DO_KIEN_TRUC_VA_THANH_PHAN.md` §1 (Elasticsearch, supabase-js, PaddleOCR 3.x), dòng gateway `/ai/` | Đã xử lý 05/11 |
| 05/11 08:51 | Người rà | `bao_cao_hoan_chinh/02_CHUONG_1_TONG_QUAN.md` (OCR 3.x, Swagger, bảng công nghệ), `bao_cao_hoan_chinh/12_CHUONG_3_XAY_DUNG_TRIEN_KHAI.md` (phiên bản OCR, cổng API) | Sửa theo S6, S7 |
| 05/11 08:52 | Người rà | `bao_cao_hoan_chinh/06_CHUONG_2_2_9_ACTIVITY.md` ghi chú vắng mặt (AD-03) | Viết lại theo `_absence_status`: ủy quyền → nghỉ phép đã duyệt chuyển quản lý; công tác không tính vắng (D2) |
| 05/11 08:59 | Người rà | file phối hợp | Thêm bảng dữ kiện đã kiểm cho W01, W02, W07 |
| 05/11 09:01 | Người rà | rà `bao_cao_hoan_chinh/10_...THIET_KE_BANG.md` | Đạt W01; ghi R1 (2 bảng đã sang `eas_archive` vẫn liệt kê trong `eas`), R2 (52 bảng không khớp) |
| 05/11 09:12 | Người rà | rà đợt 2 (14 file) + đối chiếu endpoint tự động | Đạt W01/W02; R1–R2 còn mở; mới: R3–R5 (44 endpoint bịa trong `analysis_design/`, có bảng ánh xạ), R6 ("16 nhóm" NLP) |
| 05/11 09:19 | Người rà | rà đợt 3 (7 file: quy trình, thiết kế HT, ERD, kiểm thử) | Đạt các mã lỗi, endpoint, test; mới: R7 (`STATE_CONFLICT` → `REQUEST_STATE_CONFLICT`), R2 lan sang file 09 |
| 05/11 09:24 | Người rà | rà đợt 4 (analysis_design, 12, 14) | R3–R6 đã sửa, 0 endpoint bịa; còn R1, R2, R7 |
| 05/11 09:25 | Người rà | kiểm R1 | Đã sửa; R2 chấp nhận tạm, cần xác nhận schema của 2 bảng Django |
| 05/11 09:29 | Người rà | rà đợt 5 | R2 đạt (52 = 49 − 2 + 3 + 2); R7 còn 3 chỗ (07:188–189, phan_tich 05:179) |
| 05/11 09:31 | AI viết chính | `bao_cao_hoan_chinh/*`, `phan_tich_thiet_ke/*`, `analysis_design/*` | Hoàn tất W01, W02, W07 và toàn bộ R1–R7: tách đủ 52 mục bảng `eas.*` + Bảng 2.17 `eas_archive` trong `10_CHUONG_2_3_8_THIET_KE_BANG.md`, gỡ các cột đã bỏ (`risk_weight`, `approval_level`, `username`), sửa nốt 3 chỗ `REQUEST_STATE_CONFLICT` (`07:188–189`, `phan_tich/05:179`), mở khoá |
| 05/11 09:34 | Người rà | nghiệm thu | Đạt toàn bộ W01–W07, R1–R7 |
| 05/11 09:39 | Chủ dự án | đếm bảng `eas` trên DB | 52, khớp tài liệu. Đóng R2 |
