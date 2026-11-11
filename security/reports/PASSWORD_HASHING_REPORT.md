# Password Hashing Security Report

## Status: PASS

Trạng thái trước khắc phục: **MEDIUM**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [PASSWORD_HASHING_PLAN.md](../plans/PASSWORD_HASHING_PLAN.md).

## Findings

- `PASSWORD_HASHERS = [Argon2, PBKDF2]`; mọi chỗ ghi mật khẩu dùng `make_password(..., hasher="argon2")` (đổi mật khẩu, duyệt reset, quản trị user). DB live: 42/42 tài khoản Argon2.
- Không có MD5/SHA-1/SHA-256 cho mật khẩu (SHA-256 chỉ dùng cho khóa throttle và hash chain audit).
- **MEDIUM-LOW:** `login` bỏ qua bước băm khi email không tồn tại hoặc tài khoản bị khóa → thời gian phản hồi khác biệt, dò được email nhân viên dù thông điệp lỗi đồng nhất.
- Fallback mật khẩu seed dev có giá trị mặc định trong mã (xem SECRETS_EXPOSURE).
- `fix_seed_passwords_local.py` đặt hash PBKDF2 biết trước cho tài khoản placeholder: công cụ dev chạy tay; DB live không còn placeholder.

## What's at risk

Kẻ tấn công liệt kê được email hợp lệ để rải mật khẩu (password spraying) hoặc lừa đảo có mục tiêu.

## What's already secure

Argon2 mặc định, chính sách mật khẩu 15–128 ký tự + CommonPasswordValidator, mật khẩu tạm 28 ký tự ngẫu nhiên `secrets`, bắt buộc đổi sau reset.

## Recommendations

Băm giả với Argon2 cho tài khoản không tồn tại/bị khóa.

## Verification results

- [x] Chỉ dùng Argon2 (PBKDF2 chỉ để xác minh hash cũ)
- [x] Không MD5/SHA-1/SHA-256 cho mật khẩu
- [x] Không còn hash yếu trên DB live (42/42 Argon2)
- [x] Thời gian login không phụ thuộc email có tồn tại
