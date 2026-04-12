from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.daily_cheapest import DailyCheapestPrice
from app.models.user import User
from app.schemas.route_group import (
    RouteGroupCreate,
    RouteGroupProgress,
    RouteGroupResponse,
    RouteGroupUpdate,
)
from app.services import export_service, route_group_service

router = APIRouter(prefix="/route-groups", tags=["route-groups"])

_Auth = Annotated[User, Depends(get_current_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/", response_model=list[RouteGroupResponse])
async def list_groups(session: _DB, _: _Auth, active_only: bool = True) -> list[RouteGroupResponse]:
    groups = await route_group_service.list_all(session, active_only=active_only)
    return [RouteGroupResponse.model_validate(g) for g in groups]


@router.post("/", response_model=RouteGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(body: RouteGroupCreate, session: _DB, _: _Auth) -> RouteGroupResponse:
    group = await route_group_service.create(session, body)
    return RouteGroupResponse.model_validate(group)


@router.get("/{group_id}", response_model=RouteGroupResponse)
async def get_group(group_id: uuid.UUID, session: _DB, _: _Auth) -> RouteGroupResponse:
    group = await route_group_service.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")
    return RouteGroupResponse.model_validate(group)


@router.put("/{group_id}", response_model=RouteGroupResponse)
async def update_group(
    group_id: uuid.UUID, body: RouteGroupUpdate, session: _DB, _: _Auth
) -> RouteGroupResponse:
    group = await route_group_service.update(session, group_id, body)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")
    return RouteGroupResponse.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, session: _DB, _: _Auth) -> None:
    deleted = await route_group_service.delete(session, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Route group not found")


@router.get("/{group_id}/export")
async def export_group(group_id: uuid.UUID, session: _DB, _: _Auth) -> StreamingResponse:
    group = await route_group_service.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Route group not found")

    prices_result = await session.execute(
        select(DailyCheapestPrice).where(DailyCheapestPrice.route_group_id == group_id)
    )
    prices = list(prices_result.scalars().all())

    excel_bytes = export_service.export_route_group(group, prices)
    safe_name = group.name.replace("/", "-").replace(" ", "_")
    filename = f"{safe_name}.xlsx"

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{group_id}/progress", response_model=RouteGroupProgress)
async def get_progress(group_id: uuid.UUID, session: _DB, _: _Auth) -> RouteGroupProgress:
    progress = await route_group_service.get_progress(session, group_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Route group not found")
    return progress
