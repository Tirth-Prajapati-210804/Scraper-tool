from __future__ import annotations

import time
from datetime import date

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.providers.base import ProviderResult
from app.utils.airline_codes import normalize_airline

log = get_logger(__name__)

_CABIN_MAP = {
    "economy": "Economy",
    "business": "Business",
    "first": "First",
    "premium_economy": "Economy",
}


class FlightApiProvider:
    name = "flightapi"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.flightapi.io",
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=timeout, write=10, pool=10),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
    ) -> list[ProviderResult]:
        if not self.is_configured():
            return []

        cabin_str = _CABIN_MAP.get(cabin, "Economy")
        url = (
            f"{self.base_url}/onewaytrip/{self.api_key}"
            f"/{origin}/{destination}/{depart_date.isoformat()}"
            f"/{adults}/0/0/{cabin_str}/CAD"
        )

        t0 = time.monotonic()
        response = await self.client.get(url)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if response.status_code in (402, 429):
            log.warning(
                "flightapi quota/rate-limit",
                status_code=response.status_code,
                origin=origin,
                destination=destination,
                date=str(depart_date),
            )
            return []

        response.raise_for_status()
        data = response.json()
        results = self._normalize(data)

        log.info(
            "flightapi search",
            origin=origin,
            destination=destination,
            date=str(depart_date),
            status_code=response.status_code,
            result_count=len(results),
            duration_ms=elapsed_ms,
        )
        return results

    def _normalize(self, data: object) -> list[ProviderResult]:
        results: list[ProviderResult] = []

        if not isinstance(data, dict):
            return results

        # Try fpiTrips path
        for trip in data.get("fpiTrips", []) or []:
            result = self._parse_trip(trip)
            if result:
                results.append(result)

        # Try itineraries path
        if not results:
            for itin in data.get("itineraries", []) or []:
                result = self._parse_itinerary(itin)
                if result:
                    results.append(result)

        results.sort(key=lambda r: r.price)
        return results

    def _parse_trip(self, trip: dict) -> ProviderResult | None:
        price = self._extract_price(trip)
        if not price:
            return None

        airline = self._extract_airline(trip)
        deep_link = trip.get("deepLink") or trip.get("deep_link") or ""

        return ProviderResult(
            price=price,
            currency="CAD",
            airline=normalize_airline(airline),
            deep_link=deep_link,
            provider="flightapi",
            raw_data=trip,
        )

    def _parse_itinerary(self, itin: dict) -> ProviderResult | None:
        pricing = itin.get("pricing") or {}
        price_raw = (
            pricing.get("total")
            or itin.get("price")
            or itin.get("totalPrice")
        )
        if not price_raw:
            return None

        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            return None

        if price <= 0:
            return None

        legs = itin.get("legs") or []
        airline = ""
        if legs:
            carriers = legs[0].get("carriers") or []
            airline = carriers[0] if carriers else ""

        deep_link = itin.get("deepLink") or itin.get("deep_link") or ""
        return ProviderResult(
            price=price,
            currency="CAD",
            airline=normalize_airline(airline),
            deep_link=deep_link,
            provider="flightapi",
            raw_data=itin,
        )

    def _extract_price(self, obj: dict) -> float | None:
        raw = (
            obj.get("totalPrice")
            or (obj.get("pricing") or {}).get("total")
            or obj.get("price")
        )
        if raw is None:
            return None
        try:
            val = float(raw)
            return val if val > 0 else None
        except (TypeError, ValueError):
            return None

    def _extract_airline(self, obj: dict) -> str:
        legs = obj.get("legs") or []
        if legs:
            carriers = legs[0].get("carriers") or []
            if carriers:
                return str(carriers[0])
        return obj.get("airline") or obj.get("carrier") or ""

    async def close(self) -> None:
        await self.client.aclose()
