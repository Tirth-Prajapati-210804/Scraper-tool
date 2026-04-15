"""
CRUD and business logic for SearchProfile and its legs.

Key design decisions:
- Location resolution (plain text → IATA codes) happens once at creation time
  and the results are stored in the DB. This means the scheduler never needs to
  re-run the resolver — it just reads resolved_origins / resolved_destinations.
- The service always loads profiles with their legs eagerly (selectinload) to
  avoid lazy-loading errors in async SQLAlchemy sessions.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.flight_price import FlightPrice
from app.models.search_leg import SearchLeg
from app.models.search_profile import SearchProfile
from app.schemas.search_profile import (
    ProfileProgressLeg,
    SearchProfileCreate,
    SearchProfileProgress,
    SearchProfileUpdate,
)
from app.utils.location_resolver import resolve_location


async def list_all(session: AsyncSession, active_only: bool = True) -> list[SearchProfile]:
    """Return all profiles, with legs eagerly loaded, ordered by name."""
    q = select(SearchProfile).options(selectinload(SearchProfile.legs))
    if active_only:
        q = q.where(SearchProfile.is_active.is_(True))
    result = await session.execute(q.order_by(SearchProfile.name))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, profile_id: uuid.UUID) -> SearchProfile | None:
    """Fetch a single profile with its legs. Returns None if not found."""
    result = await session.execute(
        select(SearchProfile)
        .options(selectinload(SearchProfile.legs))
        .where(SearchProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def create(session: AsyncSession, data: SearchProfileCreate) -> SearchProfile:
    """
    Create a profile and all its legs.

    For each leg, plain-text origin/destination queries are resolved to IATA
    codes via location_resolver. The resolved codes are stored in the leg so
    the scheduler never needs to repeat this lookup.

    Raises ValueError if any leg's origin or destination cannot be resolved
    (e.g. a typo like "Indai" instead of "India").
    """
    profile = SearchProfile(
        name=data.name,
        days_ahead=data.days_ahead,
        is_active=data.is_active,
    )
    session.add(profile)
    # flush() makes profile.id available in the DB without committing,
    # so the legs can reference it as a foreign key immediately
    await session.flush()

    for i, leg_data in enumerate(data.legs):
        # Convert user-typed strings like "India" → ["DEL", "BOM", "MAA", "BLR", ...]
        resolved_origins = resolve_location(leg_data.origin_query)
        resolved_destinations = resolve_location(leg_data.destination_query)

        if not resolved_origins:
            raise ValueError(
                f"Leg {i + 1}: could not resolve origin '{leg_data.origin_query}'. "
                "Use a country name (e.g. 'India'), city name (e.g. 'Mumbai'), "
                "or IATA codes (e.g. 'AMD, BOM')."
            )
        if not resolved_destinations:
            raise ValueError(
                f"Leg {i + 1}: could not resolve destination '{leg_data.destination_query}'. "
                "Use a country name, city name, or IATA codes."
            )

        leg = SearchLeg(
            profile_id=profile.id,
            leg_order=i,                                     # 0-based position
            origin_query=leg_data.origin_query,              # store original text for display
            destination_query=leg_data.destination_query,
            resolved_origins=resolved_origins,               # e.g. ["AMD"]
            resolved_destinations=resolved_destinations,     # e.g. ["DEL", "BOM"]
            min_halt_hours=leg_data.min_halt_hours,          # None = final leg
            max_halt_hours=leg_data.max_halt_hours,
        )
        session.add(leg)

    await session.commit()
    await session.refresh(profile)
    # Re-fetch with legs loaded — refresh() alone doesn't load relationships
    result = await session.execute(
        select(SearchProfile)
        .options(selectinload(SearchProfile.legs))
        .where(SearchProfile.id == profile.id)
    )
    return result.scalar_one()


async def update(
    session: AsyncSession, profile_id: uuid.UUID, data: SearchProfileUpdate
) -> SearchProfile | None:
    """Update top-level profile fields (name, days_ahead, is_active). Does not modify legs."""
    profile = await get_by_id(session, profile_id)
    if not profile:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


async def delete(session: AsyncSession, profile_id: uuid.UUID) -> bool:
    """
    Delete a profile and all its legs and prices.
    Cascade delete in the DB handles child rows automatically.
    Returns False if the profile was not found.
    """
    profile = await get_by_id(session, profile_id)
    if not profile:
        return False
    await session.delete(profile)
    await session.commit()
    return True


async def get_progress(
    session: AsyncSession, profile_id: uuid.UUID
) -> SearchProfileProgress | None:
    """
    Calculate collection coverage for a profile.

    For each leg:
        total_slots = len(resolved_origins) × len(resolved_destinations) × days_ahead
        filled_slots = number of rows in flight_prices for this leg

    A slot represents one (origin, destination, date) combination. When filled_slots
    equals total_slots, the profile has a price for every possible route on every
    tracked date — 100% coverage.
    """
    profile = await get_by_id(session, profile_id)
    if not profile:
        return None

    total_slots = 0
    filled_slots = 0
    last_scraped_at = None
    leg_progress: list[ProfileProgressLeg] = []

    for leg in profile.legs:
        # Expected number of price records for this leg:
        # every combination of origin × destination × date
        expected = (
            len(leg.resolved_origins)
            * len(leg.resolved_destinations)
            * profile.days_ahead
        )
        # Count how many of those slots have actually been collected
        count_result = await session.execute(
            select(func.count()).where(FlightPrice.leg_id == leg.id)
        )
        collected = count_result.scalar_one() or 0

        # Track when this leg was last scraped (used for "last collected X ago" display)
        last_result = await session.execute(
            select(func.max(FlightPrice.scraped_at)).where(FlightPrice.leg_id == leg.id)
        )
        leg_last = last_result.scalar_one()
        if leg_last and (last_scraped_at is None or leg_last > last_scraped_at):
            last_scraped_at = leg_last

        total_slots += expected
        filled_slots += collected
        coverage = (collected / expected * 100.0) if expected > 0 else 0.0
        leg_progress.append(
            ProfileProgressLeg(
                leg_id=leg.id,
                leg_order=leg.leg_order,
                origin_query=leg.origin_query,
                destination_query=leg.destination_query,
                total_slots=expected,
                filled_slots=collected,
                coverage_percent=round(coverage, 2),
            )
        )

    overall_coverage = (filled_slots / total_slots * 100.0) if total_slots > 0 else 0.0
    return SearchProfileProgress(
        profile_id=profile_id,
        name=profile.name,
        total_slots=total_slots,
        filled_slots=filled_slots,
        coverage_percent=round(overall_coverage, 2),
        last_scraped_at=last_scraped_at,
        legs=leg_progress,
    )
