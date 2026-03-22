"""
Tests for app.scrapers.extractors.opengraph — Layer 1 extraction.

Each test is named after the scenario it guards against so failures are
immediately self-documenting. The suite covers every bug fixed so far
plus the core happy paths.
"""

import json
import pytest
from tests.conftest import load_fixture, make_html
from app.scrapers.extractors.opengraph import extract_opengraph


URL = "https://www.example.com/product/123"


# ---------------------------------------------------------------------------
# _meta_content: name= vs property= vs itemprop=  (T&T regression guard)
# ---------------------------------------------------------------------------

class TestMetaContentAttributeMatching:
    """Guards the fix: _meta_content must check property= not just name=."""

    def test_product_price_amount_via_property(self):
        """T&T uses <meta property="product:price:amount"> — was missed before fix."""
        html = make_html(
            '<meta property="product:price:amount" content="25.99">'
            '<meta property="product:price:currency" content="USD">'
        )
        result = extract_opengraph(html, URL)
        assert result.price == 25.99
        assert result.currency == "USD"

    def test_product_price_amount_via_name(self):
        """Some sites still use name= — must not break after the fix."""
        html = make_html(
            '<meta name="product:price:amount" content="49.99">'
            '<meta name="product:price:currency" content="CAD">'
        )
        result = extract_opengraph(html, URL)
        assert result.price == 49.99
        assert result.currency == "CAD"

    def test_product_price_amount_via_itemprop(self):
        """Schema.org microdata uses itemprop=."""
        html = make_html(
            '<meta itemprop="product:price:amount" content="19.99">'
        )
        result = extract_opengraph(html, URL)
        assert result.price == 19.99

    def test_tnt_style_head(self):
        """Exact structure from T&T Supermarket page that was returning wrong price."""
        html = make_html(
            '<meta property="og:title" content="明珂咖啡脆曲奇礼盒 (5.6oz)" data-rh="true">'
            '<meta property="og:image" content="https://www.tntsupermarket.us/media/catalog/product/img.jpg" data-rh="true">'
            '<meta property="product:price:amount" content="25.99" data-rh="true">'
            '<meta property="product:price:currency" content="USD" data-rh="true">'
        )
        result = extract_opengraph(html, "https://www.tntsupermarket.us/chs/53686601-test.html")
        assert result.price == 25.99, "T&T price should be 25.99, not 29.99"
        assert result.title == "明珂咖啡脆曲奇礼盒 (5.6oz)"
        assert result.currency == "USD"


# ---------------------------------------------------------------------------
# OG price tags (og:price:amount)
# ---------------------------------------------------------------------------

class TestOGPriceTags:
    def test_og_price_amount(self):
        html = make_html('<meta property="og:price:amount" content="89.95">')
        result = extract_opengraph(html, URL)
        assert result.price == 89.95

    def test_og_price_takes_priority_over_product_price(self):
        """og:price:amount is checked first; product:price:amount is the fallback."""
        html = make_html(
            '<meta property="og:price:amount" content="99.00">'
            '<meta property="product:price:amount" content="79.00">'
        )
        result = extract_opengraph(html, URL)
        assert result.price == 99.00

    def test_twitter_data1_fallback(self):
        """twitter:data1 is the last-resort price source."""
        html = make_html('<meta name="twitter:data1" content="$34.99">')
        result = extract_opengraph(html, URL)
        assert result.price == 34.99

    def test_no_price_tags_returns_none(self):
        html = make_html('<meta property="og:title" content="Some Product">')
        result = extract_opengraph(html, URL)
        assert result.price is None


# ---------------------------------------------------------------------------
# JSON-LD: Offer  (basic path)
# ---------------------------------------------------------------------------

