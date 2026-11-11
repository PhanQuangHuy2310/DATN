# Dependencies Security Report

## Status: LOW (rủi ro chấp nhận)

Trạng thái trước khắc phục: **HIGH**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [DEPENDENCIES_PLAN.md](../plans/DEPENDENCIES_PLAN.md).

## Findings

`pip-audit` / `npm audit` (đầy đủ, định dạng JSON):

| Gói | Phiên bản | Lỗ hổng | Bản vá |
|---|---|---|---|
| starlette (qua fastapi 0.115.0) | 0.38.6 | nhiều PYSEC | 1.3.1 |
| python-multipart | 0.0.12 | 14 | 0.0.31 |
| Pillow | 10.4.0 | 66 | 13.0.0 |
| python-dotenv | 1.0.1 | 2 | 1.2.2 |
| paddlepaddle | 2.6.2 | 2 | 3.0.0 |
| protobuf (qua paddle) | 3.20.2 | 4 | 6.33.5 |
| imgaug (qua paddleocr) | 0.4.0 | 2 | không có |

- `api_core/requirements.txt`: không có lỗ hổng; mọi gói Python pin `==`.
- `web_client`: 7 moderate (minimatch) chỉ trong toolchain eslint (dev); `npm audit --omit=dev` = 0. Hai devDependency dùng `^` (`@axe-core/playwright`, `@playwright/test`).
- `web_admin`, `database/EAS_Supabase_SQL/validation`: 0. Lock file được commit đủ.
- Image nền `nginx:alpine` không pin trong `web_client/Dockerfile`, `web_admin/Dockerfile`.
- Mọi gói đều là gói phổ biến, có lịch sử dài trên PyPI/npm; không phát hiện typosquat.

## What's at risk

Lỗ hổng của starlette/python-multipart/Pillow nằm trên đường xử lý request và ảnh của ai_service (DoS khi parse multipart, lỗi giải mã ảnh).

## What's already secure

Pin chính xác ở Python; lock file npm/pubspec được commit; gateway pin digest image.

## Recommendations

1. Nâng các gói có bản vá.
2. Pin devDependency và image.
3. Chấp nhận rủi ro có thời hạn cho nhóm paddle (cần nâng PaddleOCR 3.x — đổi API).

## Verification results

- [x] Mọi gói có trên registry chính thức, lịch sử hợp lệ
- [x] Không có gói đáng ngờ
- [x] Pin chính xác (không `^`/`~` ở dependency production; devDeps cũng đã pin)
- [x] Lock file được commit
- [x] `pip-audit` api_core: 0; `requirements-local.txt` ai_service: 0; `npm audit --omit=dev`: 0
- [ ] `requirements.txt` ai_service (image OCR): còn paddlepaddle/protobuf/imgaug — rủi ro chấp nhận
