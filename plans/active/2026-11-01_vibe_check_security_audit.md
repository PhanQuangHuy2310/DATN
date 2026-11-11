# Kế hoạch: Kiểm toán và khắc phục bảo mật theo chuẩn vibe-check (17 hạng mục)

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-11-01-01 |
| Ngày mở | 01/11/2026 |
| Trạng thái | ACTIVE |
| Nhánh | `huy` |
| Chuẩn áp dụng | [benavlabs/vibe-check](https://github.com/benavlabs/vibe-check): `AGENTS.md`, `AI-CHECKLIST.md` (17 hạng mục), `skills/vibe-check/scripts/check.py` (live scan), `manual-checklist.md` |
| Phạm vi | `api_core`, `ai_service`, `web_client`, `web_admin`, `api_gateway`, `docker-compose.yml`, `database/` |

## 1. Mục tiêu

1. Chạy đủ quy trình vibe-check: live scan → chạy công cụ có sẵn (`pip-audit`, `npm audit`) → kiểm toán mã 17 hạng mục → sửa → quét lại.
2. Mỗi hạng mục có báo cáo `security/reports/{CATEGORY}_REPORT.md` và kế hoạch sửa `security/plans/{CATEGORY}_PLAN.md`; tổng hợp tại `security/AUDIT_SUMMARY.md`.
3. Sửa toàn bộ phát hiện có thật; ghi rõ rủi ro còn lại và bước kiểm tra thủ công.
4. Không làm hỏng quality gate hiện có; sửa luôn lỗi tồn đọng phát hiện trong quá trình kiểm thử.

## 2. Cơ chế hai cổng

1. **Cổng điều tra (BA / Dev / Security):** bằng chứng `file:dòng`, kết quả `curl` chỉ đọc, kết quả scanner. Mỗi phát hiện được đối chiếu với cấu hình production (nginx, compose, settings) trước khi sửa.
2. **Cổng nghiệm thu (QA / SecOps):** toàn bộ test suite, ruff, eslint, build, SQL validation và scan lại phải xanh. Không chạy request ghi vào DB thật.

## 3. Bằng chứng ban đầu (01/11/2026)

| Nguồn | Kết quả |
|---|---|
| `check.py` lên nginx cấu hình production (container `nginx:alpine` + `web_client/nginx.conf`) | 1 FAIL (`object-src` thiếu), 1 WARN (lộ `Server: nginx/1.31.6`), 22 PASS |
| `pip-audit` `api_core/requirements.txt` | Không có lỗ hổng |
| `pip-audit` `ai_service/requirements.txt` | `starlette 0.38.6` (nhiều PYSEC, bản vá đến 1.3.1), `imgaug 0.4.0` |
| `npm audit` `web_client` | 7 moderate (minimatch trong toolchain eslint, chỉ dev) |
| `npm audit` `web_admin`, `database/EAS_Supabase_SQL/validation` | 0 |
| `gitleaks`, `semgrep` | Chưa cài: không tự cài, ghi lệnh cài vào báo cáo |
| Baseline test | Django 257 OK, `tests/` 98 OK, logger OK, web 39 OK, lint OK, SQL 86 PASS, **mock SQL validation FAIL (lỗi tồn đọng)** |

## 4. Work breakdown

| # | Hạng mục | Thay đổi chính | Trạng thái |
|---|---|---|---|
| 1 | SECRETS_EXPOSURE | `ai_service/.dockerignore`; siết `.dockerignore`; nginx trả 404 cho dotfile/dump; bỏ mật khẩu dev hard-code | TODO |
| 2 | DATABASE_ACCESS | Migration `004` bật RLS + policy cho 24 bảng `mock_*` | TODO |
| 3 | AUTH_MIDDLEWARE | Xóa endpoint chết `csrf_exempt` không xác thực; role admin-events vào decorator | TODO |
| 4 | ACCESS_CONTROL | Xác minh (không cần sửa) | TODO |
| 5 | FRONTEND_SECRETS | Xác minh; nginx 404 cho asset/map không tồn tại | TODO |
| 6 | SSRF | OCR URL: chặn mọi IP không global | TODO |
| 7 | CSRF | Gỡ `csrf_exempt` (cùng #3) | TODO |
| 8 | SECURITY_HEADERS | CSP `object-src 'none'`, HSTS, `server_tokens off`, CSP API chặt | TODO |
| 9 | CORS | ai_service: bỏ credentials, header tường minh | TODO |
| 10 | RATE_LIMITING | Throttle đổi mật khẩu; reset dùng `client_ip()` | TODO |
| 11 | SQL_INJECTION | Xác minh | TODO |
| 12 | XSS | Xác minh; `Content-Disposition` chuẩn RFC 6266 | TODO |
| 13 | PAYMENT_WEBHOOKS | N/A | TODO |
| 14 | FILE_UPLOADS | Xác minh; SVG không render inline | TODO |
| 15 | ERROR_HANDLING | Tắt `/docs` ai_service ở production; lỗi OCR chung chung; JSON 404/500 | TODO |
| 16 | PASSWORD_HASHING | Chống dò email qua thời gian phản hồi | TODO |
| 17 | DEPENDENCIES | `fastapi 0.162.0` / `starlette 1.10.0` / instrumentator `8.1.0`; pin devDeps; pin image | TODO |
| 18 | Lỗi tồn đọng | Sửa `database/mock_enterprise_sql/validation/reproduce.mjs` | TODO |
| 19 | Tài liệu | `AGENTS.md`, báo cáo, changelog, chuyển kế hoạch sang `completed` | TODO |

## 5. Ràng buộc

- Không ghi vào DB Supabase thật; migration chỉ được áp dụng sau khi chủ dự án đồng ý.
- Không cài công cụ mới khi chưa hỏi.
- Không in giá trị bí mật trong tài liệu và log.

## 6. Nhật ký tiến trình (để tiếp tục khi phiên làm việc bị reset)

> Cập nhật lần cuối: 01/11/2026. Đọc mục này trước khi làm tiếp. Không làm lại các bước đã DONE. Bảng mục 4 giữ trạng thái gốc; trạng thái thật nằm ở 6.2/6.3.

### 6.1 Điều tra xong cả 17 hạng mục — kết luận

| # | Kết luận | Bằng chứng |
|---|---|---|
| 1 | HIGH: `ai_service/.env` (có `GEMINI_API_KEY`, `SUPABASE_ANON_KEY`) bị `COPY . .` vào image vì context `./ai_service` không có `.dockerignore`. LOW: `.dockerignore` gốc thiếu `**/.env.*`; nginx trả `index.html` 200 cho `/.env`, `/.git/config`; mật khẩu dev hard-code `Admin@123456`. `.env` local dùng `INTERNAL_API_SECRET` mặc định công khai (có trong history). DB password / Django secret / Supabase key không có trong history. `check_repository_secrets.py` PASS. | Live DB: 42/42 user Argon2, 0 hash placeholder |
| 2 | `eas` PASS (33/33 bảng RLS + policy chỉ role backend; anon/authenticated không quyền, không USAGE). LOW: 24 bảng `mock_*` tắt RLS, không policy (chỉ bảo vệ bằng GRANT). | Catalog read-only trên DB live |
| 3 | `policy_views.py` + `workflow/maintenance.py`: code chết (không route), endpoint không xác thực + `csrf_exempt` chạy `subprocess`. Route khác có `require_actor` đúng. admin-events kiểm role trong handler. ai_service `/docs` `/redoc` `/openapi.json` `/metrics` public. | URL resolver + grep decorator |
| 4 | PASS: predicate requester/participant/auditor-scope ở mọi resource; admin `authorize()` OPS_ADMIN GLOBAL; mock theo `RESOURCE_ROLES`. | `attachments.py`, `history_views.py`, `reporting.py` |
| 5 | PASS: không secret trong bundle, không sourcemap, client không gọi Supabase trực tiếp. | `dist/assets`, curl `.js.map` |
| 6 | LOW: OCR URL sót `100.64.0.0/10` (dùng `is_global`); còn rủi ro DNS rebinding; endpoint chỉ gọi được bằng internal secret, api_core không gọi. | `ai_service/routers/ocr.py:266` |
| 7 | PASS: SameSite=Lax, HttpOnly, Secure ở production; POST cross-origin bị 403. `csrf_exempt` chỉ trong code chết. | curl logout với Origin lạ |
| 8 | MEDIUM: thiếu `object-src 'none'` (nginx + Django); Django CSP thiếu `base-uri`, mở `connect-src http://127.0.0.1:*`; nginx thiếu HSTS, lộ version. | scan_before_nginx |
| 9 | PASS ở Django/nginx (không phát CORS). ai_service LOW: `allow_credentials=True`, `allow_headers=["*"]` thừa. | curl Origin evil |
| 10 | Login throttle OK, XFF chỉ tin khi `EAS_TRUST_PROXY_HEADERS=true`. MEDIUM: đổi mật khẩu không throttle. LOW: reset-request dùng `REMOTE_ADDR`. | `authn/views.py` |
| 11 | PASS: identifier từ allowlist, giá trị parameterized. | grep |
| 12 | PASS; LOW: `Content-Disposition` dựng tay. | grep sink |
| 13 | N/A. | grep |
| 14 | PASS (magic bytes, UUID key, bucket private, 10MB, ClamAV fail-closed). LOW: SVG chưa hạ về octet-stream. | `storage.py` |
| 15 | ai_service `ocr.py:210`, `:331` trả nguyên exception; docs bật mọi môi trường. `/health/ready` public chạy 5 query (~2s). Django 404 HTML mặc định (không lộ stack). | curl |
| 16 | Argon2. MEDIUM-LOW: email không tồn tại bỏ qua băm → dò email qua thời gian. | login |
| 17 | api_core sạch. ai_service: cặp an toàn đã xác minh metadata `fastapi==0.162.0` + `starlette==1.10.0` + `prometheus-fastapi-instrumentator==8.1.0` (7.0.0 đòi starlette<1). `imgaug 0.4.0` (qua paddleocr 2.8.1) chưa có bản vá → chấp nhận rủi ro. web_client devDeps `^`. `nginx:alpine` chưa pin ở `web_client/Dockerfile`, `web_admin/Dockerfile`. npm audit: 7 moderate chỉ trong eslint dev. | pip_audit_ai |
| 18 | Lỗi tồn đọng: `database/mock_enterprise_sql/validation/reproduce.mjs` FAIL vì chèn `asset_loan` id `32000000-0000-4000-8000-000000000002` đã có trong seed. | `node validation/reproduce.mjs` |

### 6.2 Đã sửa (DONE, test xanh)

- `ai_service/.dockerignore` (mới); `.dockerignore` thêm `**/.env.*`, `!**/.env.example`, `**/*.log`, `logs`.
- `api_core/authn/service.py`: fallback dev cần `EAS_DEV_DEFAULT_PASSWORD` tường minh; thêm `verify_login_password()` + `_timing_equalizer_hash()`.
- `api_core/authn/views.py`: login dùng `verify_login_password`; reset-request dùng `client_ip()`; đổi mật khẩu dùng throttle account+IP của login, mã `PASSWORD_CHANGE_RATE_LIMITED` (429).
- `web_client/src/domain.js`: thông điệp `PASSWORD_CHANGE_RATE_LIMITED`.
- `web_client/nginx.conf`: `server_tokens off`, `autoindex off`, HSTS, Permissions-Policy, CSP đủ directive, 404 cho dotfile/dump/map, `/assets/` thiếu → 404 (đã kiểm chứng bằng container).
- `api_gateway/nginx.conf`: CSP JSON chặt + HSTS (`nginx -t` OK).
- `api_core/middleware.py`: CSP API `default-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`.
- Xóa `api_core/workflow/policy_views.py`, `api_core/workflow/maintenance.py`.
- `admin_events_view`: role trong decorator; `list_admin_events` bỏ EXISTS trùng.
- `attachment_download`: `content_disposition_header()`; SVG → octet-stream.
- Test mới/cập nhật: `CredentialHardeningTests`, `AdminEventsRoleGateTests`, `test_attachment_download_headers.py`, `test_security_middleware.py`.

### 6.3 Còn lại (TODO, theo thứ tự)

1. ~~#2 migration 004~~ DONE: `migrations/004_mock_rls.sql` + khối RLS trong `00_mock_enterprise_schemas.sql`. Chưa áp dụng lên DB thật. Readiness vẫn chỉ đòi 001–003 (`health/views.py:84`) — nâng lên 004 sau khi áp dụng.
2. ~~#18~~ DONE: `reproduce.mjs` dùng id `...0000000000ff` và khoảng thời gian cố định 10–12/10/2026 (test cũ phụ thuộc `now()`), thêm kiểm tra RLS mọi bảng mock → PASS.
3. ~~ai_service~~ DONE: `ocr.py` dùng `not ip.is_global`, lỗi OCR chung chung (502/400) + log; `main.py` `IS_PRODUCTION` tắt docs/redoc/openapi, public path production chỉ `/health`, `/`; CORS `allow_credentials=False`, header tường minh. Test: `tests/test_ai_service_exposure.py` (mới), thêm 4 URL SSRF vào `tests/integration/test_ai_service.py`.
4. ~~Django~~ DONE (commit `e39598f`): `/health/ready` cache 5s (chỉ cache khi ready, tắt khi `test`), `handler404/handler500` JSON trong `config/urls.py`; test `JsonErrorHandlerTests` (test_health.py).
   - Các mục 6.2 + TODO 1–3 đã được commit trong `e39598f`, `24c4d07` (02/11/2026).
5. ~~#17~~ DONE: ai_service (cả 2 file requirements) `fastapi 0.162.0`, `starlette 1.10.0` (pin mới), `prometheus-fastapi-instrumentator 8.1.0`, `python-multipart 0.0.33`, `Pillow 13.0.0`, `python-dotenv 1.2.4` (audit đầy đủ dạng JSON phát hiện thêm 3 gói này — lần audit đầu bị cắt bởi `tail`). Kiểm chứng: venv tạm `%TEMP%/claude/eas-ai-venv`, 16 test AI pass, 0 skip; multipart upload parse OK. Còn lại (chấp nhận rủi ro, cần paddle 3.x đổi API): `paddlepaddle 2.6.2`, `protobuf 3.20.2`, `imgaug 0.4.0` — chỉ trong image OCR (`requirements.txt`), không có trong `requirements-local.txt`. web_client devDeps pin `4.13.0`/`1.64.0` + lockfile đồng bộ. Image nginx web_client/web_admin pin digest giống gateway.
6. ~~AGENTS.md~~ DONE: `AGENTS.md` (nguyên văn vibe-check + mục "Project notes (EAS)" ghi 3 ngoại lệ có lý do), `CLAUDE.md` = `@AGENTS.md`; `build: { sourcemap: false }` tường minh ở 2 vite config.
7. ~~Full gate~~ DONE (02/11/2026): Django 267 OK, `tests/` 100 OK, logger OK, ruff check + format (phạm vi CI) OK, compileall OK, web_client 39 pass / lint / build (0 `.map`), web_admin build, SQL 86 PASS, mock SQL PASS, `SECRET_GATE=PASS`, `npm audit --omit=dev` 0.
8. ~~Rescan~~ DONE: nginx (image đã pin) trước 1 FAIL / 1 WARN / 22 PASS → sau 0 FAIL / 0 WARN / 23 PASS. Django API trực tiếp: 0 FAIL, 1 WARN (`Server: WSGIServer` chỉ có ở dev `runserver`). Bằng chứng lưu tại `security/evidence/scan_*.json`.
9. Tài liệu: `security/reports/*_REPORT.md` (17), `security/plans/*_PLAN.md` (17), `security/AUDIT_SUMMARY.md`, `plans/reports/2026-11-01_vibe_check_security_audit_report.md`, `changelogs/2026-11-01_vibe_check_security_hardening.md` + `changelogs/README.md`, README cho `plans/active|completed|reports`; chuyển kế hoạch sang `plans/completed/`.

### 6.4 Môi trường cục bộ

- Container `eas-vibe-nginx` (127.0.0.1:8088, mount `web_client/nginx.conf` + `web_client/dist`) đang chạy; dọn bằng `docker rm -f eas-vibe-nginx`.
- Scanner nằm trong scratchpad phiên (mất khi reset): clone lại `https://github.com/benavlabs/vibe-check.git` vào thư mục tạm, chạy `python -I <repo>/skills/vibe-check/scripts/check.py http://127.0.0.1:8088 --api http://127.0.0.1:8000/health/live --json`.
- Backend chạy bằng Python global: `python manage.py runserver 127.0.0.1:8000 --noreload` (không có `.venv`).
- Baseline trước sửa: Django 257 OK, `tests/` 98 OK, web 39 OK, SQL 86 PASS, mock SQL FAIL (#18). Scan nginx: 1 FAIL, 1 WARN, 22 PASS.
- Chủ dự án tự làm: đổi mật khẩu DB Supabase (chuỗi kết nối từng hiển thị trong terminal của phiên trợ lý), thay `INTERNAL_API_SECRET` mặc định trong `.env`.
