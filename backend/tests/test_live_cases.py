"""
Live regression suite driven by tests/cases.json.

Each entry in cases.json declares what a URL is expected to yield:
  - fetch: "ok" | "blocked" | "needs-cookies"
  - expect: per-field assertions

Field assertion values (all fields except in_stock):
  "ok"   — field must be non-None
  "none" — field must be None
  null   — no assertion (site behaviour unknown or irrelevant)

in_stock assertion values:
  "ok"   — must be True or False (site exposes availability either way)
  "true" — must be True (in stock)
  "false"— must be False (out of stock)
  "none" — must be None (site doesn't expose availability)
  null   — no assertion

Run with:
    pytest --run-live tests/test_live_cases.py -v -s
    pytest --run-live --live-curl-file=/path/to/curl.txt tests/test_live_cases.py -v -s

Supersedes test_live_regression.py and test_live_stock_regression.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.dispatcher import extract_product_data
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError, fetch_page
from app.scrapers.schemas import ProductData

CASES_FILE = Path(__file__).parent / "cases.json"
ALL_CASES: list[dict] = json.loads(CASES_FILE.read_text(encoding="utf-8"))


def _make_db_mock():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock
    return db


def _check_field(field: str, value: Any, expectation: str) -> None:
    """Assert a single field against its declared expectation."""
    if field == "in_stock":
        if expectation == "ok":
            assert value in (True, False), (
                f"in_stock: expected site to expose availability (True or False), got {value!r}"
            )
        elif expectation == "true":
            assert value is True, f"in_stock: expected True (in stock), got {value!r}"
        elif expectation == "false":
            assert value is False, f"in_stock: expected False (out of stock), got {value!r}"
        elif expectation == "none":
            assert value is None, f"in_stock: expected None (not exposed), got {value!r}"
    else:
        if expectation == "ok":
            assert value is not None, f"{field}: expected a value, got None"
        elif expectation == "none":
            assert value is None, f"{field}: expected None, got {value!r}"


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c["label"])
async def test_live_case(case: dict, request):
    url = case["url"]
    fetch_expect: str = case.get("fetch", "ok")
    expect: dict[str, str | None] = case.get("expect", {})
    curl_file: str = request.config.getoption("--live-curl-file", default="")

    db = _make_db_mock()

    # ------------------------------------------------------------------ fetch
    stored_cookies = None
    if fetch_expect == "needs-cookies" and curl_file:
        # Cookie regression lane: parse cookies from the curl file and inject them
        from app.api.cookies import _parse_curl_cookies  # type: ignore[import]
        try:
            stored_cookies = _parse_curl_cookies(Path(curl_file).read_text())
        except Exception:
            pytest.skip("could not parse curl file — skipping cookie-backed case")

    try:
        html = await fetch_page(url, stored_cookies=stored_cookies)
    except SiteBlockedError as exc:
        if fetch_expect == "blocked":
            pytest.skip(f"blocked as expected: {exc}")
        pytest.fail(f"unexpected SiteBlockedError for fetch='{fetch_expect}' case: {exc}")
    except CookiesExpiredError as exc:
        if fetch_expect == "needs-cookies" and not curl_file:
            pytest.skip(f"needs cookies (no --live-curl-file provided): {exc}")
        pytest.fail(f"unexpected CookiesExpiredError: {exc}")
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Playwright browser runtime is not installed")
        raise

    if fetch_expect in ("blocked", "needs-cookies") and not curl_file:
        pytest.fail(
            f"expected fetch to fail ({fetch_expect!r}) but it succeeded — "
            "update fetch expectation in cases.json if the site is now accessible"
        )

    # --------------------------------------------------------------- extract
    with patch(
        "app.scrapers.dispatcher.extract_with_llm",
        new=AsyncMock(return_value=ProductData(url=url)),
    ):
        result, _ = await extract_product_data(html, url, db)

    # ----------------------------------------------------------------- report
    extracted = {
        "price":    result.price,
        "title":    result.title,
        "image":    result.image_url,
        "brand":    result.brand,
        "category": result.category,
        "in_stock": result.in_stock,
    }

    lines = []
    for field, value in extracted.items():
        exp = expect.get(field)
        tag = ""
        if exp == "ok":
            tag = " ✓" if (value is not None and (field != "in_stock" or value in (True, False))) else " ✗ EXPECTED"
        elif exp == "none":
            tag = " ✓" if value is None else " ✗ EXPECTED None"
        elif exp in ("true", "false"):
            tag = " ✓" if (value is (True if exp == "true" else False)) else f" ✗ EXPECTED {exp}"
        elif exp is None:
            tag = " (unchecked)"
        lines.append(f"  {field:<10} = {value!r}{tag}")

    print(f"\n[{case['label']}]\n" + "\n".join(lines))

    # --------------------------------------------------------------- assert
    for field, expectation in expect.items():
        if expectation is None:
            continue
        _check_field(field, extracted.get(field), expectation)
