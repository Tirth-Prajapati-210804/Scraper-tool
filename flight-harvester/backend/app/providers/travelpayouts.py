"""
Travelpayouts / Aviasales flight data provider.

Free forever — sign up at travelpayouts.com → Partners → copy API token from Profile.
Uses the Calendar API: one request per (origin, destination, month) returns
cheapest prices for every day in that month. Results are cached in memory so
a single HTTP call serves up to 31 individual search_one_way queries.

Cached prices are updated every few hours on Travelpayouts' side — ideal for
continuous price tracking. Not real-time bookable fares.
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.providers.base import ProviderResult

log = get_logger(__name__)

_CALENDAR_URL = "https://api.travelpayouts.com/v1/prices/calendar"


class TravelpayoutsProvider:
    name = "travelpayouts"

    def __init__(self, token: str, timeout: int = 30) -> None:
        self._token = token
        self._timeout = timeout
        # Cache keyed by (origin, destination, "YYYY-MM")
        self._cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(self._token)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _fetch_calendar(
        self, origin: str, destination: str, year_month: str, currency: str
    ) -> dict[str, Any]:
        """Fetch cheapest prices for every day in year_month (e.g. '2026-05')."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                _CALENDAR_URL,
                params={
                    "origin": origin,
                    "destination": destination,
                    "depart_date": year_month,
                    "currency": currency,
                    "calendar_type": "departure_date",
                },
                headers={"X-Access-Token": self._token},
            )
            resp.raise_for_status()
            data = resp.json()

        if not data.get("success"):
            log.warning(
                "travelpayouts_calendar_no_success",
                origin=origin,
                destination=destination,
                month=year_month,
            )
            return {}

        # Response: { "success": true, "data": { "ORIGIN": { "YYYY-MM-DD": {...}, ... } } }
        raw = data.get("data", {})
        # The outer key is the origin IATA code
        if isinstance(raw, dict):
            for _key, day_map in raw.items():
                if isinstance(day_map, dict):
                    return day_map
        return {}

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
    ) -> list[ProviderResult]:
        currency = "USD"
        year_month = depart_date.strftime("%Y-%m")
        date_str = depart_date.isoformat()
        cache_key = (origin, destination, year_month)

        async with self._lock:
            if cache_key not in self._cache:
                try:
                    self._cache[cache_key] = await self._fetch_calendar(
                        origin, destination, year_month, currency
                    )
                except Exception as exc:
                    log.warning(
                        "travelpayouts_fetch_failed",
                        origin=origin,
                        destination=destination,
                        month=year_month,
                        error=str(exc),
                    )
                    self._cache[cache_key] = {}

        day_data = self._cache[cache_key].get(date_str)
        if not day_data:
            return []

        price = day_data.get("price") or day_data.get("value")
        if not price:
            return []

        airline = str(day_data.get("airline", ""))
        stops = int(day_data.get("transfers", day_data.get("number_of_changes", 0)))
        flight_num = day_data.get("flight_number", "")
        deep_link = (
            f"https://www.aviasales.com/search/{origin}{depart_date.strftime('%d%m')}{destination}1"
        )

        return [
            ProviderResult(
                price=float(price),
                currency=currency,
                airline=airline,
                deep_link=deep_link,
                provider=self.name,
                stops=stops,
                duration_minutes=0,  # Travelpayouts calendar does not return duration
                raw_data=day_data,
            )
        ]

    async def close(self) -> None:
        self._cache.clear()
