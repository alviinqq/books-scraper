"""Tests for the command-line interface (network replaced by a stub)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from books_scraper import cli
from books_scraper.models import Book


@pytest.fixture
def stub_scrape(monkeypatch: pytest.MonkeyPatch, sample_books: list[Book]) -> dict:
    calls: dict = {}

    def fake_scrape(self, max_pages=1, category=None, details=False):  # noqa: ANN001
        calls.update(max_pages=max_pages, category=category, details=details)
        return sample_books

    monkeypatch.setattr(cli.BooksScraper, "scrape", fake_scrape)
    return calls


def test_cli_exports_json(tmp_path: Path, stub_scrape: dict) -> None:
    out = tmp_path / "books.json"
    code = cli.main(["--all", "-c", "Poetry", "--details", "-f", "json", "-o", str(out)])
    assert code == 0
    assert stub_scrape == {"max_pages": None, "category": "Poetry", "details": True}
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 2


def test_cli_sheet_requires_credentials(stub_scrape: dict) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--sheet", "abc"])


def test_cli_rejects_bad_values() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--pages", "0"])
    with pytest.raises(SystemExit):
        cli.main(["--delay", "-1"])


def test_cli_sheet_failure_is_not_fatal(
    tmp_path: Path, stub_scrape: dict, caplog: pytest.LogCaptureFixture
) -> None:
    out = tmp_path / "books.csv"
    code = cli.main(["-o", str(out), "--sheet", "abc", "--credentials", str(tmp_path / "no.json")])
    assert code == 0
    assert out.exists()
    assert "Skipping Google Sheets export" in caplog.text
