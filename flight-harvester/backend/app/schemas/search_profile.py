from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SearchLegCreate(BaseModel):
    """One leg in a multi-city journey, specified using plain-text location names."""

    origin_query: str = Field(
        min_length=1,
        max_length=200,
        description="Country, city, or IATA code(s). E.g. 'India', 'Ahmedabad', 'AMD', 'TYO, SHA'",
    )
    destination_query: str = Field(
        min_length=1,
        max_length=200,
        description="Country, city, or IATA code(s). E.g. 'Delhi', 'DEL', 'Japan'",
    )
    min_halt_hours: float | None = Field(
        default=None,
        ge=0,
        description="Minimum wait at this destination before the next leg departs. NULL = final leg.",
    )
    max_halt_hours: float | None = Field(
        default=None,
        ge=0,
        description="Maximum wait at this destination. NULL = no upper limit.",
    )


class SearchProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    days_ahead: int = Field(ge=1, le=730, default=365)
    is_active: bool = True
    legs: list[SearchLegCreate] = Field(min_length=1)


class SearchProfileUpdate(BaseModel):
    name: str | None = None
    days_ahead: int | None = Field(default=None, ge=1, le=730)
    is_active: bool | None = None


# ── Response schemas ──────────────────────────────────────────────────────────

class SearchLegResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    leg_order: int
    origin_query: str
    destination_query: str
    resolved_origins: list[str]
    resolved_destinations: list[str]
    min_halt_hours: float | None
    max_halt_hours: float | None


class SearchProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    days_ahead: int
    legs: list[SearchLegResponse]
    created_at: datetime
    updated_at: datetime


class FlightPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    leg_id: uuid.UUID
    profile_id: uuid.UUID
    origin: str
    destination: str
    depart_date: str   # ISO date string
    airline: str
    price: float
    currency: str
    provider: str
    deep_link: str | None
    stops: int | None
    duration_minutes: int | None
    scraped_at: datetime


class ProfileProgressLeg(BaseModel):
    leg_id: uuid.UUID
    leg_order: int
    origin_query: str
    destination_query: str
    total_slots: int
    filled_slots: int
    coverage_percent: float


class SearchProfileProgress(BaseModel):
    profile_id: uuid.UUID
    name: str
    total_slots: int
    filled_slots: int
    coverage_percent: float
    last_scraped_at: datetime | None
    legs: list[ProfileProgressLeg]
