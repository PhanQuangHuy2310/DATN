# Biên bản kiểm tra bản cập nhật EAS ngày 27/10/2026

## Kết quả thực tế trong phiên kiểm tra

| Lệnh/nhóm kiểm tra | Kết quả | Ý nghĩa và giới hạn |
|---|---|---|
| `python -m pytest -q tests_report tests_business connection_tests tests_readiness` | **PASS: 77 tests, 107 subtests** | Static/unit tests bằng Python 3.13.5; không giả lập Supabase thật |
| `python -m compileall -q api_core tests_report tests_business connection_tests tests_readiness` | **PASS** | Xác nhận cú pháp Python, không xác nhận hành vi tại runtime Django |
| `cd web_client && npm test` | **PASS: 21/21** | Node.js 22.16.0; kiểm tra policy frontend, FormData contract và domain logic; không chạy browser |
| `python -m pip install -r api_core/requirements.txt` | **KHÔNG THỰC HIỆN ĐƯỢC** | Không có truy cập package mirror để cài dependencies Django còn thiếu |
| `cd web_client && npm run build` | **KHÔNG THỰC HIỆN ĐƯỢC** | Chưa cài `node_modules`/Vite; cần `npm ci` tại máy của bạn |
| `flutter analyze`, `flutter build` | **KHÔNG THỰC HIỆN ĐƯỢC** | Chưa có Flutter/Dart SDK, chưa tạo android/ios wrapper |
| `manage.py test`, Supabase E2E, SQL migration | **NOT RUN** | Không sử dụng credential Supabase của người dùng; không thể xác nhận dữ liệu/quyền/transaction thật |
| Storage private, scan ClamAV, Redis, outbox, SLA thực, AI và load | **NOT RUN** | Cần hạ tầng deploy và tài khoản test có dữ liệu hợp lệ |
| TC001–TC100, KD01–KD08 | **NOT RUN / PENDING SIGNOFF** | Bắt buộc trước nghiệm thu P0, không được suy ra từ unit tests |

## Các hồi quy được bảo vệ bằng test

- Đếm sai mật khẩu độc lập theo `account` (5 lần/15 phút) và IP (30 lần/15 phút); không ghi raw username/IP vào cache keys; chỉ xóa budget account sau đăng nhập hợp lệ.
- Danh sách công việc chỉ lấy revision/workflow instance ACTIVE, đúng step/attempt/state/grant hiệu lực; tham số SQL khớp placeholders.
- React APPROVE/ACCEPT gửi đúng 3 trường `expected_version`, `outcome`, `reason:null`, các action khác không gửi trường thừa; malformed expected_version bị chặn trước call.
- Flutter đăng nhập bằng mật khẩu tạm nhận flag từ `/auth/login` và không gọi `/auth/me` trước khi đổi mật khẩu; kiểm contract quyết định, CSRF và HTTPS bằng static tests (chưa build Flutter).
- Có dấu vết tài liệu Word Nhóm 07 theo SHA256 bản người dùng vừa gửi, giữ phân biệt source matrix cũ.
- Sửa kiểm tra phân loại lỗi DB đúng vị trí `api_core/db_diagnostics.py` (không coi middleware riêng là nơi chứa phân loại SQLSTATE).

## Checklist bắt buộc khi đưa sang máy Windows có môi trường thật

- [ ] Tạo file `.env` mới từ `.env.example`, điền credential đúng runtime role Supabase/pooler và SSL; không chia sẻ file này.
- [ ] Chạy `npm ci && npm test && npm run build`, rà ESLint, responsive/a11y và Playwright browser.
- [ ] Cài Django requirements; chạy `python manage.py test` với profile test, sau đó integration tests trên DB test cô lập.
- [ ] Dùng 7 user thật theo role/scope, role đã thu hồi, và các hồ sơ A/B/C có 1/2/3 cấp; kiểm không tự duyệt/đọc lộ scope.
- [ ] Kiểm concurrency 409, idempotent replay, mới/cũ revision, queue claim/blocked/submission/acceptance/rework.
- [ ] Kiểm ClamAV CLEAN/INFECTED, dung lượng tệp, quyền tải attachment, S3 private object storage.
- [ ] Chạy worker SLA 50/100%, outbox retry/DEAD/replay, audit chain hash và report consistency.
- [ ] Chốt KD01–KD08; ký kết chính sách và chạy UAT TC001–TC100, ghi môi trường/correlation_id/chứng cứ.
- [ ] Đối với Flutter P1: `flutter create`, `flutter pub get`, `flutter analyze`, chạy emulator debug, kiểm cookie/CSRF; build release chỉ dùng HTTPS.

**Trạng thái bàn giao:** CODE UPDATED + OFFLINE TESTS PASS; **E2E/PRODUCTION/REPORT-WIDE COMPLETION NOT VERIFIED**.
