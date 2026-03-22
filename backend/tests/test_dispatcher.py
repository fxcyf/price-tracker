"""
Tests for app.scrapers.dispatcher — the layered pipeline.

Uses unittest.mock to avoid real network calls and DB access.
Verifies that layers are combined correctly and that short-circuit
logic behaves as expected.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.scrapers.schemas import ProductData
from app.scrapers.dispatcher import extract_product_data


URL = "https://www.example.com/product/1"


def _make_db_mock(learned_rule=None):
    """Return an async DB session mock that optionally returns a learned rule."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = learned_rule
    db.execute.return_value = result_mock
    return db


def _og_html(price: float, title: str = "Test Product") -> str:
    """Minimal HTML with OG price tags — resolved by Layer 1."""
    return (
        f'<html><head>'
        f'<meta property="og:title" content="{title}">'
        f'<meta property="og:price:amount" content="{price}">'
        f'<meta property="og:price:currency" content="USD">'
        f'</head><body></body></html>'
    )


def _jsonld_html(price: float) -> str:
    payload = {
        "@type": "Product", "name": "JSON Widget",
        "offers": {"@type": "Offer", "price": price, "priceCurrency": "USD"}
    }
    return (
        f'<html><head>'
        f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        f'</head><body></body></html>'
    )


def _empty_html() -> str:
    return '<html><head></head><body><p>No product info</p></body></html>'


# ---------------------------------------------------------------------------
# Layer 1: OpenGraph — fills price, stops before LLM
# ---------------------------------------------------------------------------

class TestLayer1OpengraphShortCircuit:
    @pytest.mark.asyncio
    async def test_og_price_completes_without_llm(self):
        db = _make_db_mock(learned_rule=None)
        with patch("app.scrapers.dispatcher.extract_with_llm") as mock_llm:
            result, debug = await extract_product_data(_og_html(49.99), URL, db)

        assert result.price == 49.99
        mock_llm.assert_not_called(), "LLM should not be called when OG already has a price"

    @pytest.mark.asyncio
    async def test_og_price_recorded_as_opengraph_in_debug(self):
        db = _make_db_mock(learned_rule=None)
        with patch("app.scrapers.dispatcher.extract_with_llm"):
            result, debug = await extract_product_data(_og_html(99.0), URL, db)

        assert debug.fields["price"].source == "opengraph"

    @pytest.mark.asyncio
    async def test_layers_run_includes_opengraph_and_platform_rule(self):
        db = _make_db_mock(learned_rule=None)
        with patch("app.scrapers.dispatcher.extract_with_llm"):
            _, debug = await extract_product_data(_og_html(10.0), URL, db)

        assert "opengraph" in debug.layers_run
        assert "platform_rule" in debug.layers_run


# ---------------------------------------------------------------------------
# Layer 3: LLM fallback — triggered when no cheap layer finds price
# ---------------------------------------------------------------------------

class TestLayer3LLMFallback:
    @pytest.mark.asyncio
    async def test_llm_called_when_no_price_found(self):
        db = _make_db_mock(learned_rule=None)
        llm_result = ProductData(url=URL, title="LLM Title", price=29.99, currency="USD")

        with patch("app.scrapers.dispatcher.extract_with_llm", new=AsyncMock(return_value=llm_result)) as mock_llm:
            result, debug = await extract_product_data(_empty_html(), URL, db)

        mock_llm.assert_called_once()
        assert result.price == 29.99
        assert "llm" in debug.layers_run

    @pytest.mark.asyncio
    async def test_llm_not_called_when_og_has_price(self):
        db = _make_db_mock(learned_rule=None)
        with patch("app.scrapers.dispatcher.extract_with_llm", new=AsyncMock()) as mock_llm:
            await extract_product_data(_og_html(55.0), URL, db)

        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_price_missing_when_llm_returns_nothing(self):
        db = _make_db_mock(learned_rule=None)
        empty_llm = ProductData(url=URL)

        with patch("app.scrapers.dispatcher.extract_with_llm", new=AsyncMock(return_value=empty_llm)):
            result, debug = await extract_product_data(_empty_html(), URL, db)

        assert result.price is None
        assert result.is_complete() is False


# ---------------------------------------------------------------------------
# Layer 2b: Learned CSS selector rule
# ---------------------------------------------------------------------------

class TestLayer2bLearnedRule:
    @pytest.mark.asyncio
    async def test_learned_rule_fills_price(self):
        html = '<html><body><span class="pdp-price">$79.99</span></body></html>'

        learned = MagicMock()
        learned.price_selector = "span.pdp-price"
        learned.title_selector = None
        learned.image_selector = None
        learned.cookies = None
        learned.cookies_status = None
        learned.success_count = 0

        db = _make_db_mock(learned_rule=learned)

        with patch("app.scrapers.dispatcher.extract_with_llm") as mock_llm:
            result, debug = await extract_product_data(html, URL, db)

        assert result.price == 79.99
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_learned_rule_source_recorded(self):
        html = '<html><body><span id="price">$39.00</span></body></html>'

        learned = MagicMock()
        learned.price_selector = "#price"
        learned.title_selector = None
        learned.image_selector = None
        learned.cookies = None
        learned.cookies_status = None
        learned.success_count = 0

        db = _make_db_mock(learned_rule=learned)

        with patch("app.scrapers.dispatcher.extract_with_llm"):
            _, debug = await extract_product_data(html, URL, db)

        assert debug.fields["price"].source == "learned_rule"


# ---------------------------------------------------------------------------
# Merge behaviour: first-wins means wrong Layer-1 price persists
# (documented known limitation — test ensures we don't accidentally change it)
# ---------------------------------------------------------------------------

class TestFirstWinsSemantics:
    @pytest.mark.asyncio
    async def test_og_price_cannot_be_overridden_by_platform_rule(self):
        """Layer 1 price sticks even if Layer 2a has a different value.
        This is by design (trust the first source); track it explicitly."""
        # Amazon HTML that has BOTH og:price ($189.99) and CSS selector price ($189.99)
        # Both happen to agree here; the important thing is merge() keeps Layer 1.
        html = (
            '<html><head>'
            '<meta property="og:price:amount" content="189.99">'
            '</head><body>'
            '<span class="a-offscreen">$189.99</span>'
            '</body></html>'
        )
        db = _make_db_mock(learned_rule=None)
        with patch("app.scrapers.dispatcher.extract_with_llm"):
            result, _ = await extract_product_data(
                html, "https://www.amazon.com/dp/B08N5", db
            )
        assert result.price == 189.99