class TestJsonLdOffer:
    def _html(self, payload: dict) -> str:
        return make_html(
            f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        )

    def test_basic_offer(self):
        html = self._html({
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": "Test Widget",
            "offers": {"@type": "Offer", "price": 49.99, "priceCurrency": "USD"},
        })
        result = extract_opengraph(html, URL)
        assert result.price == 49.99
        assert result.currency == "USD"
        assert result.title == "Test Widget"

    def test_offer_price_as_string(self):
        """price field is often a string in the wild."""
        html = self._html({
            "@type": "Product",
            "name": "Widget",
            "offers": {"@type": "Offer", "price": "129.00", "priceCurrency": "USD"},
        })
        result = extract_opengraph(html, URL)
        assert result.price == 129.0

    def test_offer_in_list(self):
        html = self._html({
            "@type": "Product",
            "name": "Widget",
            "offers": [
                {"@type": "Offer", "price": 59.99, "priceCurrency": "USD"},
            ],
        })
        result = extract_opengraph(html, URL)
        assert result.price == 59.99

    def test_instock_offer_preferred_in_list(self):
        """When multiple offers exist, InStock is preferred over OutOfStock."""
        html = self._html({
            "@type": "Product",
            "name": "Widget",
            "offers": [
                {"@type": "Offer", "price": 99.99, "availability": "https://schema.org/OutOfStock"},
                {"@type": "Offer", "price": 79.99, "availability": "https://schema.org/InStock"},
            ],
        })
        result = extract_opengraph(html, URL)
        assert result.price == 79.99, "Should prefer InStock offer over OutOfStock"

    def test_falls_back_to_first_offer_when_none_instock(self):
        html = self._html({
            "@type": "Product",
            "name": "Widget",
            "offers": [
                {"@type": "Offer", "price": 45.00, "availability": "https://schema.org/OutOfStock"},
                {"@type": "Offer", "price": 50.00, "availability": "https://schema.org/OutOfStock"},
            ],
        })
        result = extract_opengraph(html, URL)
        assert result.price == 45.00, "Should fall back to first offer when none are InStock"


# ---------------------------------------------------------------------------
# JSON-LD: AggregateOffer  (regression guard for the 29.99 vs 25.99 class of bug)
# ---------------------------------------------------------------------------

class TestJsonLdAggregateOffer:
    def _html(self, offers) -> str:
        payload = {"@type": "Product", "name": "Widget", "offers": offers}
        return make_html(
            f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        )

    def test_aggregate_offer_uses_low_price(self):
        """AggregateOffer must use lowPrice, not price (which can be highPrice)."""
        html = self._html({
            "@type": "AggregateOffer",
            "lowPrice": 25.99,
            "highPrice": 29.99,
            "price": 29.99,
            "priceCurrency": "USD",
        })
        result = extract_opengraph(html, URL)
        assert result.price == 25.99, "Should use lowPrice (25.99) not price/highPrice (29.99)"

    def test_aggregate_offer_falls_back_to_price_when_no_low_price(self):
        html = self._html({
            "@type": "AggregateOffer",
            "price": 39.99,
            "priceCurrency": "USD",
        })
        result = extract_opengraph(html, URL)
        assert result.price == 39.99

    def test_aggregate_offer_in_list(self):
        html = self._html([{
            "@type": "AggregateOffer",
            "lowPrice": 19.99,
            "highPrice": 39.99,
            "priceCurrency": "USD",
        }])
        result = extract_opengraph(html, URL)
        assert result.price == 19.99


# ---------------------------------------------------------------------------
# Image extraction fallbacks
# ---------------------------------------------------------------------------

