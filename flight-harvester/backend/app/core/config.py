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
    # SerpAPI Google Flights: accurate real-time prices — sign up at serpapi.com
    serpapi_key: str = ""
    # deep_search=true mirrors exact Google Flights browser prices but is 4-6x slower (~20s/search).
    # Set SERPAPI_DEEP_SEARCH=false for faster collection at the cost of minor price variance (~5-10%).
    serpapi_deep_search: bool = True
    # Demo mode: generates realistic fake prices without any API key.
    # Set DEMO_MODE=true for demos/testing. Never use in production.
    demo_mode: bool = False
    # Scheduler
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 60
    scrape_days_ahead: int = 365
    scrape_batch_size: int = 5
    scrape_delay_seconds: float = 1.0
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
            v = v.strip()
            # Handle JSON array format: '["http://localhost","http://localhost:5173"]'
            # (used by docker-compose environment block)
            if v.startswith("["):
                import json
                return json.loads(v)
            # Handle comma-separated format: "http://localhost,http://localhost:5173"
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
