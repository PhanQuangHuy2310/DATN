# CHANGELOG & ENTERPRISE AUDIT REPORT (2026-10-29)

## 1. Tổng quan đợt Audit & Đồng bộ Bàn giao
- **Tài liệu đối chiếu**:
  - Báo cáo đồ án tốt nghiệp: `docs/Report_DATN_CNTT_Nhom07_v1.0.docx`
  - Kế hoạch kiến trúc & thiết kế chi tiết: `plan.md`
  - Danh mục biểu mẫu & chính sách: `api_core/catalog/approval_menu.json` (20 dòng hiển thị / 18 mã nghiệp vụ), `api_core/catalog/plan_types.json` (18 mã mở rộng theo 4 bảng 25, 27, 28, 29), `docs/APPROVAL_MENU_POLICY_DRAFTS.json`
- **Cơ sở dữ liệu Live Supabase**: Project `DATN` (`emnusiybdkpibtqsplta`)
- **Mục tiêu**:
  1. Kiểm toán toàn diện kiến trúc, bảo mật (RBAC, SoD, Allowlist/Blacklist, Tamper-evident Audit Chain, Idempotency), logic định tuyến và giao diện Web Client theo chuẩn tập đoàn công nghệ lớn (Google Zanzibar / SAP GRC / AWS IAM / ServiceNow).
  2. Khắc phục triệt để tình trạng các loại yêu cầu nghiệp vụ trên Supabase chưa được đăng ký/xuất bản hoặc bị trùng lặp biểu mẫu.
  3. Kiểm thử tự động và kiểm thử tích hợp thực tế (End-to-End) trên Live Supabase đảm bảo 0 lỗi API, 0 lỗi logic, 0 lỗi giao diện.

---

## 2. Các vấn đề trọng yếu đã phát hiện & xử lý triệt để

### 2.1. Trên Cơ sở dữ liệu Live Supabase (`emnusiybdkpibtqsplta`)
1. **31 loại yêu cầu mở rộng chưa được đăng ký và công bố trên Supabase**:
   - **Hiện trạng trước khi sửa**: `check_approval_menu_readonly.py` báo `0/18 mã có bản phát hành đang hoạt động` (`CHƯA ĐĂNG KÝ`). Toàn bộ 18 mã trong `approval_menu.json` và 13 mã mở rộng trong `plan_types.json` chưa có mặt trong `eas.request_type` và `eas.config_release`.
   - **Khắc phục**: Đã đăng ký đầy đủ 31 mã mở rộng vào `eas.request_type`, khởi tạo và xuất bản (`PUBLISHED`) `eas.config_release` (`version = 1`) với đầy đủ `form_schema`, `route_rules`, `sla_profile`, `actor_bindings` cho cả 8 phòng ban và kích hoạt `is_active = true`. Kết quả: **41/41 loại yêu cầu** (`10 Core + 18 Menu + 13 Plan`) đều `PUBLISHED` và `ACTIVE`.
2. **6/10 loại yêu cầu Core trên Supabase bị sao chép nhầm `form_schema` của 3 loại P0**:
   - **Hiện trạng trước khi sửa**: Trên Supabase, `EXPENSE_CLAIM` và `ROOM_BOOKING` dùng nhầm `form_schema` của `LEAVE` (`handover_user_id`); `ACCESS_FACILITY`, `BUSINESS_TRIP`, `IT_SUPPORT` dùng nhầm `form_schema` của `ACCESS` (`app_code`); `EQUIPMENT_BORROW` dùng nhầm `form_schema` mua sắm của `EQUIPMENT` (`amount_vnd`).
   - **Khắc phục**: Đã thiết kế chuẩn xác `CORE_EXTRA_TEMPLATES` trong `api_core/workflow/policy_helpers.py` và phát hành bản `version = 2` (`PUBLISHED`) trên `eas.config_release` cho toàn bộ 10 loại Core, đồng thời cập nhật `draft_release_id` cho các bản nháp (`DRAFT`) đang mở để không xảy ra lỗi `STALE_DRAFT_RELEASE`.
