from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from project_env import load_project_env

from .database import DatabaseUrlError, parse_database_url, resolve_redis_url

load_project_env()

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
    "api_core.middleware.ApiSecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api_core.middleware.ApiRateLimitMiddleware",
    "api_core.middleware.ApiDatabaseErrorMiddleware",
]

# One codebase, two services. EAS_SERVICE=mock runs the simulated external
# systems (HRM, assets, facilities, ITSM, ERP...) as a separate HTTP service with
# its own database role; EAS itself only reaches them through that API.
EAS_SERVICE = os.getenv("EAS_SERVICE", "api").strip().lower()
ROOT_URLCONF = (
    "api_core.mock_sources.service_urls"
    if EAS_SERVICE == "mock"
    else "api_core.config.urls"
)
WSGI_APPLICATION = "api_core.config.wsgi.application"
ASGI_APPLICATION = "api_core.config.asgi.application"

if ENVIRONMENT == "test":
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    }
else:
    try:
        DATABASES = {
            "default": parse_database_url(
                os.getenv("EAS_MOCK_DATABASE_URL") or os.getenv("DATABASE_URL", "")
                if EAS_SERVICE == "mock"
                else os.getenv("DATABASE_URL", "")
            )
        }
    except DatabaseUrlError as exc:
        raise RuntimeError(str(exc)) from None

    # Reuse connections for 60s by default: opening a TLS session through the
    # Supabase pooler costs seconds, so per-request connects dominate latency.
    # CONN_HEALTH_CHECKS discards a stale reused connection before first use.
    # Set 0 only when diagnosing stale pooler connections locally.
    try:
        _db_max_age = int(os.getenv("EAS_DB_CONN_MAX_AGE", "60"))
        if not 0 <= _db_max_age <= 3600:
            raise ValueError
    except ValueError:
        raise RuntimeError("EAS_DB_CONN_MAX_AGE must be 0..3600") from None
    DATABASES["default"]["CONN_MAX_AGE"] = _db_max_age
    # A new TLS connection to the Supabase pooler costs ~2s from Vietnam; a
    # process-wide pool reuses connections across requests and runserver
    # threads. Django forbids pooling together with CONN_MAX_AGE > 0.
    if _db_max_age == 0:
        # Validate a pooled connection on first use per request.  This costs a
        # round trip but prevents stale connections after a long idle period.
        DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
        DATABASES["default"]["OPTIONS"].update(
            pool={
                "min_size": int(os.getenv("EAS_DB_POOL_MIN_SIZE", "2")),
                "max_size": int(os.getenv("EAS_DB_POOL_MAX_SIZE", "10")),
                "max_idle": 90,
                "timeout": 15,
            },
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )

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
REDIS_URL = resolve_redis_url(os.environ)
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
EAS_LOGIN_EMAIL_DOMAIN = os.getenv("EAS_LOGIN_EMAIL_DOMAIN", "eas.com").strip().lower()

try:
    validate_email(f"eas-user@{EAS_LOGIN_EMAIL_DOMAIN}")
except ValidationError:
    raise RuntimeError("EAS_LOGIN_EMAIL_DOMAIN must be a valid email domain") from None
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EAS_EMAIL_HOST", "").strip()
EMAIL_PORT = int(os.getenv("EAS_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EAS_EMAIL_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EAS_EMAIL_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EAS_EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EAS_EMAIL_USE_SSL", "false").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("EAS_EMAIL_FROM", "").strip()
EMAIL_TIMEOUT = int(os.getenv("EAS_EMAIL_TIMEOUT_SECONDS", "10"))
EAS_EMAIL_TEST_RECIPIENT = os.getenv("EAS_EMAIL_TEST_RECIPIENT", "").strip()
if EAS_EMAIL_TEST_RECIPIENT:
    if ENVIRONMENT not in {"development", "test"}:
        raise RuntimeError(
            "EAS_EMAIL_TEST_RECIPIENT is only allowed in development/test"
        )
    try:
        validate_email(EAS_EMAIL_TEST_RECIPIENT)
    except ValidationError:
        raise RuntimeError(
            "EAS_EMAIL_TEST_RECIPIENT must be a valid email address"
        ) from None
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise RuntimeError("Configure only one of EAS_EMAIL_USE_TLS or EAS_EMAIL_USE_SSL")

EAS_API_RATE_LIMIT_PER_MINUTE = int(
    os.getenv(
        "EAS_API_RATE_LIMIT_PER_MINUTE",
        "1200" if ENVIRONMENT != "production" else "300",
    )
)
if EAS_API_RATE_LIMIT_PER_MINUTE < 1:
    raise RuntimeError("EAS_API_RATE_LIMIT_PER_MINUTE must be >= 1")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
EAS_STORAGE_BUCKET = os.getenv("EAS_STORAGE_BUCKET", "eas-private")
EAS_CLAMAV_HOST = os.getenv("EAS_CLAMAV_HOST", "clamav")
EAS_CLAMAV_PORT = int(os.getenv("EAS_CLAMAV_PORT", "3310"))
EAS_REQUIRE_STORAGE = os.getenv("EAS_REQUIRE_STORAGE", "true").lower() == "true"
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_FAILURE_VIEW = "api_core.http.csrf_failure"
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
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:8088",
        "http://127.0.0.1:8088",
    ]
    for origin in local_origins:
        if origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)
