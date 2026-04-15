from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.models.all_flight_result import AllFlightResult
from app.models.daily_cheapest import DailyCheapestPrice
from app.models.route_group import RouteGroup


def export_route_group(
    route_group: RouteGroup,
    prices: list[DailyCheapestPrice],
    all_results: list[AllFlightResult] | None = None,
) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    # Build price lookup: (origin, destination) -> {depart_date: price_row}
    price_lookup: dict[tuple[str, str], dict[date, DailyCheapestPrice]] = {}
    for p in prices:
        key = (p.origin, p.destination)
        if key not in price_lookup:
            price_lookup[key] = {}
        price_lookup[key][p.depart_date] = p

    today = date.today()
    all_dates = [today + timedelta(days=i) for i in range(1, route_group.days_ahead + 1)]

    # --- Main sheets (cheapest price per date per origin) ---
    for origin in route_group.origins:
        name_map = route_group.sheet_name_map or {}
        sheet_name = name_map.get(origin, origin)
        ws = wb.create_sheet(title=sheet_name)

        headers = ["Date", "Dep Airport", "Arrivel Airport", "Night ", "Airline", "Flight Price"]
        _write_header_row(ws, headers)

        # Collect cheapest across all destinations for this origin
        origin_prices: dict[date, DailyCheapestPrice] = {}
        for dest in route_group.destinations:
            for d, p in price_lookup.get((origin, dest), {}).items():
                if d not in origin_prices or p.price < origin_prices[d].price:
                    origin_prices[d] = p

        for row_idx, d in enumerate(all_dates, start=2):
            ws.cell(row=row_idx, column=1, value=d)
            ws.cell(row=row_idx, column=1).number_format = "YYYY-MM-DD"
            ws.cell(row=row_idx, column=2, value=origin)
            ws.cell(row=row_idx, column=3, value=route_group.destination_label)
            ws.cell(row=row_idx, column=4, value=route_group.nights)

            if d in origin_prices:
                p = origin_prices[d]
                ws.cell(row=row_idx, column=5, value=p.airline)
                ws.cell(row=row_idx, column=6, value=int(round(float(p.price))))
            else:
                ws.cell(row=row_idx, column=5, value="-")
                ws.cell(row=row_idx, column=6, value="-")

        _autosize_columns(ws)

    # --- Special sheets (4 columns) ---
    for special in route_group.special_sheets or []:
        if isinstance(special, dict):
            spec = special
        else:
            spec = special.model_dump() if hasattr(special, "model_dump") else dict(special)

        ws = wb.create_sheet(title=spec.get("name", "Special"))
        headers = ["Date", "Dep Airport", "Arrivel Airport", "Flight Price"]
        _write_header_row(ws, headers)

        spec_origin = spec.get("origin", "")
        spec_dests = spec.get("destinations", [])
        spec_label = spec.get("destination_label", "")

        spec_prices: dict[date, DailyCheapestPrice] = {}
        for dest in spec_dests:
            for d, p in price_lookup.get((spec_origin, dest), {}).items():
                if d not in spec_prices or p.price < spec_prices[d].price:
                    spec_prices[d] = p

        for row_idx, d in enumerate(all_dates, start=2):
            ws.cell(row=row_idx, column=1, value=d)
            ws.cell(row=row_idx, column=1).number_format = "YYYY-MM-DD"
            ws.cell(row=row_idx, column=2, value=spec_origin)
            ws.cell(row=row_idx, column=3, value=spec_label)

            if d in spec_prices:
                ws.cell(row=row_idx, column=4, value=int(round(float(spec_prices[d].price))))
            else:
                ws.cell(row=row_idx, column=4, value="-")

        _autosize_columns(ws)

    # --- Per-provider sheets ---
    # One sheet per provider (e.g. "SerpAPI", "Travelpayouts", "Mock"), each
    # containing every offer that provider returned, sorted by date then price.
    if all_results:
        # Pretty-print names for sheet titles
        provider_display = {
            "serpapi":       "SerpAPI",
            "travelpayouts": "Travelpayouts",
            "mock":          "Mock",
        }

        # Group results by provider, preserving insertion order
        by_provider: dict[str, list[AllFlightResult]] = {}
        for r in all_results:
            key = r.provider.lower()
            if key not in by_provider:
                by_provider[key] = []
            by_provider[key].append(r)

        headers = [
            "Date", "Dep Airport", "Arr Airport", "Airline",
            "Price", "Currency", "Stops", "Duration (min)",
        ]

        for provider_key, provider_rows in by_provider.items():
            sheet_title = provider_display.get(provider_key, provider_key.title())
            ws = wb.create_sheet(title=sheet_title)
            _write_header_row(ws, headers)

            # Sort each provider's rows: date asc, price asc
            sorted_rows = sorted(provider_rows, key=lambda r: (r.depart_date, r.price))

            for row_idx, r in enumerate(sorted_rows, start=2):
                ws.cell(row=row_idx, column=1, value=r.depart_date)
                ws.cell(row=row_idx, column=1).number_format = "YYYY-MM-DD"
                ws.cell(row=row_idx, column=2, value=r.origin)
                ws.cell(row=row_idx, column=3, value=r.destination)
                ws.cell(row=row_idx, column=4, value=r.airline or "-")
                ws.cell(row=row_idx, column=5, value=int(round(float(r.price))))
                ws.cell(row=row_idx, column=6, value=r.currency)
                ws.cell(row=row_idx, column=7, value=r.stops if r.stops is not None else "-")
                ws.cell(
                    row=row_idx, column=8,
                    value=r.duration_minutes if r.duration_minutes else "-",
                )

            _autosize_columns(ws)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def _write_header_row(ws: object, headers: list[str]) -> None:
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)  # type: ignore[union-attr]
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")


def _autosize_columns(ws: object) -> None:
    for col_cells in ws.columns:  # type: ignore[union-attr]
        max_length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=0)
        col_letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[col_letter].width = max_length + 3  # type: ignore[union-attr]
