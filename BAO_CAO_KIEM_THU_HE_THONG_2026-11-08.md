# Báo cáo rà soát ổn định DATN — 08/11/2026

## Phạm vi

Bản đầu vào: `DATN-dangduy_UI_UX_fix_429_frontend_only.zip`. Kiểm tra logic offline ở tầng API/luồng nghiệp vụ, React client, cấu hình khởi động local và khả năng thăm dò các dịch vụ. Không chỉnh schema, database, dữ liệu nghiệp vụ hay mô hình AI. Không thêm API giả hoặc vô hiệu hóa xác thực/rate limiter.

## Kết quả thực tế trong môi trường kiểm thử

| Hạng mục | Kết quả | Giới hạn |
|---|---|---|
| `python -m pytest tests -q` | **165 passed, 4 skipped** (409 subtests) | Unit/contract tests, không phải E2E với PostgreSQL |
| `node --test web_client/e2e/*.test.mjs` | **89/89 passed** | Mô phỏng mạng / kiểm tra hợp đồng JS, không render trình duyệt |
| `python -m compileall -q api_core ai_service scripts tests` | **PASS** | Kiểm tra cú pháp Python |
| HTTP + Redis smoke qua `scripts/system_smoke_local.py` | **7/7 unreachable tại môi trường kiểm thử** | Các service local của người dùng không chạy trong container kiểm thử; không suy ra lỗi project |
| Django test suite `api_core/tests` | **CHƯA CHẠY** | Môi trường này không có package Django; chạy trên .venv Windows |
| `npm run build`, `npm run lint`, Playwright UI | **CHƯA XÁC MINH** | `npm ci` bị timeout do không truy cập được registry ở môi trường này; không có bundle mới để render |
| Supabase/Redis/AI end-to-end | **CHƯA XÁC MINH** | Không có file `.env`/credentials hoặc quyền truy cập services trên máy người dùng |

## Sửa lỗi xác nhận từ mã nguồn

1. **Luồng SoD bị rút ngắn một cấp:** Khi người xin hồ sơ là một approver chức năng, fallback lên manager đã có mặt ở bước trước (hoặc bước sau) có thể bị đánh dấu `DUPLICATE_SKIPPED` mà không kiểm tra người thay thế hợp lệ. Bây giờ raise `Requester cannot approve own request` để `workflow/service.py` kiểm tra danh sách cấp trên hợp lệ và giải quyết lại; nếu không có người hợp lệ, request phải báo lỗi thay vì bỏ cấp phê duyệt. Test R07 ban đầu fail đã PASS.
2. **Django chạy dù Redis cấu hình nhưng ngắt:** `start_backend_local.cmd` nay gọi `scripts/check_cache_local.py` để xác minh set/get thật, thử tối đa ba lần trước khi khởi động; báo lệnh khôi phục Redis thay vì để lỗi 503 xảy ra ở login. Chỉ áp dụng local; không thay đổi chính sách bảo mật production. Với `LocMemCache` của development, tiếp tục chạy và có thông báo thích hợp.
3. **AI `.env` chứa chú thích inline ở bool/int:** `start_ai_local.cmd` kiểm tra settings trước khi chạy Uvicorn child process, hiển thị tên trường sai mà không in giá trị bí mật. Không sửa ngưỡng AI.
4. **Admin hỏi thăm dò AI không cần thiết:** Bỏ polling trạng thái bảo trì dành cho nhân viên khỏi cổng Admin. Cổng nhân viên vẫn giữ nguyên cơ chế khóa khi đồng bộ quy định.
5. **Bộ kiểm tra system smoke:** `scripts/system_smoke_local.py` kiểm tra hai UI, backend liveness/readiness, API CSRF, AI health và Redis (read-only). Phát hiện 429 và `Retry-After` mà không gửi login thử dồn dập.

## Những việc cần xác minh trên Windows / CSDL thật

**P0 — Trước khi demo:**
- Redis: `docker compose up -d redis`, `docker compose ps redis`, `docker compose exec redis redis-cli ping` => PONG; test cache `manage.py shell` => OK. Cần đảm bảo container không bị xóa bởi `docker compose down` trong phiên làm việc.
- Start backend/AI/frontend/admin ở các terminal riêng. Chạy `\.venv\Scripts\python.exe scripts\system_smoke_local.py` tại thư mục project. Điều tra từng mục FAIL/WARN và log server.
- Đăng nhập thật theo role: REQUESTER, APPROVER, EXECUTOR, ACCEPTOR, POLICY_ADMIN, OPS_ADMIN, AUDITOR; kiểm tra phân quyền từng menu, 401/403, chính sách không tự duyệt, thông báo và trạng thái hồ sơ.
- Luồng E2E trong database: tạo nháp → lưu → đính kèm → submit → phê duyệt/từ chối → thực thi → nghiệm thu → kết thúc/hủy, kiểm tra thông báo và audit log tương ứng. Kiểm tra AI đề xuất không được tự vượt quyền xác nhận của con người.

**P1 — Tính ổn định và hiệu suất:**
- Kiểm tra ba migration (`contenttypes`, `sessions`) bằng `python manage.py showmigrations contenttypes sessions`; chỉ chạy migrate trên DB thật sau khi được người quản trị xác nhận và sao lưu.
- Chrome DevTools Network: ghi thời gian/size và correlation ID cho API 401, 429, 500, 503; thử đăng nhập sau khi để lâu 30 phút; Redis restart giữa phiên; lỗi `Retry-After` phải được tôn trọng.
- Kiểm tra web client/Admin bằng `npm ci`, `npm run build`, `npm run lint` (web_client), và `npm test` nếu có; đừng xem 89 Node tests là bằng chứng build đã đạt.

**P2 — UI/UX và responsive:**
- Chạy `npm run test:ui` (Playwright/Chromium) trong `web_client` khi đã có dependencies. Kiểm tra thực tế desktop 1440x900, laptop 1366x768, tablet 768x1024, mobile 390x844; nhập form, modal, sticky action, phân trang, bộ lọc và thao tác touch.
- Không thể chứng nhận không vỡ layout / nút nào cũng hoạt động chỉ bằng static tests. Cần screenshot hoặc browser automation với fixture, và kiểm thử live với role thực.

## Lệnh chạy kiểm thử trên máy người dùng

```bat
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe scripts\system_smoke_local.py
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe manage.py test api_core.tests
cd web_client
npm ci
npm run build
npm run lint
npm test
npm run test:ui
```

**An toàn dữ liệu:** `system_smoke_local.py` và `check_cache_local.py` chỉ gọi health/CSRF và một key Redis có TTL 5 giây, không submit hồ sơ, không ghi database và không hiển thị secret. Môi trường E2E thực cần người sở hữu cấp account test và kiểm tra trước khi chạy các test có thao tác ghi.