if (
    ENVIRONMENT != "test"
    and os.getenv("EAS_TRUST_PROXY_HEADERS", "false").lower() == "true"
):
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
EAS_AI_SERVICE_URL = os.getenv(
    "EAS_AI_SERVICE_URL",
    "http://127.0.0.1:8001"
    if ENVIRONMENT == "development"
    else "http://ai-service:8001",
).rstrip("/")
EAS_AI_INTERNAL_SECRET = os.getenv(
    "EAS_AI_INTERNAL_SECRET",
    os.getenv("INTERNAL_API_SECRET", ""),
)
if not EAS_AI_INTERNAL_SECRET and ENVIRONMENT in {"development", "test"}:
    EAS_AI_INTERNAL_SECRET = "eas-local-dev-shared-internal-secret-2026"
_KNOWN_WEAK_AI_SECRETS = {
    "",
    "datn-internal-secret-change-in-prod",
    "eas-local-dev-shared-internal-secret-2026",
}
if ENVIRONMENT == "production" and (
    EAS_AI_INTERNAL_SECRET in _KNOWN_WEAK_AI_SECRETS
    or "replace-with" in EAS_AI_INTERNAL_SECRET
    or len(EAS_AI_INTERNAL_SECRET) < 32
):
    raise RuntimeError(
        "EAS_AI_INTERNAL_SECRET must be a random secret of at least 32 characters in production"
    )
EAS_AI_TIMEOUT_SECONDS = float(os.getenv("EAS_AI_TIMEOUT_SECONDS", "5.0"))
# Non-login account that records AI auto-approval decisions (migration 08).
EAS_AI_SYSTEM_USER_ID = os.getenv(
    "EAS_AI_SYSTEM_USER_ID", "00000002-0000-4000-8000-0000000000a1"
)
# Human approval is mandatory by default. Two separate operator-controlled
# opt-ins are needed before any AI decision may finalize a business request.
EAS_AI_AUTO_APPROVE_ENABLED = (
    os.getenv("EAS_AI_AUTO_APPROVE_ENABLED", "false").lower() == "true"
)
EAS_AI_AUTO_APPROVAL_POLICY_APPROVED = (
    os.getenv("EAS_AI_AUTO_APPROVAL_POLICY_APPROVED", "false").lower() == "true"
)
EAS_AI_AUTO_APPROVE_MAX_WEIGHT = int(os.getenv("EAS_AI_AUTO_APPROVE_MAX_WEIGHT", "2"))
# The least-privilege worker cannot write approvals; it asks the API to run
# AI auto-approval through this internal, secret-protected endpoint.
EAS_API_INTERNAL_URL = os.getenv(
    "EAS_API_INTERNAL_URL",
    "http://127.0.0.1:8000" if ENVIRONMENT == "development" else "http://api:8000",
).rstrip("/")
EAS_WORKER_INTERNAL_SECRET = os.getenv("EAS_WORKER_INTERNAL_SECRET", "")
if not EAS_WORKER_INTERNAL_SECRET and ENVIRONMENT in {"development", "test"}:
    EAS_WORKER_INTERNAL_SECRET = "eas-local-dev-worker-internal-secret-2026"
if ENVIRONMENT == "production" and (
    len(EAS_WORKER_INTERNAL_SECRET) < 32
    or EAS_WORKER_INTERNAL_SECRET == "eas-local-dev-worker-internal-secret-2026"
):
    raise RuntimeError(
        "EAS_WORKER_INTERNAL_SECRET must be a random secret of at least 32 characters in production"
    )

# Simulated external systems (docs/TICH_HOP_HE_THONG_NGOAI.md).
EAS_MOCK_API_URL = os.getenv(
    "EAS_MOCK_API_URL",
    "http://127.0.0.1:8100/mock-api/v1"
    if ENVIRONMENT in {"development", "test"}
    else "http://mock_systems:8000/mock-api/v1",  # NOSONAR python:S5332 - internal docker service communication
).rstrip("/")
EAS_MOCK_API_SECRET = os.getenv("EAS_MOCK_API_SECRET", "")
if not EAS_MOCK_API_SECRET and ENVIRONMENT in {"development", "test"}:
    EAS_MOCK_API_SECRET = "eas-local-dev-mock-integration-secret-2026"
if ENVIRONMENT == "production" and (
    len(EAS_MOCK_API_SECRET) < 32
    or EAS_MOCK_API_SECRET == "eas-local-dev-mock-integration-secret-2026"
):
    raise RuntimeError(
        "EAS_MOCK_API_SECRET must be a random secret of at least 32 characters in production"
    )
EAS_MOCK_API_TIMEOUT_SECONDS = float(os.getenv("EAS_MOCK_API_TIMEOUT_SECONDS", "5"))

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
