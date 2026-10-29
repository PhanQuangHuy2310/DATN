from __future__ import annotations

import os
from pathlib import Path

from .database import DatabaseUrlError, parse_database_url

BASE_DIR = Path(__file__).resolve().parents[2]
ENVIRONMENT = os.getenv("EAS_ENV", "production").strip().lower()
DEBUG = (
    ENVIRONMENT == "development"
    and os.getenv("DJANGO_DEBUG", "false").lower() == "true"
)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if ENVIRONMENT in {"development", "test"}:
        # NOSONAR secrets:S6687 - ephemeral secret generated for local dev/testing only
        import hashlib

        SECRET_KEY = hashlib.sha256(b"eas-local-ephemeral-dev-test").hexdigest()
    else:
        raise RuntimeError("DJANGO_SECRET_KEY is required outside development/test")

ALLOWED_HOSTS = [
    item.strip()
    for item in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if item.strip()
]

INSTALLED_APPS = [
    "api_core",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "api_core.health",
    "api_core.catalog",
    "api_core.authn",
    "api_core.workflow",
    "api_core.mock_sources",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api_core.middleware.ApiDatabaseErrorMiddleware",
]

ROOT_URLCONF = "api_core.config.urls"
WSGI_APPLICATION = "api_core.config.wsgi.application"
ASGI_APPLICATION = "api_core.config.asgi.application"

if ENVIRONMENT == "test":
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    }
else:
    try:
        DATABASES = {"default": parse_database_url(os.getenv("DATABASE_URL", ""))}
    except DatabaseUrlError as exc:
        raise RuntimeError(str(exc)) from None

    # Optional: set to 0 when diagnosing stale long-lived Supabase/PgBouncer
    # connections in local development. Default remains 60 to avoid changing
    # the production connection policy unexpectedly.
    try:
        _db_max_age = int(os.getenv("EAS_DB_CONN_MAX_AGE", "60"))
        if not 0 <= _db_max_age <= 3600:
            raise ValueError
    except ValueError:
        raise RuntimeError("EAS_DB_CONN_MAX_AGE must be 0..3600") from None
    DATABASES["default"]["CONN_MAX_AGE"] = _db_max_age

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME = "eas_session"
SESSION_COOKIE_AGE = int(os.getenv("EAS_SESSION_AGE_SECONDS", "28800"))
EAS_SESSION_IDLE_SECONDS = int(os.getenv("EAS_SESSION_IDLE_SECONDS", "1800"))
if not 0 < EAS_SESSION_IDLE_SECONDS <= SESSION_COOKIE_AGE:
    raise RuntimeError("Session idle must be within absolute session lifetime")
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if ENVIRONMENT == "production" and not REDIS_URL:
    raise RuntimeError("REDIS_URL is required in production for shared security state")
if REDIS_URL and ENVIRONMENT != "test":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "eas-security-controls",
        }
    }
EAS_LOGIN_MAX_ATTEMPTS = int(os.getenv("EAS_LOGIN_MAX_ATTEMPTS", "5"))
EAS_LOGIN_MAX_IP_ATTEMPTS = int(os.getenv("EAS_LOGIN_MAX_IP_ATTEMPTS", "30"))
EAS_LOGIN_WINDOW_SECONDS = int(os.getenv("EAS_LOGIN_WINDOW_SECONDS", "900"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
EAS_STORAGE_BUCKET = os.getenv("EAS_STORAGE_BUCKET", "eas-private")
EAS_CLAMAV_HOST = os.getenv("EAS_CLAMAV_HOST", "clamav")
EAS_CLAMAV_PORT = int(os.getenv("EAS_CLAMAV_PORT", "3310"))
EAS_REQUIRE_STORAGE = os.getenv("EAS_REQUIRE_STORAGE", "true").lower() == "true"
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_COOKIE_SECURE = ENVIRONMENT == "production"
SECURE_SSL_REDIRECT = (
    ENVIRONMENT == "production"
    and os.getenv("EAS_SSL_REDIRECT", "true").lower() == "true"
)
SECURE_HSTS_SECONDS = 31536000 if ENVIRONMENT == "production" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = ENVIRONMENT == "production"
SECURE_HSTS_PRELOAD = (
    ENVIRONMENT == "production"
    and os.getenv("EAS_HSTS_PRELOAD", "false").lower() == "true"
)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
CSRF_TRUSTED_ORIGINS = [
    item.strip()
    for item in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if item.strip()
]
if ENVIRONMENT in {"development", "test"}:
    local_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8088",
        "http://127.0.0.1:8088",
    ]
    for origin in local_origins:
        if origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)
if os.getenv("EAS_TRUST_PROXY_HEADERS", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

EAS_RELEASE = os.getenv("EAS_RELEASE", "dev")
EAS_REQUIRE_ACTIVE_RELEASES = (
    os.getenv("EAS_REQUIRE_ACTIVE_RELEASES", "true").lower() == "true"
)
# New request types may be active but not yet published during migration.
# P0 releases are still mandatory when EAS_REQUIRE_ACTIVE_RELEASES=true.
# Opt into full-catalog gating only when *every* active type must be configured.
EAS_REQUIRE_FULL_CATALOG_READY = (
    os.getenv("EAS_REQUIRE_FULL_CATALOG_READY", "false").lower() == "true"
)
EAS_REQUIRE_MOCK_SOURCES = (
    os.getenv("EAS_REQUIRE_MOCK_SOURCES", "true").lower() == "true"
)
EAS_ALLOW_ADMIN_DB = os.getenv("EAS_ALLOW_ADMIN_DB", "false").lower() == "true"
if ENVIRONMENT == "production" and EAS_ALLOW_ADMIN_DB:
    raise RuntimeError("EAS_ALLOW_ADMIN_DB cannot be enabled in production")

# ── AI Service Integration ──
EAS_AI_SERVICE_URL = os.getenv("EAS_AI_SERVICE_URL", "http://ai-service:8001").rstrip(
    "/"
)
EAS_AI_INTERNAL_SECRET = os.getenv(
    "EAS_AI_INTERNAL_SECRET",
    os.getenv("INTERNAL_API_SECRET", ""),
)
if not EAS_AI_INTERNAL_SECRET and ENVIRONMENT in {"development", "test"}:
    EAS_AI_INTERNAL_SECRET = "eas-local-dev-shared-internal-secret-2026"
if (
    ENVIRONMENT == "production"
    and EAS_AI_INTERNAL_SECRET == "datn-internal-secret-change-in-prod"
):
    raise RuntimeError(
        "EAS_AI_INTERNAL_SECRET must be explicitly configured and cannot use default value in production"
    )
EAS_AI_TIMEOUT_SECONDS = float(os.getenv("EAS_AI_TIMEOUT_SECONDS", "5.0"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact": {"()": "api_core.logger.SensitiveDataFilter"}},
    "formatters": {"json": {"()": "api_core.logger.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact"],
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}

# Opt-in only after DBA review of the report-catalog migration.
EAS_ALLOW_REPORT_CATALOG_EXPANSION = (
    os.getenv("EAS_ALLOW_REPORT_CATALOG_EXPANSION", "false").lower() == "true"
)
