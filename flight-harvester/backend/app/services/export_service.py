from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models.all_flight_result import AllFlightResult
from app.models.route_group import RouteGroup


def export_route_group(
    route_group: RouteGroup,
    all_results: list[AllFlightResult],
) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet(title="All Results")
    headers = [
        "Date", "Dep Airport", "Arr Airport", "Airline",
        "Price", "Currency", "Stops", "Duration (min)", "Provider",
    ]
    _write_header_row(ws, headers)

    # Sort: date asc, price asc
    sorted_results = sorted(all_results, key=lambda r: (r.depart_date, r.price))

    provider_colors = {
        "serpapi": "DBEAFE",  # blue-100
    }

    for row_idx, r in enumerate(sorted_results, start=2):
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
        ws.cell(row=row_idx, column=9, value=r.provider)

        colour = provider_colors.get(r.provider.lower(), "F8FAFC")
        fill = PatternFill(start_color=colour, end_color=colour, fill_type="solid")
        for col in range(1, 10):
            ws.cell(row=row_idx, column=col).fill = fill

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
