# Kiểm thử luồng yêu cầu, bảo mật cổng, AI tự duyệt và danh mục 10 nhóm

Nhánh `dat` → `main`. 36 commit, 111 file (kể cả commit cập nhật mô tả này). Đã thử gộp với `main` hiện tại: **không xung đột**.

> ⚠️ **Trước khi deploy phải chạy migration trên Supabase** (mục "Việc cần làm khi deploy"). Code đã viết để vẫn chạy được khi migration chưa áp dụng: các tính năng mới chỉ tự bật sau khi bảng/cột tương ứng tồn tại.

## Tóm tắt thay đổi

### Phần 1 — Bảo mật & lỗi nghiệp vụ
- **Tách cổng đúng vai trò:** admin thuần (như `admin@eas.com`) chỉ vào cổng quản trị; người vừa quản trị vừa duyệt/thực hiện dùng được cả hai cổng (trước đây bị chặn khỏi cổng nhân viên nên không duyệt được hồ sơ).
- **Chặn ở proxy:** nginx cổng nhân viên trả 404 cho `/api/v1/admin/`, `/api/v1/ops/`, `/api/v1/internal/`; cổng quản trị có `nginx.conf` riêng; gateway trả 404 cho `/api/v1/internal/`. API vẫn tự kiểm tra quyền (lớp thứ hai).
- **Bỏ mật khẩu cứng:** không còn mặc định `Admin@123456`; mật khẩu seed đọc từ biến môi trường và bắt đổi ở lần đăng nhập đầu.
- **AI tự duyệt trọng số 1–2:** worker gọi endpoint nội bộ của API (có secret) để AI duyệt bằng tài khoản hệ thống `EAS AI`; vẫn qua đủ trigger, phân quyền và audit như người duyệt. Đã sửa lỗi idempotency key khiến AI tự duyệt luôn thất bại trên DB thật.
- **Thu hồi quyết định AI trong 24 giờ:** người duyệt trong phạm vi (không phải người tạo) bấm "Thu hồi duyệt tự động của AI" → hồ sơ quay về chờ duyệt thủ công, ghi audit, AI không tự duyệt lại hồ sơ đó.
- **Quy định AI lưu trong DB** (`eas.ai_policy_version`) làm nguồn chính; AI service chỉ cache, tự kéo phiên bản đang dùng khi khởi động trống. Bộ luật có hiệu lực ngay (đo trung vị 18 ms, không cần train lại).
- **Giao việc xuống cấp dưới:** người duyệt cuối được chọn cấp dưới trực tiếp có quyền EXECUTOR để giao việc.
- **Thăng cấp không phải đăng nhập lại:** cấp/sửa role không còn hủy phiên; thu hồi role vẫn hủy phiên.

### Phần 2 — Danh mục loại yêu cầu
- 10 nhóm mới: Tài chính & Mua sắm (`FINANCE`), Cấp phát tài nguyên (`RESOURCE`), Mượn cơ sở vật chất (`FACILITY`), Công việc (`WORK`), Nhân sự (`HR`), Nghỉ phép & Chấm công (`TIME`), CNTT & Bảo mật (`IT`), Pháp chế & Hợp đồng (`LEGAL`), Kinh doanh & Marketing (`SALES`), Hành chính & Kho (`ADMIN`).
- **58 loại đang dùng** (45 giữ, **13 mới**), **8 loại trùng ngưng dùng** (giữ lịch sử): `ASSET_PURCHASE` → `EQUIPMENT`, `SOFTWARE_ACCESS` → `ACCESS`, `ROOM_STUDIO` → `ROOM_BOOKING`, `ROOM_VEHICLE` → `ROOM_BOOKING`, `LEAVE_ANNUAL` → `LEAVE`, `LEAVE_LONG` → `LEAVE`, `OVERTIME_APPROVAL` → `OVERTIME_REQ`, `FACILITY_MAINTENANCE` → `FACILITY_REPAIR`.
- `IT_SUPPORT` chuyển người thực hiện từ Hành chính sang IT (release mới, release cũ giữ nguyên).
- Nguồn dữ liệu duy nhất: `api_core/catalog/catalog_v2.json`; giao diện dùng bản sinh `web_client/src/catalogV2.js` (`python scripts/generate_catalog_js.py`, có test chống lệch).

