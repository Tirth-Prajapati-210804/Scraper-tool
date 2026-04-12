from __future__ import annotations

import re
import time
from datetime import date

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.providers.base import ProviderResult
from app.utils.airline_codes import normalize_airline

log = get_logger(__name__)

PRICE_PATTERN = re.compile(
    r"(?:CAD|C\$|\$)\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", re.IGNORECASE
)
DURATION_PATTERN = re.compile(r"(\d{1,2})h(?:\s?(\d{1,2})m)?", re.IGNORECASE)
AIRLINE_PATTERN = re.compile(
    r"(?:with|on|by|via)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)*)", re.IGNORECASE
)


class SerperProvider:
    name = "serper"

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

        query = f"cheapest one way flight {origin} to {destination} {depart_date.isoformat()} CAD"
        payload = {"q": query, "gl": "ca", "hl": "en", "num": 10}
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

        t0 = time.monotonic()
        response = await self.client.post(
            "https://google.serper.dev/search",
            json=payload,
            headers=headers,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        response.raise_for_status()
        data = response.json()
        results = self._normalize(data)

        log.info(
            "serper search",
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
        for item in data.get("organic", []):
            snippet = item.get("snippet", "") or ""
            title = item.get("title", "") or ""
            text = f"{title} {snippet}"

            price_match = PRICE_PATTERN.search(text)
            if not price_match:
                continue

            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                continue

            if price <= 0:
                continue

            duration_match = DURATION_PATTERN.search(text)
            duration_min = 0
            if duration_match:
                hours = int(duration_match.group(1))
                mins = int(duration_match.group(2) or 0)
                duration_min = hours * 60 + mins

            airline_match = AIRLINE_PATTERN.search(text)
            airline_raw = airline_match.group(1) if airline_match else ""
            airline = normalize_airline(airline_raw) if airline_raw else "-"

            deep_link = item.get("link") or ""

            results.append(
                ProviderResult(
                    price=price,
                    currency="CAD",
                    airline=airline,
                    deep_link=deep_link,
                    provider="serper",
                    duration_minutes=duration_min,
                    raw_data=item,
                )
            )

        results.sort(key=lambda r: r.price)
        return results

    async def close(self) -> None:
        await self.client.aclose()
