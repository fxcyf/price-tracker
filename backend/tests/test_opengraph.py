"""
Tests for app.scrapers.extractors.opengraph — Layer 1 extraction.

Each test is named after the scenario it guards against so failures are
immediately self-documenting. The suite covers every bug fixed so far
plus the core happy paths.
"""

import json
import pytest
from tests.conftest import load_fixture, make_html
from app.scrapers.extractors.opengraph import extract_opengraph, _parse_availability


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


# ---------------------------------------------------------------------------
# _parse_availability normalizer
# ---------------------------------------------------------------------------

class TestParseAvailability:
    """Unit tests for the _parse_availability() string normalizer."""

    @pytest.mark.parametrize("raw,expected", [
        # schema.org full URI — most common in JSON-LD
        ("https://schema.org/InStock",           True),
        ("http://schema.org/InStock",            True),
        ("https://schema.org/OutOfStock",        False),
        ("https://schema.org/PreOrder",          True),
        ("https://schema.org/LimitedAvailability", True),
        ("https://schema.org/OnlineOnly",        True),
        ("https://schema.org/Discontinued",      False),
        ("https://schema.org/SoldOut",           False),
        # Short-form strings
        ("InStock",          True),
        ("OutOfStock",       False),
        ("PreOrder",         True),
        ("Discontinued",     False),
        ("SoldOut",          False),
        # Plain-text OG values (spaces and hyphens)
        ("in stock",         True),
        ("out of stock",     False),
        ("in-stock",         True),
        ("out-of-stock",     False),
        # Whitespace normalised
        ("  InStock  ",      True),
        ("  out of stock  ", False),
        # Unknown / empty → None
        ("",                 None),
        ("available",        None),
        ("unknown_value",    None),
    ])
    def test_normalizes_correctly(self, raw, expected):
        assert _parse_availability(raw) == expected


# ---------------------------------------------------------------------------
# JSON-LD availability → in_stock field
# ---------------------------------------------------------------------------

