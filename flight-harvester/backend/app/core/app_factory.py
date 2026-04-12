from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.schemas.health import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    configure_logging(settings.debug)
    log = get_logger(__name__)

    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        from app.db.session import AsyncSessionLocal
        from app.providers.registry import ProviderRegistry
        from app.services.auth_service import ensure_default_admin
        from app.tasks.scheduler import FlightScheduler

        app.state.settings = settings

        registry = ProviderRegistry(settings)
        app.state.provider_registry = registry

        async with AsyncSessionLocal() as session:
            await ensure_default_admin(session, settings)

        scheduler = FlightScheduler(
            settings=settings,
            session_factory=AsyncSessionLocal,
            provider_registry=registry,
        )
        app.state.scheduler = scheduler
        scheduler.start()

        log.info("startup complete", environment=settings.environment)
        yield

        await scheduler.stop()
        await registry.close_all()
        log.info("shutdown complete")

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1.router import router as v1_router
    app.include_router(v1_router, prefix=settings.api_v1_prefix)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Flight Harvester API is running."}

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        from app.db.health import check_db
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            db_ok = await check_db(session)

        s: Settings = request.app.state.settings
        registry = request.app.state.provider_registry
        provider_status = registry.status()

        db_status = "ok" if db_ok else "down"
        overall = "ok" if db_ok else "degraded"

        return HealthResponse(
            status=overall,
            environment=s.environment,
            database_status=db_status,
            scheduler_running=request.app.state.scheduler.is_running,
            provider_status=provider_status,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled exception", exc_info=exc, path=str(request.url))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app
