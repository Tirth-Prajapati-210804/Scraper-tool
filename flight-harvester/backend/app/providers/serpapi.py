"""
SerpAPI Google Flights provider.

Sign up at serpapi.com — free plan includes ~100 searches/month.
Paid plans start at $75/month for 5,000 searches.

Uses engine=google_flights with deep_search=true to get prices identical
to what google.com/flights shows in the browser. This is completely different
from Serper.dev (which scraped Google Search text snippets).

Set SERPAPI_KEY in .env to activate.
"""
from __future__ import annotations

from datetime import date

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.providers.base import ProviderResult

log = get_logger(__name__)

_BASE_URL = "https://serpapi.com/search.json"


class SerpApiProvider:
    name = "serpapi"

    def __init__(self, api_key: str, timeout: int = 60) -> None:
        # deep_search can be slow — use a longer default timeout
        self._api_key = api_key
        self._timeout = timeout

    def is_configured(self) -> bool:
        return bool(self._api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
    ) -> list[ProviderResult]:
        # Map cabin strings to SerpAPI travel_class values
        travel_class_map = {"economy": 1, "premium_economy": 2, "business": 3, "first": 4}
        travel_class = travel_class_map.get(cabin.lower(), 1)

        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": depart_date.isoformat(),
            "currency": "USD",
            "adults": adults,
            "type": 2,             # 1 = round-trip, 2 = one-way
            "travel_class": travel_class,
            "deep_search": "true",  # exact prices matching Google Flights browser
            "api_key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: list[ProviderResult] = []

        for section in ("best_flights", "other_flights"):
            for offer in data.get(section, []):
                price = offer.get("price")
                if not price:
                    continue

                flights = offer.get("flights", [])
                if not flights:
                    continue

                first_leg = flights[0]
                airline = first_leg.get("airline", "")
                flight_number = first_leg.get("flight_number", "")
                total_duration = offer.get("total_duration", 0)  # minutes
                stops = max(0, len(flights) - 1)

                # Build a deep link — SerpAPI provides booking_token for this
                booking_token = offer.get("booking_token", "")
                if booking_token:
                    deep_link = (
                        f"https://www.google.com/travel/flights?tfs={booking_token}"
                    )
                else:
                    deep_link = (
                        f"https://www.google.com/flights#search;f={origin};t={destination};"
                        f"d={depart_date.isoformat()};tt=o"
                    )

                results.append(
                    ProviderResult(
                        price=float(price),
                        currency="USD",
                        airline=airline,
                        deep_link=deep_link,
                        provider=self.name,
                        stops=stops,
                        duration_minutes=int(total_duration),
                        raw_data={
                            "flight_number": flight_number,
                            "section": section,
                        },
                    )
                )

        log.info(
            "serpapi_search_done",
            origin=origin,
            destination=destination,
            date=depart_date.isoformat(),
            results=len(results),
        )
        return results

    async def close(self) -> None:
        pass
