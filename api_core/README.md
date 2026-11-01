# EAS Core API

Backend P0 là Django modular monolith. Thư mục này chứa configuration, health/readiness, domain module và worker dùng chung code. Không gọi AI service hoặc Drools trên đường giao dịch P0.

## Quy tắc

- Client không truy cập trực tiếp schema `eas`.
- Runtime API dùng DB login chỉ thuộc `eas_api`; worker dùng login chỉ thuộc `eas_worker`.
- Mỗi command nghiệp vụ phải kiểm session, quyền, idempotency, expected version và state trong transaction.
- Không gọi mạng khi đang giữ database lock.
- Audit, outbox, idempotency response và thay đổi domain commit/rollback cùng nhau.
- Health readiness phải FAIL nếu schema thiếu, config chưa active hoặc runtime đang dùng quyền quản trị.

Hiện đã có auth/session, command lifecycle A/B/C, attachment/scanner adapter, outbox/SLA worker và API lookup cho 8 nguồn dữ liệu giả lập. Các module này có unit/contract test nhưng vẫn phải ghi là **integration pending** cho tới khi chạy E2E bằng runtime login, Redis, ClamAV và Storage trên staging.

## Mock source API

`/api/v1/mock/` cung cấp 17 endpoint GET theo các miền HR, tài sản, cơ sở vật chất, CRM, procurement, IT, finance và travel. Endpoint chỉ nhận resource nằm trong allowlist, yêu cầu session/role EAS, hỗ trợ `limit`, `cursor`, `q` và không xuất dữ liệu nhạy cảm. Schema và hướng dẫn nằm tại [mock_enterprise_sql](../database/mock_enterprise_sql/README.md).

## Email đăng nhập và đặt lại mật khẩu

Tài khoản EAS đăng nhập bằng email thuộc domain cấu hình `EAS_LOGIN_EMAIL_DOMAIN` (mặc định `eas.com`). Quên mật khẩu tạo yêu cầu chờ OPS_ADMIN có quyền `GLOBAL + ALL`; quản trị viên phải xác minh danh tính qua kênh độc lập trước khi duyệt. Hệ thống tạo mật khẩu tạm ngẫu nhiên, gửi đến email nhân viên và buộc đổi mật khẩu ở lần đăng nhập kế tiếp. Mật khẩu mặc định dùng chung và hộp thư tempmail không được sử dụng. Địa chỉ `@eas.com` chỉ nhận được thư nếu domain có mail provider/MX; hiện không nên xem các địa chỉ này là mailbox thật.

SMTP được cấu hình trong `.env`. Để kiểm thử gửi thư miễn phí qua một Gmail hiện có, bật xác minh 2 bước, tạo App Password trong tài khoản Google và dùng cấu hình mẫu sau:

```dotenv
EAS_EMAIL_HOST=smtp.gmail.com
EAS_EMAIL_PORT=587
EAS_EMAIL_USER=your-account@gmail.com
EAS_EMAIL_PASSWORD=your-16-character-app-password
EAS_EMAIL_USE_TLS=true
EAS_EMAIL_USE_SSL=false
EAS_EMAIL_FROM="EAS Support <your-account@gmail.com>"
EAS_LOGIN_EMAIL_DOMAIN=gmail.com
EAS_EMAIL_TEST_RECIPIENT=
```

Không dùng mật khẩu đăng nhập Google và không gửi App Password qua chat. Trong cấu hình backend, đặt SMTP Gmail và `EAS_LOGIN_EMAIL_DOMAIN=gmail.com`; để `EAS_EMAIL_TEST_RECIPIENT` trống. Backend vẫn chấp nhận địa chỉ `@eas.com` cũ trong giai đoạn chuyển đổi. Trên Supabase DATN, migration [06_dev_gmail_aliases.sql](../database/migrations/06_dev_gmail_aliases.sql) đã đổi 42 tài khoản thử nghiệm thành alias `your-account+<user-id>@gmail.com`; mọi alias nhận thư trong cùng inbox. Migration tăng `auth_version` để vô hiệu hóa phiên cũ. Không dùng chung inbox này cho tài khoản thật. Migrations 05/06 đã chạy trên DATN; không chạy lại.
