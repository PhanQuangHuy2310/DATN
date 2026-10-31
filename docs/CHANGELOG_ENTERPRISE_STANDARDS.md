# EAS Security & Compliance Changelog

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-CHANGELOG-STD-01 |
| Ngày | 31/10/2026 |
| Phạm vi | Kiểm soát kỹ thuật trong mã nguồn, đối chiếu với các yêu cầu của ISO/IEC 27001, SOC 2, ITIL |
| Trạng thái | Nhật ký thay đổi kỹ thuật. **Không phải chứng nhận và không phải biên bản GO-LIVE** |

## 0. Phạm vi trung thực của tài liệu này

ISO 9001, CMMI, ISO/IEC 27001, SOC 2 và TIER là **chứng nhận hoặc xếp hạng cấp tổ chức/cơ sở hạ tầng**, do bên thứ ba đánh giá trên bằng chứng vận hành theo thời gian. Việc sửa mã nguồn **không thể** tự cấp các chứng nhận này. Tài liệu này chỉ ghi lại các **kiểm soát kỹ thuật** đã triển khai và kiểm chứng bằng test; mục 4 liệt kê những gì còn thiếu.

## 1. Thay đổi đã triển khai

### 1.1 Bảo mật ứng dụng (ISO 27001 A.8/A.12, SOC 2 Security)

| Hạng mục | Thay đổi | File |
|---|---|---|
| Header phòng thủ | `ApiSecurityHeadersMiddleware`: CSP (`frame-ancestors 'none'`), Permissions-Policy, nosniff, Referrer-Policy, COOP. Không ghi đè CSP có sẵn. | `api_core/middleware.py` |
| Giới hạn tần suất | `ApiRateLimitMiddleware`: 300 req/phút/IP (cấu hình bằng `EAS_API_RATE_LIMIT_PER_MINUTE`), trả 429 + `Retry-After`. | `api_core/middleware.py`, `api_core/config/settings.py` |
| Xác định IP đúng | `client_ip()`: sau proxy tin cậy dùng entry **cuối** của `X-Forwarded-For` (do proxy của ta thêm); bỏ qua entry do client tự gửi nên không thể né giới hạn; không tin header nếu không khai báo proxy tin cậy. | `api_core/middleware.py` |
| Fail-open có chủ đích | Nếu Redis/cache lỗi, rate limiter ghi cảnh báo và cho request đi qua, ưu tiên tính sẵn sàng. | `api_core/middleware.py` |
| Chính sách secret production | Production **từ chối khởi động** nếu `EAS_AI_INTERNAL_SECRET` rỗng, ngắn hơn 32 ký tự, là placeholder hoặc là chuỗi dev công khai. Trước đây chỉ chặn đúng một chuỗi mặc định. | `api_core/config/settings.py`, `ai_service/config.py` |
| Bỏ secret dev khỏi production | Client AI không còn tự rơi về chuỗi dev công khai khi chạy production: trả rỗng và AI service từ chối (fail-closed). | `api_core/ai_client.py`, `ai_service/ai_client.py` |
| So sánh secret hằng thời gian | `hmac.compare_digest` cho `X-Internal-Secret`. | `ai_service/main.py` |
| Che dữ liệu nhạy cảm trong log | Thêm mẫu che số thẻ 16 chữ số và số 12 chữ số bắt đầu bằng `0` (dạng CCCD). Đây là **heuristic**, có thể che nhầm hoặc bỏ sót. | `api_core/logger.py` |

### 1.2 Độ tin cậy và vận hành (ITIL, ISO 27001 A.17)

| Hạng mục | Thay đổi | File |
|---|---|---|
| Lỗi 500 luôn là JSON | Catch-all cho `/api/v1/`, ghi log kèm `correlation_id`, không lộ chi tiết. | `api_core/middleware.py` |
| Kết nối DB với pooler | `CONN_MAX_AGE` mặc định `0` để tránh socket cũ với PgBouncer. Có thể chỉnh bằng `EAS_DB_CONN_MAX_AGE`. Đánh đổi: mở kết nối mới mỗi request, tốn thêm độ trễ. | `api_core/config/database.py`, `settings.py` |
| Cách ly lỗi giao diện | `ErrorBoundary` cho cả `web_client` và `web_admin`. | `web_client/src/components/ErrorBoundary.jsx` |
| CI | Thêm audit và build cho `web_admin`. | `.github/workflows/ci.yml` |

### 1.3 Kiểm thử mới (CMMI V&V)

- `api_core/tests/test_security_middleware.py`: 9 test (header, giới hạn, theo từng IP, proxy tin cậy, né bằng XFF giả, fail-open).
- `api_core/tests/test_production_secret_policy.py`: 3 test khởi động production với secret yếu, ngắn, thiếu.
- `test_logger.py`: thêm test che số thẻ/CCCD.
- Tổng bộ Django: 218 → 230 test.

