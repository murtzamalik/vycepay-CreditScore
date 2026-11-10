"""Environment-based application configuration using Pydantic Settings v2."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ---- Application ----
    app_name: str = "VyceScore"
    app_env: str = "development"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # ---- Database ----
    database_url: str = "postgresql+asyncpg://vycescore:changeme@localhost:5432/vycescore"
    database_echo: bool = False

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"
    redis_score_ttl_seconds: int = 86400  # 24 hours

    # ---- Kafka ----
    kafka_bootstrap_servers: str = "localhost:9092"

    # ---- Security ----
    secret_key: str = "CHANGE-ME-TO-A-RANDOM-64-CHAR-HEX-STRING"
    jwt_algorithm: str = "HS256"
    jwt_secret_key: str = "CHANGE-ME-TO-A-RANDOM-64-CHAR-HEX-STRING"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    api_key_header: str = "X-API-Key"

    # ---- CORS ----
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # ---- Scoring ----
    score_min: int = 300
    score_max: int = 900
    niq_score_min: int = 0
    niq_score_max: int = 100
    default_model_version: str = "v1.0.0"

    # ---- Compliance Partners (Phase 15) ----
    smile_id_api_key: str = ""
    smile_id_partner_id: str = ""
    smile_id_base_url: str = "https://api.smileidentity.com/v1"
    smile_id_timeout_seconds: int = 30
    smile_id_max_retries: int = 3

    comply_advantage_api_key: str = ""
    comply_advantage_base_url: str = "https://api.complyadvantage.com"
    comply_advantage_timeout_seconds: int = 30
    comply_advantage_max_retries: int = 3

    # Compliance check settings
    kyc_refresh_interval_days: int = 30
    kyc_refresh_batch_size: int = 100
    kyc_refresh_rate_limit_per_minute: int = 30
    compliance_check_encryption_key: str = ""

    # ---- Encryption (Phase 12.1) ----
    encryption_master_key: str = ""  # 64-char hex string for AES-256-GCM

    # ---- TLS (Phase 12.2) ----
    tls_cert_file: str = ""
    tls_key_file: str = ""
    tls_ca_file: str = ""
    tls_min_version: str = "TLSv1.3"

    # ---- MFA (Phase 12.7) ----
    mfa_issuer: str = "VyceScore"

    # ---- Rate Limiting ----
    rate_limit_lite: int = 120
    rate_limit_pro: int = 60
    rate_limit_batch: int = 10
    rate_limit_lite_per_hour: int = 1000
    rate_limit_pro_per_hour: int = 500
    rate_limit_deep_dive_per_hour: int = 200


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
