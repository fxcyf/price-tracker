"""Live regression tests for cookie-backed scraping flows."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.curl_parser import parse_curl
from app.scrapers.dispatcher import extract_product_data
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError, fetch_page
from app.scrapers.schemas import ProductData


def _make_db_mock():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock
    return db


@pytest.mark.live
@pytest.mark.live_cookie
@pytest.mark.slow
@pytest.mark.asyncio
async def test_cookie_backed_live_url_extracts_price(pytestconfig):
    curl_file = pytestconfig.getoption("--live-curl-file")
    curl_path = Path(curl_file)
    if not curl_path.is_file():
        pytest.fail(f"--live-curl-file does not exist: {curl_file}")

    parsed = parse_curl(curl_path.read_text(encoding="utf-8"))
    url = parsed["url"]
    cookies = parsed["cookies"]

    if not cookies:
        pytest.fail("curl file parsed successfully but contained no cookies")

    db = _make_db_mock()
    try:
        html = await fetch_page(url, stored_cookies=cookies)
    except (SiteBlockedError, CookiesExpiredError) as exc:
        pytest.fail(f"cookie-backed fetch should bypass block for graduation candidate: {exc}")

    with patch(
        "app.scrapers.dispatcher.extract_with_llm",
        new=AsyncMock(return_value=ProductData(url=url)),
    ):
        result, _ = await extract_product_data(html, url, db)

    assert result.is_complete(), f"expected price extraction from cookie-backed live URL: {url}"
