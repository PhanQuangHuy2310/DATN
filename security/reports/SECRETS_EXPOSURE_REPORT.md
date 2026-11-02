# Secrets Exposure Security Report

## Status: PASS

Trạng thái trước khắc phục: **HIGH**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [SECRETS_EXPOSURE_PLAN.md](../plans/SECRETS_EXPOSURE_PLAN.md).

## Findings

1. **HIGH — `ai_service/.env` bị đóng vào image.** `docker-compose.yml` build `ai-service` với `context: ./ai_service`, còn `ai_service/Dockerfile` chạy `COPY . .`. Thư mục này không có `.dockerignore`, nên file `.env` local (chứa `GEMINI_API_KEY`, `SUPABASE_ANON_KEY`, `INTERNAL_API_SECRET`) bị chép vào layer của image. `.dockerignore` gốc không áp dụng cho context con.
2. **LOW — `.dockerignore` gốc** chỉ loại `**/.env`, không loại `**/.env.*` (ví dụ `.env.database` chứa chuỗi kết nối thật). Các Dockerfile hiện dùng `COPY` chọn lọc nên chưa rò, nhưng không có lớp bảo vệ.
3. **LOW — nginx phục vụ SPA fallback cho đường dẫn nhạy cảm.** `try_files $uri $uri/ /index.html` khiến `/.env`, `/.git/config`, `/backup.sql` trả `200 text/html` (nội dung là `index.html`, không lộ dữ liệu, nhưng không đạt mục tiêu 404/403).
4. **LOW — mật khẩu mặc định trong mã nguồn.** `api_core/authn/service.py` (trước sửa):
   ```python
   fallback_pwd = os.getenv("EAS_DEV_DEFAULT_PASSWORD", "Admin@123456")
   ```
   Chỉ áp dụng cho hash placeholder khi `EAS_ENV=development`, nhưng `.env` local đang `development` và trỏ vào DB cloud thật.
5. **Thông tin — `.env` local dùng `INTERNAL_API_SECRET` mặc định công khai** (`datn-...`, đã nằm trong git history). Settings từ chối giá trị này khi `EAS_ENV=production`.

Kiểm tra đã chạy: `git ls-files` (chỉ có `*.env.example` với placeholder), `git grep` mẫu `sk_live_|AKIA|sb_secret_|eyJhbGciOi|postgres://user:pass@|PRIVATE KEY`, so khớp giá trị thật trong `.env`/`.env.database` với toàn bộ `git log --all -S` (không in giá trị): mật khẩu DB, `DJANGO_SECRET_KEY`, `SUPABASE_SECRET_KEY` **không** có trong history. `scripts/check_repository_secrets.py` → `SECRET_GATE=PASS`. DB live: 42/42 tài khoản dùng Argon2, 0 hash placeholder.

## What's at risk

Ai lấy được image ai_service (registry, máy build, file `docker save`) sẽ đọc được khóa Gemini và internal secret, từ đó gọi thẳng ai_service hoặc tiêu tốn quota LLM. Mật khẩu mặc định trong mã nguồn biến mọi tài khoản seed còn hash placeholder thành tài khoản biết trước mật khẩu nếu một môi trường bị đặt nhầm `EAS_ENV=development`.

## What's already secure

- `.env`, `.env.*` bị `.gitignore` chặn; chỉ `.env.example` được track, toàn bộ giá trị là placeholder (`replace-me`, `db.example.invalid`).
- `project_env.py` chỉ nạp secret ở tiến trình server; Vite chỉ lộ `VITE_*` và không biến `VITE_*` nào chứa secret.
- Production fail-closed: `settings.py` và `ai_service/config.py` từ chối secret yếu/mặc định khi `EAS_ENV=production`.
- `logger.SensitiveDataFilter` che DSN và khóa trong log (có test `test_logger.py`).
- nginx tắt directory listing (`autoindex off`; `/assets/` trả 403/404).

## Recommendations

1. Thêm `ai_service/.dockerignore`.
2. Siết `.dockerignore` gốc.
3. nginx trả 404 cho dotfile, dump, log, map.
4. Bỏ mật khẩu mặc định khỏi mã nguồn.
5. (Thủ công) Xoay vòng mật khẩu DB Supabase và `INTERNAL_API_SECRET` local.

## Verification results

- [x] `git ls-files .env` trả về rỗng
- [x] grep mẫu secret trên toàn bộ file được track không có kết quả thật (chỉ placeholder/test)
- [x] Không biến `VITE_*` nào chứa secret
- [x] `.env.example` tồn tại và chỉ có placeholder
- [x] `/.env`, `/.git/config`, `/backup.sql`, `/database/seed.sql`, `/server.log` trả 404 (đã curl trên nginx cấu hình production)
- [x] Directory listing tắt (`/assets/` không liệt kê file)
- [x] Image ai_service không còn chứa `.env` (đã có `.dockerignore`)