3. **Trigger PostgreSQL (`eas.guard_release`, `eas.guard_request`, `eas.guard_revision`, `eas.check_submission_files`) và quyền bảng (`eas_api`) còn khóa cứng ở phạm vi 3 loại P0**:
   - **Hiện trạng trước khi sửa**:
     - `eas.guard_release()` trên Supabase chỉ cho phép 3 resolver (`DIRECT_MANAGER`, `FINANCE`, `DIRECTOR`) và toán tử số (`amount_gt`, `amount_gte`), chặn toán tử mảng `app_code_in` của `SOFTWARE_ACCESS`.
     - `eas.guard_request()` và `eas.guard_revision()` chặn mọi đơn vòng đời `A`/`B` có `amount_vnd` (như `EXPENSE_CLAIM`, `PURCHASE_REQUEST`, `BUSINESS_TRIP`) và bắt buộc mọi đơn vòng đời `C` phải có `amount_vnd` + file báo giá (chặn `EQUIPMENT_BORROW`, `EMPLOYEE_ONBOARDING`).
     - Role `eas_api` (`eas_backend_login`) thiếu quyền `INSERT` trên `eas.request_type` và quyền `UPDATE (response_body)` trên `eas.idempotency_record` (khiến câu lệnh `SELECT ... FROM eas.idempotency_record ... FOR UPDATE` trong `_execute_idempotent` bị lỗi `permission denied`).
   - **Khắc phục**: Đã nâng cấp `eas.guard_release()`, `eas.guard_request()`, `eas.guard_revision()`, `eas.check_submission_files()` và cấp quyền `GRANT INSERT ON eas.request_type TO eas_api; GRANT UPDATE (response_body) ON eas.idempotency_record TO eas_api;` trên cả Live Supabase và bộ file migration `database/report_migrations/`.
4. **Cấu trúc phân quyền RBAC & Separation of Duties (SoD) 3 tầng tách biệt (Disjoint 3-Tier Enterprise Hierarchy)**:
   - **Hiện trạng trước khi sửa**: Một số nhân sự có `manager_id` trỏ tới `EXECUTOR` không có quyền `APPROVER`; quyền `EXECUTOR` và `ACCEPTOR` chỉ được gán `type_scope = 'ONE'` cho `ACCESS`/`EQUIPMENT`.
   - **Khắc phục**: Chuẩn hóa cây `manager_id` 4 tầng không chu trình (acyclic) trên `eas.app_user` và tách bạch hoàn toàn 3 tập tác nhân:
     - **Tập 1 (Quản lý trực tiếp - `DIRECT_MANAGER`)**: 8 quản lý phòng ban (`ngoc.tran`, `chau.nguyen`, `phuc.dang`, `yen.phan`, `dung.nguyen`, `vy.pham`, `phuong.to`, `tri.tran`).
     - **Tập 2 (Phê duyệt chức năng - `Functional Approvers`)**: 13 slot độc lập (`DIRECTOR`, `CTO`, `IT_MANAGER`, `CISO`, `SECURITY`, `FINANCE`, `HR_MANAGER`, `PROJECT_MANAGER`, `MARKETING_MANAGER`, `OPERATIONS_MANAGER`, `WAREHOUSE_MANAGER`, `PROCUREMENT_MANAGER`, `LEGAL`).
     - **Tập 3 (Thực thi chức năng - `Functional Executors`)**: 11 slot thực thi (`EXECUTOR_IT`, `EXECUTOR_TECH`, `EXECUTOR_ASSET`, `EXECUTOR_PROCUREMENT`, `EXECUTOR_HR`, `EXECUTOR_ADMIN`, `EXECUTOR_FINANCE`, `EXECUTOR_FACILITY`, `EXECUTOR_WAREHOUSE`, `EXECUTOR_MARKETING`, `EXECUTOR_LEGAL`).
     - Cấp đầy đủ `eas.role_membership` (`GLOBAL` + `ALL`) cho `APPROVER`, `EXECUTOR`, `ACCEPTOR`, `REQUESTER`. Đã kiểm chứng tự động **984 kịch bản định tuyến** (`41 loại yêu cầu × 8 phòng ban × 3 mức ngưỡng`) đạt **0 lỗi SoD**.

### 2.2. Trên Backend (`api_core`) & Frontend (`web_client`)
1. **Bộ nạp JSONB tự động cho kết nối PostgreSQL của Django (`api_core/apps.py`)**:
   - Khắc phục hiện tượng `django.db.backends.postgresql` ghi đè `TextLoader` lên kiểu `json`/`jsonb` khiến `connection.cursor()` trả về `str` thay vì `dict` khi truy vấn trực tiếp PostgreSQL.
