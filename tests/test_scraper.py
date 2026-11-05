"""Tests for the crawler, using a fake session instead of the network."""

from __future__ import annotations

import pytest

from books_scraper.scraper import CATALOGUE_URL, USER_AGENT, BooksScraper, build_session

from .conftest import FakeSession

PAGE2 = "https://books.toscrape.com/catalogue/page-2.html"
ATTIC = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
TRAVEL = "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"


@pytest.fixture
def session(catalogue_page1: bytes, catalogue_page2: bytes, product_detail: bytes) -> FakeSession:
    return FakeSession(
        {
            CATALOGUE_URL: catalogue_page1,
            PAGE2: catalogue_page2,
            TRAVEL: catalogue_page2,
            ATTIC: product_detail,
        }
    )


def test_build_session_sets_user_agent_and_retries() -> None:
    s = build_session(retries=4)
    assert s.headers["User-Agent"] == USER_AGENT
    assert USER_AGENT.startswith("books-scraper/")
    assert "@" not in USER_AGENT
    assert s.get_adapter("https://books.toscrape.com").max_retries.total == 4


def test_scrape_single_page(session: FakeSession) -> None:
    books = BooksScraper(delay=0, session=session).scrape(max_pages=1)
    assert len(books) == 3
    assert session.requested == [CATALOGUE_URL]


def test_scrape_all_pages_follows_next(session: FakeSession) -> None:
    books = BooksScraper(delay=0, session=session).scrape(max_pages=None)
    assert len(books) == 4
    assert session.requested == [CATALOGUE_URL, PAGE2]


def test_scrape_category_case_insensitive(session: FakeSession) -> None:
    books = BooksScraper(delay=0, session=session).scrape(category="travel")
    assert [b.title for b in books] == ["In Her Wake"]
    assert books[0].category == "Travel"
    assert session.requested == [CATALOGUE_URL, TRAVEL]


def test_unknown_category_lists_options(session: FakeSession) -> None:
    with pytest.raises(ValueError, match="Available: Historical Fiction, Mystery, Travel"):
        BooksScraper(delay=0, session=session).scrape(category="Cooking")


def test_details_enrich_books_and_survive_errors(session: FakeSession) -> None:
    books = BooksScraper(delay=0, session=session).scrape(max_pages=1, details=True)
    attic = books[0]
    assert attic.upc == "a897fe39b1053632"
    assert attic.availability == 22
    assert attic.category == "Poetry"
    # Other detail pages are missing in the fake session (404) -> logged, not fatal.
    assert books[1].upc is None
    assert len(session.requested) == 1 + 3


def test_delay_between_requests(session: FakeSession, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("books_scraper.scraper.time.sleep", sleeps.append)
    BooksScraper(delay=5, session=session).scrape(max_pages=None)
    assert len(sleeps) == 1 and 4 < sleeps[0] <= 5  # no sleep before the first request
