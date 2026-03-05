from __future__ import annotations

import re
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _clean_env_url(value: str) -> str:
    """Strip accidental shell-style assignment wrapping from env var values.

    Hosting dashboards sometimes produce values like:
        REDIS_URL="rediss://user:pass@host:6379"
    instead of the bare URL. This helper strips the prefix and quotes.
    """
    # Strip pattern like  VAR_NAME="..." or VAR_NAME='...'
    cleaned = re.sub(r"^[A-Z_]+=(?:\"|')(.+?)(?:\"|')$", r"\1", value.strip())
    # Also handle VAR_NAME=value (no quotes)
    cleaned = re.sub(r"^[A-Z_]+=", "", cleaned)
    return cleaned


# Map Supabase project ref → pooler host (used by _migrate_db_url).
# Get the exact host from Dashboard → Settings → Database → Connection String.
_SUPABASE_POOLER_HOSTS: dict[str, str] = {
    "hfbjypuoojstjquoyqid": "aws-1-eu-west-1.pooler.supabase.com",
}


def _migrate_db_url(url: str) -> str:
    """Rewrite deprecated Supabase direct-connection URLs to Supavisor pooler.

    Supabase deprecated direct ``db.<ref>.supabase.co:5432`` connections.
    The replacement is ``postgres.<ref>@<pooler_host>:6543``.

    Only rewrites URLs that match the deprecated pattern AND whose project ref
    is in ``_SUPABASE_POOLER_HOSTS``.  Unknown projects are left unchanged so
    the operator notices the failure and can fix it manually.
    """
    m = re.match(
        r"^(?P<scheme>postgres(?:ql)?://)(?P<user>[^:]+):(?P<pass>[^@]+)@db\.(?P<ref>[a-z]+)\.supabase\.co:5432/(?P<db>.+)$",
        url,
    )
    if not m:
        return url
    ref = m.group("ref")
    pooler_host = _SUPABASE_POOLER_HOSTS.get(ref)
    if not pooler_host:
        return url  # unknown project — don't guess
    return (
        f"{m.group('scheme')}{m.group('user')}.{ref}:{m.group('pass')}"
        f"@{pooler_host}:6543/{m.group('db')}"
    )


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
    cors_allow_origin_regex: str = Field(
        default="",
        alias="CORS_ALLOW_ORIGIN_REGEX",
    )
    """Regex pattern for additional allowed CORS origins (e.g. Vercel preview deployments).
    In production, automatically includes Vercel preview URL pattern if not explicitly set."""

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

    sendgrid_api_key: str | None = Field(default=None, alias="SENDGRID_API_KEY")
    email_from_address: str = Field(
        default="noreply@virtualanalyst.io",
        alias="EMAIL_FROM_ADDRESS",
    )
    email_from_name: str = Field(
        default="Virtual Analyst",
        alias="EMAIL_FROM_NAME",
    )

    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")

    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_id_professional: str | None = Field(default=None, alias="STRIPE_PRICE_ID_PROFESSIONAL")
    stripe_price_id_starter: str | None = Field(default=None, alias="STRIPE_PRICE_ID_STARTER")

    @model_validator(mode="after")
    def _clean_urls(self) -> "Settings":
        """Strip shell-style wrapping and migrate deprecated Supabase URLs."""
        self.redis_url = _clean_env_url(self.redis_url)
        self.database_url = _migrate_db_url(_clean_env_url(self.database_url))
        return self

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
        origins = [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]
        # Always include production domains so CORS works regardless of env var config
        for prod_origin in (
            "https://www.virtual-analyst.ai",
            "https://virtual-analyst.ai",
            "https://virtual-analyst-ten.vercel.app",
        ):
            if prod_origin not in origins:
                origins.append(prod_origin)
        return origins

    def cors_origin_regex(self) -> str | None:
        """Return regex for dynamically-matched CORS origins (e.g. Vercel previews).

        In production, if no explicit regex is configured, defaults to matching
        Vercel preview deployment URLs for the virtual-analyst project.
        """
        if self.cors_allow_origin_regex:
            return self.cors_allow_origin_regex
        # In production / staging, allow Vercel preview deployments automatically
        if self.environment not in ("development", "test"):
            return r"https://virtual-analyst[a-z0-9-]*\.vercel\.app"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
