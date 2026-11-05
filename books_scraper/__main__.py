"""Allow ``python -m books_scraper``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
