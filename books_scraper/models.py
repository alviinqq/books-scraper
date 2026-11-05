"""Data model for a scraped book."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass
class Book:
    """A single book as scraped from books.toscrape.com.

    ``availability`` (exact stock count) and ``upc`` are only shown on the
    product detail page, so they stay ``None`` unless the scraper runs with
    ``--details``. ``category`` is known when filtering by category or when
    detail pages are scraped.
    """

    title: str
    price: float  # GBP
    in_stock: bool
    availability: int | None  # number of copies in stock
    rating: int  # 1-5, 0 if unknown
    category: str | None
    url: str
    image_url: str
    upc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the book as a plain dict (field order preserved)."""
        return asdict(self)

    @classmethod
    def field_names(cls) -> list[str]:
        """Column names in export order."""
        return [f.name for f in fields(cls)]