class TestJsonLdAvailability:
    """Tests that in_stock is populated from the JSON-LD offer availability field."""

    def _html(self, payload: dict) -> str:
        return make_html(
            f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        )

    def test_instock_full_uri_sets_true(self):
        html = self._html({
            "@type": "Product", "name": "Widget",
            "offers": {
                "@type": "Offer", "price": 49.99, "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            },
        })
        assert extract_opengraph(html, URL).in_stock is True

    def test_outofstock_full_uri_sets_false(self):
        html = self._html({
            "@type": "Product", "name": "Widget",
            "offers": {
                "@type": "Offer", "price": 0.0,
                "availability": "https://schema.org/OutOfStock",
            },
        })
        assert extract_opengraph(html, URL).in_stock is False

    def test_preorder_treated_as_in_stock(self):
        html = self._html({
            "@type": "Product", "name": "Widget",
            "offers": {
                "@type": "Offer", "price": 99.0,
                "availability": "https://schema.org/PreOrder",
            },
        })
        assert extract_opengraph(html, URL).in_stock is True

    def test_no_availability_field_returns_none(self):
        html = self._html({
            "@type": "Product", "name": "Widget",
            "offers": {"@type": "Offer", "price": 49.99},
        })
        assert extract_opengraph(html, URL).in_stock is None

    def test_short_form_instock_string(self):
        html = self._html({
            "@type": "Product", "name": "Widget",
            "offers": {"@type": "Offer", "price": 25.0, "availability": "InStock"},
        })
        assert extract_opengraph(html, URL).in_stock is True

    def test_multiple_offers_instock_selected_sets_true(self):
        """The InStock offer is chosen AND in_stock should reflect that."""
        html = self._html({
            "@type": "Product", "name": "Widget",
            "offers": [
                {"@type": "Offer", "price": 99.99, "availability": "https://schema.org/OutOfStock"},
                {"@type": "Offer", "price": 79.99, "availability": "https://schema.org/InStock"},
            ],
        })
        result = extract_opengraph(html, URL)
        assert result.price == 79.99  # correct offer selected
        assert result.in_stock is True

    def test_all_offers_outofstock_sets_false(self):
        """Falls back to first offer (OOS) → in_stock False."""
        html = self._html({
            "@type": "Product", "name": "Widget",
            "offers": [
                {"@type": "Offer", "price": 45.00, "availability": "https://schema.org/OutOfStock"},
                {"@type": "Offer", "price": 50.00, "availability": "https://schema.org/OutOfStock"},
            ],
        })
        assert extract_opengraph(html, URL).in_stock is False


# ---------------------------------------------------------------------------
# ProductGroup (Shopify / Everlane pattern) → variant resolution
# ---------------------------------------------------------------------------

class TestProductGroupVariantResolution:
    """
    Guards the fix for ProductGroup + hasVariant (Shopify-style JSON-LD).
    Everlane was returning in_stock=None because the top-level @type was
    ProductGroup, which the extractor previously ignored entirely.
    """

    VARIANT_A_ID = "43455812272214"
    VARIANT_B_ID = "43455812304982"

    def _html(self, payload: dict, url: str = URL) -> str:
        return make_html(
            f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        )

    def _group(self, variants: list, extra: dict | None = None) -> dict:
        base = {
            "@context": "http://schema.org/",
            "@type": "ProductGroup",
            "name": "Test Cardigan",
            "brand": {"@type": "Brand", "name": "TestBrand"},
            "category": "Knitwear",
            "hasVariant": variants,
        }
        if extra:
            base.update(extra)
        return base

    def _variant(self, variant_id: str, price: float, availability: str) -> dict:
        return {
            "@type": "Product",
            "@id": f"/products/item?variant={variant_id}#variant",
            "name": f"Test Cardigan - Size {variant_id[-3:]}",
            "image": "https://example.com/img.jpg",
            "offers": {
                "@type": "Offer",
                "price": str(price),
                "priceCurrency": "USD",
                "availability": availability,
                "url": f"https://example.com/products/item?variant={variant_id}",
            },
        }

    def test_variant_matched_by_query_param_outofstock(self):
        """Exact variant= match picks the correct out-of-stock variant."""
        group = self._group([
            self._variant(self.VARIANT_A_ID, 118.0, "http://schema.org/InStock"),
            self._variant(self.VARIANT_B_ID, 118.0, "http://schema.org/OutOfStock"),
        ])
        url = f"https://example.com/products/item?variant={self.VARIANT_B_ID}"
        result = extract_opengraph(self._html(group), url)
        assert result.in_stock is False

    def test_variant_matched_by_query_param_instock(self):
        """Exact variant= match picks the correct in-stock variant."""
        group = self._group([
            self._variant(self.VARIANT_A_ID, 118.0, "http://schema.org/OutOfStock"),
            self._variant(self.VARIANT_B_ID, 118.0, "http://schema.org/InStock"),
        ])
        url = f"https://example.com/products/item?variant={self.VARIANT_B_ID}"
        result = extract_opengraph(self._html(group), url)
        assert result.in_stock is True

    def test_no_variant_param_falls_back_to_first_instock(self):
        """Without a variant= param, first in-stock variant is preferred."""
        group = self._group([
            self._variant(self.VARIANT_A_ID, 118.0, "http://schema.org/OutOfStock"),
            self._variant(self.VARIANT_B_ID, 98.0, "http://schema.org/InStock"),
        ])
        result = extract_opengraph(self._html(group), "https://example.com/products/item")
        assert result.in_stock is True
        assert result.price == 98.0

    def test_all_variants_outofstock_returns_false(self):
        """Falls back to first variant when none are in-stock → False."""
        group = self._group([
            self._variant(self.VARIANT_A_ID, 118.0, "http://schema.org/OutOfStock"),
            self._variant(self.VARIANT_B_ID, 118.0, "http://schema.org/OutOfStock"),
        ])
        result = extract_opengraph(self._html(group), "https://example.com/products/item")
        assert result.in_stock is False

    def test_group_brand_and_category_propagated_to_variant(self):
        """Brand and category from the ProductGroup are available on the result."""
        group = self._group([
            self._variant(self.VARIANT_A_ID, 118.0, "http://schema.org/InStock"),
        ])
        result = extract_opengraph(self._html(group), "https://example.com/products/item")
        assert result.brand == "TestBrand"
        assert result.category == "Knitwear"

    def test_price_extracted_from_resolved_variant(self):
        """Price comes from the resolved variant's offer."""
        group = self._group([
            self._variant(self.VARIANT_A_ID, 89.0, "http://schema.org/OutOfStock"),
            self._variant(self.VARIANT_B_ID, 118.0, "http://schema.org/InStock"),
        ])
        result = extract_opengraph(self._html(group), "https://example.com/products/item")
        assert result.price == 118.0  # first in-stock variant


# ---------------------------------------------------------------------------
# OG product:availability meta tag → in_stock field
# ---------------------------------------------------------------------------

class TestOGAvailabilityMeta:
    """Tests that in_stock is populated from <meta property="product:availability">."""

    def test_property_in_stock(self):
        html = make_html('<meta property="product:availability" content="in stock">')
        assert extract_opengraph(html, URL).in_stock is True

    def test_property_out_of_stock(self):
        html = make_html('<meta property="product:availability" content="out of stock">')
        assert extract_opengraph(html, URL).in_stock is False

    def test_name_attribute_also_works(self):
        """_meta_content checks name= as well as property=."""
        html = make_html('<meta name="product:availability" content="in stock">')
        assert extract_opengraph(html, URL).in_stock is True

    def test_no_availability_meta_returns_none(self):
        html = make_html('<meta property="og:title" content="Some Product">')
        assert extract_opengraph(html, URL).in_stock is None

    def test_jsonld_wins_over_og_meta(self):
        """JSON-LD is parsed before OG meta; left-wins merge means JSON-LD value is kept."""
        payload = {
            "@type": "Product", "name": "W",
            "offers": {
                "@type": "Offer", "price": 1,
                "availability": "https://schema.org/InStock",
            },
        }
        html = make_html(
            '<meta property="product:availability" content="out of stock">'
            f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        )
        # JSON-LD sets in_stock=True first; OG meta should not overwrite it
        assert extract_opengraph(html, URL).in_stock is True

    def test_og_meta_fills_in_when_jsonld_has_no_availability(self):
        """OG meta acts as fallback when JSON-LD offer omits availability."""
        payload = {
            "@type": "Product", "name": "W",
            "offers": {"@type": "Offer", "price": 1},  # no availability
        }
        html = make_html(
            '<meta property="product:availability" content="in stock">'
            f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        )
        assert extract_opengraph(html, URL).in_stock is True
