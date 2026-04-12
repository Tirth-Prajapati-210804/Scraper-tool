from __future__ import annotations

import uuid
from datetime import datetime

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

    @field_validator("destinations", "origins", mode="before")
    @classmethod
    def uppercase_iata(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return [str(code).strip().upper() for code in v]
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

    @field_validator("destinations", "origins", mode="before")
    @classmethod
    def uppercase_iata(cls, v: object) -> list[str] | None:
        if isinstance(v, list):
            return [str(code).strip().upper() for code in v]
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
    created_at: datetime
    updated_at: datetime


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
