# API Gateway — EAS (Enterprise Approval System)

## Mục đích

API Gateway là **điểm vào duy nhất** (single entry point) cho toàn bộ hệ thống EAS. Sử dụng Nginx reverse proxy để phân phối traffic đến các backend service.

## Kiến trúc

```
                         ┌──────────────────────┐
    Internet ──────────▶ │  API Gateway (Nginx)  │ :8080
                         │  - TLS termination    │
                         │  - Rate limiting      │
                         │  - Correlation ID     │
                         └───┬─────────┬─────────┘
                             │         │
                    ┌────────▼──┐  ┌───▼──────────┐
                    │ api_core  │  │ ai_service    │
                    │ Django    │  │ FastAPI       │
                    │ :8000     │  │ :8001         │
                    └───────────┘  └───────────────┘
```

## Routing Rules

| Path Pattern | Backend | Mục đích | Rate Limit |
|---|---|---|---|
| `/gateway/health` | Local | Health check gateway | Không |
| `/health/*` | api_core:8000 | Health check Django | Không |
| `/api/v1/auth/login` | api_core:8000 | Đăng nhập | 5 req/phút/IP |
| `/api/v1/*/attachments` | api_core:8000 | Upload file | 10 req/phút/IP |
| `/api/v1/mock/*` | api_core:8000 | 8 hệ thống nguồn mock_* | 60 req/phút/IP |
| `/api/*` | api_core:8000 | Nghiệp vụ EAS (schema eas) | 60 req/phút/IP |
| `/ai/*` | ai_service:8001 | 5 model AI đã train | 20 req/phút/IP |
| `/docs`, `/redoc` | ai_service:8001 | Swagger UI (dev only) | Không |

## AI Models (Route qua Gateway)

Gateway KHÔNG chứa AI model. Tất cả được route đến `ai_service`:

| AI Endpoint | Mô hình | Mục đích |
|---|---|---|
| `POST /ai/classify/request` | TF-IDF + SGD | Phân loại yêu cầu tự động |
| `POST /ai/risk/score` | XGBoost Ensemble | Đánh giá rủi ro |
| `POST /ai/auto-approve/evaluate` | Rule-based | Auto-approve đơn giản |
| `POST /ai/ocr/extract-url` | PaddleOCR / Gemini Vision | Bóc tách hóa đơn |
| `POST /ai/summarize/request` | Gemini 1.5 Flash | Tóm tắt yêu cầu |

Chi tiết: xem [AI_ARCHITECTURE.md](../ai_service/AI_ARCHITECTURE.md)

## Bảo mật

- ✅ Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `CSP`
- ✅ Rate limiting per-endpoint
- ✅ Request size limit: 10MB (khớp với attachment schema)
- ✅ Không log cookie, Authorization header
- ✅ Correlation ID truyền xuyên suốt
- ✅ Server tokens ẩn (`server_tokens off`)
- ✅ Forwarded headers chỉ trust internal Docker network

## Chạy

```bash
# Docker Compose (cùng toàn bộ stack)
docker compose up gateway

# Standalone
docker build -t eas-gateway .
docker run -p 8080:8080 eas-gateway
```

## File

- `nginx.conf` — Cấu hình chính (version-controlled, không dùng dashboard)
- `Dockerfile` — Container image (nginx:1.27-alpine)
