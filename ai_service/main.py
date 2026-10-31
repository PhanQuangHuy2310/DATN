"""
AI Service — FastAPI Application Entry Point (main.py)

Khởi động: uvicorn main:app --reload --host 0.0.0.0 --port 8001
"""

import hmac
import time

try:
    from config import get_settings
except (ImportError, AttributeError):
    from ai_service.config import get_settings

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from routers import auto_approve, classify, mock_context, ocr, risk, summarize

settings = get_settings()

# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Enterprise Approval System — AI Service",
    description=(
        "FastAPI service cung cấp 5 chức năng AI thông minh và dữ liệu ngữ cảnh mock:\n"
        "1. **Smart Request Classifier** — Phân loại tự động loại yêu cầu, phòng ban, template từ văn bản tiếng Việt\n"
        "2. **Risk & Fraud Scoring** — Đánh giá rủi ro và phát hiện bất thường bằng XGBoost (50.000 mẫu)\n"
        "3. **Auto-Approve** — Quyết định tự động duyệt cho Template A + risk thấp\n"
        "4. **OCR** — Bóc tách thông tin từ hóa đơn VAT / chứng từ\n"
        "5. **Summarize** — Tóm tắt yêu cầu dài và phân tích tâm thế bằng Gemini LLM\n"
        "6. **Mock Context** — Tra cứu dữ liệu từ 8 snapshot mock phục vụ quyết định AI"
    ),
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
allowed_origins = [
    origin.strip()
    for origin in settings.cors_allowed_origins.split(",")
    if origin.strip()
] or ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    corr_id = (
        request.headers.get("X-Correlation-ID")
        or request.headers.get("x-correlation-id")
        or ""
    )
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    if corr_id:
        response.headers["X-Correlation-ID"] = corr_id
    cid_str = f" [cid={corr_id}]" if corr_id else ""
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration}ms){cid_str}"
    )
    return response


@app.middleware("http")
async def verify_internal_secret(request: Request, call_next):
    public_paths = {"/docs", "/redoc", "/openapi.json", "/health", "/metrics", "/"}
    if request.url.path in public_paths:
        return await call_next(request)

    if not settings.internal_api_secret:
        return JSONResponse(
            status_code=503,
            content={"detail": "AI internal authentication is not configured"},
        )
    secret = request.headers.get("X-Internal-Secret") or ""
    if not hmac.compare_digest(secret, settings.internal_api_secret):
        return JSONResponse(
            status_code=401, content={"detail": "Unauthorized: invalid internal secret"}
        )

    return await call_next(request)


try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(
    classify.router, prefix="/ai/classify", tags=["Smart Classification"]
)
app.include_router(risk.router, prefix="/ai/risk", tags=["Risk & Fraud Scoring"])
app.include_router(
    auto_approve.router, prefix="/ai/auto-approve", tags=["Auto Approve"]
)
app.include_router(ocr.router, prefix="/ai/ocr", tags=["OCR"])
app.include_router(summarize.router, prefix="/ai/summarize", tags=["Summarize"])
app.include_router(mock_context.router, prefix="/ai/mock", tags=["Mock Data Context"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "ai-service", "version": app.version}


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "Enterprise AI Service đang hoạt động. Truy cập /docs để xem chi tiết API."
    }
