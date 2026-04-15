"""
Admin-only endpoints for user management.

All routes here require the current user to have role='admin'.
Regular users cannot access these endpoints.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import RegisterRequest, UserAdminResponse
from app.services.auth_service import (
    create_user,
    deactivate_user,
    get_user_by_id,
    list_users,
    reactivate_user,
)

router = APIRouter(prefix="/users", tags=["users"])

_Admin = Annotated[User, Depends(require_admin)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/", response_model=list[UserAdminResponse])
async def list_all_users(session: _DB, _: _Admin) -> list[UserAdminResponse]:
    """Return all users. Admin only."""
    users = await list_users(session)
    return [UserAdminResponse.model_validate(u) for u in users]


@router.post("/", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    body: RegisterRequest, session: _DB, _: _Admin
) -> UserAdminResponse:
    """Create a new user (admin can assign any role by default it's 'user'). Admin only."""
    try:
        user = await create_user(
            session,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role="user",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserAdminResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserAdminResponse)
async def get_user(user_id: uuid.UUID, session: _DB, _: _Admin) -> UserAdminResponse:
    """Fetch a single user by ID. Admin only."""
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserAdminResponse.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=UserAdminResponse)
async def deactivate(user_id: uuid.UUID, session: _DB, admin: _Admin) -> UserAdminResponse:
    """Disable a user account (soft delete — they can no longer log in). Admin only."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    user = await deactivate_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserAdminResponse.model_validate(user)


@router.post("/{user_id}/reactivate", response_model=UserAdminResponse)
async def reactivate(user_id: uuid.UUID, session: _DB, _: _Admin) -> UserAdminResponse:
    """Re-enable a deactivated user account. Admin only."""
    user = await reactivate_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserAdminResponse.model_validate(user)
