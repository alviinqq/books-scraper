"""Shared pytest fixtures: saved HTML pages and an offline fake session."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from books_scraper.models import Book

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    """Read a fixture file as bytes (like ``response.content``)."""
    return (FIXTURES / name).read_bytes()


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, content: bytes | None, url: str) -> None:
        self.content = content or b""
        self.status_code = 200 if content is not None else 404
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for {self.url}")


class FakeSession:
    """Serves fixture pages by URL and records every request made."""

    def __init__(self, pages: dict[str, bytes]) -> None:
        self.pages = pages
        self.requested: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: float | None = None) -> FakeResponse:
        self.requested.append(url)
        return FakeResponse(self.pages.get(url), url)


@pytest.fixture
def catalogue_page1() -> bytes:
    return load("catalogue_page1.html")


@pytest.fixture
def catalogue_page2() -> bytes:
    return load("catalogue_page2.html")


@pytest.fixture
def product_detail() -> bytes:
    return load("product_detail.html")


@pytest.fixture
def sample_books() -> list[Book]:
    return [
        Book("A Light in the Attic", 51.77, True, 22, 3, "Poetry",
             "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
             "https://books.toscrape.com/media/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg",
             "a897fe39b1053632"),
        Book("Tipping the Velvet", 53.74, True, None, 1, None,
             "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
             "https://books.toscrape.com/media/cache/26/0c/260c6ae16bce31c8f8c95daddd9f4a1c.jpg"),
    ]