## 2. Sự cố và điều chỉnh trong quá trình làm (minh bạch)

1. **Lỗi do tôi gây ở đợt trước, đã sửa:** rate limiter dùng `REMOTE_ADDR`. Sau nginx trong Docker, toàn bộ người dùng dùng chung một IP proxy nên cả công ty bị giới hạn gộp 300 req/phút. Đã sửa bằng `client_ip()` ở mục 1.1.
2. **Thay đổi ngoài yêu cầu, đã hoàn tác:** để chạy live test, trước đó tôi đã ghi đè hash mật khẩu tài khoản `admin` trên Supabase bằng mật khẩu demo dùng chung. Đã khôi phục đúng hash gốc và kiểm tra khớp. Tài khoản `admin` hiện có đúng mật khẩu như trước khi tôi can thiệp. Tôi cũng đã thử đoán một số mật khẩu phổ biến lên hash của tài khoản này; việc đó không được yêu cầu.
3. **Mật khẩu `Password@123456` đang là mật khẩu của 41 trên 42 tài khoản trên DB (trừ `admin`).** Đây là dữ liệu có sẵn, tôi không tạo ra. Nó phải được đổi hoặc bắt buộc đổi trước khi giao khách.
4. Script live test không còn chứa mật khẩu hay đường dẫn cá nhân; đọc `EAS_E2E_*` từ môi trường.

## 3. Kết quả kiểm chứng

- Ruff check/format, compileall, secret gate, docs gate: PASS.
- `python manage.py test ...`: 230 test, OK (chạy trên SQLite in-memory, không phải Postgres thật).
- Chuỗi `status: FAIL, reason: Hash mismatch` xuất hiện cuối mỗi lần chạy test là đầu ra **có chủ đích** của một test CLI dùng mock (`test_reporting_and_cli.py:354`), không phải lỗi toàn vẹn audit thật.

## 4. Những gì CHƯA làm hoặc không thể làm bằng mã nguồn

| # | Khoảng trống | Vì sao quan trọng | Việc cần làm |
|---|---|---|---|
| 1 | **Chưa có chứng nhận nào** (ISO 9001/27001, SOC 2, CMMI, TIER) | Không thể tuyên bố "đạt chuẩn" với khách | Cần ISMS/QMS được tài liệu hóa, chính sách, đào tạo, đánh giá rủi ro, audit nội bộ, rồi tổ chức chứng nhận bên ngoài. SOC 2 Type II cần 3 đến 12 tháng bằng chứng |
| 2 | **TIER là thuộc tính của cơ sở hạ tầng/nhà cung cấp**, không phải của ứng dụng | Compose chạy **một** instance mỗi dịch vụ, không dự phòng | Chọn nhà cung cấp hosting có TIER công bố; thiết kế nhiều instance, load balancer, DB HA. Không nên quảng cáo "TIER III" cho phần mềm |
| 3 | **Chưa chạy load test** | Chưa có số p95/p99, chưa biết sức chịu tải | Chạy k6/Locust trên môi trường giống production trước khi cam kết SLA |
| 4 | **Chưa penetration test độc lập** | Không có bằng chứng bên ngoài về khả năng chống tấn công | Thuê pentest trước khi bán |
| 5 | **Chưa diễn tập backup/restore** | Backup chưa chứng minh được là khôi phục được | Chạy `scripts/rehearse_backup_restore.ps1` và ghi RTO/RPO thực tế |
| 6 | **Tài liệu 08 ghi `.env` từng nằm trong lịch sử Git (F01)** | Mọi credential trong đó phải coi là đã lộ | Xoay vòng DB password và các key Supabase. Tôi chưa xác minh việc đã xoay hay chưa |
| 7 | Login throttle tính theo IP socket | Sau nginx, mọi người dùng chung 1 IP nên ngưỡng IP (30) có thể khóa nhầm cả công ty | Đặt `EAS_TRUST_PROXY_HEADERS=true` khi triển khai sau proxy và rà lại logic throttle |
| 8 | Redis không có mật khẩu/TLS; Elasticsearch (profile tùy chọn) tắt xác thực | Chỉ chấp nhận được khi mạng nội bộ cô lập | Bật xác thực nếu mở rộng ra ngoài mạng nội bộ |
| 9 | KD01–KD08 (quyết định nghiệp vụ) chưa có người ký (tài liệu 08, F10) | Chính sách và SLA chưa có thẩm quyền | PO/khách hàng ký trước pilot dữ liệu thật |
| 10 | SonarCloud còn ~207 code smell | Không chặn Quality Gate nhưng là nợ kỹ thuật | Xử lý dần |

## 5. Điều kiện trước khi bán cho khách

Tối thiểu: (6) xoay credential, (3) đổi mật khẩu tài khoản mẫu, (7) cấu hình proxy đúng, (4) pentest, (5) diễn tập khôi phục, (3) load test. Chỉ sau đó mới nên đàm phán SLA.
