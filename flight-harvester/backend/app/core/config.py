from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Flight Data Scrapper API"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Database
    database_url: str

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 720
    admin_email: str
    admin_password: str
    admin_full_name: str = "System Admin"

    # Provider API keys (empty = disabled)
    # Travelpayouts: free calendar API — sign up at travelpayouts.com
    travelpayouts_token: str = ""
    # SerpAPI Google Flights: accurate real-time prices — sign up at serpapi.com
    serpapi_key: str = ""
    # Mock provider — set to any non-empty string to enable fake data for testing
    # NEVER set this in production
    mock_provider_key: str = ""

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 60
    scrape_days_ahead: int = 365
    scrape_batch_size: int = 3
    scrape_delay_seconds: float = 2.0
    provider_timeout_seconds: int = 30
    provider_max_retries: int = 3

    # Monitoring
    sentry_dsn: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    @field_validator("debug", "scheduler_enabled", mode="before")
    @classmethod
    def parse_bool(cls, v: object) -> bool:
        if isinstance(v, str):
            return v.lower() not in ("false", "0", "release", "production")
        return bool(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()
