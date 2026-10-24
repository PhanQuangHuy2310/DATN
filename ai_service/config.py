"""
AI Service — Cấu hình chung (config.py)
Đọc biến môi trường từ .env và expose qua Settings singleton.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    internal_api_secret: str = "datn-internal-secret-change-in-prod"

    # --- OCR ---
    ocr_lang: str = "vi"
    ocr_use_gpu: bool = False

    # --- Auto-Approve ---
    auto_approve_max_risk: int = 2
    auto_approve_only_template_a: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
