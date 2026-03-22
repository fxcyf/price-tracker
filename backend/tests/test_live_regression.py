"""Live regression suite backed by goodcase/badcase URL lists."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.dispatcher import extract_product_data
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError, fetch_page
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


def _classify_failure(exc: Exception) -> str:
    if isinstance(exc, SiteBlockedError):
        return "blocked"
    if isinstance(exc, CookiesExpiredError):
        return "needs-cookies"
    return "fetch-failed"


GOODCASE_URLS = _load_urls(GOODCASE_FILE)
BADCASE_URLS = _load_urls(BADCASE_FILE)


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("url", GOODCASE_URLS)
async def test_goodcase_live_has_price(url: str):
    db = _make_db_mock()
    html = await fetch_page(url)
    with patch(
        "app.scrapers.dispatcher.extract_with_llm",
        new=AsyncMock(return_value=ProductData(url=url)),
    ):
        result, _ = await extract_product_data(html, url, db)
    assert result.is_complete(), f"expected complete extraction for goodcase URL: {url}"


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("url", BADCASE_URLS)
async def test_badcase_live_is_classified(url: str):
    db = _make_db_mock()
    classification = "parse-failed"
    try:
        html = await fetch_page(url)
        with patch(
            "app.scrapers.dispatcher.extract_with_llm",
            new=AsyncMock(return_value=ProductData(url=url)),
        ):
            result, _ = await extract_product_data(html, url, db)
        if result.is_complete():
            classification = "parsed"
    except Exception as exc:  # pragma: no cover - live tests by design
        classification = _classify_failure(exc)

    assert classification in {"blocked", "needs-cookies", "parse-failed", "parsed"}
