from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.flight_price import FlightPrice
from app.models.user import User
from app.schemas.search_profile import (
    FlightPriceResponse,
    SearchProfileCreate,
    SearchProfileProgress,
    SearchProfileResponse,
    SearchProfileUpdate,
)
from app.services import search_profile_service

router = APIRouter(prefix="/search-profiles", tags=["search-profiles"])

_Auth = Annotated[User, Depends(get_current_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


def _is_admin(user: User) -> bool:
    return user.role == "admin"


@router.get("/", response_model=list[SearchProfileResponse])
async def list_profiles(
    session: _DB, current_user: _Auth, active_only: bool = True
) -> list[SearchProfileResponse]:
    profiles = await search_profile_service.list_all(
        session,
        active_only=active_only,
        requesting_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return [SearchProfileResponse.model_validate(p) for p in profiles]


@router.post("/", response_model=SearchProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: SearchProfileCreate, session: _DB, current_user: _Auth
) -> SearchProfileResponse:
    try:
        profile = await search_profile_service.create(session, body, owner_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return SearchProfileResponse.model_validate(profile)


@router.get("/{profile_id}", response_model=SearchProfileResponse)
async def get_profile(
    profile_id: uuid.UUID, session: _DB, current_user: _Auth
) -> SearchProfileResponse:
    profile = await search_profile_service.get_by_id(
        session,
        profile_id,
        requesting_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return SearchProfileResponse.model_validate(profile)


@router.put("/{profile_id}", response_model=SearchProfileResponse)
async def update_profile(
    profile_id: uuid.UUID, body: SearchProfileUpdate, session: _DB, current_user: _Auth
) -> SearchProfileResponse:
    profile = await search_profile_service.update(
        session,
        profile_id,
        body,
        requesting_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return SearchProfileResponse.model_validate(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: uuid.UUID, session: _DB, current_user: _Auth) -> None:
    deleted = await search_profile_service.delete(
        session,
        profile_id,
        requesting_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Search profile not found")


@router.get("/{profile_id}/progress", response_model=SearchProfileProgress)
async def get_progress(
    profile_id: uuid.UUID, session: _DB, current_user: _Auth
) -> SearchProfileProgress:
    # Verify access first
    profile = await search_profile_service.get_by_id(
        session,
        profile_id,
        requesting_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")
    progress = await search_profile_service.get_progress(session, profile_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return progress


@router.get("/{profile_id}/prices", response_model=list[FlightPriceResponse])
async def get_prices(
    profile_id: uuid.UUID,
    session: _DB,
    current_user: _Auth,
    leg_order: int | None = None,
    origin: str | None = None,
    destination: str | None = None,
    stops: int | None = None,
    limit: int = 500,
) -> list[FlightPriceResponse]:
    """Return collected prices for a profile, optionally filtered by leg/route/stops."""
    # Verify access
    profile = await search_profile_service.get_by_id(
        session,
        profile_id,
        requesting_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")

    from app.models.search_leg import SearchLeg

    q = (
        select(FlightPrice)
        .join(SearchLeg, FlightPrice.leg_id == SearchLeg.id)
        .where(FlightPrice.profile_id == profile_id)
    )
    if leg_order is not None:
        q = q.where(SearchLeg.leg_order == leg_order)
    if origin:
        q = q.where(FlightPrice.origin == origin.upper())
    if destination:
        q = q.where(FlightPrice.destination == destination.upper())
    if stops is not None:
        if stops == 0:
            q = q.where(FlightPrice.stops == 0)
        else:
            q = q.where(FlightPrice.stops == stops)

    q = q.order_by(FlightPrice.depart_date, FlightPrice.price).limit(limit)
    result = await session.execute(q)
    prices = list(result.scalars().all())
    return [FlightPriceResponse.model_validate(p) for p in prices]


@router.get("/{profile_id}/journey", response_model=list[dict])
async def get_journey(
    profile_id: uuid.UUID,
    session: _DB,
    current_user: _Auth,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """
    Compute combined journey cost across all legs for a date window.

    For each departure date D of leg 0:
      - Leg 1 departs on D + ceil(leg0.min_halt_hours / 24) days
      - Leg 2 departs on leg1 date + ceil(leg1.min_halt_hours / 24) days
      - ...

    Returns rows sorted by total_price ascending.
    """
    import math
    from datetime import date, timedelta

    from sqlalchemy import and_

    # Verify access
    profile = await search_profile_service.get_by_id(
        session,
        profile_id,
        requesting_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")

    if len(profile.legs) == 0:
        return []

    # Parse optional date filters
    from_date: date | None = None
    to_date: date | None = None
    if date_from:
        try:
            from_date = date.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD.")
    if date_to:
        try:
            to_date = date.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD.")

    # Fetch cheapest price per (leg_id, origin, destination, depart_date)
    # for all legs in this profile in one query
    from app.models.search_leg import SearchLeg

    prices_result = await session.execute(
        select(FlightPrice)
        .join(SearchLeg, FlightPrice.leg_id == SearchLeg.id)
        .where(FlightPrice.profile_id == profile_id)
        .order_by(FlightPrice.depart_date)
    )
    all_prices = list(prices_result.scalars().all())

    # Build index: leg_id → depart_date → list of prices (cheapest first)
    price_index: dict[uuid.UUID, dict[date, list[FlightPrice]]] = {}
    for fp in all_prices:
        if fp.leg_id not in price_index:
            price_index[fp.leg_id] = {}
        d = fp.depart_date if isinstance(fp.depart_date, date) else date.fromisoformat(str(fp.depart_date))
        if d not in price_index[fp.leg_id]:
            price_index[fp.leg_id][d] = []
        price_index[fp.leg_id][d].append(fp)

    # Sort each day's prices cheapest first
    for leg_dict in price_index.values():
        for day_list in leg_dict.values():
            day_list.sort(key=lambda p: p.price)

    legs = profile.legs  # already ordered by leg_order

    # Determine leg-0 departure dates to iterate over
    leg0 = legs[0]
    leg0_dates: list[date] = sorted(price_index.get(leg0.id, {}).keys())
    if from_date:
        leg0_dates = [d for d in leg0_dates if d >= from_date]
    if to_date:
        leg0_dates = [d for d in leg0_dates if d <= to_date]

    journeys: list[dict] = []

    for start_date in leg0_dates:
        # Build the chain of leg dates for this start
        leg_dates: list[date] = [start_date]
        for i in range(1, len(legs)):
            prev_leg = legs[i - 1]
            # If the previous leg has a min_halt, advance by enough days to cover it
            halt_hours = prev_leg.min_halt_hours or 0
            days_offset = max(1, math.ceil(halt_hours / 24)) if halt_hours > 0 else 1
            leg_dates.append(leg_dates[-1] + timedelta(days=days_offset))

        # Look up cheapest price for each leg on its computed date
        leg_entries: list[dict] = []
        total_price: float = 0.0
        currency = "USD"
        valid = True

        for i, leg in enumerate(legs):
            d = leg_dates[i]
            day_prices = price_index.get(leg.id, {}).get(d, [])
            if not day_prices:
                valid = False
                break
            cheapest = day_prices[0]
            total_price += cheapest.price
            currency = cheapest.currency
            leg_entries.append({
                "leg_order": leg.leg_order,
                "origin_query": leg.origin_query,
                "destination_query": leg.destination_query,
                "origin": cheapest.origin,
                "destination": cheapest.destination,
                "depart_date": str(d),
                "airline": cheapest.airline,
                "price": cheapest.price,
                "currency": cheapest.currency,
                "provider": cheapest.provider,
                "stops": cheapest.stops,
                "duration_minutes": cheapest.duration_minutes,
                "deep_link": cheapest.deep_link,
            })

        if valid:
            journeys.append({
                "start_date": str(start_date),
                "total_price": round(total_price, 2),
                "currency": currency,
                "legs": leg_entries,
            })

    # Sort by total price ascending
    journeys.sort(key=lambda j: j["total_price"])
    return journeys
