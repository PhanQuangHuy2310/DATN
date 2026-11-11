# Tích hợp EAS với các hệ thống ngoài (schema `mock_*`) — 04/11/2026

Người soát: Data engineer (toàn quyền xử lý dữ liệu theo chủ dự án).
Dữ liệu trong tài liệu được đọc trực tiếp trên Supabase live ngày 04/11/2026 (chỉ đọc).

## 0. Nguyên tắc

8 schema `mock_*` **không thuộc EAS**. Mỗi schema giả lập một hệ thống riêng của doanh nghiệp: HRM, quản lý tài sản, quản lý toà nhà, CRM, mua sắm, ITSM, tài chính và công tác.

Ba quy tắc:

1. EAS **chỉ lấy hoặc ghi dữ liệu của chúng bằng cách gọi API**. Không câu SQL nào của EAS (`api_core`, worker, `ai_service`) được đọc hoặc ghi bảng `mock_*`.
2. Mỗi hệ thống ngoài là **nguồn sự thật** cho dữ liệu của nó. EAS chỉ được lưu **bản tham chiếu** khi có lý do kỹ thuật rõ ràng (§3), và phải ghi rõ nguồn cùng cách đồng bộ.
3. Nếu hệ thống ngoài lỗi hoặc bị tắt (circuit breaker trong `eas.mock_apis`), EAS báo lỗi rõ ràng và không tự đoán dữ liệu.

## 1. Hiện trạng: dữ liệu của mỗi schema và mức sử dụng thật

| Schema (hệ thống) | Dữ liệu cung cấp (dòng trên live) | EAS dùng thật chưa? |
|---|---|---|
| `mock_hr` (HRM) | Phòng ban (8), nhân viên (55), quỹ phép theo năm ANNUAL/SICK/PARENTAL (108) | **Không.** 55 nhân viên `@example.test` không khớp tài khoản nào trong 136 tài khoản EAS `@eas.com` (khớp theo email: 0, theo mã: 0). Mã phòng ban lệch (`HQ/IT/SALES` so với `BOD/TECH/BIZ`). Không đơn nghỉ nào kiểm tra quỹ phép |
| `mock_assets` (quản lý tài sản) | Nhóm thiết bị (8), thiết bị (45), phiếu mượn (15) | Đơn mượn thiết bị (mới làm hôm nay) **ghi thẳng SQL** vào bảng, **sai kiến trúc** |
| `mock_facilities` (toà nhà) | Chi nhánh, phòng họp / xe / bàn / chỗ đậu (18), lịch đặt | Như trên: đặt phòng, mượn xe **ghi thẳng SQL** |
| `mock_crm` | Khách hàng (20), hợp đồng (18), ticket hỗ trợ | **Không.** Đơn chiết khấu đặc biệt nhập tên khách hàng tự do |
| `mock_procurement` | Nhà cung cấp (15), danh mục hàng (35), đơn đặt hàng | **Không.** Đơn mua sắm nhập tên hàng tự do |
| `mock_it` (ITSM) | Ứng dụng (12), vai trò truy cập (22), dịch vụ IT (12), quyền đã cấp | **Không.** Đơn cấp quyền dùng danh sách cứng 8 ứng dụng / 7 vai trò, **không trùng** mã nào của ITSM (vd `PRODUCTION_DB`, `SHOPEE_SC` không tồn tại) |
| `mock_finance` (ERP tài chính) | Ngân sách theo trung tâm chi phí (8), loại chi phí kèm hạn mức (10) | **Không.** Đơn thanh toán dùng 5 loại chi phí cứng (`TIEP_KHACH`…) khác 10 mã ERP (`CLIENT`, `MEAL`…). Không kiểm tra ngân sách |
| `mock_travel` | Định mức công tác theo cấp bậc (10), phương án vé / khách sạn (18) | **Không** |

Ngoài bảng trên còn 3 điểm có vấn đề:

- `api_core/mock_sources` phục vụ API đọc `/api/v1/mock/...`, nhưng **không luồng nghiệp vụ nào gọi** các API này. API chạy chung tiến trình và chung role DB `eas_api` với EAS, nên EAS vẫn đọc được bảng mock trực tiếp.
- `ai_service` đọc **bản chụp JSON** (`ai_service/data/mock/*.json`) để tra quỹ phép, phòng họp và ngân sách. Đây là bản sao thứ ba, đã cũ, và không phản ánh lịch mượn mới.
- Lệnh `sync_employee_codes` đọc thẳng `mock_hr.employee_directory` bằng SQL.