### Phần 3 — Tách code admin/user
- Màn hình quản trị chỉ tải ở cổng quản trị (lazy-load, chỉ entry `web_admin` nạp). Đã build kiểm tra: bundle cổng nhân viên không chứa màn hình quản trị; CI có bước `scripts/check_client_bundle.py`.

### Phần 4 — Ưu tiên trung bình
- Tài khoản `EAS AI` đánh dấu hệ thống: ẩn mặc định trong quản lý người dùng, không sửa/vô hiệu hóa/đổi quyền được qua UI và API.
- Xóa `ingest_policy` / `toggle_maintenance` cũ (không có xác thực, không còn nơi gọi).
- Trang "Bộ luật quy định AI" cho POLICY_ADMIN: tải tệp JSON, danh sách phiên bản, kích hoạt/khôi phục.
- **Ủy quyền duyệt** theo khoảng thời gian (trang Tài khoản). Khi bước duyệt kích hoạt: dùng người được ủy quyền; không có ủy quyền mà người duyệt vắng (theo chấm công) → chuyển lên quản lý trực tiếp. REWORK cũng thay người thực hiện vắng.
- Chấm công khớp theo mã nhân viên, email làm dự phòng; lệnh `sync_employee_codes` báo bản ghi không khớp.
- Dockerfile ai-service nhiều tầng, PaddlePaddle ở layer riêng có cache, thêm `ai_service/.dockerignore` (trước đây thư mục `.venv-ai` local bị đưa vào build context). **Đo ngày 02/11: image 8,5 GB → 3,41 GB; build context còn 21,7 MB.** Đã bổ sung `libgl1` (OpenCV của PaddleOCR cần, thiếu thì OCR lỗi khi chạy) — phát hiện khi build thật.
- **Thu gọn build context gốc:** `.dockerignore` ở thư mục gốc loại `ai_service/`, `mobile_app/`, `database/`, `tests/`, `scripts/`, `plans/`, cache IDE/ruff và log. Các image `api`, `worker`, `web`, `web-admin` chỉ copy `api_core/`, `manage.py`, `project_env.py`, `web_client/`, `web_admin/`, nhưng trước đây vẫn phải gửi cả repo vào Docker mỗi lần build — thừa khoảng **2,2 GB** trên máy dev (venv AI local 1,4 GB + `ai_service/training/data` 824 MB). Có test chặn trường hợp loại nhầm thư mục mà Dockerfile cần.
- Smoke test OCR chạy PaddleOCR thật trên 3 hóa đơn tự sinh, thêm job CI `ocr-smoke`; bộ trích xuất trường chịu được OCR mất dấu tiếng Việt.

### Phần 5 — Ưu tiên thấp
- Menu tự tải lại quyền (`/me`) khi quay lại tab và sau khi đổi quyền (gộp lời gọi trong 5 giây).
- Test secret-policy và test email không còn bị `.env` local ảnh hưởng (`EAS_SKIP_DOTENV`).
- Cổng Redis lấy từ biến môi trường; Redis của Docker publish ra `127.0.0.1:6380` để không đụng Redis có sẵn ở 6379 trên máy.

### Phần 7 — Tối ưu hiệu năng & Docker (02/11)

| Hạng mục | Trước | Sau |
|---|---|---|
| Request OCR đầu tiên sau khi khởi động AI service | 21,3 s | **1,6 s** (các lần sau 0,8 s) |
| Bundle JS cổng nhân viên (tải lần đầu) | 451,6 KB (gzip ~130 KB) | **335,1 KB** (gzip 99,6 KB), 6 màn hình phụ thành chunk lazy |
| Image ai-service | 8,5 GB | **3,69 GB** |
| Build context của api/worker/web/web-admin | cả repo (+~2,2 GB venv AI và dữ liệu huấn luyện) | ≤ 5,4 MB; build 5 image mất 1 phút 27 giây |
| 3 test fallback của AI client | ~10 s, phụ thuộc AI service có chạy hay không | ~2 s, kết quả cố định |

