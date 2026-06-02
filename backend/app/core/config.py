from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Search: backend/.env → project-root/.env (last match wins)
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Neural Hub AI Triage Nurse"
    app_version: str = "1.0.0"
    secret_key: str
    debug: bool = False

    # Database
    database_url: str
    database_url_sync: str
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    # AI — OpenAI (primary)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 4096

    # AI — Anthropic (optional, leave blank if not available)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 4096

    @property
    def active_ai_provider(self) -> str:
        """Returns 'openai' or 'anthropic' depending on which key is set."""
        if self.openai_api_key:
            return "openai"
        if self.anthropic_api_key:
            return "anthropic"
        raise ValueError("No AI provider configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")

    # Email
    sendgrid_api_key: str = ""
    from_email: str = "noreply@neuralhub.ai"
    from_name: str = "Neural Hub"

    # Storage
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint_url: str = ""

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    # Sentry
    sentry_dsn: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
