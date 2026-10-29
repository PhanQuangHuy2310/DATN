# Pull Request: Kiến trúc Quản trị Doanh nghiệp 5 Cấp & Chuẩn hóa 53 Loại Yêu Cầu

## Thông Tin Pull Request
- **Branch Nguồn:** `huy`
- **Branch Đích:** `main`
- **Repository:** `https://github.com/PhanQuangHuy2310/DATN`
- **Link so sánh / tạo PR:** [Tạo Pull Request huy -> main](https://github.com/PhanQuangHuy2310/DATN/compare/main...huy?expand=1)
- **Tài liệu tham chiếu:**
  - Báo cáo đồ án: `docs/Report_DATN_CNTT_Nhom07_v1.0.docx`
  - Kế hoạch triển khai: `plan.md` (Mục 23 & 24)
  - Nhật ký kiểm toán: `CHANGELOG_AUDIT_20261029.md`
  - Script CSDL: `database/report_migrations/01_request_catalog_expansion_REVIEW_BEFORE_RUN.sql`, `04_approved_actor_resolvers_DBA_REVIEW_ONLY.sql`, `05_enterprise_5level_and_catalog_DBA_REVIEW_ONLY.sql`

---

## 1. Tóm Tắt Mục Tiêu & Bối Cảnh (Executive Summary)
Pull Request này giải quyết toàn diện 2 yêu cầu cốt lõi theo tiêu chuẩn doanh nghiệp lớn (SAP Ariba, ServiceNow, Workday, Coupa, ISO 27001 / COSO ERM):
1. **Khắc phục và chuẩn hóa 41 loại yêu cầu ban đầu**: Khớp 100% giữa tài liệu báo cáo `Report_DATN_CNTT_Nhom07_v1.0.docx`, `plan.md`, codebase và cơ sở dữ liệu Live Supabase (`emnusiybdkpibtqsplta`). Khắc phục triệt để lỗi sao chép form schema sai ở 6/10 loại core và nạp đầy đủ 18 loại Menu nghiệp vụ + 13 loại Kế hoạch mở rộng.
2. **Thiết kế & Triển khai Kiến trúc Phân tầng Quản trị 5 Cấp (`5-Level Enterprise Delegation of Authority & Risk Weight`)**:
   - Mở rộng giới hạn quy trình từ `1..3` cấp lên **chuẩn 5 cấp (`Cấp 1..5`)** trên toàn bộ Database DDL, Constraints, Triggers, Backend Engine và Frontend React.
   - Bổ sung **12 loại yêu cầu doanh nghiệp mới** chuyên biệt cho các nghiệp vụ trọng yếu (Nhân sự định biên, Chiết khấu thương mại, Mua sắm/Nhà cung cấp, Thanh lý tài sản, Điều chuyển ngân sách công ty, Thay đổi khẩn cấp an toàn thông tin), nâng quy mô toàn hệ thống lên **53 loại yêu cầu hoạt động**.
   - Bổ sung trường 5 cấp (`risk_weight`, `approval_level`, `tier_level`, `resolver_code`) đồng bộ trên cả 6 bảng cốt lõi của quy trình: `eas.request_type`, `eas.config_release`, `eas.request`, `eas.request_revision`, `eas.workflow_instance`, `eas.approval_step`.

---

## 2. Kiến Trúc Quản Trị 5 Cấp (`5-Level Enterprise DoA & Risk Matrix`)

| Cấp độ | Phân tầng nghiệp vụ | Trọng số (`risk_weight`) | Số cấp duyệt (`approval_level`) | Chuỗi phê duyệt mẫu | SLA mục tiêu | Số lượng loại yêu cầu |
| :---: | :--- | :---: | :---: | :--- | :---: | :---: |
| **Cấp 1** | **Tác nghiệp cơ bản** (*Operational / Low Risk*) | `1/5` | **1 cấp** | `Step 1`: Quản lý trực tiếp (`DIRECT_MANAGER`) hoặc Đầu mối phụ trách | `4h – 8h` | 10 loại trọng số 1 · 17 loại duyệt 1 cấp |
| **Cấp 2** | **Nghiệp vụ phòng ban** (*Departmental / Moderate Risk*) | `2/5` | **2 cấp** | `Step 1`: Quản lý trực tiếp $\rightarrow$ `Step 2`: Đầu mối chuyên môn (`HR` / `IT` / `FINANCE` / `OPS`) | `16h – 24h` | 13 loại trọng số 2 · 15 loại duyệt 2 cấp |
| **Cấp 3** | **Kiểm soát chéo & Ngân sách vừa** (*Cross-Functional / Elevated Risk*) | `3/5` | **3 cấp** | `Step 1`: Quản lý trực tiếp $\rightarrow$ `Step 2`: Trưởng bộ phận chuyên môn $\rightarrow$ `Step 3`: Tài chính / Rủi ro | `24h – 48h` | 17 loại trọng số 3 · 16 loại duyệt 3 cấp |
| **Cấp 4** | **Cam kết tài chính lớn & Nhân sự định biên** (*Executive / High Risk*) | `4/5` | **4 cấp** | `Step 1`: Quản lý trực tiếp $\rightarrow$ `Step 2`: Chuyên môn $\rightarrow$ `Step 3`: Kiểm soát Tài chính $\rightarrow$ `Step 4`: Ban Giám đốc Khối | `48h – 72h` | 7 loại trọng số 4 · 3 loại duyệt 4 cấp |
| **Cấp 5** | **Trọng yếu chiến lược & Khẩn cấp An ninh** (*Board / Critical Risk*) | `5/5` | **5 cấp** | `Step 1`: Quản lý trực tiếp $\rightarrow$ `Step 2`: Chuyên môn $\rightarrow$ `Step 3`: Pháp chế / Bảo mật $\rightarrow$ `Step 4`: Giám đốc Khối / CFO $\rightarrow$ `Step 5`: Tổng Giám đốc / HĐQT | `24h – 96h` | 6 loại trọng số 5 · 2 loại duyệt 5 cấp |

---

## 3. Danh Mục 12 Loại Yêu Cầu Mới Mở Rộng (Tổng Cộng 53 Loại Yêu Cầu)
- **Cấp 1 (Duyệt 1 cấp)**:
  1. `VISITOR_SECURITY_PASS`: Đăng ký khách & đối tác ra vào tòa nhà (Khối `FACILITY`, Mẫu `A`).
  2. `TAX_INVOICE_ISSUE`: Yêu cầu xuất hóa đơn GTGT cho khách hàng (Khối `FINANCE`, Mẫu `B`).
- **Cấp 2 (Duyệt 2 cấp)**:
  3. `TRAINING_COURSE`: Đăng ký khóa đào tạo & thi chứng chỉ chuyên môn (Khối `HR`, Mẫu `B`).
  4. `NDA_PRIVACY_CLEARANCE`: Thẩm định thỏa thuận bảo mật (NDA) & dữ liệu đối tác (Khối `GENERAL`, Mẫu `B`).
- **Cấp 3 (Duyệt 3 cấp)**:
  5. `INTERNAL_TRANSFER`: Điều chuyển nội bộ liên phòng ban / vị trí (Khối `HR`, Mẫu `B`).
  6. `SPECIAL_DISCOUNT`: Phê duyệt chiết khấu thương mại đặc biệt ngoài khung (Khối `GENERAL`, Mẫu `A`).
  7. `SUPPLIER_ONBOARDING`: Thẩm định & phê duyệt nhà cung cấp mới vào danh mục (Khối `PROCUREMENT`, Mẫu `B`).
- **Cấp 4 (Duyệt 4 cấp)**:
  8. `RECRUITMENT_REQ`: Yêu cầu tuyển dụng nhân sự - Headcount Requisition (Khối `HR`, Mẫu `C`).
  9. `MARKETING_CAMPAIGN`: Phê duyệt ngân sách chiến dịch Marketing & Sự kiện (Khối `GENERAL`, Mẫu `C`).
  10. `ASSET_DISPOSAL`: Thanh lý, hủy bỏ hoặc nhượng bán tài sản cố định (Khối `ASSET`, Mẫu `C`).
- **Cấp 5 (Duyệt 5 cấp)**:
  11. `BUDGET_REALLOCATION`: Điều chuyển & bổ sung ngân sách năm giữa các hạng mục (Khối `FINANCE`, Mẫu `C`).
  12. `SECURITY_INCIDENT_HOTFIX`: Phê duyệt thay đổi khẩn cấp Production - Emergency Hotfix (Khối `IT`, Mẫu `C`).

---

## 4. Chi Tiết Thay Đổi Kỹ Thuật (Technical Details)

### 🔹 Cơ Sở Dữ Liệu (`PostgreSQL / Supabase`)
- **DDL Migration Script:** `database/report_migrations/05_enterprise_5level_and_catalog_DBA_REVIEW_ONLY.sql`.
- **Cập nhật 6 bảng:**
  - `eas.request_type`: Thêm cột `risk_weight` (`smallint 1..5`), `approval_level` (`smallint 1..5`).
  - `eas.config_release`: Thêm cột `risk_weight`, `approval_level`. Nâng cấp trigger `eas.guard_release()` cho phép `1..5` bước duyệt trên mỗi bậc ngân sách.
  - `eas.request`: Thêm cột `risk_weight`, `approval_level` lưu vết hồ sơ thực tế.
  - `eas.request_revision`: Thêm cột `risk_weight`, `approval_level` bảo toàn lịch sử phiên bản.
  - `eas.workflow_instance`: Thêm cột `risk_weight`, `approval_level`; nâng cấp constraint cho phép chuỗi `resolved_route` dài tối đa 5 bước.
  - `eas.approval_step`: Thêm cột `tier_level` (`smallint 1..5`), `resolver_code` (`varchar(40)`); nâng cấp constraint `approval_step_step_no_check` cho phép `step_no BETWEEN 1 AND 5`.
- **Phân quyền role `eas_api`:** Cấp đầy đủ `SELECT, INSERT, UPDATE` trên tất cả các cột mới.

### 🔹 Phân Hệ Backend (`api_core`)
- `api_core/catalog/enterprise_types.json`: Khai báo 5-level metadata, ma trận phân cấp và 12 loại yêu cầu.
- `api_core/catalog/plan_catalog.py`: Tích hợp bộ nạp metadata 5 cấp, hợp nhất 53 loại yêu cầu hoàn chỉnh.
- `api_core/catalog/views.py`: Trả về `risk_weight`, `approval_level`, `level_meta`, `five_level_framework` và từ điển nhãn Tiếng Việt qua API `/api/v1/request-types`, `/api/v1/catalog/menu`, `/api/v1/catalog/plan`.
- `api_core/domain/validation.py`: Mở rộng validation release cho phép chuỗi phê duyệt `1..5` người (`approver_slots`).
- `api_core/domain/routing.py`: Hỗ trợ định tuyến tự động `1..5` bước, mở rộng trích xuất ngân sách cho các trường `deal_value_vnd`, `salary_budget_vnd`, `residual_value_vnd`.
- `api_core/domain/plan_constraints.py`: Thêm kiểm tra ràng buộc nghiệp vụ cho `SPECIAL_DISCOUNT`, `BUDGET_REALLOCATION`, `TRAINING_COURSE`, `MARKETING_CAMPAIGN`.
- `api_core/workflow/service.py`: Persist đầy đủ các cột 5 cấp vào CSDL khi khởi tạo nháp và khi nộp hồ sơ.
- `api_core/apps.py`: Đăng ký `JsonLoader`/`JsonbLoader` trên tín hiệu `connection_created` cho kết nối PostgreSQL.

### 🔹 Phân Hệ Frontend (`web_client`)
- `web_client/src/domain.js`: Bổ sung ma trận 5 cấp `FIVE_LEVEL_FRAMEWORK`, `TYPE_LEVEL_MATRIX`, `getRequestTypeLevelMeta`, từ điển Tiếng Việt cho 53 loại yêu cầu.
- `web_client/src/components/RequestTypeMenu.jsx`: Bổ sung bộ lọc 5 cấp độ (`Cấp 1/5` .. `Cấp 5/5`), hiển thị huy hiệu trọng số và số cấp phê duyệt.
- `web_client/src/components/PlanCatalog.jsx`: Trình bày bảng danh mục 53 loại yêu cầu trực quan với bộ lọc cấp độ, mẫu quy trình và khối chuyên môn.
- `web_client/src/components/RequestEditor.jsx` & `RequestDetail.jsx`: Hiển thị huy hiệu cấp độ rủi ro, phân bậc phê duyệt và danh sách bước duyệt `Bước 1/5 .. 5/5` kèm thông tin `resolver_code`.

---

## 5. Kết Quả Kiểm Thử & Nghiệm Thu (Verification & Evidence)

1. **Kiểm thử tự động Backend (Django Test Suite + Regression)**:
   - `python manage.py test api_core.tests tests_business tests_readiness tests_report connection_tests -v 1`
   - **Kết quả:** `Ran 218 tests in 8.355s - OK` (**218/218 bài kiểm thử PASS, 0 lỗi, 0 cảnh báo**).
2. **Kiểm thử Frontend**:
   - `node --test e2e/domain.test.mjs`: **8/8 bài kiểm thử PASS**.
   - `npm run build`: Production bundle Vite hoàn tất không lỗi (`dist/assets/index-C42pz5O-.js`, 139ms).
3. **Kiểm thử Live Supabase (`emnusiybdkpibtqsplta`)**:
   - **53/53 loại yêu cầu** đã `PUBLISHED`, `is_active = true`.
   - **1.272/1.272 kịch bản định tuyến** (`53 loại × 8 phòng ban × 3 tầng ngân sách`) PASS 100%, tuân thủ nghiêm ngặt nguyên tắc SoD (Separation of Duties).
   - Kiểm thử thực tế `create_draft` và `submit_request` thành công trên cả 5 cấp độ phê duyệt trực tiếp trên Live Supabase.