- **Làm nóng OCR:** AI service khởi tạo PaddleOCR trong luồng nền khi khởi động (`/health` không bị chặn); khóa trong tiến trình + khóa file giữa các worker uvicorn để không tải model trùng; model lưu trong volume `ai_ocr_models` nên chỉ tải một lần. Tắt bằng `OCR_WARMUP=false`.
- **Sửa 2 lỗi chỉ lộ ra khi chạy container thật:** thiếu `libgl1` (OpenCV của PaddleOCR không import được) và user `aiuser` có `HOME=/nonexistent` nên PaddleOCR không ghi được model → OCR trong container đều lỗi. Đã sửa, kèm test.
- **Đã kiểm tra trên stack Docker thật:** cổng nhân viên 8080 trả 404 cho `/api/v1/admin/`, `/api/v1/ops/`, `/api/v1/internal/`; cổng quản trị 8081 vẫn tới được API admin (401 khi chưa đăng nhập); gateway 8088 trả 404 cho `/api/v1/internal/`; API trả 401 cho `/internal` khi thiếu secret; Redis trả lời ở `127.0.0.1:6380`; OCR trong container đọc đúng 3/3 hóa đơn mẫu.

## Kết quả kiểm thử (chạy local ngày 02/11/2026)

| Bộ kiểm thử | Kết quả |
|---|---|
| Django `python manage.py test` | **385 đạt**, 1 bỏ qua (smoke OCR khi Python không có PaddleOCR) |
| `python tests/run_tests.py` | **150 đạt** |
| AI `tests.integration` (scenarios + service) | **29 đạt** |
| Smoke OCR với PaddleOCR thật (`tests/ocr_smoke`) | **3/3 đạt** — số tiền, ngày, nhà cung cấp đúng 3/3 ảnh; chạy được cả trong container ai-service |
| Frontend `web_client` `npm test` | **52 đạt**; lint sạch; build OK |
| `web_admin` build | OK |
| Kiểm tra bundle cổng nhân viên | Không chứa màn hình quản trị |
| ruff 0.16.10 (bản CI) check + format | Sạch |

Số liệu OCR: độ tin cậy 95,7–96,6%; đọc đúng chữ 97,8–99,2% nhưng **giữ đúng dấu chỉ 83,1–88,5%** (giới hạn của model PaddleOCR `vi`), nên tên nhà cung cấp trả về không dấu.

Chưa kiểm thử được: chạy trên Supabase thật sau migration (cần chạy migration trước).

## Danh mục loại yêu cầu mới

Trọng số 1–5. Vòng đời: **A** = duyệt xong là hoàn tất; **B** = duyệt → thực hiện; **C** = duyệt → thực hiện → nghiệm thu.

