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
    q = select(SearchProfile).options(selectinload(SearchProfile.legs))
    if active_only:
        q = q.where(SearchProfile.is_active.is_(True))
    result = await session.execute(q.order_by(SearchProfile.name))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, profile_id: uuid.UUID) -> SearchProfile | None:
    result = await session.execute(
        select(SearchProfile)
        .options(selectinload(SearchProfile.legs))
        .where(SearchProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def create(session: AsyncSession, data: SearchProfileCreate) -> SearchProfile:
    profile = SearchProfile(
        name=data.name,
        days_ahead=data.days_ahead,
        is_active=data.is_active,
    )
    session.add(profile)
    await session.flush()  # get profile.id

    for i, leg_data in enumerate(data.legs):
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
            leg_order=i,
            origin_query=leg_data.origin_query,
            destination_query=leg_data.destination_query,
            resolved_origins=resolved_origins,
            resolved_destinations=resolved_destinations,
            min_halt_hours=leg_data.min_halt_hours,
            max_halt_hours=leg_data.max_halt_hours,
        )
        session.add(leg)

    await session.commit()
    await session.refresh(profile)
    # Reload with legs
    result = await session.execute(
        select(SearchProfile)
        .options(selectinload(SearchProfile.legs))
        .where(SearchProfile.id == profile.id)
    )
    return result.scalar_one()


async def update(
    session: AsyncSession, profile_id: uuid.UUID, data: SearchProfileUpdate
) -> SearchProfile | None:
    profile = await get_by_id(session, profile_id)
    if not profile:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


async def delete(session: AsyncSession, profile_id: uuid.UUID) -> bool:
    profile = await get_by_id(session, profile_id)
    if not profile:
        return False
    await session.delete(profile)
    await session.commit()
    return True


async def get_progress(
    session: AsyncSession, profile_id: uuid.UUID
) -> SearchProfileProgress | None:
    profile = await get_by_id(session, profile_id)
    if not profile:
        return None

    total_slots = 0
    filled_slots = 0
    last_scraped_at = None
    leg_progress: list[ProfileProgressLeg] = []

    for leg in profile.legs:
        expected = (
            len(leg.resolved_origins)
            * len(leg.resolved_destinations)
            * profile.days_ahead
        )
        count_result = await session.execute(
            select(func.count()).where(FlightPrice.leg_id == leg.id)
        )
        collected = count_result.scalar_one() or 0

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
