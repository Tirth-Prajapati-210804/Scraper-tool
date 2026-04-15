"""
Travelpayouts / Aviasales flight data provider.

Free forever — sign up at travelpayouts.com → Partners → copy API token from Profile.

HOW IT WORKS (Calendar API):
  Instead of querying one date at a time, this provider fetches the cheapest price
  for every day in an entire month with a single HTTP request. Results are stored
  in an in-memory cache so all 30 individual search_one_way() calls for that month
  are served instantly without hitting the API again.

  Example: 10 route pairs × 12 months = only 120 HTTP calls for a full year of data.

ACCURACY:
  Prices are cached on Aviasales' servers and refreshed every few hours.
  Expect ~85–90% accuracy vs. live booking prices — suitable for price tracking
  and alerting, but users should always verify before booking.
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
        # Cache key: (origin_IATA, destination_IATA, "YYYY-MM")
        # Value: dict mapping "YYYY-MM-DD" → raw price data for that day
        # One cache entry covers all 30+ days in a month for a given route.
        self._cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        # Lock prevents two concurrent requests from fetching the same
        # (origin, destination, month) calendar simultaneously
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(self._token)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _fetch_calendar(
        self, origin: str, destination: str, year_month: str, currency: str
    ) -> dict[str, Any]:
        """
        Fetch cheapest prices for every day in year_month (e.g. '2026-05').

        Returns a dict like:
            { "2026-05-01": {"price": 89, "airline": "6E", "transfers": 0}, ... }

        Returns {} if the API reports no data or the response is malformed.
        The @retry decorator automatically retries up to 3 times on HTTP errors.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                _CALENDAR_URL,
                params={
                    "origin": origin,
                    "destination": destination,
                    "depart_date": year_month,   # "YYYY-MM" format → returns full month
                    "currency": currency,
                    "calendar_type": "departure_date",
                    "one_way": "true",           # without this the API returns round-trip
                },                               # cached prices, which are often absent for
                                                 # low-traffic routes like regional India→SEA
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

        # Response shape: { "success": true, "data": { "ORIGIN": { "YYYY-MM-DD": {...} } } }
        # The outer key under "data" is the origin IATA code — we iterate and take the first
        # dict value that is itself a dict (the day-keyed price map).
        raw = data.get("data", {})
        result: dict[str, Any] = {}
        if isinstance(raw, dict):
            for _key, day_map in raw.items():
                if isinstance(day_map, dict):
                    result = day_map
                    break

        if not result:
            # HTTP 200 + success=true but no actual price data for this route/month.
            # Travelpayouts only caches data for frequently searched routes — low-traffic
            # routes (e.g. regional Indian airports → Southeast Asia) often return empty.
            log.info(
                "travelpayouts_calendar_empty",
                origin=origin,
                destination=destination,
                month=year_month,
                note="Route may not have enough search volume for Travelpayouts cache",
            )
        return result

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
    ) -> list[ProviderResult]:
        """
        Return the cheapest price for origin→destination on depart_date.

        On the first call for a given (origin, destination, month), fetches the
        full month calendar from the API and caches it. Subsequent calls for other
        dates in the same month are served from cache with no HTTP request.
        """
        currency = "USD"
        year_month = depart_date.strftime("%Y-%m")  # e.g. "2026-05"
        date_str = depart_date.isoformat()           # e.g. "2026-05-14"
        cache_key = (origin, destination, year_month)

        # Acquire lock before checking the cache to prevent duplicate concurrent
        # fetches for the same route+month combination
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
                    # Store empty dict so we don't retry on every subsequent call
                    self._cache[cache_key] = {}

        day_data = self._cache[cache_key].get(date_str)
        if not day_data:
            # No price data for this specific date (Travelpayouts has no cached fare)
            return []

        # "price" is the standard key; "value" is used by some older response formats
        price = day_data.get("price") or day_data.get("value")
        if not price:
            return []

        airline = str(day_data.get("airline", ""))
        # "transfers" = number of stops; fallback to "number_of_changes" for older API versions
        stops = int(day_data.get("transfers", day_data.get("number_of_changes", 0)))
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
                # Travelpayouts calendar API does not return flight duration —
                # set to 0 as a sentinel; the UI handles 0/None as "unknown"
                duration_minutes=0,
                raw_data=day_data,
            )
        ]

    def clear_cache(self) -> None:
        """Discard all cached calendar data so the next request re-fetches from the API."""
        self._cache.clear()

    async def close(self) -> None:
        # Clear the in-memory cache on shutdown to free memory
        self._cache.clear()
