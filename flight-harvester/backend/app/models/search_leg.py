from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SearchLeg(Base):
    __tablename__ = "search_legs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False)
    leg_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # User-typed query strings
    origin_query: Mapped[str] = mapped_column(String(200), nullable=False)
    destination_query: Mapped[str] = mapped_column(String(200), nullable=False)

    # Resolved IATA codes (cached at creation time)
    resolved_origins: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    resolved_destinations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Halt requirement before the NEXT leg departs (NULL = final leg)
    min_halt_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_halt_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    profile: Mapped[SearchProfile] = relationship("SearchProfile", back_populates="legs")
    prices: Mapped[list[FlightPrice]] = relationship("FlightPrice", back_populates="leg", cascade="all, delete-orphan")

    __table_args__ = (
        sa.UniqueConstraint("profile_id", "leg_order", name="uq_search_legs_profile_order"),
    )
