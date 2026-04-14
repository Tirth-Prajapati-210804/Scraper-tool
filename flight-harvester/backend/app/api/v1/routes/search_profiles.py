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


@router.get("/", response_model=list[SearchProfileResponse])
async def list_profiles(
    session: _DB, _: _Auth, active_only: bool = True
) -> list[SearchProfileResponse]:
    profiles = await search_profile_service.list_all(session, active_only=active_only)
    return [SearchProfileResponse.model_validate(p) for p in profiles]


@router.post("/", response_model=SearchProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: SearchProfileCreate, session: _DB, _: _Auth
) -> SearchProfileResponse:
    try:
        profile = await search_profile_service.create(session, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return SearchProfileResponse.model_validate(profile)


@router.get("/{profile_id}", response_model=SearchProfileResponse)
async def get_profile(
    profile_id: uuid.UUID, session: _DB, _: _Auth
) -> SearchProfileResponse:
    profile = await search_profile_service.get_by_id(session, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return SearchProfileResponse.model_validate(profile)


@router.put("/{profile_id}", response_model=SearchProfileResponse)
async def update_profile(
    profile_id: uuid.UUID, body: SearchProfileUpdate, session: _DB, _: _Auth
) -> SearchProfileResponse:
    profile = await search_profile_service.update(session, profile_id, body)
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return SearchProfileResponse.model_validate(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: uuid.UUID, session: _DB, _: _Auth) -> None:
    deleted = await search_profile_service.delete(session, profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Search profile not found")


@router.get("/{profile_id}/progress", response_model=SearchProfileProgress)
async def get_progress(
    profile_id: uuid.UUID, session: _DB, _: _Auth
) -> SearchProfileProgress:
    progress = await search_profile_service.get_progress(session, profile_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return progress


@router.get("/{profile_id}/prices", response_model=list[FlightPriceResponse])
async def get_prices(
    profile_id: uuid.UUID,
    session: _DB,
    _: _Auth,
    leg_order: int | None = None,
    origin: str | None = None,
    destination: str | None = None,
    limit: int = 500,
) -> list[FlightPriceResponse]:
    """Return collected prices for a profile, optionally filtered by leg/route."""
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

    q = q.order_by(FlightPrice.depart_date, FlightPrice.price).limit(limit)
    result = await session.execute(q)
    prices = list(result.scalars().all())
    return [FlightPriceResponse.model_validate(p) for p in prices]
