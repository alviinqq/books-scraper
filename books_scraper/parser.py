"""Pure HTML parsing functions for books.toscrape.com.

Nothing in this module touches the network, which keeps it easy to test
against saved HTML fixtures.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import Book

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

_PRICE_RE = re.compile(r"(\d+(?:\.\d+)?)")
_STOCK_RE = re.compile(r"\((\d+)\s+available\)")


def make_soup(html: str | bytes) -> BeautifulSoup:
    """Build a BeautifulSoup tree using the stdlib HTML parser."""
    return BeautifulSoup(html, "html.parser")


def parse_price(text: str) -> float:
    """Convert a price string such as ``"£51.77"`` to ``51.77``.

    Tolerates the mojibake ``"Â£51.77"`` produced when the page is decoded
    with the wrong charset.
    """
    match = _PRICE_RE.search(text.replace(",", ""))
    if not match:
        raise ValueError(f"Cannot parse price from {text!r}")
    return float(match.group(1))


def parse_rating(tag: Tag | None) -> int:
    """Read the star rating from ``<p class="star-rating Three">`` (0 if missing)."""
    if tag is None:
        return 0
    for cls in tag.get("class", []):
        if cls in RATING_WORDS:
            return RATING_WORDS[cls]
    return 0


def parse_stock_count(text: str) -> int | None:
    """Extract ``22`` from ``"In stock (22 available)"``; ``None`` if absent."""
    match = _STOCK_RE.search(text)
    return int(match.group(1)) if match else None


def _clean(text: str) -> str:
    """Collapse runs of whitespace into single spaces."""
    return " ".join(text.split())


def parse_listing(html: str | bytes, page_url: str, category: str | None = None) -> list[Book]:
    """Parse every ``article.product_pod`` on a catalogue / category page.

    Args:
        html: Raw page HTML.
        page_url: URL the page was fetched from; used to resolve relative links.
        category: Category name to attach to each book (known when scraping a
            category page, otherwise ``None``).
    """
    soup = make_soup(html)
    books: list[Book] = []
    for pod in soup.select("article.product_pod"):
        link = pod.select_one("h3 > a")
        price = pod.select_one("p.price_color")
        if link is None or price is None:
            continue  # malformed card - skip rather than crash
        availability = pod.select_one("p.instock.availability, p.availability")
        availability_text = _clean(availability.get_text()) if availability else ""
        img = pod.select_one("img")

        books.append(
            Book(
                title=link.get("title") or _clean(link.get_text()),
                price=parse_price(price.get_text()),
                in_stock=availability_text.lower().startswith("in stock"),
                availability=parse_stock_count(availability_text),
                rating=parse_rating(pod.select_one("p.star-rating")),
                category=category,
                url=urljoin(page_url, link["href"]),
                image_url=urljoin(page_url, img["src"]) if img and img.get("src") else "",
            )
        )
    return books


def parse_next_page(html: str | bytes, page_url: str) -> str | None:
    """Return the absolute URL of the next page, or ``None`` on the last page."""
    link = make_soup(html).select_one("li.next > a")
    return urljoin(page_url, link["href"]) if link and link.get("href") else None


def parse_categories(html: str | bytes, page_url: str) -> dict[str, str]:
    """Map category name -> absolute URL from the sidebar of any catalogue page."""
    soup = make_soup(html)
    return {
        _clean(a.get_text()): urljoin(page_url, a["href"])
        for a in soup.select("div.side_categories ul li ul li a")
    }


def parse_detail(html: str | bytes) -> dict[str, str | int | None]:
    """Extract detail-only fields from a product page.

    Returns a dict with ``upc``, ``availability`` (stock count) and ``category``.
    """
    soup = make_soup(html)
    table: dict[str, str] = {}
    for row in soup.select("table.table.table-striped tr"):
        th, td = row.find("th"), row.find("td")
        if th and td:
            table[_clean(th.get_text())] = _clean(td.get_text())

    # Breadcrumb: Home > Books > <Category> > <Title>
    crumbs = soup.select("ul.breadcrumb li a")
    category = _clean(crumbs[2].get_text()) if len(crumbs) >= 3 else None

    return {
        "upc": table.get("UPC"),
        "availability": parse_stock_count(table.get("Availability", "")),
        "category": category,
    }
