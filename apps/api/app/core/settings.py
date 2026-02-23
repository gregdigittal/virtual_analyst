from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/finmodel_dev",
        alias="DATABASE_URL",
    )
    pool_min_size: int = Field(default=2, ge=0, alias="DB_POOL_MIN_SIZE")
    pool_max_size: int = Field(default=20, ge=1, le=100, alias="DB_POOL_MAX_SIZE")
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    supabase_url: str = Field(default="http://localhost:54321", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    supabase_jwt_secret: str | None = Field(default=None, alias="SUPABASE_JWT_SECRET")
    """JWT secret for verifying Supabase access tokens (Project Settings → API → JWT Secret). When set, auth middleware overwrites X-Tenant-ID / X-User-ID from the Bearer token."""

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    cors_allowed_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )

    rate_limit: str = Field(default="100/minute", alias="RATE_LIMIT")
    cron_secret: str | None = Field(default=None, alias="CRON_SECRET")
    """Shared secret for cron endpoints (e.g. X-Cron-Secret). When set, POST /api/v1/assignments/cron/deadline-reminders requires this header."""

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    llm_tokens_monthly_limit: int = Field(default=1_000_000, ge=0, alias="LLM_TOKENS_MONTHLY_LIMIT")
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1, alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    circuit_breaker_recovery_seconds: int = Field(default=60, ge=1, alias="CIRCUIT_BREAKER_RECOVERY_SECONDS")

    agent_sdk_enabled: bool = Field(default=True, alias="AGENT_SDK_ENABLED")
    agent_sdk_default_model: str = Field(default="sonnet", alias="AGENT_SDK_DEFAULT_MODEL")
    agent_sdk_max_turns: int = Field(default=15, ge=1, le=50, alias="AGENT_SDK_MAX_TURNS")
    agent_sdk_max_budget_usd: float = Field(default=0.50, ge=0.01, le=10.0, alias="AGENT_SDK_MAX_BUDGET_USD")
    agent_excel_ingestion_enabled: bool = Field(default=True, alias="AGENT_EXCEL_INGESTION_ENABLED")
    agent_draft_chat_enabled: bool = Field(default=True, alias="AGENT_DRAFT_CHAT_ENABLED")
    agent_budget_nl_query_enabled: bool = Field(default=True, alias="AGENT_BUDGET_NL_QUERY_ENABLED")
    agent_reforecast_enabled: bool = Field(default=True, alias="AGENT_REFORECAST_ENABLED")

    xero_client_id: str | None = Field(default=None, alias="XERO_CLIENT_ID")
    xero_client_secret: str | None = Field(default=None, alias="XERO_CLIENT_SECRET")
    quickbooks_client_id: str | None = Field(default=None, alias="QUICKBOOKS_CLIENT_ID")
    quickbooks_client_secret: str | None = Field(default=None, alias="QUICKBOOKS_CLIENT_SECRET")
    integration_callback_base_url: str = Field(
        default="http://localhost:3000",
        alias="INTEGRATION_CALLBACK_BASE_URL",
    )
    """Frontend URL to redirect user after OAuth success (e.g. ?connection_id=)."""
    integration_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/integrations/connections/callback",
        alias="INTEGRATION_OAUTH_REDIRECT_URI",
    )
    """OAuth redirect_uri registered with provider; must point at this API callback."""
    oauth_state_secret: str = Field(
        default="change-me-in-production",
        alias="OAUTH_STATE_SECRET",
    )
    """Secret key for signing OAuth state tokens (HMAC-SHA256)."""
    oauth_encryption_key: str = Field(
        default="",
        alias="OAUTH_ENCRYPTION_KEY",
    )
    """Fernet key for encrypting OAuth tokens at rest. Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"""

    metrics_secret: str | None = Field(default=None, alias="METRICS_SECRET")

    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_id_professional: str | None = Field(default=None, alias="STRIPE_PRICE_ID_PROFESSIONAL")
    stripe_price_id_starter: str | None = Field(default=None, alias="STRIPE_PRICE_ID_STARTER")

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.environment not in ("development", "test"):
            if not self.supabase_jwt_secret:
                raise ValueError(
                    "SUPABASE_JWT_SECRET is required in production. "
                    "Set ENVIRONMENT=development to disable auth."
                )
            if self.oauth_state_secret == "change-me-in-production":
                raise ValueError(
                    "OAUTH_STATE_SECRET is still default — set a secure random value for production!"
                )
            if not self.oauth_encryption_key:
                raise ValueError(
                    "OAUTH_ENCRYPTION_KEY is required in production — generate with: "
                    "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )
            cors_origins = self.cors_allowed_origins_list()
            for origin in cors_origins:
                if not origin.startswith("https://"):
                    raise ValueError(
                        f"CORS origin must use HTTPS in production: {origin}"
                    )
        if self.pool_min_size > self.pool_max_size:
            raise ValueError(f"DB_POOL_MIN_SIZE ({self.pool_min_size}) > DB_POOL_MAX_SIZE ({self.pool_max_size})")
        return self

    def cors_allowed_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
