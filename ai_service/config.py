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
    # --- Server ---
    ai_service_host: str = "0.0.0.0"
    ai_service_port: int = 8001
    ai_service_reload: bool = True

    # --- Gemini ---
    gemini_api_key: str = ""

    # --- Supabase ---
    supabase_url: str = ""
    supabase_anon_key: str = ""

    # --- Model paths ---
    risk_model_path: str = "models/risk_model.pkl"
    risk_label_encoder_path: str = "models/label_encoder.pkl"
    risk_feature_columns_path: str = "models/feature_columns.json"

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
    eas_mock_api_url: str = "http://mock_systems:8000/mock-api/v1"  # NOSONAR python:S5332 - internal docker service communication
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
