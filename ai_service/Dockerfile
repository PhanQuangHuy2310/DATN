# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Stage 1 — builder: virtualenv with all wheels + pre-downloaded OCR models.
# PaddlePaddle (largest dependency) is its own layer so changing other
# requirements does not reinstall it; pip downloads stay in a BuildKit cache
# mount and never land in an image layer.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 libgl1 \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv

WORKDIR /build
COPY requirements-paddle.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-paddle.txt

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Pre-download the Vietnamese OCR models into the image (no network at runtime).
# Without network the build still succeeds; models then download on first use.
RUN (python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=False)" \
     || echo "OCR model pre-download skipped") \
    && mkdir -p /root/.paddleocr \
    && find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} +

# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim base, runtime libs only, non-root user.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HOME=/home/aiuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 libgl1 libsm6 libxrender1 libxext6 curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system aiuser \
    && adduser --system --ingroup aiuser --home /home/aiuser aiuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=aiuser:aiuser /root/.paddleocr /home/aiuser/.paddleocr
COPY --chown=aiuser:aiuser . .
RUN mkdir -p models training/data data && chown -R aiuser:aiuser models training data

USER aiuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
