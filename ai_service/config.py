"""
AI Service — Cấu hình chung (config.py)
Đọc biến môi trường từ .env và expose qua Settings singleton.
"""

from functools import lru_cache
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except (ImportError, ModuleNotFoundError):
    try:
        from pydantic import BaseModel as BaseSettings  # type: ignore[assignment]

        SettingsConfigDict = dict  # type: ignore[assignment]
    except (ImportError, ModuleNotFoundError):
        BaseSettings = object  # type: ignore[assignment, misc]
        SettingsConfigDict = dict  # type: ignore[assignment]

try:
    from project_env import load_project_env
except (
    ModuleNotFoundError
):  # Separate AI Docker image receives settings as environment variables.
    load_project_env = None

if load_project_env is not None:
    load_project_env()

_AI_SERVICE_DIR = Path(__file__).resolve().parent
_AI_ENV_PATH = _AI_SERVICE_DIR.parent / ".env"


class Settings(BaseSettings):
    # Host/port come from the uvicorn command line (Dockerfile, start_ai_local.cmd).

    # --- Gemini (hỗ trợ 1 hoặc nhiều key để tự động xoay vòng / failover) ---
    gemini_api_key: str = ""
    gemini_api_keys: str = ""
    # Google retires old versions (gemini-1.5-flash now 404s). Flash-Lite
    # answers in ~2 s; full Flash / flash-latest take > 25 s and would always
    # hit the API's 10 s AI timeout. Override with GEMINI_MODEL.
    gemini_model: str = "gemini-3.5-flash-lite"

    # Model files are fixed names under models/ written by training/train.py.

    # --- Security ---
    internal_api_secret: str = ""
    cors_allowed_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    # --- OCR ---
    ocr_lang: str = "vi"
    ocr_use_gpu: bool = False
    # Load the OCR models in the background at startup so the first user
    # request does not pay the ~20 s model initialisation.
    ocr_warmup: bool = True

    # --- Policy rules source of truth (api_core, eas.ai_policy_version) ---
    eas_api_internal_url: str = "http://api:8000"  # NOSONAR python:S5332 - internal docker service communication
    # Simulated external systems (docs/TICH_HOP_HE_THONG_NGOAI.md): the AI reads
    # them through their API, never from snapshots or the database.
    eas_mock_api_url: str = "http://mock-systems:8000/mock-api/v1"  # NOSONAR python:S5332 - internal docker service communication
    eas_mock_api_secret: str = ""

    # --- Auto-Approve ---
    auto_approve_max_risk: int = 2
    auto_approve_only_template_a: bool = True

    model_config = SettingsConfigDict(
        env_file=_AI_ENV_PATH,
        env_file_encoding="utf-8-sig",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, context: object, /) -> None:
        import os

        try:
            from gemini_key_pool import resolve_keys
        except ImportError:
            from ai_service.gemini_key_pool import resolve_keys

        explicit_empty = (
            "GEMINI_API_KEY" in os.environ
            and not os.environ.get("GEMINI_API_KEY", "").strip()
            and not os.environ.get("GEMINI_API_KEYS", "").strip()
        )
        if not explicit_empty:
            merged_keys = resolve_keys([self.gemini_api_key, self.gemini_api_keys])
            if merged_keys:
                self.gemini_api_key = ",".join(merged_keys)

        env = (
            os.getenv("EAS_ENV", os.getenv("ENVIRONMENT", "development"))
            .lower()
            .strip()
        )
        if env != "production" and not self.internal_api_secret:
            self.internal_api_secret = "eas-local-dev-shared-internal-secret-2026"

        if env == "production" and (
            self.internal_api_secret
            in {
                "",
                "datn-internal-secret-change-in-prod",
                "eas-local-dev-shared-internal-secret-2026",
            }
            or len(self.internal_api_secret) < 32
        ):
            raise ValueError(
                "INTERNAL_API_SECRET must be a random secret of at least 32 characters in production"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
