# =============================================================================
# API Gateway — Dockerfile (Nginx reverse proxy cho EAS)
# Route: /api/* → api_core | /ai/* → ai_service | /api/v1/mock/* → 8 mock schema
# =============================================================================
# Dùng cùng base image (đã pin digest) với web_client để giảm bề mặt tấn công
# và tái sử dụng layer cache.
FROM nginx:1.31.6-alpine@sha256:df221db836e1754089190208cee7eeda94f233197056426eda74a43ab1abeac2

RUN apk upgrade --no-cache \
    && apk del --no-network nginx-module-image-filter libgd fontconfig libexpat \
    && rm -f /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf

# Chạy non-root. docker-compose mount tmpfs cho /var/cache/nginx và /var/run
# (uid 101 = nginx) vì container chạy read_only + cap_drop ALL.
USER nginx
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/gateway/health || exit 1
