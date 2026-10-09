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
