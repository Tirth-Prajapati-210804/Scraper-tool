from __future__ import annotations

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FlightPrice(Base):
    __tablename__ = "flight_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    leg_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("search_legs.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False)

    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    destination: Mapped[str] = mapped_column(String(10), nullable=False)
    depart_date: Mapped[date] = mapped_column(Date, nullable=False)
    airline: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    leg: Mapped[SearchLeg] = relationship("SearchLeg", back_populates="prices")

    __table_args__ = (
        sa.UniqueConstraint("leg_id", "origin", "destination", "depart_date", name="uq_flight_prices_leg_route_date"),
    )
