# Kế hoạch hoàn thiện và khắc phục toàn diện phân hệ `api_core` (P0)

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-10-22-01 |
| Ngày mở | 22/10/2026 |
| Ngày hoàn thành | 22/10/2026 |
| Trạng thái | COMPLETED |
| Phạm vi | Toàn diện phân hệ `api_core` P0 theo `eas_api_core_master_prompt.md` |
| Quyền tiếp tục | Chủ dự án phê duyệt thực thi tự động qua `/goal` |

## 1. Cơ chế hai cổng

1. **Cổng hướng dẫn:** Đối chiếu đặc tả v2.0, schema PostgreSQL 00_eas_supabase_schema.sql v2.0.1, 68 sơ đồ chốt cuối trên Drive và master prompt; thiết kế các module sạch, an toàn, tuân thủ thứ tự khóa và bất biến toàn cục.
2. **Cổng hội đồng:** Kiểm thử nghịch đảo (negative/boundary/auth/IDOR/concurrency/error codes); kiểm tra tính tương thích ngược với 67 test hiện hữu và `web_client`; xác nhận bằng chứng chạy thực tế, không chấp nhận trạng thái giả định.
3. Chỉ đánh dấu `VERIFIED` khi lệnh kiểm thử tương ứng đã chạy và cho kết quả `OK` / `PASS`.

## 2. Bảng Work Breakdown & Deliverables

| Work item | Điểm mù / UC liên quan | Deliverable | Gate hội đồng | Trạng thái |
|---|---|---|---|---|
| W01: Fix nghiệp vụ & trigger service | UC04, UC06, UC07, UC11, UC12, TC029, TC041, TC055, TC058, TC059 | `api_core/workflow/service.py`: On conflict participant, draft restore on NEEDS_INFO, viewed_release_id, next actor check, idempotency replay read check | Boundary & idempotency tests | VERIFIED |
| W02: Draft PATCH, Issues, Read & Download | UC03, UC05, UC08, UC10, UC11, TC013, TC014, TC018, TC023–026, TC073 | `api_core/domain/validation.py`, `api_core/workflow/service.py`, `api_core/storage.py`, `api_core/workflow/views.py`: update_draft, validate_draft_payload, report_execution_issue, anti-IDOR read, get_private_object | Mass-assignment, IDOR 404, file download tests | VERIFIED |
| W03: Module OPS Admin | UC09, UC14, AD-05, SD-07, SD-22, TC024, TC039–041, TC046, TC055, TC057, TC067 | `api_core/workflow/ops_service.py`: ops metadata query, reassign actor (step/executor/acceptor/planned_executor), dead outbox replay | SoD check, RUNNING attempt split, dead event replay tests | VERIFIED |
| W04: Module Config Release | UC02, AD-07, SD-09, TC010–012, TC097 | `api_core/workflow/config_service.py`: list, clone/create, patch draft, validate release candidate, publish release | Guard release validation, canonical SHA256, immutable release tests | VERIFIED |
| W05: Worker, Notifications, Reports & Audit Verify | UC13, UC14, UC15, SD-08, SD-13, SD-15, SD-16, TC061–070, TC093, TC096 | `api_core/worker.py`, `api_core/workflow/reporting.py`: inactive/revoked outbox skip, SLA audit logging, notification CRUD, reports query, audit verification engine | Outbox delivery skip, SLA alert audit, audit chain verify tests | VERIFIED |
| W06: 4 Management Commands | UC17, SD-11, SD-14, TC005–009, TC083–085, TC096 | `api_core/management/commands/`: `identity_import.py`, `account_reset.py`, `audit_verify.py`, `privacy_case.py` | CLI dry-run/apply, password reset via env, cycle check, retention hold block | VERIFIED |
| W07: URL Routing & Aliases | Task 7 mapping table, 03_Du_lieu_va_API_v2.docx | `api_core/workflow/urls.py`, `api_core/config/urls.py`: đầy đủ routes và aliases chuẩn | URL resolution & contract tests | VERIFIED |
| W08: Automated Testing & Quality Gates | TC001–TC100, CI/CD gates | `api_core/tests/test_ops_and_config.py`, `api_core/tests/test_reporting_and_cli.py`: unit/contract test suites + Ruff, compileall, validate_env, validate_docs | 100% tests PASS, 0 lint error, all gates pass | VERIFIED |

## 3. Nhật ký đối soát

### Đợt 1 — 22/10/2026: Khởi tạo kế hoạch và rà soát baseline
- Baseline: 67 Django tests PASS, 4 logger tests PASS, Ruff format & check PASS, validate_env PASS (3 profiles), validate_docs PASS (DOCS_GATE=PASS).
- Mở kế hoạch EAS-PLAN-2026-10-22-01 để thực hiện chi tiết 8 tasks theo `eas_api_core_master_prompt.md`.

### Đợt 2 — 22/10/2026: Nghiệm thu hoàn tất toàn bộ 8 hạng mục
- **Test suite:** 91 Django tests PASS + 4 logger tests PASS = 95/95 tests PASS (100%).
- **Linter & Formatter:** `ruff check` đạt 0 lỗi, `ruff format --check` đạt chuẩn 67 files formatted.
- **Bytecode & Compiler:** `python -m compileall -q api_core manage.py test_logger.py` không phát hiện lỗi cú pháp.
- **Environment Profiles:** 3/3 profiles (`compose`: 22 vars, `api`: 24 vars, `worker`: 15 vars) kiểm tra thành công.
- **Documentation & Consistency:** `validate_docs.py` đạt `DOCS_GATE=PASS` (18 markdown files, 68 sơ đồ Mermaid, 100 test cases TC001-TC100, 17 use cases UC01-UC17, 0 broken links).
- Kết luận: Đóng kế hoạch, chuyển lưu trữ vào `plans/completed/`.
