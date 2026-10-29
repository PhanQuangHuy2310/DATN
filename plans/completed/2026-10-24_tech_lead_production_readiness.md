# Kế hoạch Hoàn Tất: Nâng Cấp Toàn Diện Chuẩn Production-Ready & SonarQube (docs/2.md)

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-10-24-03 |
| Ngày mở | 24/10/2026 |
| Ngày hoàn tất | 24/10/2026 |
| Trạng thái | COMPLETED (VERIFIED 100%) |
| Phạm vi | 10 Task toàn diện theo `docs/2.md`: Route rules sync, PaddleOCR lazy singleton cache, X-Correlation-ID tracing, Nginx client_max_body_size 10m, Docker non-root user & compose least-privilege, Outbox worker graceful shutdown (SIGTERM/SIGINT) & reporting memory guard (LIMIT 100k), SonarQube cognitive complexity refactoring (ops_service, validation, service, routing), Web client perspective tabs & AI Assist UX, SonarQube properties & CI workflow đa nhánh, Toàn bộ 100% Quality Gates |
| Tác giả | Tech Lead & Autonomous IT Department |

## 1. Cơ chế hai cổng (Two-Gate Control)

1. **Cổng hướng dẫn (PO / BA / Architect / Senior Dev):**
   - Đồng bộ toán tử định tuyến `route_rules` (`amount_gt`, `amount_gte`, `days_gt`, `app_code_in`) qua SQL Trigger, Schema migration, và Python Domain Routing/Validation.
   - Giải quyết tắc nghẽn bộ nhớ & khởi tạo OCR: Áp dụng Lazy Singleton Pattern với Thread Lock cho `PaddleOCR` trong `ai_service/routers/ocr.py`.
   - Chuẩn hóa Observability & Correlation Tracing: Truyền `X-Correlation-ID` xuyên suốt từ client -> `api_core` -> `ai_service` -> worker.
   - Gia cố bảo mật hạ tầng: Cấu hình `client_max_body_size 10m` và timeouts trong `web_client/nginx.conf`, tạo user phi đặc quyền `aiuser` (UID 10001) trong `ai_service/Dockerfile`, áp dụng `no-new-privileges:true` và `cap_drop: [ALL]` trong `docker-compose.yml`, chuyển Elasticsearch vào profile `search-optional` và bind `127.0.0.1`.
   - Tối ưu Worker & Reporting: Triển khai graceful shutdown với tín hiệu `SIGTERM`/`SIGINT`, `close_old_connections()` định kỳ, và đặt ngưỡng chặn `LIMIT 100000` chống tràn bộ nhớ trong `get_request_metrics_report`.
   - Tái cấu trúc SonarQube Cognitive Complexity: Tách các helper hàm độc lập cho `ops_service.py` (`reassign_actor`), `validation.py` (`_validate_route_rules_structure`, `_validate_resolved_actors`), `routing.py` (`_match_amount`, `_match_days`, `_match_app_code`), và `service.py` (`create_draft`, `update_draft`, `report_execution_issue`, `submit_request`, `decide_approval`, `submit_execution`, `decide_acceptance`).
   - Nâng cấp UX `web_client`: Thêm hệ thống tabs perspective theo 7 vai trò chuẩn RBAC, tích hợp các nút `"🤖 Gợi ý & Đánh giá rủi ro AI"` mượt mà.
   - Thiết lập cấu hình SonarQube: Tạo `sonar-project.properties` và cập nhật `.github/workflows/ci.yml` kiểm thử đa nhánh (`main`, `huy`, `dat`), tạo báo cáo coverage XML và linting/syntax check tự động.

