# Frontend Secrets Security Report

## Status: PASS

Trạng thái trước khắc phục: **PASS**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [FRONTEND_SECRETS_PLAN.md](../plans/FRONTEND_SECRETS_PLAN.md).

## Findings

- `web_client/src`, `web_admin/src`, `public/`, `mobile_app/lib`: không có khóa, token hay mật khẩu. Chỉ có `VITE_API_BASE_URL`, `VITE_EAS_PORTAL`, `VITE_ADMIN_PORTAL_URL` (không bí mật).
- Bundle `dist/assets/*.js`: grep `sk_|AKIA|sb_secret|eyJhbGci|AIza` chỉ ra `sk_description` (tên khóa i18n, dương tính giả).
- Không có file `.map` trong `dist`; `GET /assets/<bundle>.js.map` trước sửa trả `200 text/html` (SPA fallback), sau sửa trả 404.
- Trình duyệt chỉ gọi API cùng origin (`/api`), không gọi trực tiếp bên thứ ba (Gemini, Supabase).

## What's at risk

Không có.

## What's already secure

Mọi lời gọi nhạy cảm (AI, lưu trữ) đi qua `api_core` với secret phía server.

## Recommendations

Khai báo `build.sourcemap: false` tường minh để không vô tình bật lại.

## Verification results

- [x] Không có secret trong file frontend
- [x] Lời gọi nhạy cảm đi qua backend
- [x] Chỉ có khóa công khai phía client (thực tế: không có khóa nào)
- [x] Không biến `VITE_*` nào chứa secret
- [x] `<bundle>.js.map` trả 404
