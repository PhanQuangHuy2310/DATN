# Release / Changelog: Hoàn Thiện Toàn Diện Hệ Thống EAS (Routing, AI Services, Security & Frontend RBAC)

## 1. Mục tiêu và Bối cảnh
Thực hiện chuẩn hóa và khắc phục toàn diện theo kế hoạch kiểm toán hệ thống EAS (`docs/1.md`):
- Đồng bộ toán tử định tuyến động giữa CSDL, tầng Domain và tầng Validation.
- Khắc phục triệt để lỗi không tương thích schema giữa `api_core` và `ai_service`, hỗ trợ đa định dạng mock data và loại bỏ đường dẫn tuyệt đối.
- Tích hợp các safe proxy endpoints cho AI Assist trong `api_core`.
- Tăng cường bảo mật toàn diện: Anti-SSRF, khóa tài liệu nhạy cảm trên Nginx, ép buộc secret sản xuất, siết CORS và Least Privilege trên CSDL.
- Nâng cấp giao diện người dùng `web_client` hỗ trợ đầy đủ 7 vai trò RBAC và trợ lý AI thông minh mà vẫn bảo toàn tương thích 100% với E2E smoke tests.

## 2. Các Hạng mục Triển khai Chính

### 2.1. Đồng bộ Ma trận Định tuyến (Route Rules Synchronization)
- **Toán tử mở rộng**: Bổ sung `days_gt` và `app_code_in` đồng bộ cùng `amount_gt` và `amount_gte` vào tập `SUPPORTED_OPERATORS` trong `api_core/domain/routing.py`.
- **Domain Validation**: Cập nhật `api_core/domain/validation.py` kiểm định chặt chẽ cấu trúc `days_gt` (số nguyên không âm) và `app_code_in` (mảng chuỗi ký tự không rỗng).
- **Database Trigger**: Cập nhật trigger `eas.guard_release()` trong `database/EAS_Supabase_SQL/00_eas_supabase_schema.sql` cho phép lưu trữ và kích hoạt release với các toán tử mới.
- **Payload Handling**: Bổ sung trích xuất trường ngày tháng từ payload đề xuất (`days`, `duration_days`, `total_days`, hoặc tính toán từ `start_date` / `end_date`) và hỗ trợ `amount_vnd` tùy chọn.
- **Kiểm thử**: Bổ sung unit tests cho `days_gt` và `app_code_in` trong `api_core/tests/test_domain.py`.

### 2.2. Khắc phục Schema Mismatch & Context Lookups AI
- **`mock_context.py`**:
  - `lookup_leave_balance`: Hỗ trợ cả 2 định dạng khóa (`code` và `employee_code`), nhãn (`label` và `display_name`), và chấp nhận số ngày nghỉ dạng số thực lẻ (ví dụ: `12.5` ngày).
  - `lookup_facility_available`: Hỗ trợ nhận diện tình trạng qua cả `is_available` (boolean) và `status` (string).
  - `lookup_department_budget`: Ánh xạ mã phòng ban sang mã cost center tài chính và truy vấn cả 2 trường hợp.
- **`ai_client.py` & `risk.py`**:
  - Hỗ trợ song song cả tham số legacy và schema `RiskInput` (`amount_vnd`, `num_attachments`, `past_requests_count`, `has_receipt`, `department`, `is_off_hours`).
  - Tích hợp Pydantic `model_validator(mode="before")` tự động ánh xạ dữ liệu đầu vào.
- **Training Scripts**: Thay thế toàn bộ đường dẫn tĩnh cục bộ bằng đường dẫn động `Path(__file__).resolve().parents[1]` trong `inspect_models.py` và `test_inference.py`.

### 2.3. Safe AI Assist Proxy Endpoints trong `api_core`
- **Endpoints**: Bổ sung 3 endpoint proxy an toàn tại `api_core/workflow/views.py`:
  - `POST /api/v1/ai/classify`
  - `POST /api/v1/ai/risk-score`
  - `POST /api/v1/ai/summarize`
- **Xác thực & Bảo mật**: Yêu cầu người dùng đăng nhập qua `@require_actor()`, tự động kèm `EAS_AI_INTERNAL_SECRET` khi gọi sang `ai_service`.
- **Contract Tests**: Bổ sung kiểm thử hợp đồng và xác thực 401 unauthenticated trong `api_core/tests/test_workflow_api.py`.

### 2.4. Tăng Cường Bảo Mật Đa Tầng (Security Hardening)
- **Nginx Protection**: Giới hạn truy cập các tài liệu OpenAPI nhạy cảm (`/docs`, `/redoc`, `/openapi.json`) chỉ cho phép mạng nội bộ (`127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`) và chặn toàn bộ bên ngoài.
- **Anti-SSRF OCR**: Thêm cơ chế kiểm tra `validate_safe_image_url()` trong `ai_service/routers/ocr.py` ngăn chặn gọi đến IP loopback, link-local, multicast, IP mạng riêng rọi nội bộ và các địa chỉ metadata đám mây (`169.254.169.254`, `metadata.google.internal`).
- **Production Secrets Validation**: Kiểm tra tính an toàn của `EAS_AI_INTERNAL_SECRET` và `internal_api_secret`, từ chối khởi động nếu môi trường là `production` mà vẫn sử dụng secret mặc định.
- **CORS Hardening**: Siết chặt cấu hình CORS tại `ai_service/main.py` theo danh sách nguồn hợp lệ `settings.cors_allowed_origins`.
- **CSDL Least Privilege**: Thu hồi quyền truy cập schema `eas` từ `PUBLIC`, loại bỏ phân quyền trực tiếp cho `anon` và `authenticated` trong `database/schema.sql` và migration init.

### 2.5. Nâng cấp Giao diện Frontend RBAC & AI Assist
- **Hỗ trợ 7 vai trò RBAC**: `REQUESTER`, `APPROVER`, `EXECUTOR`, `ACCEPTOR`, `OPS_ADMIN`, `POLICY_ADMIN`, `AUDITOR`.
- **Tính năng theo vai trò**:
  - Khởi tạo đề xuất kèm AI Assist phân loại danh mục, phân tích rủi ro và tóm tắt nội dung.
  - Phê duyệt / Từ chối / Chuyển tiếp đề xuất theo luồng nghiệp vụ.
  - Thực thi phiếu và Xác nhận nghiệm thu.
  - Quản trị quy tắc định tuyến chính sách và vận hành hệ thống.
  - Kiểm toán viên kiểm tra tính toàn vẹn của chuỗi băm mật mã (Cryptographic Hash Chain Verification).
- **Bảo toàn E2E Smoke Tests**: Duy trì 100% các selector `data-testid` và DOM elements phục vụ kiểm thử tự động.

## 3. Bằng Chứng Kiểm Thử & Quality Gates (100% XANH)
- **Django Tests:** `108/108 tests PASS` (14.2s).
- **AI Integration Tests:** `11/11 tests PASS` (2.4s).
- **Logger Tests:** `4/4 tests PASS`.
- **Frontend Build & Lint:** `npm run lint` PASS, `npm run build` PASS (135ms).
- **Ruff Linter & Formatter:** PASS (0 errors, 0 warnings, 79 files formatted).
- **Python Compiler:** `compileall` PASS (0 syntax errors).
- **Secret Scan:** `SECRET_GATE=PASS` (0 secret lộ).
- **Docs Gate:** `DOCS_GATE=PASS` (21 files, 68 diagrams, 0 broken links).
- **Environment Profiles:** `PASS` (22 required variables verified).
