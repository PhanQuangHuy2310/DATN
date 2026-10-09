# Báo cáo thực thi nâng cấp EAS

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-DOC-10 |
| Phiên bản | 1.0 |
| Ngày chạy | 09/10/2026 |
| Phạm vi | Security containment, Supabase verification, executable backend foundation, CI và domain P0 |
| Trạng thái release | PRE-PRODUCTION / NO-GO |

## 1. Thay đổi đã thực hiện

### Repository và bảo mật

- Thêm `.gitignore` cho secret, cache, log, build output và local Supabase state.
- Thêm `.env.example` không chứa credential; frontend chỉ giữ `VITE_API_BASE_URL`.
- Thêm automated secret gate, không in giá trị khớp.
- Thêm JSON logging và redaction cho Authorization/password/token/key/DSN, chống log injection bằng escape newline.
- Thêm template tạo/kiểm hai runtime login tách `eas_api` và `eas_worker`.

### Kiến trúc và tài liệu

- Đồng bộ README gốc với ADR01 modular monolith.
- Chuyển AI, Drools và mobile về P1; loại chúng khỏi Compose P0.
- Ghi rõ frontend/admin/worker/storage còn thiếu, không tuyên bố đã triển khai.
- Bổ sung báo cáo thẩm định, chiến lược thương mại và biên bản Supabase.

### Backend foundation

- Django 5.2 LTS, Gunicorn và Psycopg được pin version.
- Parser `DATABASE_URL` che lỗi, hỗ trợ DSN cũ có ký tự `@` và yêu cầu PostgreSQL/TLS profile.
- Production settings bật HTTPS redirect, secure cookie, HSTS, referrer policy, CSRF origin và proxy trust có điều kiện.
- `GET /health/live` không phụ thuộc DB.
- `GET /health/ready` fail-closed nếu schema/type/config/runtime role không đạt.
- `GET /api/v1/meta/request-types` chỉ trả metadata không nhạy cảm.
- Docker container chạy non-root, read-only filesystem, drop capability và healthcheck.

### Domain P0

- Validate/normalize chuỗi NFC/trim, type, length, enum, UUID/date, required/unknown field và HTML.
- Luật riêng LEAVE: ngày hiện tại Asia/Ho_Chi_Minh, thứ tự ngày, tối đa 30 ngày, không tự bàn giao.
- Route engine allowlist cho integer amount operators, đúng một default và priority duy nhất.
- Resolve DIRECT_MANAGER/department binding/REQUESTER, route 1–3 cấp và separation of duties.
- Kiểm đúng các ngưỡng EQUIPMENT: dưới 10 triệu, từ 10 đến đúng 50 triệu, trên 50 triệu.

## 2. Bằng chứng đã chạy

| Gate | Môi trường | Actual result | Trạng thái |
|---|---|---|---|
| Database package | PGlite PostgreSQL 18.3 WASM | 86 SQL assertion, installer/verify/regression/rollback/seed | PASS |
| Supabase installation | PostgreSQL 17.6, session read-only | 30 bảng, 27 routine, 60 RLS policy, verify script | PASS |
| Django/API/domain test | Python 3.12 | 66 test: auth/session, audit, workflow, storage, worker, mock-source API, health, DB config, payload, routing và logger | PASS |
| Mock enterprise SQL | PostgreSQL WASM + Supabase 17.6 | 8 schema, 23 bảng, 6 view, migration 001–003; invariant/concurrency/privilege/readiness | PASS |
| Web client | Vite/ESLint/npm audit | lint, production build, 0 vulnerability | PASS |
| Ruff lint | Source foundation | Không lỗi | PASS |
| Ruff format | Source foundation | Tất cả file đúng format | PASS |
| Dependency audit | requirements pin | Không có vulnerability đã biết | PASS |
| Django deploy check | Production settings giả lập, secret entropy đủ | Không cảnh báo | PASS |
| Compose config | Docker Compose parser | Cú pháp hợp lệ | PASS |
| Secret gate | Git tracked files | Ba `.env` đang tracked | **FAIL/BLOCKER** |
| Remote app readiness | Supabase thật | Admin DB role; chưa có active releases | **FAIL-CLOSED đúng thiết kế** |
| Container build/run | Local | Docker daemon không hoạt động | NOT RUN |
| TC001–TC100 | Application/UAT | Chưa có full application/release/evidence | NOT RUN |

## 3. Blocker cần chủ dự án xử lý

### B01 — Credential đã lộ

Rotate DB password và Supabase secret key đã xuất hiện trong Git/chat. Sau rotate, xác minh credential cũ bị từ chối. Không gửi key mới trong hội thoại hoặc commit.

### B02 — `.env` đang tracked

Ba file sau vẫn ở Git index/history:

- `api_core/.env`
- `web_admin/.env`
- `web_client/.env`

`.gitignore` không tự gỡ file đã tracked. Cần chủ dự án chỉ định nhánh để thực hiện quy trình Git được phép; sau đó chạy secret gate đến PASS và quyết định rewrite history có phối hợp với mọi clone.

### B03 — Runtime role chưa đạt

DSN hiện dùng vai trò quản trị. Chạy template `deploy/sql/01_runtime_logins.example.sql` bằng bản sao ngoài repository, sau đó chạy `02_verify_runtime_roles.sql`. Backend chỉ nhận DSN của `eas_backend_login`.

### B04 — Chưa có active release

Ba request type tồn tại nhưng chưa gắn active release. Không chạy demo seed trên project thật khi chưa xác định đây là development trống. POLICY_ADMIN phải validate/publish profile được chấp thuận và tạo admin audit.

### B05 — MCP không xuất hiện trong phiên

Danh sách MCP tool/resource của phiên không có Supabase. Project vẫn đã được kiểm qua DSN read-only. Sau khi connector được enable cho đúng workspace và phiên được mở lại, chuyển thao tác quản trị sang MCP capability có kiểm soát.

## 4. Việc chưa được tuyên bố hoàn thành

- Auth/session, command transaction, storage/scanner, worker và React client đã có implementation/unit test; vẫn thiếu E2E staging và concurrency evidence nên chưa được gọi là nghiệm thu.
- Reassign và web admin đầy đủ chưa được triển khai.
- Mock-source API đã có 17 route và schema thật trên Supabase; deployment của Django API cùng runtime role trên staging chưa chạy E2E.
- Accessibility mới qua static lint; chưa có browser/screen-reader test.
- Incremental migration, staging, image build, SBOM/image scan.
- Backup/restore/rollback rehearsal, RPO/RTO và load test.
- UAT, pilot KPI và commercial validation.

Không dùng báo cáo này để đổi các mục trên thành PASS.

## 5. Cập nhật bằng chứng vòng runtime ngày 09/10/2026

Các trạng thái cũ “Docker/E2E/backup NOT RUN” trong tài liệu này đã được thay thế bởi biên bản [EAS-DOC-13](./13_Bien_ban_kiem_chung_runtime_E2E_DR.md): stack năm container đã chạy, browser E2E 4/4 PASS, logical backup/restore PASS và hai image ứng dụng có 0 fixable Critical/High tại thời điểm scan. Runtime role và active release cũng đã đạt readiness.

Các blocker còn hiệu lực: credential rotation; `.env` còn trong Git index/history; Storage private E2E; acceptance suite đầy đủ, N/N-1 migration, PITR/object restore, load test và UAT. Vì vậy kết luận production vẫn là `NO-GO`.
