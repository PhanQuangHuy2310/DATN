FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

RUN addgroup --system eas && adduser --system --ingroup eas eas
WORKDIR /app

COPY api_core/requirements.txt /tmp/requirements.txt
RUN python -m pip install --disable-pip-version-check --requirement /tmp/requirements.txt

COPY manage.py /app/manage.py
COPY api_core /app/api_core

USER eas
EXPOSE 8000
CMD ["gunicorn", "api_core.config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
