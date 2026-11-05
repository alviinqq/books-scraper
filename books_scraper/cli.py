"""Command-line interface: ``python -m books_scraper --help``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import requests

from . import __version__
from .exporters import FORMATS, ExportError, export, export_google_sheet
from .scraper import BooksScraper

log = logging.getLogger("books_scraper")


def positive_int(value: str) -> int:
    """argparse type: integer >= 1."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return number


def non_negative_float(value: str) -> float:
    """argparse type: float >= 0."""
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="books_scraper",
        description="Scrape books.toscrape.com and export to CSV, XLSX or JSON.",
    )
    pages = parser.add_mutually_exclusive_group()
    pages.add_argument("-p", "--pages", type=positive_int, default=1,
                       help="number of listing pages to scrape (default: 1)")
    pages.add_argument("-a", "--all", action="store_true", help="scrape all pages")
    parser.add_argument("-c", "--category", help='category name, e.g. "Travel" (case-insensitive)')
    parser.add_argument("-f", "--format", choices=FORMATS, default="csv",
                        help="output format (default: csv)")
    parser.add_argument("-o", "--output", type=Path,
                        help="output file (default: output/books.<format>)")
    parser.add_argument("-d", "--delay", type=non_negative_float, default=1.0,
                        help="seconds between requests (default: 1.0)")
    parser.add_argument("--details", action="store_true",
                        help="also open each product page (UPC, exact stock count, category)")
    parser.add_argument("--list-categories", action="store_true",
                        help="print available categories and exit")
    parser.add_argument("--sheet", metavar="SPREADSHEET_ID",
                        help="also upload results to this Google Sheet (optional)")
    parser.add_argument("--credentials", type=Path, metavar="JSON",
                        help="service-account key file for --sheet")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.sheet and not args.credentials:
        parser.error("--sheet requires --credentials <service-account.json>")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    # urllib3 debug output is noisy; keep it at INFO unless asked.
    logging.getLogger("urllib3").setLevel(logging.INFO if args.verbose else logging.WARNING)

    scraper = BooksScraper(delay=args.delay)
    try:
        if args.list_categories:
            for name in sorted(scraper.get_categories()):
                print(name)
            return 0
        books = scraper.scrape(
            max_pages=None if args.all else args.pages,
            category=args.category,
            details=args.details,
        )
    except ValueError as exc:
        log.error("%s", exc)
        return 2
    except requests.RequestException as exc:
        log.error("Network error: %s", exc)
        return 1
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        return 130

    if not books:
        log.warning("No books found - nothing to export")
        return 1

    output = args.output or Path("output") / f"books.{args.format}"
    path = export(books, output, args.format)
    log.info("Saved %d books to %s", len(books), path)

    if args.sheet:
        try:
            url = export_google_sheet(books, args.sheet, args.credentials)
            log.info("Uploaded to Google Sheets: %s", url)
        except ExportError as exc:
            log.warning("Skipping Google Sheets export: %s", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