## 2. Kiến trúc mục tiêu

```
Trình duyệt / mobile ──► EAS API (api_core) ──HTTP + X-Integration-Secret──► Mock Systems API
                          │  role DB: eas_api                                 │  role DB: eas_mock
                          ▼                                                   ▼
                     schema eas  (KHÔNG có quyền vào mock_*)            schema mock_* (8 hệ thống)
EAS worker ──HTTP──► Mock Systems API     ai_service ──HTTP──► Mock Systems API
```

- **Mock Systems API** là một tiến trình riêng: dịch vụ `mock_systems` trong docker-compose, cùng image `api_core`, chạy với `EAS_SERVICE=mock`.
  - Chỉ phục vụ `/mock-api/v1/<hệ thống>/...`.
  - Dùng role DB riêng `eas_mock`, là role duy nhất được đọc và ghi `mock_*`.
  - Xác thực bằng header `X-Integration-Secret` (biến `EAS_MOCK_API_SECRET`).
- **EAS** gọi qua một client duy nhất là `api_core/integrations/client.py`. Client:
  - đặt timeout 5 giây;
  - tôn trọng cờ tắt tích hợp `eas.mock_apis.is_enabled`;
  - đổi lỗi thành `INTEGRATION_UNAVAILABLE` (503).
- **Quyền DB:** `eas_api` và `eas_worker` bị thu hồi mọi quyền trên `mock_*`. Muốn đọc lén cũng không được.
- **Trình duyệt** không gọi hệ thống ngoài. Danh sách chọn trên biểu mẫu (phòng, xe, ứng dụng…) đi qua EAS: `GET /api/v1/integrations/options?type_code=…`.
- **Ghi sang hệ thống ngoài có bù trừ:** mỗi lệnh ghi gửi `source_request_id` = id đơn EAS, và API xử lý trùng lặp theo khoá này. Worker chạy đối soát định kỳ (§4.4) để huỷ phần giữ chỗ "mồ côi" khi giao dịch EAS bị huỷ sau lúc gọi API.

## 3. Dữ liệu EAS trùng hoặc tham chiếu hệ thống ngoài

| Dữ liệu trong `eas` | Tương ứng ở hệ thống ngoài | Quyết định | Mục đích giữ bản tham chiếu và cách đồng bộ |
|---|---|---|---|
| `department` (code, name, parent) | `mock_hr.department` | **Giữ làm bản tham chiếu** | Khoá ngoại của người dùng, phân quyền theo phòng, định tuyến duyệt, audit. Các thứ này cần dữ liệu cục bộ, toàn vẹn và nhanh. Đồng bộ một chiều HRM → EAS qua `GET /hr/departments`. Mã phòng là khoá chung |
| `app_user`: họ tên, phòng ban, quản lý, mã NV, đang làm hay đã nghỉ | `mock_hr.employee` | **Giữ.** Thêm `employee_code` làm khoá liên kết | Đăng nhập, mật khẩu, vai trò là dữ liệu riêng của EAS. Thuộc tính nhân sự được đồng bộ từ HRM (`GET /hr/employees`) bằng lệnh `sync_hr_directory`. EAS không tự sửa các thuộc tính này |
| `user_leave_and_trips` | HRM: quỹ phép đã dùng | **Giữ.** Đây là kết quả duyệt của EAS | EAS là nơi duyệt. Bảng ghi đơn nghỉ/công tác đã duyệt, dùng cho trạng thái làm việc và phân công thay. Khi đơn nghỉ có lương được duyệt, EAS gọi `POST /hr/leave-usages` để trừ quỹ phép bên HRM |
| `mock_apis` | Không có | **Giữ** | Danh mục cổng tích hợp và cờ tắt khẩn cấp (circuit breaker). Đây là cấu hình của EAS, không phải dữ liệu hệ thống ngoài |
| Danh sách cứng trong biểu mẫu: `app_code`, `requested_role`, `expense_category` | ITSM, ERP tài chính | **Bỏ danh sách cứng** | Trường trở thành chuỗi tự do trong schema. Danh sách chọn lấy từ API. Khi gửi, EAS gọi API để kiểm tra mã còn hiệu lực |
| `room_code`, `vehicle_code`, `asset_category` (thêm hôm nay) | Hệ thống tài sản, toà nhà | Như trên | |
| Bản chụp JSON trong `ai_service/data/mock` | Cả 8 hệ thống | **Xoá** | AI gọi Mock Systems API (cache 60 giây) |
| Ghi SQL trực tiếp của migration 17 cũ | Hệ thống tài sản, toà nhà | **Thay** bằng API: giữ chỗ, huỷ, trả | §4.2 |

