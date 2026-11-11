# EAS Security & Compliance Changelog

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-CHANGELOG-STD-02 |
| Ngày | 31/10/2026 |
| Phạm vi | Kiểm soát kỹ thuật trong mã nguồn, đối chiếu với các yêu cầu của ISO 9001, CMMI, ISO/IEC 27001, SOC 2, ITIL |
| Trạng thái | Nhật ký thay đổi kỹ thuật. **Không phải chứng nhận và không phải biên bản GO-LIVE** |

## 0. Phạm vi trung thực của tài liệu này

ISO 9001, CMMI, ISO/IEC 27001, SOC 2 và TIER là **chứng nhận hoặc xếp hạng cấp tổ chức/cơ sở hạ tầng**, do bên thứ ba đánh giá trên bằng chứng vận hành theo thời gian. Việc sửa mã nguồn **không thể** tự cấp các chứng nhận này. Tài liệu này chỉ ghi lại các **kiểm soát kỹ thuật** đã triển khai và kiểm chứng bằng test; mục 4 liệt kê những gì còn thiếu.

## 1. Thay đổi đã triển khai

### 1.1 Bảo mật ứng dụng & Danh tính (ISO 27001 A.8/A.9/A.12, SOC 2 Security & Privacy)

| Hạng mục | Thay đổi | File |
|---|---|---|
| Proxy-aware Login Throttle | `login()` dùng `client_ip(request)` thay vì `REMOTE_ADDR`. Sau proxy tin cậy (`EAS_TRUST_PROXY_HEADERS=true`), throttle theo IP thực tế của client từ entry cuối của `X-Forwarded-For`, không còn nguy cơ khóa nhầm toàn bộ công ty. | `api_core/authn/views.py` |
| Ép đổi mật khẩu trước go-live | Tạo lệnh quản trị `enforce_initial_passwords.py` `--operator <user> --approval <ticket>` để bật `must_change_password=True`, tăng `auth_version` hủy toàn bộ session cũ của các tài khoản seed, ghi nhật ký kiểm toán bất biến. | `api_core/management/commands/enforce_initial_passwords.py` |
| Che PII trước khi gửi LLM | `sanitize_prompt_text()` che số thẻ (PAN 16 số), số CCCD (12 số) và bearer token/api keys thành `[REDACTED_*]` trước khi gửi prompt tới Google Gemini. | `ai_service/routers/summarize.py` |
| Giới hạn Payload AI Service | Middleware `limit_request_size` chặn request vượt quá 20MB (HTTP 413 `Payload too large`), phòng ngừa cạn kiệt bộ nhớ (OOM/DoS). | `ai_service/main.py` |
| Loại bỏ Deprecation Warning | Thay `asyncio.get_event_loop()` bằng `asyncio.get_running_loop()`; chuyển Pydantic `example=` sang `examples=[...]`. | `api_core/ai_client.py`, `ai_service/ai_client.py`, `ai_service/routers/classify.py` |
| Header phòng thủ | `ApiSecurityHeadersMiddleware`: CSP (`frame-ancestors 'none'`), Permissions-Policy, nosniff, Referrer-Policy, COOP. Không ghi đè CSP có sẵn. | `api_core/middleware.py` |
| Giới hạn tần suất chung | `ApiRateLimitMiddleware`: 300 req/phút/IP (cấu hình bằng `EAS_API_RATE_LIMIT_PER_MINUTE`), trả 429 + `Retry-After`. | `api_core/middleware.py`, `api_core/config/settings.py` |
| Fail-open có chủ đích | Nếu Redis/cache lỗi, rate limiter ghi cảnh báo và cho request đi qua, ưu tiên tính sẵn sàng. | `api_core/middleware.py` |
| Chính sách secret production | Production **từ chối khởi động** nếu `EAS_AI_INTERNAL_SECRET` rỗng, ngắn hơn 32 ký tự, là placeholder hoặc là chuỗi dev công khai. | `api_core/config/settings.py`, `ai_service/config.py` |
| So sánh secret hằng thời gian | `hmac.compare_digest` cho `X-Internal-Secret`. | `ai_service/main.py` |
| Che dữ liệu nhạy cảm trong log | Che số thẻ 16 chữ số và số CCCD 12 chữ số trong console log. | `api_core/logger.py` |

### 1.2 Độ tin cậy và vận hành (ITIL, ISO 27001 A.17)

| Hạng mục | Thay đổi | File |
|---|---|---|
| Lỗi 500 luôn là JSON | Catch-all cho `/api/v1/`, ghi log kèm `correlation_id`, không lộ chi tiết. | `api_core/middleware.py` |
| Kết nối DB với pooler | `CONN_MAX_AGE` mặc định `0` để tránh socket cũ với PgBouncer. | `api_core/config/database.py`, `settings.py` |
| Cách ly lỗi giao diện | `ErrorBoundary` cho cả `web_client` và `web_admin`. | `web_client/src/components/ErrorBoundary.jsx` |
| CI | Thêm audit và build cho `web_admin`. | `.github/workflows/ci.yml` |

