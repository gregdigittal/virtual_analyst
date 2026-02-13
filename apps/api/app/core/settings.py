from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    cors_allowed_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )

    rate_limit: str = Field(default="100/minute", alias="RATE_LIMIT")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    def cors_allowed_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