2. **Trích xuất hạn mức tiền tệ đa trường (`api_core/domain/routing.py`, `api_core/workflow/service.py`)**:
   - Bổ sung `MONETARY_PAYLOAD_FIELDS` và `extract_amount_vnd(..., allow_zero=False)` hỗ trợ đầy đủ 7 trường tiền tệ (`amount_vnd`, `amount`, `estimated_budget`, `refund_amount`, `contract_value`, `estimated_cost`, `estimated_price`) cho cả định tuyến tự động và lưu trữ `request_revision.amount_vnd`.
3. **Ràng buộc nghiệp vụ chuyên sâu (`api_core/domain/plan_constraints.py`, `api_core/domain/validation.py`)**:
   - Kiểm tra định dạng giờ `HH:MM` và `end_time > start_time` cho `ROOM_BOOKING`.
   - Kiểm tra `end_date >= start_date` cho tất cả các loại đơn có khoảng ngày (`LEAVE_SPECIAL`, `BUSINESS_TRIP`, `ACCESS_FACILITY`, `EQUIPMENT_BORROW`, `WFH_REQ`, `SOFTWARE_ACCESS`, `PROD_DATA_ACCESS`).
   - Kiểm tra SoD `handover_user_id != requester_id` cho `LEAVE_SPECIAL`.
4. **Cơ chế Fallback an toàn cho ClamAV & Object Storage ở môi trường Local Dev (`api_core/storage.py`)**:
   - Khi `ENVIRONMENT == "development"` và `EAS_REQUIRE_STORAGE=False`, hỗ trợ quét chữ ký EICAR nội bộ và lưu trữ tệp đính kèm vào `.local_storage/` nếu chưa cấu hình ClamAV daemon / Supabase Storage bucket, trong khi vẫn giữ nguyên cơ chế `fail-closed` nghiêm ngặt trên môi trường `production` và `test`.
5. **Hoàn thiện nhãn Tiếng Việt & thanh điều hướng Frontend (`web_client/src/domain.js`, `App.jsx`, `RequestEditor.jsx`, `RequestDetail.jsx`, `api_core/catalog/views.py`)**:
   - Phủ 100% nhãn Tiếng Việt (`field_labels`) cho toàn bộ thuộc tính `form_schema` của cả 41 loại yêu cầu.
   - Bổ sung mục `"plan-catalog"` ("Danh mục 18 loại đơn") vào nhóm menu `"QUẢN TRỊ HỆ THỐNG"` trên `App.jsx`.
   - Hỗ trợ xem trước hạn mức tiền tệ và lộ trình phê duyệt cho tất cả các trường ngân sách trong `RequestEditor.jsx`.

---

## 3. Kết quả Kiểm thử & Xác nhận Bàn giao
- `python -X utf8 manage.py test api_core.tests --noinput`: **130/130 PASS**
- `tests_business` (`35 tests`), `tests_readiness` (`10 tests`), `tests_report` (`15 tests`), `connection_tests` (`13 tests`): **73/73 PASS**
- `web_client/e2e` (`24 tests`) & `vite build web_client`: **24/24 PASS**, build thành công (`dist/assets/index-D-Y3MCqx.js`)
- `python -X utf8 check_approval_menu_readonly.py`: **18/18 mã có bản phát hành đang hoạt động (`ĐÃ CÔNG BỐ`)**
- `python -X utf8 diagnose_readiness_readonly.py`: **41 loại đơn active, 0 chưa có release hợp lệ (`PASS`)**
- Kiểm thử `submit_request` thực tế trên Live Supabase (`EXPENSE_CLAIM`, `PURCHASE_REQUEST`, `ROOM_BOOKING`, `LEAVE_SPECIAL`, `EQUIPMENT_BORROW`): **5/5 trả về `201 Created` (`PENDING_APPROVAL`)**


---

## 4. Đợt Audit & Mở rộng Kiến trúc Phân quyền 5 Cấp + 12 Loại Yêu cầu Doanh nghiệp (53 Loại Yêu cầu Toàn hệ thống)

### 4.1. Nâng cấp Cơ sở dữ liệu Live Supabase (`emnusiybdkpibtqsplta`) & Migration `05_enterprise_5level_and_catalog_DBA_REVIEW_ONLY.sql`
1. **Nâng cấp Ràng buộc & Trigger PostgreSQL từ 3 cấp lên 5 cấp (`1..5`)**:
   - `eas.approval_step`: Nâng cấp `approval_step_step_no_check` lên `CHECK (step_no >= 1 AND step_no <= 5)`.
   - `eas.workflow_instance`: Nâng cấp `workflow_instance_resolved_route_check` lên `CHECK (jsonb_typeof(resolved_route) = 'array' AND jsonb_array_length(resolved_route) >= 1 AND jsonb_array_length(resolved_route) <= 5)`.
   - `eas.guard_release()`: Nâng cấp kiểm tra số lượng người duyệt trong mỗi rule từ `1..3` lên `1..5` (`Route requires 1..5 approvers`).
