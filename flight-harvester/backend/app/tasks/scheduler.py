from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.collection_run import CollectionRun
from app.models.route_group import RouteGroup
from app.providers.registry import ProviderRegistry
from app.services.alert_service import AlertService
from app.services.price_collector import PriceCollector

log = get_logger(__name__)


class FlightScheduler:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        provider_registry: ProviderRegistry,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.provider_registry = provider_registry
        self.alert_service = AlertService(settings)
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self.scheduler.running

    def start(self) -> None:
        if not self.settings.scheduler_enabled:
            log.info("scheduler_disabled")
            return

        self.scheduler.add_job(
            self.run_collection_cycle,
            trigger="interval",
            minutes=self.settings.scheduler_interval_minutes,
            id="flight_collection",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.cleanup_old_data,
            trigger="interval",
            hours=24,
            id="daily_cleanup",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True
        log.info("scheduler_started", interval=self.settings.scheduler_interval_minutes)

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self._is_running = False
        log.info("scheduler_stopped")

    async def run_collection_cycle(self) -> None:
        log.info("collection_cycle_started")

        async with self.session_factory() as session:
            run = CollectionRun(status="running")
            session.add(run)
            await session.flush()

            try:
                result = await session.execute(
                    select(RouteGroup).where(RouteGroup.is_active.is_(True))
                )
                groups = result.scalars().all()

                if not groups:
                    log.warning("no_active_route_groups")
                    run.status = "completed"
                    run.finished_at = func.now()
                    await session.commit()
                    return

                providers = self.provider_registry.get_enabled()
                if not providers:
                    log.warning("no_providers_enabled")
                    run.status = "completed"
                    run.finished_at = func.now()
                    await session.commit()
                    return

                total_success = 0
                total_errors = 0
                total_routes = 0

                for group in groups:
                    dates = self._generate_dates(group.days_ahead)

                    for origin in group.origins:
                        total_routes += 1
                        log.info(
                            "collecting_route",
                            group=group.name,
                            origin=origin,
                            destinations=group.destinations,
                            dates_count=len(dates),
                        )

                        try:
                            remaining = await self._filter_already_scraped(
                                session, origin, group.destinations, dates
                            )

                            if not remaining:
                                log.info("route_already_complete", origin=origin)
                                total_success += 1
                                continue

                            collector = PriceCollector(session=session, providers=providers)
                            stats = await collector.collect_route_batch(
                                origin=origin,
                                destinations=group.destinations,
                                dates=remaining,
                                route_group_id=group.id,
                                batch_size=self.settings.scrape_batch_size,
                                delay_seconds=self.settings.scrape_delay_seconds,
                            )

                            total_success += stats["success"]
                            total_errors += stats["errors"]

                        except Exception as exc:
                            total_errors += 1
                            log.exception(
                                "route_collection_failed",
                                origin=origin,
                                error=str(exc),
                            )

                run.status = "completed"
                run.routes_total = total_routes
                run.routes_success = total_success
                run.routes_failed = total_errors
                run.dates_scraped = total_success
                run.finished_at = func.now()
                await session.commit()

                await self.alert_service.send_summary(
                    f"Collection cycle complete: {total_success} prices collected, "
                    f"{total_errors} errors, {len(groups)} route groups."
                )

            except Exception as exc:
                run.status = "failed"
                run.errors = [str(exc)]
                await session.commit()
                log.exception("collection_cycle_failed", error=str(exc))
                await self.alert_service.send_alert(f"Collection cycle FAILED: {exc}")

        log.info("collection_cycle_finished")

    def _generate_dates(self, days_ahead: int) -> list[date]:
        today = date.today()
        return [today + timedelta(days=d) for d in range(1, days_ahead + 1)]

    async def _filter_already_scraped(
        self,
        session: AsyncSession,
        origin: str,
        destinations: list[str],
        dates: list[date],
    ) -> list[date]:
        today = date.today()
        result = await session.execute(
            text("""
                SELECT DISTINCT depart_date FROM scrape_logs
                WHERE origin = :origin
                  AND destination = ANY(:destinations)
                  AND status = 'success'
                  AND created_at::date = :today
                  AND depart_date = ANY(:dates)
            """),
            {
                "origin": origin,
                "destinations": destinations,
                "today": today,
                "dates": dates,
            },
        )
        already_done = {row[0] for row in result.fetchall()}
        return [d for d in dates if d not in already_done]

    async def cleanup_old_data(self) -> None:
        """Delete scrape_logs and collection_runs older than 30 days."""
        log.info("cleanup_started")
        try:
            async with self.session_factory() as session:
                await session.execute(
                    text(
                        "DELETE FROM scrape_logs WHERE created_at < now() - interval '30 days'"
                    )
                )
                await session.execute(
                    text(
                        "DELETE FROM collection_runs WHERE started_at < now() - interval '30 days'"
                    )
                )
                await session.commit()
            log.info("cleanup_finished")
        except Exception as exc:
            log.exception("cleanup_failed", error=str(exc))

    async def trigger_single_group(self, group_id: UUID) -> dict[str, int]:
        stats: dict[str, int] = {"success": 0, "errors": 0, "skipped": 0}

        async with self.session_factory() as session:
            result = await session.execute(
                select(RouteGroup).where(
                    RouteGroup.id == group_id, RouteGroup.is_active.is_(True)
                )
            )
            group = result.scalar_one_or_none()
            if not group:
                return stats

            providers = self.provider_registry.get_enabled()
            if not providers:
                return stats

            dates = self._generate_dates(group.days_ahead)

            for origin in group.origins:
                remaining = await self._filter_already_scraped(
                    session, origin, group.destinations, dates
                )
                if not remaining:
                    continue

                collector = PriceCollector(session=session, providers=providers)
                part = await collector.collect_route_batch(
                    origin=origin,
                    destinations=group.destinations,
                    dates=remaining,
                    route_group_id=group.id,
                    batch_size=self.settings.scrape_batch_size,
                    delay_seconds=self.settings.scrape_delay_seconds,
                )
                stats["success"] += part["success"]
                stats["errors"] += part["errors"]
                stats["skipped"] += part["skipped"]

        return stats