## 4. Luồng dữ liệu sau khi sửa

### 4.1 Nhân sự (HRM)

- Dữ liệu HRM giả lập được **căn lại theo tổ chức thật của EAS** (migration mock `005_align_with_eas.sql`):
  - 8 phòng ban dùng đúng mã EAS;
  - 136 nhân viên, email `@eas.com`, mã `E0001…`, đúng quan hệ quản lý;
  - quỹ phép 2026 cho mỗi người (ANNUAL 12 ngày, SICK 30, PARENTAL 180).

  Lý do: dữ liệu mock trước đây không liên quan đến người dùng thật, nên không tra cứu được gì.
- Lệnh `python manage.py sync_hr_directory` gọi HRM API, rồi điền `app_user.employee_code` và kiểm tra lệch phòng ban hoặc quản lý.
- **Nghỉ phép có lương** (`LEAVE`, `leave_kind = CO_LUONG`):
  - khi gửi, EAS gọi `GET /hr/leave-balances?employee_code=…`; số ngày xin vượt quỹ còn lại → `LEAVE_BALANCE_EXCEEDED`;
  - khi duyệt, EAS gọi `POST /hr/leave-usages` để trừ quỹ.

  Nghỉ không lương không kiểm tra quỹ. Nghỉ chế độ thai sản dùng quỹ PARENTAL, nghỉ ốm dài ngày dùng quỹ SICK.

### 4.2 Tài sản và toà nhà (mượn phòng, xe, thiết bị)

Quy tắc nghiệp vụ không đổi so với lần trước. Chỉ đổi cách thực hiện:

| Bước | Lời gọi API |
|---|---|
| Danh sách chọn | `GET /facilities/resources`, `GET /assets/categories` |
| Kiểm tra lúc gửi | `GET /facilities/resources/{code}/availability?from&to`, `GET /assets/categories/{code}/availability?from&to` |
| Duyệt bước cuối: giữ chỗ | `POST /facilities/reservations`, `POST /assets/loans` (khoá chống trùng `source_request_id`) |
| BGĐ thu hồi | EAS tìm người đang giữ qua `GET .../holders`, huỷ bằng `POST /…/{id}/cancel`, rồi chuyển đơn của nhân viên sang REJECTED |
| Hết hạn | Worker gọi `GET /…?source=EAS&ended_before=now` rồi `POST /…/{id}/return` |

### 4.3 ITSM, ERP tài chính, mua sắm, CRM, công tác

| Hệ thống | EAS dùng |
|---|---|
| ITSM | Đơn cấp quyền chọn ứng dụng và vai trò từ ITSM. Khi đơn hoàn tất, EAS gọi `POST /it/user-access` để cấp quyền (có `expires_at` theo số ngày xin) |
| ERP tài chính | Đơn thanh toán chọn loại chi phí từ ERP, và số tiền vượt hạn mức ngày (`daily_limit_minor`) bị chặn. Các đơn có số tiền (tạm ứng, mua sắm, thanh toán, chiến dịch) được kiểm tra ngân sách còn lại của trung tâm chi phí của phòng người gửi (`approved − committed − spent`); khi duyệt, EAS gọi `POST /finance/commitments` |
| Mua sắm, CRM, công tác | Cung cấp ngữ cảnh cho AI qua API (danh mục hàng, nhà cung cấp, khách hàng, định mức công tác). Biểu mẫu chưa có trường mã tương ứng; chưa ép kiểm tra (§6) |

### 4.4 Đối soát

Worker chạy mỗi vòng:

1. Trả lại các phần mượn đã hết hạn.
2. Huỷ phần giữ chỗ có `source_request_id` mà đơn EAS không ở trạng thái đã duyệt. Trường hợp này xảy ra khi giao dịch EAS bị huỷ sau lúc gọi API.

## 5. Triển khai

