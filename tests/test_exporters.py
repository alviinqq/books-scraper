"""Tests for CSV / JSON / XLSX exporters and the optional Google Sheets path."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

from books_scraper.exporters import ExportError, export, export_google_sheet
from books_scraper.models import Book


def test_export_csv(tmp_path: Path, sample_books: list[Book]) -> None:
    path = export(sample_books, tmp_path / "out" / "books.csv", "csv")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == Book.field_names()
    assert rows[0]["title"] == "A Light in the Attic"
    assert rows[0]["price"] == "51.77"
    assert rows[1]["availability"] == ""


def test_export_json(tmp_path: Path, sample_books: list[Book]) -> None:
    path = export(sample_books, tmp_path / "books.json", "json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["price"] == 51.77
    assert data[0]["availability"] == 22
    assert data[1]["upc"] is None


def test_export_xlsx(tmp_path: Path, sample_books: list[Book]) -> None:
    path = export(sample_books, tmp_path / "books.xlsx", "xlsx")
    ws = load_workbook(path).active
    header = [c.value for c in ws[1]]
    assert header == Book.field_names()
    assert ws.max_row == 3
    assert ws.freeze_panes == "A2"
    assert ws["A1"].font.bold

    price_col = header.index("price") + 1
    price_cell = ws.cell(row=2, column=price_col)
    assert price_cell.value == 51.77
    assert "£" in price_cell.number_format
    assert ws.column_dimensions["A"].width >= len("A Light in the Attic")


def test_export_unknown_format(tmp_path: Path, sample_books: list[Book]) -> None:
    with pytest.raises(ValueError):
        export(sample_books, tmp_path / "books.xml", "xml")


def test_google_sheet_without_library(
    tmp_path: Path, sample_books: list[Book], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "gspread", None)  # makes `import gspread` fail
    with pytest.raises(ExportError, match="pip install gspread"):
        export_google_sheet(sample_books, "sheet-id", tmp_path / "creds.json")


def test_google_sheet_missing_credentials(tmp_path: Path, sample_books: list[Book]) -> None:
    pytest.importorskip("gspread")
    with pytest.raises(ExportError, match="Credentials file not found"):
        export_google_sheet(sample_books, "sheet-id", tmp_path / "missing.json")
