from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_run import CollectionRun
from app.models.daily_cheapest import DailyCheapestPrice
from app.models.route_group import RouteGroup
from app.models.scrape_log import ScrapeLog
from app.providers.registry import ProviderRegistry
from app.schemas.stats import OverviewStats, ProviderStat


async def get_overview(
    session: AsyncSession,
    registry: ProviderRegistry,
) -> OverviewStats:
    # Active route groups
    rg_result = await session.execute(
        select(func.count()).where(RouteGroup.is_active.is_(True))
    )
    active_groups = rg_result.scalar_one() or 0

    # Total prices
    price_result = await session.execute(select(func.count(DailyCheapestPrice.id)))
    total_prices = price_result.scalar_one() or 0

    # Distinct origins / destinations
    origin_result = await session.execute(
        select(func.count(DailyCheapestPrice.origin.distinct()))
    )
    total_origins = origin_result.scalar_one() or 0

    dest_result = await session.execute(
        select(func.count(DailyCheapestPrice.destination.distinct()))
    )
    total_destinations = dest_result.scalar_one() or 0

    # Last collection run
    run_result = await session.execute(
        select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
    )
    last_run = run_result.scalar_one_or_none()

    # Provider stats
    provider_status = registry.status()
    provider_stats: dict[str, ProviderStat] = {}

    for name, status in provider_status.items():
        configured = status == "configured"
        last_success = None
        success_rate = None

        if configured:
            ls_result = await session.execute(
                select(func.max(ScrapeLog.created_at)).where(
                    ScrapeLog.provider == name,
                    ScrapeLog.status == "success",
                )
            )
            last_success = ls_result.scalar_one()

            total_q = await session.execute(
                select(func.count()).where(ScrapeLog.provider == name)
            )
            total_logs = total_q.scalar_one() or 0

            if total_logs > 0:
                success_q = await session.execute(
                    select(func.count()).where(
                        ScrapeLog.provider == name,
                        ScrapeLog.status == "success",
                    )
                )
                success_count = success_q.scalar_one() or 0
                success_rate = round(success_count / total_logs, 4)

        provider_stats[name] = ProviderStat(
            configured=configured,
            last_success=last_success,
            success_rate=success_rate,
        )

    return OverviewStats(
        active_route_groups=active_groups,
        total_prices_collected=total_prices,
        total_origins=total_origins,
        total_destinations=total_destinations,
        last_collection_at=last_run.started_at if last_run else None,
        last_collection_status=last_run.status if last_run else None,
        provider_stats=provider_stats,
    )
