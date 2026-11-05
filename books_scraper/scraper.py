"""Network layer: polite HTTP session and crawling logic."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import __version__
from .models import Book
from .parser import parse_categories, parse_detail, parse_listing, parse_next_page

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_URL = BASE_URL + "catalogue/page-1.html"
USER_AGENT = f"books-scraper/{__version__}"

log = logging.getLogger(__name__)


def build_session(retries: int = 3, backoff: float = 1.0) -> requests.Session:
    """Create a ``requests.Session`` with a User-Agent and retry/backoff policy.

    Retries cover connection errors and HTTP 429/5xx responses; the wait time
    grows exponentially (``backoff * 2 ** (attempt - 1)`` seconds).
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class BooksScraper:
    """Crawl catalogue pages (and optionally product pages) of books.toscrape.com.

    Args:
        delay: Seconds to wait between consecutive requests.
        timeout: Per-request timeout in seconds.
        session: Optional pre-configured session (handy for tests).
    """

    def __init__(
        self,
        delay: float = 1.0,
        timeout: float = 15.0,
        session: requests.Session | None = None,
    ) -> None:
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.session = session or build_session()
        self._last_request: float | None = None

    # ------------------------------------------------------------------ HTTP
    def fetch(self, url: str) -> bytes:
        """GET ``url`` respecting the configured delay; return raw bytes.

        Bytes (not ``response.text``) are returned so BeautifulSoup can pick up
        the charset from the page's ``<meta>`` tag and decode "£" correctly.
        """
        if self._last_request is not None:
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        log.debug("GET %s", url)
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        finally:
            self._last_request = time.monotonic()
        return response.content

    # ------------------------------------------------------------ categories
    def get_categories(self) -> dict[str, str]:
        """Return a mapping of category name -> category URL."""
        return parse_categories(self.fetch(CATALOGUE_URL), CATALOGUE_URL)

    def resolve_category(self, name: str) -> tuple[str, str]:
        """Find a category by case-insensitive name; return ``(name, url)``.

        Raises:
            ValueError: if no such category exists (message lists valid ones).
        """
        categories = self.get_categories()
        for cat_name, url in categories.items():
            if cat_name.lower() == name.strip().lower():
                return cat_name, url
        available = ", ".join(sorted(categories))
        raise ValueError(f"Unknown category {name!r}. Available: {available}")

    # -------------------------------------------------------------- crawling
    def iter_listing(
        self,
        start_url: str,
        max_pages: int | None = 1,
        category: str | None = None,
    ) -> Iterator[Book]:
        """Yield books page by page, following ``li.next`` links.

        Args:
            start_url: First listing page.
            max_pages: Stop after this many pages (``None`` = all pages).
            category: Category name to attach to each book, if known.
        """
        url: str | None = start_url
        page = 0
        while url and (max_pages is None or page < max_pages):
            page += 1
            html = self.fetch(url)
            books = parse_listing(html, url, category=category)
            log.info("Page %d: %d books (%s)", page, len(books), url)
            yield from books
            url = parse_next_page(html, url)

    def enrich(self, book: Book) -> Book:
        """Fill detail-page fields (UPC, exact stock, category) in place."""
        detail = parse_detail(self.fetch(book.url))
        book.upc = detail["upc"]  # type: ignore[assignment]
        if detail["availability"] is not None:
            book.availability = detail["availability"]  # type: ignore[assignment]
        book.category = book.category or detail["category"]  # type: ignore[assignment]
        return book

    def scrape(
        self,
        max_pages: int | None = 1,
        category: str | None = None,
        details: bool = False,
    ) -> list[Book]:
        """Run a full scrape and return the collected books.

        Args:
            max_pages: Number of listing pages (``None`` = all).
            category: Optional category name filter.
            details: Also visit every product page for UPC / stock count.
        """
        if category:
            category, start_url = self.resolve_category(category)
            log.info("Category: %s", category)
        else:
            start_url = CATALOGUE_URL

        books = list(self.iter_listing(start_url, max_pages, category))

        if details:
            total = len(books)
            for i, book in enumerate(books, 1):
                try:
                    self.enrich(book)
                except requests.RequestException as exc:
                    log.warning("Details failed for %s: %s", book.url, exc)
                if i % 20 == 0 or i == total:
                    log.info("Details: %d/%d", i, total)
        return books
