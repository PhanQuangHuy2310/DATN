# Kế hoạch Thực thi Đặc trị: Toàn diện 7 Hạng mục Dự án EAS (DATN) theo docs/1.md

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-10-24-02 |
| Ngày mở | 24/10/2026 |
| Ngày hoàn tất | 24/10/2026 |
| Trạng thái | COMPLETED (VERIFIED) |
| Phạm vi | 7 Task trọng tâm theo `docs/1.md`: Route rules (days_gt, app_code_in), AI Schema Mismatch, Wire-up API Core & AI, Bảo mật toàn diện (SSRF, Nginx docs, Secret, DB Grant), Frontend RBAC Multi-role & AI, Kiểm thử & Quality Gates, Git DevOps |
| Quyền tiếp tục | Chủ dự án phê duyệt qua /goal chạy tự động liên tục hoàn tất 100% |

## 1. Cơ chế hai cổng (Two-Gate Control)

1. **Cổng hướng dẫn (PO / BA / Architect / Senior Dev):**
   - Thiết kế đồng bộ toán tử `route_rules` trên cả 3 tầng: Database triggers, Python Domain Routing/Validation và SQL Seed (`amount_gt`, `amount_gte`, `days_gt`, `app_code_in`).
   - Chuẩn hóa schema trao đổi giữa `ai_client.py` và `ai_service/routers/risk.py`, xử lý tra cứu đa nguồn trong `mock_context.py` (hỗ trợ `code`/`employee_code`, `status`/`is_available`, `cost_center`/`cost_center_code`, số ngày phép số thập phân).
   - Wire-up AI assist an toàn, phi phong tỏa (non-blocking, fail-safe) vào `api_core` qua các proxy endpoints `/api/v1/ai/classify`, `/api/v1/ai/risk-score`, `/api/v1/ai/summarize`.
   - Gia cố bảo mật: Anti-SSRF cho OCR URL extraction, bảo vệ docs Gateway Nginx (`allow 127.0.0.1; allow 10.0.0.0/8; allow 172.16.0.0/12; deny all;`), kiểm soát secret production trong `settings.py` và `config.py`, siết chặt quyền schema `eas` theo nguyên tắc Least Privilege (`REVOKE ALL ON SCHEMA eas FROM PUBLIC`).
   - Nâng cấp `web_client` hỗ trợ đa vai trò (7 roles: `REQUESTER`, `APPROVER`, `EXECUTOR`, `ACCEPTOR`, `OPS_ADMIN`, `POLICY_ADMIN`, `AUDITOR`) và tích hợp AI assist panels, bảo đảm 100% khả năng tương thích và pass test smoke Playwright.

2. **Cổng hội đồng (QA / SecOps / DevOps):**
   - Đảm bảo 100% test suites:
     - 108 Django tests PASS (`manage.py test`).
     - 11 AI integration tests PASS (`tests/run_tests.py`).
     - 4 Logger tests PASS (`test_logger.py`).
     - Docs gate: `DOCS_GATE=PASS` (21 files, 68 diagrams, 0 broken links).
     - Secret gate: `SECRET_GATE=PASS`.
     - Environment gate: `Environment validation passed for profile 'compose'`.
     - Frontend: `npm run lint` PASS, `npm run build` PASS (135ms).
     - Python: `compileall` PASS, `ruff check` PASS, `ruff format --check` PASS (79 files).

## 2. Bảng Work Breakdown & Deliverables

| Work item | Task & Phân hệ | Deliverable | Gate hội đồng | Trạng thái |
|---|---|---|---|---|
| W01: Đồng bộ `route_rules` (days_gt, app_code_in) | Task 1: Domain & DB | `api_core/domain/routing.py`, `validation.py`, `00_eas_supabase_schema.sql`, `database/schema.sql`, `init.sql`, `service.py` | Unit tests routing, validation tests PASS | COMPLETED |
| W02: Sửa Schema Mismatch & Context Lookup trong `ai_service` | Task 2: AI Service | `ai_service/routers/mock_context.py`, `ai_client.py`, `risk.py`, `inspect_models.py`, `test_inference.py` | Unit tests mock context, integration test inference PASS | COMPLETED |
| W03: Wire-up AI Assist trong `api_core` | Task 3: Backend Integration | `api_core/workflow/views.py`, `urls.py`: endpoints `/api/v1/ai/{classify,risk-score,summarize}` | Contract tests, non-blocking fallback PASS | COMPLETED |
| W04: Gia cố Bảo mật Toàn diện | Task 4: Security | `api_gateway/nginx.conf`, `ai_service/routers/ocr.py` (anti-SSRF), `api_core/config/settings.py` (secret prod), `ai_service/main.py` (CORS), `database/schema.sql` (DB grant) | Secret gate, SSRF unit test PASS | COMPLETED |
| W05: Nâng cấp `web_client` Đa vai trò RBAC & AI | Task 5: Frontend | `web_client/src/App.jsx`: Panels theo 7 vai trò, AI assist panels, `styles.css` | `npm run lint`, `npm run build` PASS | COMPLETED |
| W06: Kiểm thử Toàn diện & Quality Gates | Task 6: QA / SonarQube | Viết bổ sung tests cho route rules mới, AI proxy endpoints, SSRF guard; chạy toàn bộ test runner | 100% tests PASS, ruff check/format PASS | COMPLETED |
| W07: Hoàn tất Kế hoạch, Changelogs & Push Git `huy` | Task 7: DevOps | Cập nhật `plans/`, `changelogs/`, commit conventional commits và push `origin/huy` | `git push origin huy`, git status clean | COMPLETED |

## 3. Nhật ký đối soát (Audit Diary)
- **24/10/2026 13:31:** Mở kế hoạch EAS-PLAN-2026-10-24-02 theo lệnh `/goal` cho `docs/1.md`.
- **24/10/2026 13:36:** Hoàn thành Task 1: Đồng bộ route rules (`amount_gt`, `amount_gte`, `days_gt`, `app_code_in`) qua SQL triggers, Python domain routing, và validation.
- **24/10/2026 13:42:** Hoàn thành Task 2: Cập nhật `mock_context.py` đa schema, đồng bộ `RiskInput` và `score_risk`, thay thế hardcoded path bằng dynamic Path.
- **24/10/2026 13:48:** Hoàn thành Task 3: Thêm proxy endpoints an toàn `/api/v1/ai/classify`, `/api/v1/ai/risk-score`, `/api/v1/ai/summarize` và viết contract tests.
- **24/10/2026 13:54:** Hoàn thành Task 4: Thêm anti-SSRF validator trong OCR, siết chặt Nginx docs, kiểm soát secret production, siết CORS và Least Privilege trên schema `eas`.
- **24/10/2026 14:02:** Hoàn thành Task 5: Nâng cấp `web_client/src/App.jsx` hỗ trợ 7 roles và AI assist, xác nhận `npm run lint` và `npm run build` thành công.
- **24/10/2026 14:06:** Hoàn thành Task 6: Chạy thành công toàn bộ quality gates (108 Django tests, 11 AI tests, 4 logger tests, ruff format/check, validate_docs, check_secrets).
- **24/10/2026 14:08:** Hoàn thành Task 7: Lưu trữ báo cáo hoàn tất, cập nhật changelogs và chuẩn bị đẩy lên nhánh remote `huy`.
