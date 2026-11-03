# Server-Side Request Forgery Security Report

## Status: PASS

Trạng thái trước khắc phục: **LOW**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [SSRF_PLAN.md](../plans/SSRF_PLAN.md).

## Findings

Nơi duy nhất tải URL do người gọi cung cấp: `POST /ai/ocr/extract-url` (`ai_service/routers/ocr.py`).

- Đã có: chỉ cho `http`/`https`, chặn hostname metadata, phân giải DNS trước, chặn IP private/loopback/link-local/reserved/multicast; `httpx` mặc định không theo redirect.
- **LOW:** điều kiện chặn sót dải CGNAT `100.64.0.0/10` (`is_private=False`) và các dải không định tuyến công cộng khác.
- **Rủi ro còn lại:** DNS rebinding (TOCTOU giữa lần phân giải để kiểm tra và lần `httpx` tự phân giải).
- Khả năng tiếp cận: endpoint nằm sau `X-Internal-Secret`, ai_service chỉ bind `127.0.0.1:8001`, gateway giới hạn `/ai/*`, `api_core` không gọi endpoint này. Các lời gọi khác (`storage.py` tới `SUPABASE_URL`, `ai_client` tới `EAS_AI_SERVICE_URL`) dùng URL cấu hình, không phải đầu vào người dùng.

## What's at risk

Một caller nội bộ biết secret có thể dùng OCR để thăm dò mạng nội bộ qua dải CGNAT hoặc qua DNS rebinding.

## What's already secure

Lược đồ, hostname metadata, phân giải trước khi gọi, không theo redirect, có timeout 30s, endpoint được bảo vệ bằng secret.

## Recommendations

1. Chặn mọi IP không phải `is_global`.
2. (Tương lai) gắn kết nối vào IP đã kiểm tra nếu endpoint được mở cho luồng người dùng.

## Verification results

- [x] Mọi URL người dùng được kiểm tra trước khi tải
- [x] Chặn 127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1 (và thêm CGNAT, mapped IPv6)
- [x] Chỉ cho http/https
- [x] Phân giải hostname và kiểm tra IP trước khi gọi
- [ ] Chống DNS rebinding bằng ghim IP — chưa làm, ghi nhận rủi ro còn lại
