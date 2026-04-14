from __future__ import annotations

from app.core.config import Settings
from app.providers.base import FlightProvider
from app.providers.flightapi import FlightApiProvider
from app.providers.kiwi import KiwiProvider
from app.providers.mock import MockProvider
from app.providers.serper import SerperProvider


class ProviderRegistry:
    """Creates, manages, and reports on all providers."""

    def __init__(self, settings: Settings) -> None:
        self.providers: dict[str, FlightProvider] = {}

        if settings.kiwi_api_key:
            self.providers["kiwi"] = KiwiProvider(
                api_key=settings.kiwi_api_key,
                timeout=settings.provider_timeout_seconds,
            )
        if settings.flightapi_api_key:
            self.providers["flightapi"] = FlightApiProvider(
                api_key=settings.flightapi_api_key,
                base_url=settings.flightapi_base_url,
                timeout=settings.provider_timeout_seconds,
            )
        if settings.serper_api_key:
            self.providers["serper"] = SerperProvider(
                api_key=settings.serper_api_key,
                timeout=settings.provider_timeout_seconds,
            )
        if settings.mock_provider_key:
            self.providers["mock"] = MockProvider(key=settings.mock_provider_key)

    def get_enabled(self) -> list[FlightProvider]:
        return list(self.providers.values())

    def status(self) -> dict[str, str]:
        all_providers: dict[str, str] = {
            "kiwi": "disabled",
            "flightapi": "disabled",
            "serper": "disabled",
        }
        for name, provider in self.providers.items():
            all_providers[name] = "configured" if provider.is_configured() else "disabled"
        return all_providers

    async def close_all(self) -> None:
        for provider in self.providers.values():
            await provider.close()
