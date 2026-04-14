from __future__ import annotations

from app.core.config import Settings
from app.providers.base import FlightProvider
from app.providers.mock import MockProvider
from app.providers.serpapi import SerpApiProvider
from app.providers.travelpayouts import TravelpayoutsProvider


class ProviderRegistry:
    """Creates, manages, and reports on all providers."""

    def __init__(self, settings: Settings) -> None:
        self.providers: dict[str, FlightProvider] = {}

        # Travelpayouts: free, calendar-based bulk scanning (PRIMARY)
        if settings.travelpayouts_token:
            self.providers["travelpayouts"] = TravelpayoutsProvider(
                token=settings.travelpayouts_token,
                timeout=settings.provider_timeout_seconds,
            )

        # SerpAPI Google Flights: real-time accurate prices (SECONDARY)
        if settings.serpapi_key:
            self.providers["serpapi"] = SerpApiProvider(
                api_key=settings.serpapi_key,
                timeout=settings.provider_timeout_seconds,
            )

        # Mock: deterministic fake data for local testing only
        if settings.mock_provider_key:
            self.providers["mock"] = MockProvider(key=settings.mock_provider_key)

    def get_enabled(self) -> list[FlightProvider]:
        return list(self.providers.values())

    def status(self) -> dict[str, str]:
        all_providers: dict[str, str] = {
            "travelpayouts": "disabled",
            "serpapi": "disabled",
            "mock": "disabled",
        }
        for name, provider in self.providers.items():
            all_providers[name] = "configured" if provider.is_configured() else "disabled"
        return all_providers

    async def close_all(self) -> None:
        for provider in self.providers.values():
            await provider.close()