class TestImageExtraction:
    def test_og_image(self):
        html = make_html('<meta property="og:image" content="https://example.com/img.jpg">')
        result = extract_opengraph(html, URL)
        assert result.image_url == "https://example.com/img.jpg"

    def test_og_image_secure_url_fallback(self):
        html = make_html('<meta property="og:image:secure_url" content="https://example.com/secure.jpg">')
        result = extract_opengraph(html, URL)
        assert result.image_url == "https://example.com/secure.jpg"

    def test_twitter_image_fallback(self):
        html = make_html('<meta name="twitter:image" content="https://example.com/tw.jpg">')
        result = extract_opengraph(html, URL)
        assert result.image_url == "https://example.com/tw.jpg"

    def test_itemprop_image_last_resort(self):
        html = make_html(
            body='<img itemprop="image" src="https://example.com/micro.jpg" />'
        )
        result = extract_opengraph(html, URL)
        assert result.image_url == "https://example.com/micro.jpg"

    def test_og_image_takes_priority_over_twitter(self):
        html = make_html(
            '<meta property="og:image" content="https://example.com/og.jpg">'
            '<meta name="twitter:image" content="https://example.com/tw.jpg">'
        )
        result = extract_opengraph(html, URL)
        assert result.image_url == "https://example.com/og.jpg"


# ---------------------------------------------------------------------------
# Brand extraction
# ---------------------------------------------------------------------------

class TestBrandExtraction:
    def test_og_brand(self):
        html = make_html('<meta property="og:brand" content="Nike">')
        result = extract_opengraph(html, URL)
        assert result.brand == "Nike"

    def test_jsonld_brand_string(self):
        payload = {"@type": "Product", "name": "X", "brand": "Adidas",
                   "offers": {"@type": "Offer", "price": 1}}
        html = make_html(f'<script type="application/ld+json">{json.dumps(payload)}</script>')
        result = extract_opengraph(html, URL)
        assert result.brand == "Adidas"

    def test_jsonld_brand_dict(self):
        payload = {"@type": "Product", "name": "X",
                   "brand": {"@type": "Brand", "name": "Apple"},
                   "offers": {"@type": "Offer", "price": 1}}
        html = make_html(f'<script type="application/ld+json">{json.dumps(payload)}</script>')
        result = extract_opengraph(html, URL)
        assert result.brand == "Apple"

    def test_itemprop_brand_microdata_fallback(self):
        html = make_html(
            body='<div itemprop="brand"><span itemprop="name">Sony</span></div>'
        )
        result = extract_opengraph(html, URL)
        assert result.brand == "Sony"


# ---------------------------------------------------------------------------
# Price parsing edge cases
# ---------------------------------------------------------------------------

class TestPriceParsing:
    def _html_with_price(self, price_str: str) -> str:
        return make_html(f'<meta property="og:price:amount" content="{price_str}">')

    @pytest.mark.parametrize("raw,expected", [
        ("29.99", 29.99),
        ("$29.99", 29.99),
        ("1,299.00", 1299.0),
        ("  49.00  ", 49.0),
        ("0.99", 0.99),
    ])
    def test_price_string_formats(self, raw, expected):
        result = extract_opengraph(self._html_with_price(raw), URL)
        assert result.price == expected

    def test_empty_price_string_returns_none(self):
        result = extract_opengraph(self._html_with_price(""), URL)
        assert result.price is None

    def test_non_numeric_price_returns_none(self):
        result = extract_opengraph(self._html_with_price("N/A"), URL)
        assert result.price is None


# ---------------------------------------------------------------------------
# Fixture-based regression tests (real HTML shapes from the test suite)
# ---------------------------------------------------------------------------

class TestFixtures:
    def test_amazon_fixture_og_price(self):
        html = load_fixture("amazon_product.html")
        result = extract_opengraph(html, "https://www.amazon.com/dp/B08N5WRWNW")
        assert result.price == 189.99
        assert result.title is not None
        assert result.image_url is not None

    def test_generic_fixture_jsonld_price(self):
        html = load_fixture("generic_product.html")
        result = extract_opengraph(html, "https://www.somestore.com/products/sony-xm5")
        assert result.price == 279.99
        assert "Sony" in (result.title or "")

    def test_no_og_fixture_returns_no_price(self):
        html = load_fixture("no_og_product.html")
        result = extract_opengraph(html, "https://www.unknownstore.com/products/x900")
        assert result.price is None
        assert result.title is None