| Bước | Ai làm | Nội dung |
|---|---|---|
| 0 | Bạn | Nếu chưa chạy: `database/migrations/16_worker_delegation_and_working_hours.sql` |
| 1 | Bạn | Chạy `database/mock_enterprise_sql/migrations/005_align_with_eas.sql`. File căn dữ liệu mock theo EAS và giữ nguyên lịch sử: 55 hồ sơ mẫu cũ chuyển TERMINATED, không xoá dòng nào |
| 2 | Bạn | Chạy `database/migrations/17_external_systems_via_api.sql`. File thay bản 17 cũ: tạo role `eas_mock`, thu hồi quyền `mock_*` của `eas_api`/`eas_worker`, thêm biểu mẫu mới, thêm nhóm phân loại (tài liệu `PHAN_LOAI_YEU_CAU.md`) |
| 3 | Bạn | Tạo role đăng nhập cho Mock Systems API: `CREATE ROLE eas_mock_login LOGIN PASSWORD '<mật khẩu mạnh>' IN ROLE eas_mock;`. Đưa DSN vào `.env` là `EAS_MOCK_DATABASE_URL` (không commit) |
| 4 | Bạn | Đặt `EAS_MOCK_API_SECRET` (chuỗi ngẫu nhiên) trong `.env`. Khởi động dịch vụ `mock_systems` |
| 5 | Dev (đã làm) | Code mới: client tích hợp, bỏ mọi SQL trực tiếp vào `mock_*`, AI gọi API |
| 6 | Dev | `python manage.py sync_hr_directory --apply` |

## 6. Kiểm thử (bản sao local, 04/11/2026)

Bản sao `m17test` có dữ liệu mock giống live. Thứ tự đã chạy: 005, rồi 17 (hai lần), rollback 17 (hai lần), rồi 17 lại. Kết quả: 12 nhóm, 61 loại trên menu. Rollback trả lại 10 nhóm cũ và quyền đọc cũ.

Chạy thật hai tiến trình:

- Mock Systems API ở cổng 8100, role `eas_mock_login`.
- EAS bằng role thành viên `eas_backend_login`, không phải superuser.

| Bước | Kết quả |
|---|---|
| 0 | Role EAS **không** đọc được `mock_*` (`has_schema_privilege(...)` = false) |
| 1 | Hai người đặt cùng phòng, cùng giờ: đơn duyệt trước thắng (COMPLETED), đơn duyệt sau tự động REJECTED. Đơn gửi muộn bị 409. Vượt sức chứa bị chặn. Mã phòng không có trong hệ thống toà nhà → lỗi trường |
| 1b | BGĐ đặt trùng giờ: đơn của nhân viên chuyển REJECTED, chỗ giữ bị huỷ trong hệ thống toà nhà, có thông báo `RESOURCE_PREEMPTED` |
| 2 | Mượn hết 13 laptop còn trống; người khác xin thêm bị 409; BGĐ xin 1 chiếc → đơn của nhân viên bị thu hồi |
| 3 | Nghỉ phép có lương 2 ngày: quỹ ANNUAL trong HRM 12 → 10. Xin vượt quỹ bị chặn. Nghỉ không lương 16 ngày không trừ quỹ, ghi `UNPAID_LEAVE` |
| 4 | Đề nghị mua sắm 12 triệu: ngân sách TECH trong ERP, phần đã cam kết tăng đúng 12 triệu |
| 5 | Đơn cấp quyền chọn vai trò của ứng dụng khác → `ROLE_NOT_IN_APPLICATION` |
| 6 | Hết thời gian mượn: worker trả lại laptop và phòng qua API |

Test tự động: `api_core` 338/338, `tests/run_tests.py` 153 ca, web 64/64, build sạch.

Test `NoDirectMockAccessTests` chặn mọi câu SQL tới `mock_*` ngoài `api_core/mock_sources`. Health check có thêm hai chỉ tiêu:

- `eas_role_has_no_mock_table_access`;
- `mock_systems_api_reachable`.

Migration mock `004_hrm_attendance.sql` (bảng chấm công chưa từng chạy trên live) đã xoá. Chấm công là dữ liệu giả lập và không được đọc nữa; xem `THIET_KE_SCHEMA_EAS_V2.md` §7.

## 7. Chưa làm (ngoài phạm vi đợt này)

- Đơn mua sắm chọn mã hàng / nhà cung cấp từ e-Procurement, và tạo đơn đặt hàng (`purchase_order`) khi hoàn tất.
- Đơn chiết khấu chọn mã khách hàng / hợp đồng từ CRM.
- Đơn công tác kiểm tra định mức theo cấp bậc. HRM chưa có trường cấp bậc chuẩn.
