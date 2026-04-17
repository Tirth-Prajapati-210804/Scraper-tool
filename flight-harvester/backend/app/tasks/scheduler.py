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
        self._stop_requested: bool = False
        self._is_collecting: bool = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self.scheduler.running

    @property
    def is_collecting(self) -> bool:
        return self._is_collecting

    def request_stop(self) -> None:
        if self._is_collecting:
            self._stop_requested = True
            log.info("stop_requested")

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
        if self._is_collecting:
            log.warning("collection_already_running_skipping")
            return

        self._stop_requested = False
        self._is_collecting = True
        log.info("collection_cycle_started")

        async with self.session_factory() as session:
            run = CollectionRun(status="running")
            session.add(run)
            await session.flush()

            try:
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

                groups_result = await session.execute(
                    select(RouteGroup).where(RouteGroup.is_active.is_(True))
                )
                groups = list(groups_result.scalars().all())

                collector = PriceCollector(
                    session_factory=self.session_factory,
                    providers=providers,
                )

                for group in groups:
                    if self._stop_requested:
                        log.info("collection_stopped_between_groups", group=group.name)
                        break

                    dates = self._generate_dates(group.days_ahead)
                    for origin in group.origins:
                        if self._stop_requested:
                            break

                        total_routes += 1
                        try:
                            remaining = await self._filter_already_scraped(
                                session, origin, group.destinations, dates
                            )
                            if not remaining:
                                total_success += 1
                                continue
                            stats = await collector.collect_route_batch(
                                origin=origin,
                                destinations=group.destinations,
                                dates=remaining,
                                route_group_id=group.id,
                                batch_size=self.settings.scrape_batch_size,
                                delay_seconds=self.settings.scrape_delay_seconds,
                                stop_check=lambda: self._stop_requested,
                            )
                            total_success += stats["success"]
                            total_errors += stats["errors"]
                        except Exception as exc:
                            total_errors += 1
                            log.exception("route_collection_failed", origin=origin, error=str(exc))

                run.status = "stopped" if self._stop_requested else "completed"
                run.routes_total = total_routes
                run.routes_success = total_success
                run.routes_failed = total_errors
                run.dates_scraped = total_success
                run.finished_at = func.now()
                await session.commit()

                if not self._stop_requested:
                    await self.alert_service.send_summary(
                        f"Collection complete: {total_success} prices, "
                        f"{total_errors} errors across {len(groups)} route groups."
                    )

            except Exception as exc:
                run.status = "failed"
                run.errors = [str(exc)]
                await session.commit()
                log.exception("collection_cycle_failed", error=str(exc))
                await self.alert_service.send_alert(f"Collection cycle FAILED: {exc}")
            finally:
                self._is_collecting = False
                self._stop_requested = False

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
            collector = PriceCollector(
                session_factory=self.session_factory,
                providers=providers,
            )

            for origin in group.origins:
                remaining = await self._filter_already_scraped(
                    session, origin, group.destinations, dates
                )
                if not remaining:
                    continue
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

    async def cleanup_old_data(self) -> None:
        log.info("cleanup_started")
        try:
            async with self.session_factory() as session:
                await session.execute(
                    text("DELETE FROM scrape_logs WHERE created_at < now() - interval '30 days'")
                )
                await session.execute(
                    text("DELETE FROM collection_runs WHERE started_at < now() - interval '30 days'")
                )
                await session.commit()
            log.info("cleanup_finished")
        except Exception as exc:
            log.exception("cleanup_failed", error=str(exc))