2. **Bổ sung cột dữ liệu 5 Cấp trên cả 6 bảng nghiệp vụ cốt lõi**:
   - `eas.request_type`: `risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5)`, `approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5)`.
   - `eas.config_release`: `risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5)`, `approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5)`.
   - `eas.request`: `risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5)`, `approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5)`.
   - `eas.request_revision`: `risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5)`, `approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5)`.
   - `eas.workflow_instance`: `risk_weight smallint NOT NULL DEFAULT 3 CHECK (risk_weight BETWEEN 1 AND 5)`, `approval_level smallint NOT NULL DEFAULT 1 CHECK (approval_level BETWEEN 1 AND 5)`.
   - `eas.approval_step`: `tier_level smallint NOT NULL DEFAULT 1 CHECK (tier_level BETWEEN 1 AND 5)`, `resolver_code character varying(40)`.
   - Cấp đầy đủ quyền `GRANT SELECT, INSERT, UPDATE` trên các cột mới cho `eas_api` và đồng bộ dữ liệu lịch sử cho toàn bộ 53 loại yêu cầu.

### 4.2. Bổ sung 12 Loại Yêu cầu Doanh nghiệp Mới theo Mô hình 5 Cấp (`api_core/catalog/enterprise_types.json`)
Qua rà soát mô hình 8 phòng ban (`BOD`, `TECH`, `FIN`, `HR`, `BIZ`, `MKT`, `OPS`, `LEGAL`) và 8 phân hệ vệ tinh (`mock_hr`, `mock_assets`, `mock_facilities`, `mock_crm`, `mock_procurement`, `mock_it`, `mock_finance`, `mock_travel`), hệ thống đã bổ sung và xuất bản (`PUBLISHED`) **12 loại yêu cầu doanh nghiệp mới** phủ kín cả 5 cấp độ:
- **Cấp 1 (Rủi ro rất thấp — Duyệt 1 cấp)**:
  1. `VISITOR_SECURITY_PASS` (`FACILITY`, Mẫu `A`, Duyệt 1 cấp: `DIRECT_MANAGER`): Thẻ an ninh khách & đối tác ra vào.
  2. `TAX_INVOICE_ISSUE` (`FINANCE`, Mẫu `B`, Duyệt 1 cấp: `FINANCE`, Thực thi: `EXECUTOR_FINANCE`): Phát hành / điều chỉnh hóa đơn VAT.
- **Cấp 2 (Rủi ro thấp — Duyệt 2 cấp)**:
  3. `TRAINING_COURSE` (`HR`, Mẫu `B`, Duyệt 2 cấp: `DIRECT_MANAGER -> HR_MANAGER`, Thực thi: `EXECUTOR_HR`): Đăng ký đào tạo & chứng chỉ nghề nghiệp.
  4. `NDA_PRIVACY_CLEARANCE` (`GENERAL`, Mẫu `B`, Duyệt 2 cấp: `DIRECT_MANAGER -> LEGAL`, Thực thi: `EXECUTOR_LEGAL`): Thẩm định NDA & chia sẻ dữ liệu đối tác.
- **Cấp 3 (Rủi ro trung bình — Duyệt 3 cấp)**:
  5. `INTERNAL_TRANSFER` (`HR`, Mẫu `B`, Duyệt 3 cấp: `DIRECT_MANAGER -> HR_MANAGER -> DIRECTOR`, Thực thi: `EXECUTOR_HR`): Điều chuyển nội bộ & bổ nhiệm nhân sự.
  6. `SPECIAL_DISCOUNT` (`GENERAL`, Mẫu `A`, Duyệt 3 cấp: `DIRECT_MANAGER -> MARKETING_MANAGER -> FINANCE`): Phê duyệt chiết khấu thương mại đặc biệt.
  7. `SUPPLIER_ONBOARDING` (`PROCUREMENT`, Mẫu `B`, Duyệt 3 cấp: `DIRECT_MANAGER -> PROCUREMENT_MANAGER -> FINANCE`, Thực thi: `EXECUTOR_PROCUREMENT`): Thẩm định & phê duyệt nhà cung cấp mới.
