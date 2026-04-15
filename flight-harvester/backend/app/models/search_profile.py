"""
SearchProfile model — a named set of flight legs the system tracks continuously.

A profile like "India to Canada" contains one or more SearchLeg rows. The scheduler
runs collection cycles for every active profile on its configured interval.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # When False the scheduler skips this profile entirely (user has paused it)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # How many days into the future to search (e.g. 365 = search the next year of dates)
    days_ahead: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Ordered list of legs (leg_order 0, 1, 2, ...) — cascade delete removes all
    # legs and their collected prices when the profile is deleted
    legs: Mapped[list[SearchLeg]] = relationship("SearchLeg", back_populates="profile", cascade="all, delete-orphan", order_by="SearchLeg.leg_order")
