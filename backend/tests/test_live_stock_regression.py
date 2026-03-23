"""
Live regression tests for stock availability (in_stock) extraction.

DEPRECATED — superseded by test_live_cases.py which drives per-field
assertions (including in_stock) from tests/cases.json.  Kept for
backward compatibility.

For each goodcase and badcase URL this suite records whether the scraper
was able to extract a definitive stock status (True/False) or got nothing
(None).  The test itself never fails on None — some sites genuinely don't
expose availability data.  A failure means the extractor raised an
unexpected exception or returned a non-bool non-None value.

Run with:
    pytest --run-live tests/test_live_stock_regression.py -v
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.dispatcher import extract_product_data
from app.scrapers.fetcher import (
    CookiesExpiredError,
    SiteBlockedError,
    fetch_page,
)
from app.scrapers.schemas import ProductData

TESTS_DIR = Path(__file__).parent
GOODCASE_FILE = TESTS_DIR / "goodcase" / "url.txt"
BADCASE_FILE = TESTS_DIR / "badcase" / "url.txt"


def _load_urls(path: Path) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def _make_db_mock():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock
    return db


GOODCASE_URLS = _load_urls(GOODCASE_FILE)
BADCASE_URLS = _load_urls(BADCASE_FILE)


# ---------------------------------------------------------------------------
# Goodcase: pages we can successfully scrape — stock status should extract
# cleanly (True, False, or None if the site doesn't expose it).
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("url", GOODCASE_URLS)
async def test_goodcase_live_in_stock_extractable(url: str):
    """
    in_stock must be True, False, or None — never an unexpected type.
    Logs the result so the output serves as a site-by-site audit of
    which platforms expose availability data.
    """
    db = _make_db_mock()
    try:
        html = await fetch_page(url)
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Playwright browser runtime is not installed")
        pytest.skip(f"fetch failed — not a stock-extraction issue: {exc}")

    with patch(
        "app.scrapers.dispatcher.extract_with_llm",
        new=AsyncMock(return_value=ProductData(url=url)),
    ):
        result, _ = await extract_product_data(html, url, db)

    assert result.in_stock in (True, False, None), (
        f"in_stock must be bool or None, got {result.in_stock!r}"
    )

    status = "in_stock=True" if result.in_stock is True else (
        "in_stock=False" if result.in_stock is False else "in_stock=None (not exposed)"
    )
    print(f"\n  {url}\n  → {status}")


# ---------------------------------------------------------------------------
# Badcase: pages behind bot-protection or JS walls — we may not be able to
# fetch them at all.  When we do get HTML, stock extraction is still valid.
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("url", BADCASE_URLS)
async def test_badcase_live_in_stock_valid_when_fetchable(url: str):
    """
    For badcase URLs that we can actually fetch, in_stock must still be a
    valid type.  When fetch fails (blocked/expired), the test is skipped —
    the inability to fetch is the known bad condition, not a stock bug.
    """
    db = _make_db_mock()
    try:
        html = await fetch_page(url)
    except (SiteBlockedError, CookiesExpiredError) as exc:
        pytest.skip(f"expected fetch failure for badcase URL: {exc}")
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Playwright browser runtime is not installed")
        pytest.skip(f"fetch failed: {exc}")

    with patch(
        "app.scrapers.dispatcher.extract_with_llm",
        new=AsyncMock(return_value=ProductData(url=url)),
    ):
        result, _ = await extract_product_data(html, url, db)

    assert result.in_stock in (True, False, None), (
        f"in_stock must be bool or None, got {result.in_stock!r}"
    )

    status = "in_stock=True" if result.in_stock is True else (
        "in_stock=False" if result.in_stock is False else "in_stock=None (not exposed)"
    )
    print(f"\n  {url}\n  → {status}")