- **Cấp 4 (Rủi ro cao — Duyệt 4 cấp)**:
  8. `RECRUITMENT_REQ` (`HR`, Mẫu `C`, Duyệt 4 cấp: `DIRECT_MANAGER -> HR_MANAGER -> FINANCE -> DIRECTOR`, Thực thi: `EXECUTOR_HR`, Nghiệm thu: `DIRECT_MANAGER`): Yêu cầu tuyển dụng nhân sự (Headcount).
  9. `MARKETING_CAMPAIGN` (`GENERAL`, Mẫu `C`, Duyệt 4 cấp: `DIRECT_MANAGER -> MARKETING_MANAGER -> FINANCE -> DIRECTOR`, Thực thi: `EXECUTOR_MARKETING`, Nghiệm thu: `REQUESTER`): Ngân sách chiến dịch Marketing & Sự kiện.
  10. `ASSET_DISPOSAL` (`ASSET`, Mẫu `C`, Duyệt 4 cấp: `DIRECT_MANAGER -> WAREHOUSE_MANAGER -> FINANCE -> DIRECTOR`, Thực thi: `EXECUTOR_ASSET`, Nghiệm thu: `DIRECT_MANAGER`): Thanh lý & hủy tài sản cố định.
- **Cấp 5 (Trọng yếu / Đặc biệt nghiêm trọng — Duyệt 5 cấp)**:
  11. `BUDGET_REALLOCATION` (`FINANCE`, Mẫu `C`, Duyệt 5 cấp: `DIRECT_MANAGER -> PROJECT_MANAGER -> OPERATIONS_MANAGER -> FINANCE -> DIRECTOR`, Thực thi: `EXECUTOR_FINANCE`, Nghiệm thu: `REQUESTER`): Điều chuyển & bổ sung ngân sách liên bộ phận.
  12. `SECURITY_INCIDENT_HOTFIX` (`IT`, Mẫu `C`, Duyệt 5 cấp: `DIRECT_MANAGER -> IT_MANAGER -> SECURITY -> CISO -> CTO`, Thực thi: `EXECUTOR_TECH`, Nghiệm thu: `CTO`): Khắc phục sự cố bảo mật & Hotfix khẩn cấp.

### 4.3. Đồng bộ Xử lý Backend (`api_core`) & Hiển thị Frontend (`web_client`)
- **Backend (`api_core`)**:
  - Nâng cấp `api_core/domain/validation.py` và `api_core/domain/routing.py` hỗ trợ lộ trình phê duyệt `1..5` cấp và trích xuất hạn mức tiền tệ từ `deal_value_vnd`, `salary_budget_vnd`, `residual_value_vnd`.
  - Bổ sung kiểm tra ràng buộc nghiệp vụ chéo cho `BUDGET_REALLOCATION` (`source_budget_code != target_budget_code`), `SPECIAL_DISCOUNT` (`amount_vnd <= deal_value_vnd`), `TRAINING_COURSE`, `MARKETING_CAMPAIGN` trong `api_core/domain/plan_constraints.py`.
  - Mở khóa publish cho `RESIGNATION` trong `api_core/workflow/config_service.py` khi đã cấu hình `executor`.
  - Lưu trữ tự động `risk_weight`, `approval_level`, `tier_level`, `resolver_code` khi tạo nháp (`create_draft`) và gửi yêu cầu (`submit_request`) trong `api_core/workflow/service.py`; trả về đầy đủ thông tin 5 cấp trên `/api/v1/request-types`, `/api/v1/meta/request-type-forms`, `/api/v1/meta/plan-request-types`, `/api/v1/requests`, `/api/v1/requests/<id>`, và `/api/v1/admin/request-types`.
- **Frontend (`web_client`)**:
  - Cập nhật `web_client/src/domain.js`, `RequestTypeMenu.jsx`, `RequestEditor.jsx`, `RequestDetail.jsx`, `PlanCatalog.jsx`, `IdentityAdmin.jsx`, và `App.jsx` hiển thị bộ lọc 5 cấp, huy hiệu `Trọng số Cấp X/5 · Duyệt Y/5 cấp`, và lộ trình phê duyệt 1–5 cấp kèm chức danh resolver (`resolver_code`) và tên người xử lý (`assignee_name`).
