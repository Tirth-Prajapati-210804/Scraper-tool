from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpecialSheetConfig(BaseModel):
    name: str
    origin: str
    destination_label: str
    destinations: list[str]
    columns: int = 4


class RouteGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    destination_label: str = Field(min_length=1, max_length=100)
    destinations: list[str] = Field(min_length=1)
    origins: list[str] = Field(min_length=1)
    nights: int = Field(ge=1, le=90, default=12)
    days_ahead: int = Field(ge=1, le=730, default=365)
    sheet_name_map: dict[str, str] = {}
    special_sheets: list[SpecialSheetConfig] = []
    currency: str = "USD"
    max_stops: int | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("destinations", "origins", mode="before")
    @classmethod
    def uppercase_iata(cls, v: object) -> list[str]:
        import re
        if isinstance(v, list):
            codes = [str(code).strip().upper() for code in v]
            for code in codes:
                if not re.match(r"^[A-Z0-9]{2,4}$", code):
                    raise ValueError(
                        f"'{code}' is not a valid IATA airport code. "
                        "Codes must be 2-4 uppercase letters or digits (e.g. YVR, DPS, TYO)."
                    )
            return codes
        return v  # type: ignore[return-value]


class RouteGroupUpdate(BaseModel):
    name: str | None = None
    destination_label: str | None = None
    destinations: list[str] | None = None
    origins: list[str] | None = None
    nights: int | None = Field(default=None, ge=1, le=90)
    days_ahead: int | None = Field(default=None, ge=1, le=730)
    sheet_name_map: dict[str, str] | None = None
    special_sheets: list[SpecialSheetConfig] | None = None
    is_active: bool | None = None
    currency: str | None = None
    max_stops: int | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("destinations", "origins", mode="before")
    @classmethod
    def uppercase_iata(cls, v: object) -> list[str] | None:
        import re
        if isinstance(v, list):
            codes = [str(code).strip().upper() for code in v]
            for code in codes:
                if not re.match(r"^[A-Z0-9]{2,4}$", code):
                    raise ValueError(
                        f"'{code}' is not a valid IATA airport code. "
                        "Codes must be 2-4 uppercase letters or digits (e.g. YVR, DPS, TYO)."
                    )
            return codes
        return v  # type: ignore[return-value]


class RouteGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    destination_label: str
    destinations: list[str]
    origins: list[str]
    nights: int
    days_ahead: int
    sheet_name_map: dict[str, str]
    special_sheets: list[SpecialSheetConfig]
    is_active: bool
    currency: str
    max_stops: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime


class RouteGroupFromTextCreate(BaseModel):
    """Create a route group using plain-text location names instead of raw IATA codes."""

    origin: str = Field(min_length=1, max_length=200, description="e.g. 'Canada' or 'Toronto'")
    destination: str = Field(min_length=1, max_length=200, description="e.g. 'Vietnam' or 'Tokyo'")
    nights: int = Field(ge=1, le=90, default=10)
    days_ahead: int = Field(ge=1, le=730, default=365)
    currency: str = "USD"
    max_stops: int | None = None
    start_date: date | None = None
    end_date: date | None = None


class RouteGroupFromTextResponse(BaseModel):
    """Response for /from-text endpoint — includes the created group plus resolved codes."""

    group: RouteGroupResponse
    resolved_origins: list[str]
    resolved_destinations: list[str]


class PerOriginProgress(BaseModel):
    total: int
    collected: int


class RouteGroupProgress(BaseModel):
    route_group_id: uuid.UUID
    name: str
    total_dates: int
    dates_with_data: int
    coverage_percent: float
    last_scraped_at: datetime | None
    per_origin: dict[str, PerOriginProgress]
    scraped_dates: list[str] = []
