"""
Configuration Module

Manages application configuration using pydantic-settings.
Loads environment variables and provides typed configuration objects.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_bot",
        description="Async PostgreSQL database URL",
    )
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30, ge=1, le=300)
    db_pool_recycle: int = Field(default=3600, ge=300, le=7200)
    db_echo: bool = Field(default=False, description="Log SQL queries")

    # Telegram Bot Configuration
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token from @BotFather (legacy single-bot mode)",
        min_length=0,
    )
    telegram_webhook_url: Optional[str] = Field(
        default=None,
        description="Public webhook URL for Telegram updates",
    )
    webhook_secret_token: Optional[str] = Field(
        default=None,
        description="Secret token for webhook security",
        min_length=20,
    )

    # Multi-Bot Configuration
    bots_api_url: str = Field(
        default="https://api.salona.me/api/v1/integrations/telegram/bots",
        description="External API endpoint to fetch bot configurations",
    )
    bots_api_token: Optional[str] = Field(
        default=None,
        description="Bearer token for authenticating with bots API",
    )
    webhook_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for bot webhooks (e.g., https://your-domain.com)",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key",
        min_length=20,
    )
    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="OpenAI model to use",
    )
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=500, ge=50, le=4000)

    # Application Settings
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1024, le=65535)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Security
    secret_key: str = Field(
        default="change-me-in-production-use-strong-secret",
        min_length=32,
    )

    telegram_bots_endpoint: str = Field(
        default="/telegram/webhook",
        description="Endpoint path for Telegram bot webhooks",
    )

    llm_host: str = Field(
        default="localhost",
        description="Host for local LLM server",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL uses asyncpg driver."""
        if isinstance(v, str):
            if v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif not v.startswith("postgresql+asyncpg://"):
                raise ValueError(
                    "Database URL must use postgresql+asyncpg:// scheme for async support"
                )
        return v

    @property
    def database_url_str(self) -> str:
        """Return database URL as string."""
        return str(self.database_url)


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure singleton pattern - settings are loaded once.

    Returns:
        Settings: Application settings instance
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
