from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.daily_cheapest import DailyCheapestPrice  # noqa: F401 — imported for side-effect
from app.models.scrape_log import ScrapeLog
from app.providers.base import FlightProvider, ProviderResult
from app.utils.airline_codes import normalize_airline

log = get_logger(__name__)


@dataclass
class CollectionResult:
    origin: str
    destination: str
    depart_date: date
    cheapest: ProviderResult | None
    provider_results: dict[str, list[ProviderResult]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class PriceCollector:
    def __init__(self, session: AsyncSession, providers: list[FlightProvider]) -> None:
        self.session = session
        self.providers = providers

    async def collect_single_date(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        route_group_id: UUID,
    ) -> CollectionResult:
        all_results: list[ProviderResult] = []
        provider_results: dict[str, list[ProviderResult]] = {}
        errors: dict[str, str] = {}

        for provider in self.providers:
            start = time.monotonic()
            try:
                results = await provider.search_one_way(origin, destination, depart_date)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                provider_results[provider.name] = results
                all_results.extend(results)

                log_entry = ScrapeLog(
                    route_group_id=route_group_id,
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    provider=provider.name,
                    status="success" if results else "no_results",
                    offers_found=len(results),
                    cheapest_price=results[0].price if results else None,
                    duration_ms=elapsed_ms,
                )
                self.session.add(log_entry)

            except Exception as exc:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                errors[provider.name] = str(exc)
                log.warning(
                    "provider_error",
                    provider=provider.name,
                    origin=origin,
                    destination=destination,
                    date=str(depart_date),
                    error=str(exc),
                )

                log_entry = ScrapeLog(
                    route_group_id=route_group_id,
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    provider=provider.name,
                    status="error",
                    offers_found=0,
                    error_message=str(exc)[:500],
                    duration_ms=elapsed_ms,
                )
                self.session.add(log_entry)

        cheapest = min(all_results, key=lambda r: r.price) if all_results else None

        if cheapest:
            await self._upsert_cheapest(
                route_group_id=route_group_id,
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                result=cheapest,
            )

        await self.session.commit()

        return CollectionResult(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            cheapest=cheapest,
            provider_results=provider_results,
            errors=errors,
        )

    async def _upsert_cheapest(
        self,
        route_group_id: UUID,
        origin: str,
        destination: str,
        depart_date: date,
        result: ProviderResult,
    ) -> None:
        stmt = text("""
            INSERT INTO daily_cheapest_prices
                (id, route_group_id, origin, destination, depart_date,
                 airline, price, currency, provider, deep_link,
                 stops, duration_minutes, scraped_at)
            VALUES
                (gen_random_uuid(), :route_group_id, :origin, :destination, :depart_date,
                 :airline, :price, :currency, :provider, :deep_link,
                 :stops, :duration_minutes, now())
            ON CONFLICT (origin, destination, depart_date)
            DO UPDATE SET
                airline          = EXCLUDED.airline,
                price            = EXCLUDED.price,
                currency         = EXCLUDED.currency,
                provider         = EXCLUDED.provider,
                deep_link        = EXCLUDED.deep_link,
                stops            = EXCLUDED.stops,
                duration_minutes = EXCLUDED.duration_minutes,
                route_group_id   = EXCLUDED.route_group_id,
                scraped_at       = now()
            WHERE daily_cheapest_prices.price > EXCLUDED.price
        """)
        await self.session.execute(
            stmt,
            {
                "route_group_id": str(route_group_id),
                "origin": origin,
                "destination": destination,
                "depart_date": depart_date,
                "airline": normalize_airline(result.airline),
                "price": result.price,
                "currency": result.currency,
                "provider": result.provider or "unknown",
                "deep_link": result.deep_link[:2048] if result.deep_link else None,
                "stops": result.stops if result.stops is not None else None,
                "duration_minutes": result.duration_minutes if result.duration_minutes else None,
            },
        )

    async def collect_route_batch(
        self,
        origin: str,
        destinations: list[str],
        dates: list[date],
        route_group_id: UUID,
        batch_size: int = 3,
        delay_seconds: float = 2.0,
    ) -> dict[str, int]:
        stats: dict[str, int] = {"success": 0, "errors": 0, "skipped": 0}

        for dest in destinations:
            for i in range(0, len(dates), batch_size):
                batch = dates[i : i + batch_size]
                tasks = [
                    self.collect_single_date(origin, dest, d, route_group_id)
                    for d in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        stats["errors"] += 1
                    elif isinstance(result, CollectionResult):
                        if result.cheapest:
                            stats["success"] += 1
                        else:
                            stats["skipped"] += 1

                if i + batch_size < len(dates):
                    await asyncio.sleep(delay_seconds)

        return stats