### 1.3 Kiểm thử mới (CMMI V&V)

- `api_core/tests/test_authn.py`: thêm test throttle cách ly IP client sau proxy tin cậy.
- `api_core/tests/test_administration.py`: thêm test lệnh quản trị `enforce_initial_passwords`.
- `tests/integration/test_ai_service.py`: thêm test `sanitize_prompt_text` che PII trước khi gửi LLM.
- `api_core/tests/test_security_middleware.py`: 9 test security middleware.
- `api_core/tests/test_production_secret_policy.py`: 3 test production startup policy.
- `test_logger.py`: test che số thẻ/CCCD.
- Toàn bộ test suite: 100% PASS.

## 2. Sự cố và điều chỉnh trong quá trình làm (minh bạch)

1. **Đã xử lý dứt điểm điểm nghẽn proxy**: Cả `ApiRateLimitMiddleware` và `login()` trong `authn/views.py` hiện đều sử dụng chung hàm `client_ip()` xử lý an toàn IP cuối của `X-Forwarded-For` khi bật `EAS_TRUST_PROXY_HEADERS=true`.
2. **Đã có công cụ ép đổi mật khẩu seed**: Lệnh `enforce_initial_passwords` giải quyết triệt để rủi ro mật khẩu mặc định `Password@123456` trước khi bàn giao hệ thống.
3. **Đã bảo vệ PII trước LLM**: Dữ liệu thẻ và CCCD không còn bị gửi nguyên vẹn ra Google Gemini.
4. Script live test không còn chứa mật khẩu hay đường dẫn cá nhân; đọc `EAS_E2E_*` từ môi trường.

## 3. Kết quả kiểm chứng

- Ruff check/format, compileall, secret gate, docs gate: **PASS**.
- `python manage.py test`: **PASS** (chạy trên SQLite in-memory).
- `python tests/run_tests.py`: **12/12 PASS**.
- `npm run build --prefix web_client`: **PASS**.
- `npm run build --prefix web_admin`: **PASS**.

## 4. Những gì CHƯA làm hoặc không thể làm bằng mã nguồn

| # | Khoảng trống | Vì sao quan trọng | Việc cần làm |
|---|---|---|---|
| 1 | **Chưa có chứng nhận nào** (ISO 9001/27001, SOC 2, CMMI, TIER) | Không thể tuyên bố "đạt chuẩn" với khách | Cần ISMS/QMS được tài liệu hóa, chính sách, đào tạo, đánh giá rủi ro, audit nội bộ, rồi tổ chức chứng nhận bên ngoài. SOC 2 Type II cần 3 đến 12 tháng bằng chứng |
| 2 | **TIER là thuộc tính của cơ sở hạ tầng/nhà cung cấp**, không phải của ứng dụng | Compose chạy **một** instance mỗi dịch vụ, không dự phòng | Chọn nhà cung cấp hosting có TIER công bố; thiết kế nhiều instance, load balancer, DB HA. Không nên quảng cáo "TIER III" cho phần mềm |
| 3 | **Chưa chạy load test** | Chưa có số p95/p99, chưa biết sức chịu tải | Chạy k6/Locust trên môi trường giống production trước khi cam kết SLA |
| 4 | **Chưa penetration test độc lập** | Không có bằng chứng bên ngoài về khả năng chống tấn công | Thuê pentest trước khi bán |
| 5 | **Chưa diễn tập backup/restore** | Backup chưa chứng minh được là khôi phục được | Chạy `scripts/rehearse_backup_restore.ps1` và ghi RTO/RPO thực tế |
| 6 | **Tài liệu 08 ghi `.env` từng nằm trong lịch sử Git (F01)** | Mọi credential trong đó phải coi là đã lộ | Xoay vòng DB password và các key Supabase trước khi go-live thương mại |
| 7 | Redis không có mật khẩu/TLS; Elasticsearch (profile tùy chọn) tắt xác thực | Chỉ chấp nhận được khi mạng nội bộ cô lập | Bật xác thực nếu mở rộng ra ngoài mạng nội bộ |
| 8 | KD01–KD08 (quyết định nghiệp vụ) chưa có người ký (tài liệu 08, F10) | Chính sách và SLA chưa có thẩm quyền | PO/khách hàng ký trước pilot dữ liệu thật |
| 9 | SonarCloud còn một số code smell cấp thấp | Không chặn Quality Gate nhưng là nợ kỹ thuật | Xử lý dần theo backlog |

## 5. Điều kiện trước khi bán cho khách

Tối thiểu: (1) chạy `enforce_initial_passwords` trên DB khách, (2) xoay credential Supabase/DB, (3) cấu hình proxy `EAS_TRUST_PROXY_HEADERS=true`, (4) pentest bên thứ 3, (5) diễn tập khôi phục, (6) load test theo SLA cam kết.