| Nhóm | Mã | Tên | Trọng số | Vòng đời | Luồng duyệt |
|---|---|---|---|---|---|
| Tài chính & Mua sắm | `ADVANCE_LARGE` | Tạm ứng dự án lớn (>50tr) | 4 | B | QL trực tiếp → Kế toán → Giám đốc ⇒ thực hiện: FINANCE |
|  | `ADVANCE_MEDIUM` | Tạm ứng chi phí (10-50tr) | 3 | B | QL trực tiếp → Kế toán ⇒ thực hiện: FINANCE |
|  | `ADVANCE_SMALL` | Tạm ứng chi phí (<10tr) | 2 | B | QL trực tiếp → Kế toán ⇒ thực hiện: FINANCE |
|  | `BUDGET_REALLOCATION` | Điều chuyển & bổ sung ngân sách liên bộ phận | 5 | C | QL trực tiếp → PM → Vận hành → Kế toán → Giám đốc ⇒ thực hiện: FINANCE ⇒ nghiệm thu: Người tạo |
|  | `EQUIPMENT` | Mua sắm thiết bị / tài sản | 3 | C | QL trực tiếp (khi amount_gt 50000000: QL trực tiếp → Kế toán → Giám đốc) (khi amount_gte 10000000: QL trực tiếp → Kế toán) ⇒ thực hiện: ASSET ⇒ nghiệm thu: Người tạo |
|  | `EXPENSE_CLAIM` | Thanh toán chi phí | 3 | A | QL trực tiếp → Kế toán (khi amount_gt 20000000: QL trực tiếp → Kế toán → Giám đốc) |
|  | `PURCHASE_REQUEST` | Đề nghị mua sắm | 3 | B | QL trực tiếp (khi amount_gt 50000000: QL trực tiếp → Kế toán → Giám đốc) (khi amount_gte 5000000: QL trực tiếp → Kế toán) ⇒ thực hiện: PROCUREMENT |
|  | `REFUND_COMPENSATION` | Hoàn tiền / Đền bù | 2 | A | QL trực tiếp |
|  | `REIMBURSEMENT` | Quyết toán tạm ứng | 2 | B | QL trực tiếp → Kế toán ⇒ thực hiện: FINANCE |
|  | `SAAS_LICENSE_BUY` | Mua bản quyền phần mềm mới | 3 | C | QL trực tiếp → IT → Kế toán ⇒ thực hiện: PROCUREMENT ⇒ nghiệm thu: QL trực tiếp |
|  | `SALARY_ADVANCE` | Ứng lương **(mới)** | 2 | B | QL trực tiếp → Kế toán ⇒ thực hiện: FINANCE |
|  | `SUPPLIER_ONBOARDING` | Thẩm định & phê duyệt nhà cung cấp mới | 3 | B | QL trực tiếp → TP Mua sắm → Kế toán ⇒ thực hiện: PROCUREMENT |
|  | `TAX_INVOICE_ISSUE` | Phát hành / điều chỉnh hóa đơn VAT | 1 | B | Kế toán ⇒ thực hiện: FINANCE |
|  | `VENDOR_PAYMENT` | Thanh toán Hợp đồng Vendor | 5 | C | QL trực tiếp → Kế toán → Giám đốc ⇒ thực hiện: FINANCE ⇒ nghiệm thu: QL trực tiếp |
| Cấp phát tài nguyên | `ACCESS` | Cấp tài khoản & quyền truy cập | 2 | B | QL trực tiếp (khi app_code_in ['PRODUCTION_DB', 'AWS_CONSOLE', 'ERP_SAP']: QL trực tiếp → Giám đốc) ⇒ thực hiện: IT |
|  | `LAPTOP_PROVISION` | Cấp máy tính / thiết bị làm việc | 2 | C | QL trực tiếp ⇒ thực hiện: IT ⇒ nghiệm thu: Người tạo |
|  | `OFFICE_SUPPLIES` | Cấp văn phòng phẩm | 1 | B | QL trực tiếp ⇒ thực hiện: ADMIN |
|  | `RESOURCE_REVOKE` | Thu hồi tài khoản / thiết bị **(mới)** | 2 | C | QL trực tiếp ⇒ thực hiện: IT ⇒ nghiệm thu: QL trực tiếp |
| Mượn cơ sở vật chất | `ACCESS_FACILITY` | Cấp thẻ ra vào | 2 | B | QL trực tiếp → Vận hành ⇒ thực hiện: FACILITY |
|  | `EQUIPMENT_BORROW` | Mượn thiết bị / đồ dùng | 2 | C | QL trực tiếp → IT ⇒ thực hiện: ASSET ⇒ nghiệm thu: Người tạo |
|  | `ROOM_BOOKING` | Đặt phòng họp | 1 | A | QL trực tiếp |
|  | `VEHICLE_BOOKING` | Mượn xe công vụ **(mới)** | 2 | C | QL trực tiếp ⇒ thực hiện: ADMIN ⇒ nghiệm thu: Người tạo |
|  | `VISITOR_SECURITY_PASS` | Thẻ an ninh khách & đối tác ra vào | 1 | A | QL trực tiếp |
| Công việc | `CROSS_DEPT_SUPPORT` | Hỗ trợ liên phòng ban **(mới)** | 2 | C | QL trực tiếp → Vận hành ⇒ thực hiện: ADMIN ⇒ nghiệm thu: Người tạo |
|  | `PROJECT_INITIATION` | Đề xuất khởi tạo dự án **(mới)** | 4 | C | QL trực tiếp → PM → Kế toán → Giám đốc ⇒ thực hiện: TECH ⇒ nghiệm thu: PM |
|  | `TASK_REQUEST` | Yêu cầu xử lý công việc **(mới)** | 1 | C | QL trực tiếp ⇒ thực hiện: ADMIN ⇒ nghiệm thu: Người tạo |
| Nhân sự | `BUSINESS_TRIP` | Đăng ký đi công tác | 3 | B | QL trực tiếp → HR (khi amount_gt 30000000: QL trực tiếp → Kế toán → Giám đốc) ⇒ thực hiện: ADMIN |
|  | `DISCIPLINE_REQ` | Đề xuất kỷ luật **(mới)** | 4 | B | QL trực tiếp → HR → Giám đốc ⇒ thực hiện: HR |
|  | `EMPLOYEE_ONBOARDING` | Tiếp nhận nhân viên mới | 3 | C | HR → QL trực tiếp ⇒ thực hiện: HR ⇒ nghiệm thu: QL trực tiếp |
|  | `HR_CERTIFICATE` | Xin giấy xác nhận công tác / thu nhập **(mới)** | 1 | B | HR ⇒ thực hiện: HR |
|  | `INTERNAL_TRANSFER` | Điều chuyển nội bộ | 3 | B | QL trực tiếp → HR → Giám đốc ⇒ thực hiện: HR |
|  | `PROMOTION_REQ` | Đề xuất thăng chức **(mới)** | 4 | B | QL trực tiếp → HR → Giám đốc ⇒ thực hiện: HR |
|  | `RECRUITMENT_REQ` | Yêu cầu tuyển dụng nhân sự | 4 | C | QL trực tiếp → HR → Kế toán → Giám đốc ⇒ thực hiện: HR ⇒ nghiệm thu: QL trực tiếp |
|  | `RESIGNATION` | Thôi việc / Bàn giao | 4 | C | QL trực tiếp → HR → Giám đốc ⇒ thực hiện: HR ⇒ nghiệm thu: Người tạo |
|  | `REWARD_REQ` | Đề xuất khen thưởng **(mới)** | 3 | B | QL trực tiếp → HR (khi amount_gt 10000000: QL trực tiếp → HR → Giám đốc) ⇒ thực hiện: FINANCE |
|  | `SALARY_ADJUSTMENT` | Điều chỉnh lương **(mới)** | 5 | B | QL trực tiếp → HR → Kế toán → Giám đốc ⇒ thực hiện: HR |
|  | `TRAINING_COURSE` | Đăng ký đào tạo & chứng chỉ nghề nghiệp | 2 | B | QL trực tiếp → HR ⇒ thực hiện: HR |
| Nghỉ phép & Chấm công | `ATTENDANCE_ADJUSTMENT` | Điều chỉnh chấm công | 1 | A | QL trực tiếp |
|  | `LEAVE` | Nghỉ phép | 1 | A | QL trực tiếp (khi days_gt 2: QL trực tiếp → Giám đốc) |
|  | `LEAVE_SPECIAL` | Nghỉ phép đặc biệt | 2 | A | QL trực tiếp → HR (khi days_gt 3: QL trực tiếp → HR → Giám đốc) |
|  | `OVERTIME_REQ` | Đăng ký làm thêm giờ (OT) | 2 | B | QL trực tiếp ⇒ thực hiện: HR |
|  | `WFH_REQ` | Làm việc từ xa (WFH) | 1 | A | QL trực tiếp |
| CNTT & Bảo mật | `DATA_UAT_EXPORT` | Trích xuất dữ liệu / UAT | 3 | B | IT → Bảo mật ⇒ thực hiện: TECH |
|  | `FEATURE_RELEASE` | Feature Request / Release | 3 | C | QL trực tiếp → IT ⇒ thực hiện: TECH ⇒ nghiệm thu: PM |
|  | `IT_SUPPORT` | Yêu cầu hỗ trợ IT | 1 | B | QL trực tiếp ⇒ thực hiện: IT |
|  | `PROD_DATA_ACCESS` | Cấp quyền Dữ liệu nhạy cảm/Server | 5 | C | QL trực tiếp → Bảo mật → CTO ⇒ thực hiện: IT ⇒ nghiệm thu: CTO |
|  | `SECURITY_INCIDENT_HOTFIX` | Khắc phục sự cố bảo mật & Hotfix khẩn cấp | 5 | C | QL trực tiếp → IT → Bảo mật → CISO → CTO ⇒ thực hiện: TECH ⇒ nghiệm thu: CTO |
|  | `SERVER_FIREWALL` | Cấp Server / Firewall | 3 | C | IT → Bảo mật → CTO ⇒ thực hiện: IT ⇒ nghiệm thu: CTO |
| Pháp chế & Hợp đồng | `CONTRACT_APPROVAL` | Duyệt hợp đồng | 5 | C | QL trực tiếp → Kế toán → Pháp chế ⇒ thực hiện: FINANCE ⇒ nghiệm thu: Pháp chế |
|  | `DOCUMENT_SEAL` | Đóng dấu / ký văn bản **(mới)** | 2 | B | QL trực tiếp → Pháp chế ⇒ thực hiện: ADMIN |
|  | `NDA_PRIVACY_CLEARANCE` | Thẩm định NDA & chia sẻ dữ liệu đối tác | 2 | B | QL trực tiếp → Pháp chế ⇒ thực hiện: LEGAL |
|  | `POLICY_ISSUANCE` | Ban hành quy chế nội bộ **(mới)** | 4 | B | QL trực tiếp → Pháp chế → Giám đốc ⇒ thực hiện: LEGAL |
| Kinh doanh & Marketing | `FLASH_SALE_VOUCHER` | Flash Sale / Voucher | 4 | B | QL trực tiếp → Kế toán ⇒ thực hiện: MARKETING |
|  | `MARKETING_CAMPAIGN` | Ngân sách chiến dịch Marketing & Sự kiện | 4 | C | QL trực tiếp → Marketing → Kế toán → Giám đốc ⇒ thực hiện: MARKETING ⇒ nghiệm thu: Người tạo |
|  | `SPECIAL_DISCOUNT` | Phê duyệt chiết khấu thương mại đặc biệt | 3 | A | QL trực tiếp → Marketing → Kế toán |
| Hành chính & Kho | `ASSET_DISPOSAL` | Thanh lý & hủy tài sản cố định | 4 | C | QL trực tiếp → Kho → Kế toán → Giám đốc ⇒ thực hiện: ASSET ⇒ nghiệm thu: QL trực tiếp |
|  | `FACILITY_REPAIR` | Sửa chữa sự cố văn phòng | 2 | C | Vận hành ⇒ thực hiện: FACILITY ⇒ nghiệm thu: QL trực tiếp |
|  | `WAREHOUSE_TRANSFER` | Luân chuyển kho | 3 | B | Kho ⇒ thực hiện: WAREHOUSE |

