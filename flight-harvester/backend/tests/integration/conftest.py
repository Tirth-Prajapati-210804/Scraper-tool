"""
Integration test fixtures.

These tests require a real PostgreSQL instance. The DATABASE_URL env var
(set in the root conftest.py) points to the test DB. CI provisions PostgreSQL
as a service; locally, run `createdb flight_test` first.

Tables are created once per session via metadata.create_all, then TRUNCATED
between each test so each test starts with a clean slate.
"""
from __future__ import annotations

import uuid

import pytest
import httpx
import sqlalchemy as sa
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.app_factory import create_app
from app.core.security import hash_password
from app.db.base import Base
from app.models.user import User
# Import all models so their tables are registered in Base.metadata
import app.models  # noqa: F401

# ── Re-use the same DB URL the root conftest exports via env var ──────────────

import os

_DB_URL = os.environ["DATABASE_URL"]

_TEST_SETTINGS = Settings(
    _env_file=None,  # type: ignore[call-arg]
    database_url=_DB_URL,
    jwt_secret_key="integration-test-secret-that-is-32-chars!",
    admin_email="admin@integration.test",
    admin_password="IntegrationPass1!",
    scheduler_enabled=False,
    environment="test",
    debug=False,
    serpapi_key="",
    demo_mode=False,
)

_engine = create_async_engine(_DB_URL, pool_pre_ping=True)
_SessionFactory = async_sessionmaker(_engine, expire_on_commit=False)


# ── Helper: insert admin user (idempotent via ON CONFLICT DO NOTHING) ─────────

async def _seed_admin() -> None:
    """Create the test admin user. Safe to call multiple times."""
    async with _engine.begin() as conn:
        await conn.execute(
            pg_insert(User.__table__)
            .values(
                id=str(uuid.uuid4()),
                email=_TEST_SETTINGS.admin_email,
                hashed_password=hash_password(_TEST_SETTINGS.admin_password),
                full_name=_TEST_SETTINGS.admin_full_name,
                role="admin",
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=["email"])
        )


# ── Session-scoped: create tables once, seed admin ───────────────────────────

@pytest.fixture(scope="session", autouse=True)
async def create_tables():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # ASGITransport does not dispatch ASGI lifespan events, so ensure_default_admin
    # in app_factory.py never runs during tests. Seed the admin directly here.
    await _seed_admin()
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Function-scoped: wipe all rows before each test, re-seed admin ───────────

@pytest.fixture(autouse=True)
async def clean_db():
    yield
    async with _engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))
    # Re-seed admin so auth_client works for the next test
    await _seed_admin()


# ── App + HTTP client ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    return create_app(settings=_TEST_SETTINGS)


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ── Convenience: authenticated client ────────────────────────────────────────

@pytest.fixture
async def auth_client(client):
    """Client pre-authenticated as the default admin."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@integration.test", "password": "IntegrationPass1!"},
    )
    assert res.status_code == 200, f"Login fixture failed: {res.text}"
    token = res.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
