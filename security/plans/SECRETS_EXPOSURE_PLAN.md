# Secrets Exposure Fix Plan

Báo cáo: [SECRETS_EXPOSURE_REPORT.md](../reports/SECRETS_EXPOSURE_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `ai_service/.dockerignore` — loại `.env`, `.env.*` (trừ `.env.example`), `.venv*`, `__pycache__`, `*.log`.
- `.dockerignore` — thêm `**/.env.*`, `!**/.env.example`, `**/*.log`, `logs`.
- `web_client/nginx.conf` — `location ~ /\.(?!well-known/) { return 404; }`, `location ~* \.(env|sql|bak|backup|dump|log|ini|conf|map|py|sh|ps1|cmd)$ { return 404; }`, `autoindex off`.
- `api_core/authn/service.py` — fallback dev chỉ khi `EAS_DEV_DEFAULT_PASSWORD` được đặt tường minh; không còn giá trị mặc định.

## New files

- `ai_service/.dockerignore`
- Test `CredentialHardeningTests.test_seed_fallback_requires_explicit_dev_password`, `test_seed_fallback_never_applies_outside_development` (`api_core/tests/test_authn.py`).

## Verification goals

- [x] `git ls-files .env` trả về rỗng
- [x] grep mẫu secret trên toàn bộ file được track không có kết quả thật (chỉ placeholder/test)
- [x] Không biến `VITE_*` nào chứa secret
- [x] `.env.example` tồn tại và chỉ có placeholder
- [x] `/.env`, `/.git/config`, `/backup.sql`, `/database/seed.sql`, `/server.log` trả 404 (đã curl trên nginx cấu hình production)
- [x] Directory listing tắt (`/assets/` không liệt kê file)
- [x] Image ai_service không còn chứa `.env` (đã có `.dockerignore`)

## Manual verification (for the human)

- Đổi mật khẩu `eas_backend_login` / `eas_worker_login` trên Supabase: chuỗi kết nối từng hiển thị trong terminal của phiên trợ lý AI ngày 01/11/2026.
- Thay `INTERNAL_API_SECRET` trong `.env` local bằng chuỗi ngẫu nhiên ≥ 32 ký tự (giá trị hiện tại là mặc định công khai).
- Nếu image ai_service đã từng được push lên registry trước bản sửa: xoá image đó và xoay `GEMINI_API_KEY`.
- Cài `gitleaks` (`winget install gitleaks` hoặc tải bản phát hành) rồi chạy `gitleaks detect --source . --verbose`.
