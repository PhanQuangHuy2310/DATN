# Password Hashing Fix Plan

Báo cáo: [PASSWORD_HASHING_REPORT.md](../reports/PASSWORD_HASHING_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `api_core/authn/service.py` — `verify_login_password()` + `_timing_equalizer_hash()` (Argon2 hash ngẫu nhiên, cache theo tiến trình).
- `api_core/authn/views.py` — login dùng `verify_login_password`.

## New files

- Test `test_unknown_account_still_pays_one_password_hash`.

## Verification goals

- [x] Chỉ dùng Argon2 (PBKDF2 chỉ để xác minh hash cũ)
- [x] Không MD5/SHA-1/SHA-256 cho mật khẩu
- [x] Không còn hash yếu trên DB live (42/42 Argon2)
- [x] Thời gian login không phụ thuộc email có tồn tại

## Manual verification (for the human)

- Không có.
