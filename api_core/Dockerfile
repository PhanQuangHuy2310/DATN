FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

RUN addgroup --system eas && adduser --system --ingroup eas eas
WORKDIR /app

COPY api_core/requirements.txt /tmp/requirements.txt
RUN python -m pip install --disable-pip-version-check --requirement /tmp/requirements.txt

COPY manage.py project_env.py /app/
COPY api_core /app/api_core

USER eas
EXPOSE 8000
# A page load or post-save sync fires ~8 reads at once, each waiting on several
# ~240 ms round trips to the Sydney pooler: 8 threads per worker keep them from
# queueing. --timeout stays above the DB statement timeout (30 s on the pooler)
# so a slow query ends as a clean 503, not a killed worker and an nginx 502.
# Warm the Redis read cache in the background, then hand PID 1 to gunicorn.
CMD ["sh", "-c", "(python manage.py warm_read_cache || true) & exec gunicorn api_core.config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 8 --timeout 45 --access-logfile - --error-logfile -"]
