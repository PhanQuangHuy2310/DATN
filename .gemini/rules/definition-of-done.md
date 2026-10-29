---
description: Quy tắc bắt buộc (Hard Gate) cho mọi task: AI Agent chỉ được phép báo cáo hoàn thành (DONE) khi code đã được push và 100% GitHub Check Status + SonarQube Quality Gate đều PASS (Xanh).
globs: ["**/*"]
alwaysApply: true
---

# MANDATORY DEFINITION OF DONE (HARD GATE POLICY)

Kể từ thời điểm này, đối với MỌI yêu cầu sửa lỗi, nâng cấp tính năng, refactor hoặc tối ưu dự án, bạn BẮT BUỘC phải tuân thủ quy trình khép kín sau đây. **Một công việc được coi là CHƯA HOÀN THÀNH (NOT DONE) nếu bất kỳ bước nào dưới đây chưa PASS 100%:**

## 1. Cấm báo cáo "Done" sớm (No Premature Completion)
- TUYỆT ĐỐI KHÔNG ĐƯỢC dừng lại và báo cáo hoàn thành khi mới chỉ sửa code trên local mà chưa chạy hết toàn bộ các cổng kiểm tra (Quality Gates) hoặc khi GitHub Check Status / SonarQube trên remote vẫn đang báo `FAIL`, `ERROR`, `ACTION_REQUIRED`, hoặc `PENDING`.
- TUYỆT ĐỐI KHÔNG hỏi người dùng "Bạn có muốn tôi sửa lỗi CI này không?" — nếu thấy bất kỳ check nào chưa xanh, bạn phải tự động đọc log, tự sửa, tự test lại và tự push lại ngay lập tức.

## 2. 7 Cổng Kiểm Tra Local Bắt Buộc Trước Khi Push (Local Pre-Push Gates)
Trước mỗi lệnh `git push`, bạn PHẢI chạy thực tế trong terminal và xác nhận `exit code = 0` cho toàn bộ 7 cổng sau:
1. **Secret Gate**: `python scripts/check_repository_secrets.py` -> Phải in ra `SECRET_GATE=PASS` (không có bất kỳ file `.env` nào nằm trong `git ls-files`).
2. **Docs & RTM Gate**: `python scripts/validate_docs.py` -> Phải in ra `DOCS_GATE=PASS`.
3. **Environment Templates Gate**: Chạy `python scripts/validate_env.py` với `--allow-placeholders` cho cả 5 file `.env.example` (`compose`, `api`, `worker`, `web_client`, `web_admin`).
4. **Linter, Formatter & Complexity Gate (SonarQube Pre-check)**:
   - `ruff check api_core ai_service manage.py test_logger.py scripts tests` (0 errors)
   - `ruff format --check api_core manage.py test_logger.py scripts` (100% formatted)
   - `python -m compileall -q api_core ai_service manage.py test_logger.py scripts tests`
   - Mọi hàm mới hoặc sửa đổi trong `api_core/` và `ai_service/routers/` phải có Cognitive Complexity <= 15, không lặp lại string literals >= 4 lần (Sonar Rule `S1192`), không có biến/import thừa (`S1481`), không có khối `except` rỗng.
5. **Backend & AI Automated Tests Gate**:
   - `EAS_ENV=test python manage.py test -v 2` -> 100% PASS.
   - `python -m unittest -v test_logger.py` -> 100% PASS.
   - `python tests/run_tests.py` -> 100% PASS (0 failed).
6. **Database Validation Gate**:
   - `cd database/EAS_Supabase_SQL/validation && npm test` -> `"result": "PASS"`.
7. **Frontend Gate**:
   - `cd web_client && npm run lint && npm run build` -> 0 errors, build thành công.

## 3. Vòng Lặp Kiểm Tra Remote GitHub Check Status & SonarQube (Remote CI/CD Gate)
Sau khi `git push -u origin huy`:
1. Chờ 10–15 giây để GitHub Actions khởi tạo workflow, sau đó chạy lệnh kiểm tra trạng thái:
   - `gh run list --branch huy --limit 5`
   - `gh run watch <run_id> --exit-status` (hoặc `gh pr checks`)
2. Nếu bất kỳ job nào trong GitHub Actions (`secret-gate`, `backend`, `database`, `frontend`, `container-config`, `documentation`, `sonarqube`) bị **FAIL**:
   - Lập tức chạy `gh run view <run_id> --log-failed` để lấy log lỗi chi tiết.
   - Phân tích nguyên nhân gốc rễ, sửa code/config trên local, chạy lại bước kiểm tra local tương ứng, commit và `git push` lại lên nhánh `huy`.
   - Tiếp tục theo dõi `gh run watch` cho đến khi **100% các Check Status trên GitHub và SonarQube Quality Gate đều hiển thị `PASS` / `SUCCESS` (Màu Xanh)**.
3. Chỉ khi tất cả các check đã PASS 100%, bạn mới được phép kết thúc phiên làm việc và xuất báo cáo tổng kết kèm bằng chứng.