## Migration — chạy theo thứ tự trên Supabase SQL Editor

| # | File | Nội dung | Rollback |
|---|---|---|---|
| 1 | `database/migrations/08_ai_system_account.sql` | Tài khoản hệ thống `EAS AI` | `rollback/08_ai_system_account_rollback.sql` |
| 2 | `database/migrations/09_ai_policy_store.sql` | Bảng `eas.ai_policy_version` | `rollback/09_ai_policy_store_rollback.sql` |
| 3 | `database/migrations/10_ai_auto_approve_revoke.sql` | Cho phép thu hồi AI tự duyệt trong 24 giờ | `rollback/10_ai_auto_approve_revoke_rollback.sql` (đã đối chiếu khôi phục đúng hàm gốc) |
| 4 | `database/migrations/11_request_category_regroup.sql` | 10 nhóm, trọng số, ngưng 8 loại | `rollback/11_request_category_regroup_rollback.sql` |
| 5 | `database/migrations/12_request_types_new.sql` | 13 loại mới + cấu hình đã công bố | `rollback/12_request_types_new_rollback.sql` (ngưng dùng, không xóa) |
| 6 | `database/migrations/13_it_support_executor.sql` | IT_SUPPORT do IT thực hiện | `rollback/13_it_support_executor_rollback.sql` |
| 7 | `database/migrations/14_system_account_flag.sql` | Cột `is_system_account` | `rollback/14_system_account_flag_rollback.sql` |
| 8 | `database/migrations/15_approval_delegation.sql` | Bảng ủy quyền duyệt | `rollback/15_approval_delegation_rollback.sql` |
| 9 | `database/migrations/16_employee_code.sql` | Cột `employee_code` | `rollback/16_employee_code_rollback.sql` |
| 10 | `database/mock_enterprise_sql/migrations/004_hrm_attendance.sql` | Bảng chấm công mock | (bảng mock, xóa tay nếu cần) |
| 11 | `database/mock_enterprise_sql/migrations/005_attendance_employee_code.sql` | Chấm công theo mã nhân viên | `mock_enterprise_sql/migrations/rollback/005_attendance_employee_code_rollback.sql` |

