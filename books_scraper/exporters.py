"""Export scraped books to CSV, JSON, XLSX or Google Sheets."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Book

FORMATS = ("csv", "xlsx", "json")


class ExportError(RuntimeError):
    """Raised when an export cannot be completed (e.g. missing dependency)."""


def _prepare(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def export_csv(books: Sequence[Book], path: str | Path) -> Path:
    """Write books to a UTF-8 CSV (with BOM so Excel shows "£" correctly)."""
    path = _prepare(path)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=Book.field_names())
        writer.writeheader()
        writer.writerows(b.to_dict() for b in books)
    return path


def export_json(books: Sequence[Book], path: str | Path) -> Path:
    """Write books to a pretty-printed JSON array."""
    path = _prepare(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump([b.to_dict() for b in books], fh, ensure_ascii=False, indent=2)
    return path


def export_xlsx(books: Sequence[Book], path: str | Path) -> Path:
    """Write books to a styled Excel workbook.

    Styling: bold white header on a dark fill, frozen header row, auto filter,
    auto-sized columns and a ``£#,##0.00`` number format for prices.
    """
    path = _prepare(path)
    columns = Book.field_names()
    wb = Workbook()
    ws = wb.active
    ws.title = "Books"
    ws.append(columns)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="305496")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for book in books:
        ws.append([book.to_dict()[c] for c in columns])

    price_col = columns.index("price") + 1
    for (cell,) in ws.iter_rows(min_row=2, min_col=price_col, max_col=price_col):
        cell.number_format = "£#,##0.00"

    for idx, name in enumerate(columns, 1):
        values = [name] + [str(v) for v in (b.to_dict()[name] for b in books) if v is not None]
        width = min(max(len(v) for v in values) + 2, 60)
        ws.column_dimensions[get_column_letter(idx)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)
    return path


EXPORTERS = {"csv": export_csv, "xlsx": export_xlsx, "json": export_json}


def export(books: Sequence[Book], path: str | Path, fmt: str) -> Path:
    """Dispatch to the exporter for ``fmt`` (one of :data:`FORMATS`)."""
    try:
        exporter = EXPORTERS[fmt]
    except KeyError:
        raise ValueError(f"Unsupported format {fmt!r}; choose from {FORMATS}") from None
    return exporter(books, path)


def export_google_sheet(
    books: Sequence[Book],
    spreadsheet_id: str,
    credentials_file: str | Path,
    worksheet: str = "Books",
) -> str:
    """Upload books to a Google Sheet using a service-account key.

    The spreadsheet must be shared with the service account's e-mail.
    Requires the optional ``gspread`` and ``google-auth`` packages.

    Returns:
        URL of the spreadsheet.

    Raises:
        ExportError: if the libraries or the credentials file are missing,
            or the API call fails.
    """
    try:
        import gspread  # type: ignore[import-not-found]
    except ImportError:
        raise ExportError(
            "Google Sheets export needs optional packages: pip install gspread google-auth"
        ) from None

    creds = Path(credentials_file)
    if not creds.is_file():
        raise ExportError(f"Credentials file not found: {creds}")

    try:
        client = gspread.service_account(filename=str(creds))
        spreadsheet = client.open_by_key(spreadsheet_id)
        try:
            ws = spreadsheet.worksheet(worksheet)
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(worksheet, rows=len(books) + 1, cols=len(Book.field_names()))
        rows = [Book.field_names()] + [
            ["" if v is None else v for v in b.to_dict().values()] for b in books
        ]
        ws.update(rows, "A1")
        ws.freeze(rows=1)
    except Exception as exc:  # gspread raises many different error types
        raise ExportError(f"Google Sheets export failed: {exc}") from exc
    return spreadsheet.url
