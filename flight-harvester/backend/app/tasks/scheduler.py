"""
Flight collection scheduler.

Runs two recurring jobs:
  - flight_collection: calls run_collection_cycle() every SCHEDULER_INTERVAL_MINUTES
  - daily_cleanup: calls cleanup_old_data() once every 24 hours

Set SCHEDULER_ENABLED=false in .env to disable all scheduled work (useful when
running the API server during local development without wanting background tasks).

Stop support:
  Call request_stop() to signal a running cycle to abort at the next checkpoint
  (between legs, between batches). The cycle marks its CollectionRun as "stopped"
  and exits cleanly without raising an exception.
"""
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
from app.models.search_profile import SearchProfile
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
        # Cancellation state — reset at the start of every cycle
        self._stop_requested: bool = False
        self._is_collecting: bool = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self.scheduler.running

    @property
    def is_collecting(self) -> bool:
        """True while a collection cycle is actively running."""
        return self._is_collecting

    def request_stop(self) -> None:
        """
        Signal the current collection cycle to stop at its next checkpoint.

        The cycle checks this flag between legs and between batches, so it may
        complete a few more API calls before actually stopping (never mid-batch).
        The CollectionRun row is marked "stopped" instead of "completed".
        """
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
            max_instances=1,   # prevent overlapping runs if a cycle takes longer than the interval
            coalesce=True,     # if multiple triggers fired while the job was running, run only once
            misfire_grace_time=300,  # allow up to 5 min late start before skipping a cycle
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
        """
        Main collection loop — runs every SCHEDULER_INTERVAL_MINUTES minutes.

        Processes two systems in each cycle:
          1. Search Profiles (new): each profile has ordered legs; prices are
             written to the flight_prices table keyed by leg_id.
          2. Route Groups (legacy): flat origin→destinations groups; prices are
             written to daily_cheapest_prices. Kept for backwards compatibility.

        A CollectionRun row is written to the DB at the start and updated at the
        end, so the Logs page can show history of every cycle.

        If request_stop() is called while this is running, the cycle will finish
        its current batch and then exit, marking the run as "stopped".
        """
        # Guard: don't allow concurrent collections (can happen via manual trigger)
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

                # ── New: search profiles (multi-leg) ─────────────────────────
                # selectinload fetches all legs in a single extra query rather than
                # issuing one query per profile (avoids N+1 problem)
                from sqlalchemy.orm import selectinload
                profiles_result = await session.execute(
                    select(SearchProfile)
                    .options(selectinload(SearchProfile.legs))
                    .where(SearchProfile.is_active.is_(True))
                )
                profiles = list(profiles_result.scalars().all())

                collector = PriceCollector(
                    session_factory=self.session_factory,
                    providers=providers,
                )

                for profile in profiles:
                    if self._stop_requested:
                        log.info("collection_stopped_between_profiles", profile=profile.name)
                        break

                    # Generate the list of future dates to collect for this profile
                    dates = self._generate_dates(profile.days_ahead)
                    log.info("collecting_profile", profile=profile.name, legs=len(profile.legs))

                    for leg in profile.legs:
                        if self._stop_requested:
                            log.info("collection_stopped_between_legs", leg_id=str(leg.id))
                            break

                        total_routes += 1
                        try:
                            stats = await collector.collect_leg_batch(
                                leg_id=leg.id,
                                profile_id=profile.id,
                                origins=leg.resolved_origins,
                                destinations=leg.resolved_destinations,
                                dates=dates,
                                batch_size=self.settings.scrape_batch_size,
                                delay_seconds=self.settings.scrape_delay_seconds,
                                stop_check=lambda: self._stop_requested,
                            )
                            total_success += stats["success"]
                            total_errors += stats["errors"]
                            log.info(
                                "leg_collected",
                                profile=profile.name,
                                leg=leg.leg_order,
                                origins=leg.resolved_origins,
                                destinations=leg.resolved_destinations,
                                **stats,
                            )
                        except Exception as exc:
                            total_errors += 1
                            log.exception("leg_collection_failed", leg_id=str(leg.id), error=str(exc))

                # ── Legacy: route groups ──────────────────────────────────────
                if not self._stop_requested:
                    groups_result = await session.execute(
                        select(RouteGroup).where(RouteGroup.is_active.is_(True))
                    )
                    groups = list(groups_result.scalars().all())

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
                                # Skip dates already successfully scraped today to
                                # avoid redundant API calls on repeated cycles
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
                else:
                    groups = []

                # Mark run as stopped or completed depending on whether we were cancelled
                run.status = "stopped" if self._stop_requested else "completed"
                run.routes_total = total_routes
                run.routes_success = total_success
                run.routes_failed = total_errors
                run.dates_scraped = total_success
                run.finished_at = func.now()
                await session.commit()

                if not self._stop_requested:
                    await self.alert_service.send_summary(
                        f"Collection cycle complete: {total_success} prices collected, "
                        f"{total_errors} errors across {len(profiles)} profiles + {len(groups)} route groups."
                    )
                else:
                    log.info("collection_cycle_stopped_by_user", success=total_success, errors=total_errors)

            except Exception as exc:
                run.status = "failed"
                run.errors = [str(exc)]
                await session.commit()
                log.exception("collection_cycle_failed", error=str(exc))
                await self.alert_service.send_alert(f"Collection cycle FAILED: {exc}")
            finally:
                # Always clear the collecting flag, even if an exception occurred
                self._is_collecting = False
                self._stop_requested = False

        log.info("collection_cycle_finished")

    def _generate_dates(self, days_ahead: int) -> list[date]:
        """Return a list of dates from tomorrow through days_ahead days into the future."""
        today = date.today()
        return [today + timedelta(days=d) for d in range(1, days_ahead + 1)]

    async def _filter_already_scraped(
        self,
        session: AsyncSession,
        origin: str,
        destinations: list[str],
        dates: list[date],
    ) -> list[date]:
        """
        Return only the dates that have NOT been successfully scraped today.

        Queries scrape_logs for rows with status='success' created today for this
        origin/destinations combination, then removes those dates from the input list.
        This prevents wasting API calls re-fetching prices already collected in an
        earlier cycle run on the same day.
        """
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
        # Return only dates not already covered
        return [d for d in dates if d not in already_done]

    async def cleanup_old_data(self) -> None:
        """
        Delete scrape_logs and collection_runs older than 30 days.

        Runs once every 24 hours. Keeps the DB from growing indefinitely —
        we only need recent logs for debugging and the dashboard.
        """
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

    async def trigger_single_profile(self, profile_id: UUID) -> dict[str, int]:
        """
        Manually trigger a collection run for one specific search profile.
        Called by the API when the user clicks "Trigger Collection" on the
        Search Profile detail page.
        """
        stats: dict[str, int] = {"success": 0, "errors": 0, "skipped": 0}

        async with self.session_factory() as session:
            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(SearchProfile)
                .options(selectinload(SearchProfile.legs))
                .where(SearchProfile.id == profile_id, SearchProfile.is_active.is_(True))
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return stats

            providers = self.provider_registry.get_enabled()
            if not providers:
                return stats

            dates = self._generate_dates(profile.days_ahead)
            collector = PriceCollector(
                session_factory=self.session_factory,
                providers=providers,
            )

            for leg in profile.legs:
                try:
                    part = await collector.collect_leg_batch(
                        leg_id=leg.id,
                        profile_id=profile.id,
                        origins=leg.resolved_origins,
                        destinations=leg.resolved_destinations,
                        dates=dates,
                        batch_size=self.settings.scrape_batch_size,
                        delay_seconds=self.settings.scrape_delay_seconds,
                    )
                    stats["success"] += part["success"]
                    stats["errors"] += part["errors"]
                    stats["skipped"] += part["skipped"]
                except Exception as exc:
                    stats["errors"] += 1
                    log.exception(
                        "profile_leg_trigger_failed",
                        leg_id=str(leg.id),
                        error=str(exc),
                    )

        return stats

    async def trigger_single_group(self, group_id: UUID) -> dict[str, int]:
        """
        Manually trigger a collection run for one specific route group.
        Called by the API when the user clicks "Trigger Scrape" on the detail page.
        """
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

                collector = PriceCollector(
                    session_factory=self.session_factory,
                    providers=providers,
                )
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
