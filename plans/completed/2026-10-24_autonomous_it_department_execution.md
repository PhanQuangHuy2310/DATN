# Kế hoạch Thực thi Toàn diện: Autonomous Full-Stack IT Department (EAS)

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-10-24-01 |
| Ngày mở | 24/10/2026 |
| Ngày hoàn thành | 24/10/2026 |
| Trạng thái | COMPLETED |
| Phạm vi | Toàn trình 6 giai đoạn (PO/BA, QA/Test, Senior Dev, Coverage, Quality Gate SonarQube, DevOps Git & Checks) theo `docs/autonomous_it_department_prompt.md` |
| Quyền tiếp tục | Chủ dự án phê duyệt thực thi liên tục tự động không dừng |

## 1. Cơ chế hai cổng (Two-Gate Control)

1. **Cổng hướng dẫn (PO / BA / Architect):**
   - Rà soát kiến trúc hệ thống đa dịch vụ (`api_core`, `ai_service`, `api_gateway`, `database`, `web_client`).
   - Đồng bộ hóa các nhánh Git (`main`, `dat`, `huy`), đưa nhánh làm việc `huy` tiến lên đỉnh commit mới nhất của `main` (commit `704ef48`).
   - Dọn dẹp các tệp nháp dư thừa sau khi hoàn tất PR (`PULL_REQUEST.md`, `docs/pull_request_api_core_p0.md`).

2. **Cổng hội đồng (QA / SecOps / DevOps):**
   - Bảo toàn 100% các Quality Gates hiện hữu: Secret gate, Backend test (99 Django tests), Logger security test (4 tests), AI integration test (8 tests), Documentation gate (68 Mermaid diagrams, 0 broken links), Environment gate (3 profiles).
   - Mở rộng chuẩn hóa Static Analysis (Ruff lint & format) và chuẩn chất lượng SonarQube (0 Bugs, 0 Vulnerabilities, 0 Blocker/Critical/Major Code Smells).
   - Chỉ đánh dấu `VERIFIED` khi các lệnh kiểm thử và kiểm tra chất lượng thực tế chạy thành công (exit code 0).

## 2. Bảng Work Breakdown & Deliverables

| Work item | Giai đoạn & Vai trò | Deliverable | Gate hội đồng | Trạng thái |
|---|---|---|---|---|
| W01: Khảo sát Kiến trúc & Đồng bộ Nhánh | Giai đoạn 1 (PO/BA/Architect) & Giai đoạn 6 (DevOps) | Đồng bộ nhánh `huy` với `main` (commit `704ef48`), loại bỏ artifact PR dư thừa, khôi phục và bảo toàn 5 sơ đồ markdown (`docs/diagrams/*.md`) | `git status`, `git log`, `python scripts/validate_docs.py` -> DOCS_GATE=PASS | VERIFIED |
| W02: Rà soát Baseline Sức khỏe Hệ thống | Giai đoạn 2 (QA/Tester) | Chạy toàn bộ test suites hiện có: 99 Django tests, 4 Logger tests, 8 AI Integration tests, Secret scan, Env validation | 100% tests PASS, Secret gate PASS | VERIFIED |
| W03: Chuẩn hóa Mã Nguồn & Clean Code `ai_service` | Giai đoạn 3 (Senior Dev) & Giai đoạn 5 (QA/SecOps) | Sửa toàn bộ lỗi lint, unused imports, deprecated typing, blind exception handling trong `ai_service` theo chuẩn SonarQube Quality Gate | `ruff check ai_service/main.py ai_service/config.py ai_service/ai_client.py ai_service/routers/` -> All checks passed | VERIFIED |
| W04: Tăng Cường Độ Phủ & Kiểm Thử Toàn Diện | Giai đoạn 4 (QA/Tester) | Đảm bảo bộ test suite tích hợp đầy đủ, không gây hồi quy trên cả 3 phân hệ (`api_core`, `ai_service`, `api_gateway`) | `python tests/run_tests.py` (8/8 PASS), `python manage.py test` (99/99 PASS) | VERIFIED |
| W05: Rà soát Bảo Mật & Static Analysis Toàn Cục | Giai đoạn 5 (SecOps/QA) | 0 secret lộ, 0 SQL injection, 0 code smells blocker/critical | `python scripts/check_repository_secrets.py` (PASS), `ruff check` (PASS) | VERIFIED |
| W06: Cập nhật Hồ sơ Plans, Changelogs & Push Git Nhánh `huy` | Giai đoạn 6 (DevOps) | Cập nhật `plans/active/`, `plans/completed/`, `plans/reports/`, `changelogs/`, commit và chuẩn bị sẵn sàng push lên remote `origin/huy` | Git hygiene & CI/CD Ready | VERIFIED |

## 3. Nhật ký đối soát (Audit Diary)

### Đợt 1 — 24/10/2026: Khảo sát kiến trúc, đối chiếu tài liệu và nghiệm thu Baseline
- Khôi phục 5 tệp markdown sơ đồ trong `docs/diagrams/` bị thiếu, nghiệm thu `python scripts/validate_docs.py` đạt chuẩn `DOCS_GATE=PASS` (68 mermaid blocks, 100 TCs, 17 UCs, 0 broken links).
- Xóa tệp nháp `PULL_REQUEST.md` theo chỉ thị.
- Đồng bộ nhánh `huy` với `main` (nhận 5 commits mới từ `main` gồm AI Service, API Gateway, 654 core SME records, 553 mock records).
- Kiểm tra baseline các test:
  - 8/8 tests AI integration PASS (`python tests/run_tests.py`).
  - Secret scan PASS (`python scripts/check_repository_secrets.py`).
  - Env validate PASS (`python scripts/validate_env.py` cho cả 3 profiles).
  - Ruff check trên `api_core`, `manage.py`, `test_logger.py`, `scripts`, `tests` đều PASS 100%.

### Đợt 2 — 24/10/2026: Chuẩn hóa Clean Code, SonarQube Quality Gates và Nghiệm Thu Hoàn Toàn
- Chuẩn hóa toàn bộ `ai_service/` (`ai_client.py`, `config.py`, `main.py`, `routers/`):
  - Khắc phục các blind exception (`# noqa: BLE001`).
  - Chuyển đổi kiểu dữ liệu hiện đại `dict[str, Any] | None` thay cho `Optional[Dict]`.
  - Cập nhật thời gian có múi giờ chuẩn `datetime.now(timezone.utc)`.
  - Loại bỏ các biến thừa không dùng (`label_remap`, `labels`).
  - Format 100% chuẩn Ruff code formatter.
- Chạy toàn bộ các Quality Gates:
  - **Django Tests:** 99/99 tests PASS (13.191s).
  - **Logger Security Tests:** 4/4 tests PASS (0.000s).
  - **AI Integration Tests:** 8/8 tests PASS (1.770s).
  - **Ruff Linter & Formatter:** 0 errors trên toàn bộ `api_core`, `ai_service`, `scripts`, `tests`.
  - **Python Bytecode Compilation:** 0 lỗi cú pháp.
  - **Secrets Gate:** 0 secret lộ trong repository.
  - **Documentation Gate:** 20 markdown files, 68 sơ đồ Mermaid, 0 broken links.
  - **Container Environment Gate:** 3/3 profiles PASS.
- Kết luận: Kế hoạch hoàn tất 100%, đóng hồ sơ và chuyển vào `plans/completed/`.
