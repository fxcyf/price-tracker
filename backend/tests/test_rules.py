"""
Tests for app.scrapers.extractors.rules — Layer 2a platform CSS rules.
"""

import pytest
from tests.conftest import load_fixture, make_html
from app.scrapers.extractors.rules import (
    extract_by_rules,
    extract_by_learned_rule,
    _detect_platform,
    _parse_price,
)


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

class TestDetectPlatform:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.amazon.com/dp/B08N5WRWNW", "amazon.com"),
        ("https://amazon.com/dp/B08N5WRWNW", "amazon.com"),
        ("https://www.bestbuy.com/product/...", "bestbuy.com"),
        ("https://www.target.com/p/product", "target.com"),
        ("https://www.walmart.com/ip/product/123", "walmart.com"),
        ("https://www.homedepot.com/p/product/123", "homedepot.com"),
        ("https://www.jcrew.com/p/product/CJ755", "jcrew.com"),
        ("https://www.unknownstore.com/product", None),
        ("https://www.tntsupermarket.us/product", None),
    ])
    def test_detect(self, url, expected):
        assert _detect_platform(url) == expected

    def test_subdomain_matches(self):
        assert _detect_platform("https://old.amazon.com/dp/B08N5") == "amazon.com"


# ---------------------------------------------------------------------------
# _parse_price
# ---------------------------------------------------------------------------

class TestParsePrice:
    @pytest.mark.parametrize("text,expected", [
        ("$49.99", 49.99),
        ("49.99", 49.99),
        ("  $128.00  ", 128.0),
        ("1,299.00", 1299.0),
        (None, None),
        ("", None),
        ("Free", None),
        ("USD 29.99", 29.99),
    ])
    def test_parse(self, text, expected):
        assert _parse_price(text) == expected


# ---------------------------------------------------------------------------
# extract_by_rules: Amazon
# ---------------------------------------------------------------------------

class TestAmazonRules:
    def test_amazon_fixture_extracts_price(self):
        html = load_fixture("amazon_product.html")
        result = extract_by_rules(html, "https://www.amazon.com/dp/B08N5WRWNW")
        assert result.price == 189.99
        assert result.platform == "amazon"

    def test_amazon_fixture_extracts_title(self):
        html = load_fixture("amazon_product.html")
        result = extract_by_rules(html, "https://www.amazon.com/dp/B08N5WRWNW")
        assert result.title is not None
        assert len(result.title) > 5

    def test_non_amazon_url_returns_empty(self):
        html = load_fixture("amazon_product.html")
        result = extract_by_rules(html, "https://www.unknownstore.com/product")
        assert result.price is None
        assert result.platform == "generic"

    def test_amazon_currency_is_usd(self):
        html = load_fixture("amazon_product.html")
        result = extract_by_rules(html, "https://www.amazon.com/dp/B08N5")
        assert result.currency == "USD"


# ---------------------------------------------------------------------------
# extract_by_rules: unknown platform → no-op
# ---------------------------------------------------------------------------

class TestUnknownPlatform:
    def test_unknown_platform_returns_all_none(self):
        html = make_html(
            '<meta property="og:title" content="Some Product">',
            '<div class="price">$99.99</div>'
        )
        result = extract_by_rules(html, "https://www.unknown-store.com/product/1")
        assert result.price is None
        assert result.title is None
        assert result.platform == "generic"


# ---------------------------------------------------------------------------
# extract_by_learned_rule
# ---------------------------------------------------------------------------

class TestLearnedRule:
    def test_learned_price_selector(self):
        html = make_html(body='<span class="sale-price">$149.00</span>')
        result = extract_by_learned_rule(
            html, url="https://example.com/p/1",
            price_selector=".sale-price",
            title_selector=None,
            image_selector=None,
        )
        assert result.price == 149.0

    def test_learned_title_selector(self):
        html = make_html(body='<h1 class="product-name">Blue Sneakers</h1>')
        result = extract_by_learned_rule(
            html, url="https://example.com/p/1",
            price_selector=None,
            title_selector="h1.product-name",
            image_selector=None,
        )
        assert result.title == "Blue Sneakers"

    def test_learned_image_selector(self):
        html = make_html(body='<img class="main-img" src="https://cdn.example.com/shoe.jpg" />')
        result = extract_by_learned_rule(
            html, url="https://example.com/p/1",
            price_selector=None,
            title_selector=None,
            image_selector="img.main-img",
        )
        assert result.image_url == "https://cdn.example.com/shoe.jpg"

    def test_bad_selector_returns_none_gracefully(self):
        html = make_html(body='<div>nothing here</div>')
        result = extract_by_learned_rule(
            html, url="https://example.com/p/1",
            price_selector="#nonexistent-element",
            title_selector=None,
            image_selector=None,
        )
        assert result.price is None

    def test_no_og_fixture_with_correct_learned_selectors(self):
        html = load_fixture("no_og_product.html")
        result = extract_by_learned_rule(
            html, url="https://www.unknownstore.com/products/x900",
            price_selector=".sale-price",
            title_selector="h1.product-name",
            image_selector="img.product-image",
        )
        assert result.price == 149.0
        assert result.title == "Ultra Bass Wireless Headphones X900"
        assert "x900" in (result.image_url or "")
