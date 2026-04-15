from __future__ import annotations

import time
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.services.auth_service import authenticate, create_user, issue_login_response

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple in-memory rate limiter: IP → list of attempt timestamps
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 5      # max attempts
_RATE_WINDOW = 60.0  # seconds


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if this IP has exceeded the login rate limit."""
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    attempts = [t for t in _login_attempts[ip] if t > window_start]
    _login_attempts[ip] = attempts
    if len(attempts) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a minute and try again.",
        )
    _login_attempts[ip].append(now)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    user = await authenticate(session, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return issue_login_response(user, settings)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    """
    Create a new user account. Anyone can register; new users get the 'user' role.
    Admins are only created via the seed process or by another admin promoting a user.
    """
    try:
        user = await create_user(
            session,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role="user",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)
