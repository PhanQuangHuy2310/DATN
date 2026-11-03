# Dependencies Fix Plan

Báo cáo: [DEPENDENCIES_REPORT.md](../reports/DEPENDENCIES_REPORT.md). Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md).

## Changes

- `ai_service/requirements.txt`, `ai_service/requirements-local.txt` — `fastapi==0.162.0`, `starlette==1.10.0` (pin mới), `prometheus-fastapi-instrumentator==8.1.0` (7.0.0 yêu cầu starlette<1), `python-multipart==0.0.33`, `Pillow==13.0.0`, `python-dotenv==1.2.4`.
- `web_client/package.json` + `package-lock.json` — `@axe-core/playwright` `4.13.0`, `@playwright/test` `1.64.0`.
- `web_client/Dockerfile`, `web_admin/Dockerfile` — `nginx:1.31.6-alpine@sha256:df221db8…` (giống gateway).

## New files

- Không có file mới.

## Verification goals

- [x] Mọi gói có trên registry chính thức, lịch sử hợp lệ
- [x] Không có gói đáng ngờ
- [x] Pin chính xác (không `^`/`~` ở dependency production; devDeps cũng đã pin)
- [x] Lock file được commit
- [x] `pip-audit` api_core: 0; `requirements-local.txt` ai_service: 0; `npm audit --omit=dev`: 0
- [ ] `requirements.txt` ai_service (image OCR): còn paddlepaddle/protobuf/imgaug — rủi ro chấp nhận

## Manual verification (for the human)

- Lên kế hoạch nâng PaddleOCR 3.x (`PaddleOCR(use_gpu=...)` đổi tham số) để loại `paddlepaddle 2.6.2`, `protobuf 3.20.2`, `imgaug`.
- Build lại image ai_service và chạy smoke OCR thật (Pillow 13 + paddle) trước khi triển khai.