Rollback chạy **ngược thứ tự** (ví dụ rollback 12 trước 11).

## Việc cần làm khi deploy

1. Chạy migration theo bảng trên.
2. Sau migration:
   - Nếu container AI đang có file quy định cũ: `python manage.py import_ai_policy_file ai_service/data/active_enterprise_policy.json --operator <email POLICY_ADMIN>`.
   - `python manage.py sync_employee_codes` (chạy thử), rồi thêm `--apply` để ghi mã nhân viên.
3. Biến môi trường mới (xem `.env.example`):
   - **Production bắt buộc** `EAS_WORKER_INTERNAL_SECRET` (≥32 ký tự ngẫu nhiên; thiếu thì API không khởi động).
   - Tùy chọn: `EAS_AI_AUTO_APPROVE_ENABLED`, `EAS_AI_AUTO_APPROVE_MAX_WEIGHT` (mặc định 2), `EAS_DEV_DEFAULT_PASSWORD`, `EAS_SEED_PASSWORD`, `EAS_REDIS_HOST`, `EAS_REDIS_PORT`, `EAS_REDIS_HOST_PORT` (mặc định 6380).
4. Build lại image: `docker compose up -d --build` (api, worker, web, web-admin, gateway, ai-service).

## Gợi ý dọn dẹp (không nằm trong PR, cần nhóm quyết)

