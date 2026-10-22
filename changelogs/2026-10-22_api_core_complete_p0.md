# Release: Enterprise Approval System — Hoàn thiện Toàn diện Phân hệ `api_core` P0

## 1. Mục tiêu và Phạm vi
Bản phát hành này hoàn thiện 100% các năng lực và khắc phục triệt để các lỗi tiềm ẩn trong phân hệ `api_core` theo tài liệu `eas_api_core_master_prompt.md`, đảm bảo tính toàn vẹn với bộ 30 bảng `eas.*`, 27 trigger/function bảo vệ bất biến, tuân thủ nghiêm ngặt 8 State Machines và 22 Sequence Diagrams.

## 2. Các Hạng mục Triển khai Chính

### Task 1: Nghiệp vụ & Trigger Service
- Sửa lỗi `UniqueViolation` trên `eas.request_participant` khi Resubmit từ `NEEDS_INFO` (thêm `ON CONFLICT DO NOTHING` và bổ sung `acceptor_id`).
- Bảo toàn tệp đính kèm nháp khi chuyển sang `NEEDS_INFO` (sao chép lại tệp `CLEAN` từ `revision_attachment` sang `draft_attachment`).
- Kiểm tra `viewed_release_id` chống `CONFIG_CHANGED` (HTTP 409).
- Kiểm tra `ASSIGNEE_UNAVAILABLE` (HTTP 409) cho người nhận bước kế tiếp ở cả approval, execution và rework acceptance.
- Kiểm tra quyền đọc của actor trước khi replay idempotent response (bảo vệ quyền riêng tư `TC058`).

### Task 2: Hồ Sơ, Lưu Nháp, Báo Vướng & Tải Tệp Chống IDOR
- Bổ sung `validate_draft_payload` và `update_draft` (`PATCH /api/v1/requests/<id>`).
- Triển khai báo vướng / không thể nhận việc `report_execution_issue` (`POST /api/v1/requests/<id>/issues`).
- Áp dụng predicate quyền đọc chuẩn chống IDOR (trả 404 thay vì 403 khi không có quyền).
- Tải tệp an toàn qua `get_private_object` với đầy đủ security headers và audit trail.

### Task 3: Module Điều Phối `OPS_ADMIN`
- Triển khai `api_core/workflow/ops_service.py`:
  - `GET /api/v1/ops/requests` (danh sách metadata điều phối có whitelist, bảo vệ PII).
  - `POST /api/v1/requests/<id>/reassign` (điều chuyển APPROVER, EXECUTOR, ACCEPTOR, PLANNED_EXECUTOR với kiểm tra SoD và tách attempt khi RUNNING).
  - `POST /api/v1/ops/outbox/<id>/replay` (chuyển trạng thái outbox event từ DEAD về PENDING an toàn).

### Task 4: Module Quản Trị Cấu Hình `config_release`
- Triển khai `api_core/workflow/config_service.py` cho `POLICY_ADMIN`:
  - Quản lý vòng đời `config_release`: Create/Clone, Update DRAFT, Validate, Publish.
  - Tính toán `validation_hash` và `content_sha256` chuẩn hóa RFC 8785 (JCS) + SHA-256.

### Task 5: Worker, Notifications, Báo Cáo & Audit
- Nâng cấp `api_core/worker.py` (bỏ qua thông báo khi người nhận inactive/revoked, ghi `admin_event`, ghi audit cho SLA alert).
- Triển khai `api_core/workflow/reporting.py`: Notifications CRUD, Báo cáo thống kê theo kỳ hạn & scope, Tra cứu và xác minh chuỗi hash audit (`verify_audit_chain`).

### Task 6: 4 Management Commands Quản Trị
- `identity_import.py`: Import manifest có kiểm tra chu kỳ và ràng buộc scope.
- `account_reset.py`: Reset trạng thái / mật khẩu qua biến môi trường an toàn.
- `audit_verify.py`: CLI xác minh tính toàn vẹn mật mã của chuỗi hash audit.
- `privacy_case.py`: Xử lý quyền riêng tư và kiểm tra legal retention hold.

### Task 7: Đồng Bộ URL Routes & Aliases
- Khai báo đầy đủ các route và alias chuẩn theo `03_Du_lieu_va_API_v2.docx`.

### Task 8: Kiểm Thử Tự Động & Quality Gates
- Bổ sung bộ kiểm thử `test_ops_and_config.py` và `test_reporting_and_cli.py`.

## 3. Bằng Chứng Thực Nghiệm (Quality Gates)
- **Django Automated Tests:** `91/91 tests PASS` (3.088s)
- **Logger Security Tests:** `4/4 tests PASS` (0.000s)
- **Tổng số tests PASS:** `95/95 tests (100%)`
- **Ruff Linter:** `0 errors, 0 warnings`
- **Ruff Formatter:** `67 files clean and formatted`
- **Python Compile:** `0 syntax errors`
- **Environment Profiles:** 3/3 passed (`compose`: 22 vars, `api`: 24 vars, `worker`: 15 vars)
- **Documentation Verification:** `DOCS_GATE=PASS` (18 markdown files, 68 sơ đồ Mermaid, 100 test cases, 17 use cases)
