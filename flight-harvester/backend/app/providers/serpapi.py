"""
SerpAPI Google Flights provider.

Sign up at serpapi.com — free plan includes ~100 searches/month.
Paid plans start at $75/month for 5,000 searches.

HOW IT WORKS:
  SerpAPI scrapes google.com/flights and returns the results as structured JSON.
  This is completely different from Serper.dev (which scraped Google *Search* text
  snippets and returned random unrelated prices).

  With deep_search=true, prices are 100% identical to what you see in the Google
  Flights browser UI. Without it, prices can be off by up to 4x on some routes.

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
        # deep_search=true makes responses significantly slower than normal searches,
        # so we use a 60-second timeout instead of the default 30
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
        """
        Search Google Flights for origin→destination on depart_date.

        Returns all offers from both "best_flights" and "other_flights" sections,
        sorted by Google's ranking (best first). The caller (PriceCollector) picks
        the cheapest across all providers.
        """
        # SerpAPI encodes cabin class as a number, not a string
        travel_class_map = {"economy": 1, "premium_economy": 2, "business": 3, "first": 4}
        travel_class = travel_class_map.get(cabin.lower(), 1)

        params = {
            "engine": "google_flights",
            "departure_id": origin,        # IATA code, e.g. "AMD"
            "arrival_id": destination,     # IATA code, e.g. "DEL"
            "outbound_date": depart_date.isoformat(),
            "currency": "USD",
            "adults": adults,
            "type": 2,             # 1 = round-trip, 2 = one-way
            "travel_class": travel_class,
            # deep_search=true mirrors the exact prices shown in the browser.
            # Without this flag, SerpAPI may return a faster but less accurate
            # estimate that can differ significantly from the real price.
            "deep_search": "true",
            "api_key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: list[ProviderResult] = []

        # Google Flights splits results into two sections:
        #   "best_flights"  — top picks ranked by price + convenience
        #   "other_flights" — remaining options, usually more stops or worse times
        for section in ("best_flights", "other_flights"):
            for offer in data.get(section, []):
                price = offer.get("price")
                if not price:
                    continue

                flights = offer.get("flights", [])
                if not flights:
                    continue

                first_leg = flights[0]
                flight_number = first_leg.get("flight_number", "")
                airline_name = first_leg.get("airline", "")

                # Flight numbers always start with the correct 2-letter IATA code
                # (e.g. "VJ 767" → "VJ"). This is more reliable than the airline
                # name field which can be garbled or use wrong abbreviations.
                if flight_number:
                    airline = flight_number.split()[0]
                else:
                    airline = airline_name

                total_duration = offer.get("total_duration", 0)  # already in minutes

                # stops = number of connecting flights in the itinerary
                # A direct flight has 1 flight segment → len(flights) - 1 = 0 stops
                stops = max(0, len(flights) - 1)

                # SerpAPI provides a booking_token that can be used to deep-link
                # directly into the Google Flights booking flow for this exact offer
                booking_token = offer.get("booking_token", "")
                if booking_token:
                    deep_link = (
                        f"https://www.google.com/travel/flights?tfs={booking_token}"
                    )
                else:
                    # Fallback: generic Google Flights search link for this route/date
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
