from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.daily_cheapest import DailyCheapestPrice
from app.models.user import User
from app.schemas.daily_price import DailyPriceResponse, PriceTrendPoint

router = APIRouter(prefix="/prices", tags=["prices"])

_Auth = Annotated[User, Depends(get_current_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/", response_model=list[DailyPriceResponse])
async def list_prices(
    session: _DB,
    _: _Auth,
    route_group_id: uuid.UUID | None = Query(default=None),
    origin: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=500, le=2000),
) -> list[DailyPriceResponse]:
    q = select(DailyCheapestPrice).order_by(DailyCheapestPrice.depart_date).limit(limit)
    if route_group_id:
        q = q.where(DailyCheapestPrice.route_group_id == route_group_id)
    if origin:
        q = q.where(DailyCheapestPrice.origin == origin.upper())
    if date_from:
        q = q.where(DailyCheapestPrice.depart_date >= date_from)
    if date_to:
        q = q.where(DailyCheapestPrice.depart_date <= date_to)

    result = await session.execute(q)
    return [DailyPriceResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/trend", response_model=list[PriceTrendPoint])
async def price_trend(
    session: _DB,
    _: _Auth,
    origin: str = Query(),
    destination: str = Query(),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[PriceTrendPoint]:
    q = (
        select(DailyCheapestPrice)
        .where(
            DailyCheapestPrice.origin == origin.upper(),
            DailyCheapestPrice.destination == destination.upper(),
        )
        .order_by(DailyCheapestPrice.depart_date)
    )
    if date_from:
        q = q.where(DailyCheapestPrice.depart_date >= date_from)
    if date_to:
        q = q.where(DailyCheapestPrice.depart_date <= date_to)

    result = await session.execute(q)
    return [
        PriceTrendPoint(
            depart_date=p.depart_date,
            price=float(p.price),
            airline=p.airline,
        )
        for p in result.scalars().all()
    ]
