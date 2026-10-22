# Pull Request: Hoàn thiện Toàn diện Phân hệ `api_core` P0

## Thông Tin Pull Request
- **Branch Nguồn:** `huy`
- **Branch Đích:** `main`
- **Repository:** `https://github.com/PhanQuangHuy2310/DATN`
- **Link tạo PR trên GitHub:** [Tạo Pull Request huy -> main](https://github.com/PhanQuangHuy2310/DATN/compare/main...huy?expand=1)
- **Tài liệu tham chiếu:** [docs/eas_api_core_master_prompt.md](eas_api_core_master_prompt.md), [plans/completed/2026-10-22_api_core_full_remediation.md](../plans/completed/2026-10-22_api_core_full_remediation.md), [plans/reports/2026-10-22_api_core_p0_final_report.md](../plans/reports/2026-10-22_api_core_p0_final_report.md)

---

## 1. Mục Tiêu & Phạm Vi
Pull Request này khắc phục triệt để các điểm nghẽn và hoàn thiện 100% năng lực phân hệ `api_core` P0 theo tài liệu chỉ đạo [eas_api_core_master_prompt.md](eas_api_core_master_prompt.md). Tất cả các sửa đổi tuân thủ nghiêm ngặt:
- Bộ 30 bảng cơ sở dữ liệu `eas.*`, 27 trigger/function bảo vệ bất biến toàn cục.
- 8 State Machines và 22 Sequence Diagrams đã chốt.
- Nguyên tắc an toàn dữ liệu: Không thêm ORM migration vào `eas.*`, sử dụng parameterized SQL (%s) tuyệt đối, kiểm soát chặt chẽ SoD (Separation of Duties), Anti-IDOR (404 thay vì 403), và bảo vệ tính bất biến mật mã RFC 8785 (JCS) + SHA-256.

---

## 2. Các Hạng Mục Đã Triển Khai (Tasks 1 - 8)

### 🔹 Task 1: Nghiệp Vụ & Trigger Service
- **Khắc phục `UniqueViolation` trên `request_participant`:** Bổ sung `ON CONFLICT (request_id, actor_id, participant_role) DO NOTHING` khi nộp lại hồ sơ từ trạng thái `NEEDS_INFO`, đồng thời lưu trữ đầy đủ `acceptor_id`.
- **Bảo toàn tệp đính kèm nháp:** Tự động sao chép các tệp đính kèm `CLEAN` từ `revision_attachment` sang `draft_attachment` khi hồ sơ bị yêu cầu bổ sung thông tin (`NEEDS_INFO`), giúp người yêu cầu không bị mất tệp khi cập nhật gửi lại.
- **Xác thực phiên bản cấu hình quy trình:** Kiểm tra `viewed_release_id` khớp với `active_release_id` của loại yêu cầu; nếu có sai lệch, từ chối với mã lỗi `CONFIG_CHANGED` (HTTP 409).
- **Kiểm tra tính khả dụng của người nhận kế tiếp:** Trả lỗi chuẩn `ASSIGNEE_UNAVAILABLE` (HTTP 409) ở các bước Approval, Execution và Rework Acceptance nếu người nhận bị vô hiệu hóa hoặc không còn hoạt động.
- **Bảo mật phản hồi Idempotency (`TC058`):** Kiểm tra quyền truy cập (Read Authorization) của Actor hiện tại trước khi phát lại phản hồi đã lưu, ngăn chặn rò rỉ dữ liệu qua Idempotency-Key.

### 🔹 Task 2: Hồ Sơ Nháp, Báo Vướng & Tải Tệp Chống IDOR
- **Lưu nháp an toàn (`PATCH /api/v1/requests/<id>`):** Bổ sung hàm `validate_draft_payload` cho phép lưu nháp khi chưa đủ các trường bắt buộc, nhưng kiểm tra nghiêm ngặt ngăn chặn HTML/Script injection và mass-assignment.
- **Báo vướng / Từ chối nhận việc (`POST /api/v1/requests/<id>/issues`):** Triển khai endpoint cho phép người thực hiện báo cáo vướng mắc hoặc lý do không thể nhận việc khi hồ sơ ở trạng thái `IN_PROGRESS`.
- **Anti-IDOR Predicate:** Áp dụng nguyên tắc Fail-closed cho tất cả các endpoint truy vấn chi tiết và tải tệp — trả `404 Not Found` (thay vì 403) khi tài nguyên không tồn tại hoặc actor không có quyền truy cập.
- **Tải tệp an toàn qua `get_private_object`:** Thiết lập headers bảo mật `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'` và ghi nhận vết kiểm toán (Audit Trail) cho mỗi lượt tải.

### 🔹 Task 3: Module Điều Phối OPS Admin
- Triển khai module `api_core/workflow/ops_service.py`:
  - `GET /api/v1/ops/requests`: Truy vấn danh sách metadata hồ sơ điều phối, chỉ cho phép các trường an toàn trong whitelist, bảo vệ thông tin PII.
  - `POST /api/v1/requests/<id>/reassign`: Cho phép `OPS_ADMIN` điều chuyển `APPROVER`, `EXECUTOR`, `ACCEPTOR`, `PLANNED_EXECUTOR` có kiểm tra SoD và tự động tách attempt độc lập khi hồ sơ đang ở trạng thái `RUNNING`.
  - `POST /api/v1/ops/outbox/<id>/replay`: Cho phép phát lại các sự kiện outbox đã rơi vào trạng thái `DEAD`.

### 🔹 Task 4: Module Quản Trị Cấu Hình Quy Trình
- Triển khai module `api_core/workflow/config_service.py` cho `POLICY_ADMIN`:
  - Đầy đủ vòng đời quản lý bản phát hành quy trình: List, Create/Clone, Patch Draft, Validate Candidate, Publish.
  - Tính toán `validation_hash` và `content_sha256` dựa trên chuẩn hóa JSON Canonicalization RFC 8785 (JCS) kết hợp SHA-256.
  - Đảm bảo bản phát hành đã `PUBLISHED` là bất biến (immutable) tuyệt đối.

### 🔹 Task 5: Nâng Cấp Worker, Thông Báo, Báo Cáo & Audit
- **Nâng cấp `api_core/worker.py`:** Tự động phát hiện và bỏ qua thông báo nếu người nhận đã bị vô hiệu hóa hoặc thu hồi quyền (`inactive/revoked`), ghi sự kiện vào `admin_event` và ghi nhận audit log cho các cảnh báo vi phạm SLA.
- **Module `api_core/workflow/reporting.py`:**
  - Quản lý danh sách thông báo và đánh dấu đã đọc (`/api/v1/notifications`).
  - Tổng hợp báo cáo chỉ số yêu cầu (`/api/v1/reports/requests`) với kiểm tra chặt chẽ biên thời gian (tối đa 366 ngày, `created_from <= created_to`).
  - Động cơ xác minh chuỗi băm audit `verify_audit_chain` theo thuật toán SHA-256 canonical.

### 🔹 Task 6: 4 Management Commands Quản Trị Hệ Thống
1. `python manage.py identity_import`: Nạp cơ cấu tổ chức, người dùng từ tệp JSON; tích hợp thuật toán phát hiện chu kỳ trong cây phòng ban (chu kỳ -> exit code 2).
2. `python manage.py account_reset`: Reset mật khẩu hoặc trạng thái tài khoản an toàn qua biến môi trường `EAS_TEMP_PASSWORD` (tối thiểu 12 ký tự).
3. `python manage.py audit_verify`: CLI kiểm tra tính toàn vẹn mật mã của chuỗi hash audit (exit code 0 khi PASS, exit code 2 khi FAIL).
4. `python manage.py privacy_case`: Xử lý quyền riêng tư GDPR / Nghị định 13; chặn thao tác xóa nếu hồ sơ đang chịu lệnh giữ lại pháp lý (`active retention hold` -> exit code 2).

### 🔹 Task 7: Đồng Bộ URL Routes & Aliases
- Khai báo đầy đủ các route và alias chuẩn theo tài liệu thiết kế `03_Du_lieu_va_API_v2.docx`:
  - Hồ sơ: `/submit`, `/decisions` (alias: `/approval`), `/cancel` (alias: `/withdraw`), `/claim`, `/execution/submit` (alias: `/execution`), `/rework-acceptance` (alias: `/acceptance`).
  - Đính kèm: `/attachments/<id>`, `/attachments/<id>/download`.
  - Cấu hình & Điều phối: `/config-releases`, `/config-releases/<id>/validate`, `/config-releases/<id>/publish`, `/ops/requests`, `/ops/outbox/<id>/replay`, `/requests/<id>/reassign`.
  - Thông báo & Báo cáo: `/notifications`, `/notifications/<id>/read`, `/reports/requests`, `/requests/<id>/audit`, `/requests/<id>/audit/verify`.

### 🔹 Task 8: Bộ Kiểm Thử Bổ Sung & Quality Gates
- Bổ sung 2 bộ test suites mới:
  - `api_core/tests/test_ops_and_config.py` (bao phủ UC02, UC03, UC05, UC09, UC10, UC11)
  - `api_core/tests/test_reporting_and_cli.py` (bao phủ UC13, UC14, UC15, UC17 CLI commands)
- Tổng số bài test tự động đạt **95/95 PASS (100%)**.

---

## 3. Bằng Chứng Kiểm Định Thực Tế (Quality Gates)

```bash
# 1. Django Test Suite: 91 tests PASS (3.088s)
$env:EAS_ENV='test'; python manage.py test -v 2
Ran 91 tests in 3.088s - OK

# 2. Logger Security Test Suite: 4 tests PASS (0.000s)
python -m unittest -v test_logger.py
Ran 4 tests in 0.000s - OK

# 3. Ruff Linter: 0 errors
ruff check api_core manage.py test_logger.py scripts
All checks passed!

# 4. Ruff Formatter: 67 files formatted
ruff format --check api_core manage.py test_logger.py scripts
67 files already formatted

# 5. Python Bytecode Compiler: 0 syntax errors
python -m compileall -q api_core manage.py test_logger.py

# 6. Environment Validation: 3/3 profiles PASS
python scripts/validate_env.py --file .env.example --profile compose --allow-placeholders
python scripts/validate_env.py --file api_core/.env.example --profile api --allow-placeholders
python scripts/validate_env.py --file api_core/.env.worker.example --profile worker --allow-placeholders

# 7. Documentation & RTM Gate: PASS
python scripts/validate_docs.py
markdown_files=18, mermaid_blocks=68, unique_TC001_TC100=100, RTM_UC01_UC17=17, broken_links=0, DOCS_GATE=PASS
```

---

## 4. Danh Sách Files Thay Đổi

```text
Modified:
  - api_core/authn/urls.py
  - api_core/authn/views.py
  - api_core/config/urls.py
  - api_core/domain/__init__.py
  - api_core/domain/validation.py
  - api_core/storage.py
  - api_core/worker.py
  - api_core/workflow/attachments.py
  - api_core/workflow/service.py
  - api_core/workflow/urls.py
  - api_core/workflow/views.py
  - changelogs/README.md
  - plans/completed/README.md
  - plans/reports/README.md

Added:
  - api_core/management/commands/account_reset.py
  - api_core/management/commands/audit_verify.py
  - api_core/management/commands/identity_import.py
  - api_core/management/commands/privacy_case.py
  - api_core/tests/test_ops_and_config.py
  - api_core/tests/test_reporting_and_cli.py
  - api_core/workflow/config_service.py
  - api_core/workflow/ops_service.py
  - api_core/workflow/reporting.py
  - changelogs/2026-10-22_api_core_complete_p0.md
  - docs/eas_api_core_master_prompt.md
  - docs/pull_request_api_core_p0.md
  - plans/completed/2026-10-22_api_core_full_remediation.md
  - plans/reports/2026-10-22_api_core_p0_final_report.md
```

---

## 5. Checklist Trước Khi Merge
- [x] Không thêm ORM migration trên `eas.*`
- [x] 100% truy vấn SQL sử dụng parameterized syntax `%s`
- [x] Đã xử lý phân tách quyền SoD và ngăn chặn rò rỉ IDOR (trả 404 cho tài nguyên ngoài quyền)
- [x] 95/95 Unit/Contract tests chạy thành công
- [x] Tất cả các Quality Gates (`ruff`, `compileall`, `validate_env`, `validate_docs`) đều đạt chuẩn
