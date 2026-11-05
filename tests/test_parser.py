"""Tests for the pure HTML parsing functions."""

from __future__ import annotations

import pytest

from books_scraper.parser import (
    make_soup,
    parse_categories,
    parse_detail,
    parse_listing,
    parse_next_page,
    parse_price,
    parse_rating,
    parse_stock_count,
)

PAGE1 = "https://books.toscrape.com/catalogue/page-1.html"
PAGE2 = "https://books.toscrape.com/catalogue/page-2.html"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("£51.77", 51.77), ("Â£51.77", 51.77), (" £1,234.50 ", 1234.5), ("£10", 10.0)],
)
def test_parse_price(text: str, expected: float) -> None:
    assert parse_price(text) == expected


def test_parse_price_invalid() -> None:
    with pytest.raises(ValueError):
        parse_price("free")


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<p class="star-rating Three"></p>', 3),
        ('<p class="star-rating Five"></p>', 5),
        ('<p class="star-rating"></p>', 0),
    ],
)
def test_parse_rating(html: str, expected: int) -> None:
    assert parse_rating(make_soup(html).p) == expected


def test_parse_rating_missing_tag() -> None:
    assert parse_rating(None) == 0


def test_parse_stock_count() -> None:
    assert parse_stock_count("In stock (22 available)") == 22
    assert parse_stock_count("In stock") is None
    assert parse_stock_count("") is None


def test_parse_listing_fields(catalogue_page1: bytes) -> None:
    books = parse_listing(catalogue_page1, PAGE1)
    assert len(books) == 3

    first = books[0]
    assert first.title == "A Light in the Attic"  # full title from @title, not truncated text
    assert first.price == 51.77
    assert first.in_stock is True
    assert first.availability is None  # count only exists on the detail page
    assert first.rating == 3
    assert first.category is None
    assert first.upc is None
    assert first.url == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert first.image_url == (
        "https://books.toscrape.com/media/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg"
    )
    assert [b.rating for b in books] == [3, 1, 5]


def test_parse_listing_attaches_category(catalogue_page1: bytes) -> None:
    books = parse_listing(catalogue_page1, PAGE1, category="Travel")
    assert {b.category for b in books} == {"Travel"}


def test_parse_listing_skips_malformed_cards(catalogue_page2: bytes) -> None:
    books = parse_listing(catalogue_page2, PAGE2)
    assert [b.title for b in books] == ["In Her Wake"]


def test_parse_listing_empty_page() -> None:
    assert parse_listing("<html><body></body></html>", PAGE1) == []


def test_parse_next_page(catalogue_page1: bytes, catalogue_page2: bytes) -> None:
    assert parse_next_page(catalogue_page1, PAGE1) == PAGE2
    assert parse_next_page(catalogue_page2, PAGE2) is None


def test_parse_next_page_from_category_index() -> None:
    html = '<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>'
    url = "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
    assert parse_next_page(html, url) == (
        "https://books.toscrape.com/catalogue/category/books/mystery_3/page-2.html"
    )


def test_parse_categories(catalogue_page1: bytes) -> None:
    cats = parse_categories(catalogue_page1, PAGE1)
    assert list(cats) == ["Travel", "Mystery", "Historical Fiction"]  # "Books" root excluded
    assert cats["Travel"] == (
        "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"
    )


def test_parse_detail(product_detail: bytes) -> None:
    detail = parse_detail(product_detail)
    assert detail == {"upc": "a897fe39b1053632", "availability": 22, "category": "Poetry"}


def test_parse_detail_missing_table() -> None:
    assert parse_detail("<html></html>") == {"upc": None, "availability": None, "category": None}
