# Pull Request: Kiến trúc Quản trị Doanh nghiệp 5 Cấp, Chuẩn hóa 53 Loại Yêu Cầu & Hoàn Thiện Quality Gates

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
Pull Request này giải quyết toàn diện các yêu cầu cốt lõi theo tiêu chuẩn doanh nghiệp lớn (SAP Ariba, ServiceNow, Workday, Coupa, ISO 27001 / COSO ERM) và vượt qua 100% các trạm kiểm định chất lượng (Quality Gates):
1. **Khắc phục và chuẩn hóa 41 loại yêu cầu ban đầu**: Khớp 100% giữa tài liệu báo cáo `Report_DATN_CNTT_Nhom07_v1.0.docx`, `plan.md`, codebase và cơ sở dữ liệu Live Supabase (`emnusiybdkpibtqsplta`). Khắc phục triệt để lỗi sao chép form schema sai ở 6/10 loại core và nạp đầy đủ 18 loại Menu nghiệp vụ + 13 loại Kế hoạch mở rộng.
2. **Thiết kế & Triển khai Kiến trúc Phân tầng Quản trị 5 Cấp (`5-Level Enterprise Delegation of Authority & Risk Weight`)**:
   - Mở rộng giới hạn quy trình từ `1..3` cấp lên **chuẩn 5 cấp (`Cấp 1..5`)** trên toàn bộ Database DDL, Constraints, Triggers, Backend Engine và Frontend React.
   - Bổ sung **12 loại yêu cầu doanh nghiệp mới** chuyên biệt cho các nghiệp vụ trọng yếu, nâng quy mô toàn hệ thống lên **53 loại yêu cầu hoạt động**.
   - Bổ sung trường 5 cấp (`risk_weight`, `approval_level`, `tier_level`, `resolver_code`) đồng bộ trên cả 6 bảng cốt lõi: `eas.request_type`, `eas.config_release`, `eas.request`, `eas.request_revision`, `eas.workflow_instance`, `eas.approval_step`.
3. **Vượt qua 100% Quality Gates của CI/CD (`.github/workflows/ci.yml`)**:
   - Khắc phục kiểm định cơ sở dữ liệu WASM PGlite: Đồng bộ 263 cột và 140 CHECK constraints sau khi tích hợp metadata danh mục nghiệp vụ.
   - Khắc phục toàn bộ cảnh báo / lỗi linter Backend: `ruff check` (0 lỗi), `ruff format` (100% chuẩn định dạng 92 tệp Python).
   - Khắc phục toàn bộ lỗi Frontend ESLint: Triệt tiêu hoàn toàn cascading render trong `useEffect`, loại bỏ vi phạm ARIA `tabIndex` trên các phần tử cuộn, đảm bảo dependencies hook sạch sẽ.

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

## 4. Báo Cáo Chất Lượng Quality Gates (100% PASS)

| Trạm kiểm định (Quality Gate) | Lệnh thực thi kiểm tra | Kết quả đạt được | Trạng thái |
| :--- | :--- | :--- | :---: |
| **1. Secret Gate** | `python scripts/check_repository_secrets.py` | `SECRET_GATE=PASS` (Không có API keys / mật khẩu) | ✅ PASS |
| **2. Database Schema Gate** | `cd database/EAS_Supabase_SQL/validation && npm test` | `sql_assertions: 86, result: PASS` trên PostgreSQL 18.3 WASM | ✅ PASS |
| **3. Backend Lint & Format** | `ruff check` & `ruff format --check` | `All checks passed! 92 files already formatted` | ✅ PASS |
| **4. Frontend Lint & Build** | `npm run lint` & `npm run build` | `0 errors, 0 warnings`, bundle Vite tạo thành công | ✅ PASS |
| **5. Frontend Unit Tests** | `node --test e2e/domain.test.mjs` | `8/8 tests passed` (FSM guards, RBAC, SoD) | ✅ PASS |
| **6. Container & Docs Gate** | `validate_env.py` & `validate_docs.py` | `compose: 27 vars, api: 26 vars; DOCS_GATE=PASS` | ✅ PASS |
| **7. Django & Regression Suite** | `python manage.py test ...` | `Ran 218 tests in 16.167s - OK` (218/218 tests) | ✅ PASS |
| **8. Standalone AI & Logger Tests**| `python tests/run_tests.py` | `Ran 15 tests - OK` (Inference fallback, anti-SSRF, logger) | ✅ PASS |
