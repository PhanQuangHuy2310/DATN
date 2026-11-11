# Frontend Secrets Fix Plan

Báo cáo: [FRONTEND_SECRETS_REPORT.md](../reports/FRONTEND_SECRETS_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `web_client/vite.config.js`, `web_admin/vite.config.js` — `build: { sourcemap: false }`.
- `web_client/nginx.conf` — `/assets/` thiếu file trả 404; đuôi `.map` trả 404.

## New files

- Không có.

## Verification goals

- [x] Không có secret trong file frontend
- [x] Lời gọi nhạy cảm đi qua backend
- [x] Chỉ có khóa công khai phía client (thực tế: không có khóa nào)
- [x] Không biến `VITE_*` nào chứa secret
- [x] `<bundle>.js.map` trả 404

## Manual verification (for the human)

- Mở DevTools → Network trên trang đăng nhập: mọi request đi tới cùng origin.
