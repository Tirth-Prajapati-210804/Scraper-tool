from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.collection_run import CollectionRun
from app.models.scrape_log import ScrapeLog
from app.models.user import User

router = APIRouter(prefix="/collection", tags=["collection"])


@router.get("/status")
async def collection_status(
    request: Request,
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return whether a collection cycle is currently running."""
    scheduler = request.app.state.scheduler
    return {
        "is_collecting": scheduler.is_collecting,
        "scheduler_running": scheduler.is_running,
    }


@router.post("/trigger")
async def trigger_collection(
    request: Request,
    background_tasks: BackgroundTasks,
    _: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    scheduler = request.app.state.scheduler
    if scheduler.is_collecting:
        return {"status": "already_running"}
    registry = request.app.state.provider_registry
    if not registry.get_enabled():
        raise HTTPException(
            status_code=400,
            detail="No flight data provider is configured. Add SERPAPI_KEY to your .env file, or enable DEMO_MODE=true to use fake data.",
        )
    background_tasks.add_task(scheduler.run_collection_cycle)
    return {"status": "triggered"}


@router.post("/stop")
async def stop_collection(
    request: Request,
    _: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """
    Signal the running collection cycle to stop at its next batch boundary.
    Returns immediately — the cycle may take a few seconds to actually stop.
    """
    scheduler = request.app.state.scheduler
    if not scheduler.is_collecting:
        return {"status": "not_running"}
    scheduler.request_stop()
    return {"status": "stop_requested"}


@router.post("/trigger-group/{group_id}")
async def trigger_group(
    group_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    _: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    scheduler = request.app.state.scheduler
    registry = request.app.state.provider_registry
    if not registry.get_enabled():
        raise HTTPException(
            status_code=400,
            detail="No flight data provider is configured. Add SERPAPI_KEY to your .env file, or enable DEMO_MODE=true to use fake data.",
        )
    background_tasks.add_task(scheduler.trigger_single_group, group_id)
    return {"status": "triggered", "group_id": str(group_id)}



@router.get("/runs")
async def list_runs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=20, le=100),
) -> list[dict]:
    result = await session.execute(
        select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "routes_total": r.routes_total,
            "routes_success": r.routes_success,
            "routes_failed": r.routes_failed,
            "dates_scraped": r.dates_scraped,
            "errors": r.errors,
        }
        for r in runs
    ]


@router.get("/logs")
async def list_logs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    route_group_id: uuid.UUID | None = Query(default=None),
    origin: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> list[dict]:
    q = select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(limit)
    if route_group_id:
        q = q.where(ScrapeLog.route_group_id == route_group_id)
    if origin:
        q = q.where(ScrapeLog.origin == origin)

    result = await session.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": str(lg.id),
            "origin": lg.origin,
            "destination": lg.destination,
            "depart_date": lg.depart_date.isoformat(),
            "provider": lg.provider,
            "status": lg.status,
            "offers_found": lg.offers_found,
            "cheapest_price": float(lg.cheapest_price) if lg.cheapest_price else None,
            "error_message": lg.error_message,
            "duration_ms": lg.duration_ms,
            "created_at": lg.created_at.isoformat() if lg.created_at else None,
        }
        for lg in logs
    ]
