from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginResponse, UserResponse


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(
    session: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    role: str = "user",
) -> User:
    """Create a new user. Raises ValueError if the email is already registered."""
    existing = await get_user_by_email(session, email)
    if existing:
        raise ValueError(f"Email '{email}' is already registered.")
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def list_users(session: AsyncSession) -> list[User]:
    """Return all users ordered by creation date. Admin-only."""
    result = await session.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def deactivate_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Deactivate (soft-delete) a user. Returns None if not found."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    user.is_active = False
    await session.commit()
    await session.refresh(user)
    return user


async def reactivate_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Re-enable a deactivated user. Returns None if not found."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    return user


async def ensure_default_admin(session: AsyncSession, settings: Settings) -> None:
    existing = await get_user_by_email(session, settings.admin_email)
    if existing:
        return
    admin = User(
        email=settings.admin_email,
        hashed_password=hash_password(settings.admin_password),
        full_name=settings.admin_full_name,
        role="admin",
        is_active=True,
    )
    session.add(admin)
    await session.commit()


def issue_login_response(user: User, settings: Settings) -> LoginResponse:
    token = create_access_token(
        subject=str(user.id),
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_access_token_expire_minutes,
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )
