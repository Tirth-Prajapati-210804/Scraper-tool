"""
SearchLeg model — one flight segment within a SearchProfile.

A single-destination profile has one leg (leg_order=0, min_halt_hours=None).
A multi-city profile has multiple legs:
    Leg 0: AMD → BOM, min_halt_hours=6   (wait at least 6h in Mumbai)
    Leg 1: BOM → DEL, min_halt_hours=24  (wait at least 24h in Delhi)
    Leg 2: DEL → JFK, min_halt_hours=None (final destination)

Each leg is collected independently by the scheduler. The UI combines leg prices
to show the total journey cost across all legs for a given date window.
"""
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
    # 0-based position within the profile (leg 0 = first flight)
    leg_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # What the user typed — stored so the UI can always show the original intent
    # e.g. "India", "Canada", "Tokyo", "AMD, BOM"
    origin_query: Mapped[str] = mapped_column(String(200), nullable=False)
    destination_query: Mapped[str] = mapped_column(String(200), nullable=False)

    # IATA codes resolved at creation time from origin_query / destination_query.
    # Stored as JSON arrays to avoid re-running location resolution every cycle.
    # e.g. resolved_origins = ["DEL", "BOM", "MAA", "BLR"] for origin_query = "India"
    resolved_origins: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    resolved_destinations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Minimum wait time between this leg's arrival and the next leg's departure.
    # NULL means this is the final leg — no onward flight to connect to.
    min_halt_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_halt_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    profile: Mapped[SearchProfile] = relationship("SearchProfile", back_populates="legs")
    prices: Mapped[list[FlightPrice]] = relationship("FlightPrice", back_populates="leg", cascade="all, delete-orphan")

    # Enforce unique leg positions per profile — prevents accidentally creating
    # two "leg 1" entries for the same profile
    __table_args__ = (
        sa.UniqueConstraint("profile_id", "leg_order", name="uq_search_legs_profile_order"),
    )