- 13 script chẩn đoán/khởi động ở thư mục gốc không được file nào tham chiếu (`check_approval_menu_readonly.py`, `check_schema_contract.py`, `diagnose_supabase.py`, `diagnose_eas_lists_readonly.py`, `diagnose_readiness_readonly.py`, `recover_admin_password_interactive.py`, `report_conformance.py`, `verify_admin_password_local.py`, `check_local.cmd`, `setup_local.cmd`, `start_backend.ps1`, `start_frontend.ps1`…). Có thể gom vào `scripts/` hoặc xóa nếu không còn ai dùng.
- Dữ liệu huấn luyện sinh tự động `ai_service/training/data/partitions` (801 MB, đã gitignore) tạo lại được bằng `enterprise_bigdata_generator.py`, nhưng dữ liệu sinh ngẫu nhiên nên lần sau sẽ khác.

## Quyết định cần trưởng nhóm xác nhận

- Hàm DB `eas.ai_revocable` ghi cứng id tài khoản AI `00000002-0000-4000-8000-0000000000a1` (khớp migration 08 và mặc định `EAS_AI_SYSTEM_USER_ID`). Đổi biến này thì phải sửa hàm.
- Thu hồi AI tự duyệt: mọi APPROVER trong phạm vi phòng/loại (trừ người tạo) đều thu hồi được, không chỉ người duyệt gốc.
- `api_core/workflow/maintenance.py` không còn nơi gọi sau khi xóa hàm cũ; đang giữ lại.
- Dữ liệu HRM giả lập (55 nhân viên, email `@example.test`) không trùng 42 tài khoản: `sync_employee_codes` chỉ khớp được 2 người theo tên. Chấm công vẫn chạy nhờ dự phòng email; muốn khớp mã thật cần seed lại HRM.

## Chưa hoàn thành

- Tải trước model OCR lúc build luôn lỗi `zlib ... inconsistent stream state` dưới BuildKit (lúc chạy container thì tải được); đã xử lý bằng volume `ai_ocr_models` + làm nóng lúc khởi động, nhưng lần khởi động đầu trên máy mới vẫn tải model (~20 s, chạy nền).
- Kiểm thử end-to-end trên Supabase thật cho các tính năng cần migration (thực hiện sau khi chạy migration).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
