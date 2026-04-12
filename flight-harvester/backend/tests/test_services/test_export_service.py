from __future__ import annotations

import uuid
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import MagicMock

import openpyxl
import pytest

from app.services.export_service import export_route_group


# ── helpers ──────────────────────────────────────────────────────────────────

def make_route_group(
    origins: list[str] = None,
    destinations: list[str] = None,
    sheet_name_map: dict | None = None,
    special_sheets: list | None = None,
    days_ahead: int = 5,
) -> MagicMock:
    rg = MagicMock()
    rg.id = uuid.uuid4()
    rg.name = "Test Group"
    rg.destination_label = "TYO/SHA"
    rg.destinations = destinations or ["TYO", "SHA"]
    rg.origins = origins or ["YYZ", "YVR"]
    rg.nights = 12
    rg.days_ahead = days_ahead
    rg.sheet_name_map = sheet_name_map or {"YYZ": "YYZ", "YVR": "YVR"}
    rg.special_sheets = special_sheets or []
    return rg


def make_price(
    origin: str,
    destination: str,
    depart_date: date,
    price: float = 1500.0,
    airline: str = "AC",
) -> MagicMock:
    p = MagicMock()
    p.origin = origin
    p.destination = destination
    p.depart_date = depart_date
    p.price = price
    p.airline = airline
    p.currency = "CAD"
    return p


# ── tests ─────────────────────────────────────────────────────────────────────

def test_export_generates_correct_sheet_names() -> None:
    rg = make_route_group()
    excel_bytes = export_route_group(rg, [])
    wb = openpyxl.load_workbook(BytesIO(excel_bytes))
    assert "YYZ" in wb.sheetnames
    assert "YVR" in wb.sheetnames


def test_export_has_correct_headers() -> None:
    rg = make_route_group(origins=["YYZ"])
    rg.origins = ["YYZ"]
    rg.sheet_name_map = {"YYZ": "YYZ"}
    excel_bytes = export_route_group(rg, [])
    wb = openpyxl.load_workbook(BytesIO(excel_bytes))
    ws = wb["YYZ"]
    assert ws.cell(1, 1).value == "Date"
    assert ws.cell(1, 2).value == "Dep Airport"
    assert ws.cell(1, 3).value == "Arrivel Airport"  # intentional typo from client
    assert ws.cell(1, 4).value == "Night "            # trailing space from client
    assert ws.cell(1, 5).value == "Airline"
    assert ws.cell(1, 6).value == "Flight Price"


def test_export_prices_are_integers() -> None:
    rg = make_route_group(origins=["YYZ"], days_ahead=3)
    rg.origins = ["YYZ"]
    rg.sheet_name_map = {"YYZ": "YYZ"}
    tomorrow = date.today() + timedelta(days=1)
    price = make_price("YYZ", "TYO", tomorrow, price=1587.50)

    excel_bytes = export_route_group(rg, [price])
    wb = openpyxl.load_workbook(BytesIO(excel_bytes))
    ws = wb["YYZ"]
    # row 2 = tomorrow
    assert ws.cell(2, 6).value == 1588


def test_export_missing_dates_show_dash() -> None:
    rg = make_route_group(origins=["YYZ"], days_ahead=3)
    rg.origins = ["YYZ"]
    rg.sheet_name_map = {"YYZ": "YYZ"}
    # No prices provided
    excel_bytes = export_route_group(rg, [])
    wb = openpyxl.load_workbook(BytesIO(excel_bytes))
    ws = wb["YYZ"]
    assert ws.cell(2, 5).value == "-"
    assert ws.cell(2, 6).value == "-"


def test_special_sheet_has_4_columns() -> None:
    special = {
        "name": "Osaka to Beijing",
        "origin": "KIX",
        "destination_label": "Beijing (Any)",
        "destinations": ["BJS", "PEK"],
        "columns": 4,
    }
    rg = make_route_group(origins=["YYZ"], days_ahead=2, special_sheets=[special])
    rg.origins = ["YYZ"]
    rg.sheet_name_map = {"YYZ": "YYZ"}

    excel_bytes = export_route_group(rg, [])
    wb = openpyxl.load_workbook(BytesIO(excel_bytes))
    assert "Osaka to Beijing" in wb.sheetnames
    ws = wb["Osaka to Beijing"]
    assert ws.cell(1, 1).value == "Date"
    assert ws.cell(1, 2).value == "Dep Airport"
    assert ws.cell(1, 3).value == "Arrivel Airport"
    assert ws.cell(1, 4).value == "Flight Price"
    # Column 5 should not exist (only 4 cols)
    assert ws.cell(1, 5).value is None


def test_export_cheapest_across_destinations() -> None:
    """When multiple destinations have prices, keep the cheapest."""
    rg = make_route_group(origins=["YYZ"], days_ahead=3)
    rg.origins = ["YYZ"]
    rg.sheet_name_map = {"YYZ": "YYZ"}
    tomorrow = date.today() + timedelta(days=1)
    cheap = make_price("YYZ", "TYO", tomorrow, price=1200.0, airline="AC")
    expensive = make_price("YYZ", "SHA", tomorrow, price=1800.0, airline="UA")

    excel_bytes = export_route_group(rg, [cheap, expensive])
    wb = openpyxl.load_workbook(BytesIO(excel_bytes))
    ws = wb["YYZ"]
    assert ws.cell(2, 6).value == 1200
    assert ws.cell(2, 5).value == "AC"


def test_export_uses_sheet_name_map() -> None:
    rg = make_route_group(
        origins=["YYZ", "YVR"],
        sheet_name_map={"YYZ": "YYZ-DPS", "YVR": "YVR-DPS"},
    )
    excel_bytes = export_route_group(rg, [])
    wb = openpyxl.load_workbook(BytesIO(excel_bytes))
    assert "YYZ-DPS" in wb.sheetnames
    assert "YVR-DPS" in wb.sheetnames
    assert "YYZ" not in wb.sheetnames
