from __future__ import annotations

import time
from datetime import date

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.providers.base import ProviderResult
from app.utils.airline_codes import normalize_airline

log = get_logger(__name__)


class KiwiProvider:
    name = "kiwi"

    def __init__(self, api_key: str, timeout: int = 30) -> None:
        self.api_key = api_key
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

        params = {
            "fly_from": origin,
            "fly_to": destination,
            "date_from": depart_date.strftime("%d/%m/%Y"),
            "date_to": depart_date.strftime("%d/%m/%Y"),
            "flight_type": "oneway",
            "curr": "CAD",
            "adults": adults,
            "sort": "price",
            "limit": 5,
            "max_stopovers": 2,
        }
        headers = {"apikey": self.api_key}

        t0 = time.monotonic()
        response = await self.client.get(
            "https://tequila-api.kiwi.com/v2/search",
            params=params,
            headers=headers,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        response.raise_for_status()
        data = response.json()
        results = self._normalize(data)

        log.info(
            "kiwi search",
            origin=origin,
            destination=destination,
            date=str(depart_date),
            status_code=response.status_code,
            result_count=len(results),
            duration_ms=elapsed_ms,
        )
        return results

    def _normalize(self, data: dict) -> list[ProviderResult]:
        results = []
        for item in data.get("data", []):
            route = item.get("route") or []
            if not route:
                continue

            airline_raw = route[0].get("airline", "")
            airline = normalize_airline(airline_raw)

            duration_obj = item.get("duration", {})
            total_seconds = duration_obj.get("total", 0) if isinstance(duration_obj, dict) else 0
            duration_min = max(0, total_seconds // 60)

            stops = max(0, len(route) - 1)
            price = float(item.get("price", 0))
            deep_link = item.get("deep_link") or item.get("booking_link") or ""

            if price > 0:
                results.append(
                    ProviderResult(
                        price=price,
                        currency="CAD",
                        airline=airline,
                        deep_link=deep_link,
                        duration_minutes=duration_min,
                        stops=stops,
                        raw_data=item,
                    )
                )
        results.sort(key=lambda r: r.price)
        return results

    async def close(self) -> None:
        await self.client.aclose()
