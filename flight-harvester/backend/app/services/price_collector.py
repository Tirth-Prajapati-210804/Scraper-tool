from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.models.daily_cheapest import DailyCheapestPrice  # noqa: F401 — side-effect import
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
    """
    Coordinates searches across all configured providers for a single route/date,
    then writes the cheapest result to the database.

    Each collect_single_date() call gets its own DB session (created from
    session_factory) so concurrent calls don't share a session and cause
    transaction conflicts.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        providers: list[FlightProvider],
    ) -> None:
        self.session_factory = session_factory
        self.providers = providers

    async def collect_single_date(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        route_group_id: UUID,
        *,
        leg_id: UUID | None = None,
        profile_id: UUID | None = None,
    ) -> CollectionResult:
        """
        Search all providers for origin→destination on depart_date.

        Writes to:
        - scrape_logs (always, one row per provider)
        - daily_cheapest_prices (legacy route-group path, when leg_id is None)
        - flight_prices (new path, when leg_id + profile_id are provided)
        """
        all_results: list[ProviderResult] = []
        provider_results: dict[str, list[ProviderResult]] = {}
        errors: dict[str, str] = {}

        async with self.session_factory() as session:
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
                    session.add(log_entry)

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
                    session.add(log_entry)

            cheapest = min(all_results, key=lambda r: r.price) if all_results else None

            if cheapest:
                if leg_id and profile_id:
                    # New path: write to flight_prices (per-leg)
                    await self._upsert_flight_price(
                        session=session,
                        leg_id=leg_id,
                        profile_id=profile_id,
                        origin=origin,
                        destination=destination,
                        depart_date=depart_date,
                        result=cheapest,
                    )
                else:
                    # Legacy path: write to daily_cheapest_prices (route-group)
                    await self._upsert_cheapest(
                        session=session,
                        route_group_id=route_group_id,
                        origin=origin,
                        destination=destination,
                        depart_date=depart_date,
                        result=cheapest,
                    )

            await session.commit()

        return CollectionResult(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            cheapest=cheapest,
            provider_results=provider_results,
            errors=errors,
        )

    # ── flight_prices upsert (new per-leg path) ───────────────────────────────

    async def _upsert_flight_price(
        self,
        session: AsyncSession,
        leg_id: UUID,
        profile_id: UUID,
        origin: str,
        destination: str,
        depart_date: date,
        result: ProviderResult,
    ) -> None:
        stmt = text("""
            INSERT INTO flight_prices
                (id, leg_id, profile_id, origin, destination, depart_date,
                 airline, price, currency, provider, deep_link,
                 stops, duration_minutes, scraped_at)
            VALUES
                (gen_random_uuid(), :leg_id, :profile_id,
                 :origin, :destination, :depart_date,
                 :airline, :price, :currency, :provider, :deep_link,
                 :stops, :duration_minutes, now())
            ON CONFLICT (leg_id, origin, destination, depart_date)
            DO UPDATE SET
                airline          = EXCLUDED.airline,
                price            = EXCLUDED.price,
                currency         = EXCLUDED.currency,
                provider         = EXCLUDED.provider,
                deep_link        = EXCLUDED.deep_link,
                stops            = EXCLUDED.stops,
                duration_minutes = EXCLUDED.duration_minutes,
                scraped_at       = now()
            -- Only update if the new price is strictly cheaper than what's stored.
            -- If the new price is equal or higher, the existing record is kept unchanged.
            WHERE flight_prices.price > EXCLUDED.price
        """)
        await session.execute(
            stmt,
            {
                "leg_id": str(leg_id),
                "profile_id": str(profile_id),
                "origin": origin,
                "destination": destination,
                "depart_date": depart_date,
                "airline": normalize_airline(result.airline),
                "price": result.price,
                "currency": result.currency,
                "provider": result.provider or "unknown",
                "deep_link": result.deep_link[:2048] if result.deep_link else None,
                "stops": result.stops if result.stops is not None else None,
                "duration_minutes": result.duration_minutes or None,
            },
        )

    # ── daily_cheapest_prices upsert (legacy route-group path) ───────────────

    async def _upsert_cheapest(
        self,
        session: AsyncSession,
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
            -- Same cheapest-wins logic as the flight_prices upsert above
            WHERE daily_cheapest_prices.price > EXCLUDED.price
        """)
        await session.execute(
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
                "duration_minutes": result.duration_minutes or None,
            },
        )

    # ── batch helpers ─────────────────────────────────────────────────────────

    async def collect_leg_batch(
        self,
        leg_id: UUID,
        profile_id: UUID,
        origins: list[str],
        destinations: list[str],
        dates: list[date],
        batch_size: int = 5,
        delay_seconds: float = 1.0,
        stop_check: Callable[[], bool] | None = None,
    ) -> dict[str, int]:
        """
        Collect prices for all origin×destination pairs for a search leg.

        stop_check: optional callable that returns True when the caller wants the
        batch loop to abort early (used by the scheduler's stop-collection feature).
        The current batch finishes before stopping — never halts mid-batch.
        """
        stats: dict[str, int] = {"success": 0, "errors": 0, "skipped": 0}

        for origin in origins:
            for dest in destinations:
                for i in range(0, len(dates), batch_size):
                    # Check stop signal before starting each batch
                    if stop_check and stop_check():
                        return stats

                    batch = dates[i : i + batch_size]
                    tasks = [
                        self.collect_single_date(
                            origin,
                            dest,
                            d,
                            profile_id,          # route_group_id slot (unused for logs)
                            leg_id=leg_id,
                            profile_id=profile_id,
                        )
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
                        # Pause between batches to avoid hitting provider rate limits
                        await asyncio.sleep(delay_seconds)

        return stats

    async def collect_route_batch(
        self,
        origin: str,
        destinations: list[str],
        dates: list[date],
        route_group_id: UUID,
        batch_size: int = 3,
        delay_seconds: float = 2.0,
        stop_check: Callable[[], bool] | None = None,
    ) -> dict[str, int]:
        """
        Legacy route-group collection path.

        stop_check: optional callable that returns True when the caller wants the
        batch loop to abort early (see collect_leg_batch for details).
        """
        stats: dict[str, int] = {"success": 0, "errors": 0, "skipped": 0}

        for dest in destinations:
            for i in range(0, len(dates), batch_size):
                # Check stop signal before starting each batch
                if stop_check and stop_check():
                    return stats

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