2. **Cổng hội đồng (QA / SecOps / DevOps):**
   - Đảm bảo 100% test suites:
     - 108 Django tests PASS (`manage.py test`).
     - 11 AI integration tests PASS (`tests/run_tests.py`).
     - 4 Logger security tests PASS (`test_logger.py`).
     - 86 SQL assertions PASS (`npm test` in `database/EAS_Supabase_SQL/validation`).
     - Secret gate: `SECRET_GATE=PASS`.
     - Docs gate: `DOCS_GATE=PASS` (22 markdown files, 68 diagrams, 100 TC unique, 17 UC).
     - Environment gate: PASS trên toàn bộ 5 profile (`compose`, `api`, `worker`, `web_client`, `web_admin`).
     - Frontend: `npm run lint` PASS, `npm run build` PASS (159ms).
     - Python: `compileall` PASS, `ruff check` PASS, `ruff format --check` PASS (70 files).

## 2. Bảng Work Breakdown & Deliverables

| Task | Hạng mục | Deliverable | Kết quả kiểm tra | Trạng thái |
|---|---|---|---|---|
| Task 1 | Đồng bộ `route_rules` | `api_core/domain/routing.py`, `validation.py` | 42/42 domain & workflow tests PASS | COMPLETED |
| Task 2 | AI Schema & OCR Lazy Singleton | `ai_service/routers/ocr.py`, `ai_client.py`, `main.py` | OCR chỉ tải khi gọi, Correlation ID truyền thông suốt | COMPLETED |
| Task 3 | Wire-up AI Assist & Correlation ID | `api_core/ai_client.py`, `api_core/workflow/views.py` | Proxy endpoints an toàn, log tracing PASS | COMPLETED |
| Task 4 | Security Hardening (Nginx, Docker, Compose) | `web_client/nginx.conf`, `ai_service/Dockerfile`, `docker-compose.yml` | Non-root container, security_opt, ES local bind | COMPLETED |
| Task 5 | Worker Resilience & Reporting Guard | `run_outbox_worker.py`, `api_core/workflow/reporting.py` | Graceful shutdown, connection refresh, LIMIT 100k | COMPLETED |
| Task 6 | Refactor SonarQube Cognitive Complexity | `ops_service.py`, `validation.py`, `routing.py`, `service.py` | Tách nhỏ hàm, độ phức tạp <= 15, logic 100% nhất quán | COMPLETED |
| Task 7 | Frontend Perspective Tabs & AI UX | `web_client/src/App.jsx`, `web_client/src/styles.css` | 7 role tabs, AI buttons, build 159ms | COMPLETED |
| Task 8 | SonarQube Config & Multi-branch CI/CD | `sonar-project.properties`, `.github/workflows/ci.yml` | Nhánh main/huy/dat, coverage XML, AI checks | COMPLETED |
| Task 9 | Quality Gates Local 100% Xanh | Scripts, Tests, Linters, Build | 108 Django + 11 AI + 4 Logger + 86 SQL PASS | COMPLETED |
| Task 10 | Git Push & Pull Request Content | Remote branch `huy` | Push origin huy, PR text hoàn thiện | COMPLETED |

## 3. Nhật ký đối soát (Audit Diary)
- **24/10/2026 18:35:** Tiếp nhận chỉ thị thực thi `docs/2.md` trên nhánh `huy`.
- **24/10/2026 18:45:** Hoàn thành Tasks 1–5: Lazy Singleton OCR, X-Correlation-ID tracing, Least privilege Docker/Compose, Worker graceful shutdown, Memory limit reporting.
- **24/10/2026 19:00:** Hoàn thành Task 6: Tái cấu trúc Cognitive Complexity cho `ops_service.py`, `validation.py`, `routing.py`, `service.py`.
- **24/10/2026 19:03:** Hoàn thành Task 7: Thêm tabs perspective cho 7 vai trò và AI Assist panel trong `web_client`.
- **24/10/2026 19:05:** Hoàn thành Task 8: Thiết lập `sonar-project.properties` và CI/CD workflow đa nhánh.
- **24/10/2026 19:08:** Hoàn thành Task 9: Chạy toàn bộ 100% Quality Gates (Secrets, Docs, Env, Ruff check/format, Bytecode compile, 108 Django tests, 11 AI tests, 4 Logger tests, 86 SQL tests, Vite build).
- **24/10/2026 19:10:** Hoàn thành Task 10: Commit và chuẩn bị sẵn sàng nội dung Pull Request bàn giao trực tiếp.
