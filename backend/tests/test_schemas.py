"""
Tests for app.scrapers.schemas — ProductData merge and is_complete logic.
"""

from app.scrapers.schemas import ProductData


BASE_URL = "https://example.com/p/1"


class TestIsComplete:
    def test_complete_when_price_is_set(self):
        d = ProductData(url=BASE_URL, price=99.99)
        assert d.is_complete() is True

    def test_incomplete_when_price_is_none(self):
        d = ProductData(url=BASE_URL, title="Some Product")
        assert d.is_complete() is False

    def test_price_zero_is_complete(self):
        d = ProductData(url=BASE_URL, price=0.0)
        assert d.is_complete() is True


class TestMerge:
    def test_price_first_wins(self):
        """Once a price is set, a later layer cannot overwrite it."""
        a = ProductData(url=BASE_URL, price=99.99)
        b = ProductData(url=BASE_URL, price=79.99)
        merged = a.merge(b)
        assert merged.price == 99.99

    def test_missing_price_filled_from_other(self):
        a = ProductData(url=BASE_URL, title="Hat")
        b = ProductData(url=BASE_URL, price=29.99)
        merged = a.merge(b)
        assert merged.price == 29.99

    def test_title_first_wins(self):
        a = ProductData(url=BASE_URL, title="Original Title")
        b = ProductData(url=BASE_URL, title="Different Title")
        merged = a.merge(b)
        assert merged.title == "Original Title"

    def test_missing_title_filled_from_other(self):
        a = ProductData(url=BASE_URL, price=10.0)
        b = ProductData(url=BASE_URL, title="New Title")
        merged = a.merge(b)
        assert merged.title == "New Title"

    def test_generic_platform_treated_as_absent(self):
        """A real platform name from a later layer should win over 'generic'."""
        a = ProductData(url=BASE_URL, platform="generic")
        b = ProductData(url=BASE_URL, platform="amazon")
        merged = a.merge(b)
        assert merged.platform == "amazon"

    def test_specific_platform_not_overwritten_by_generic(self):
        a = ProductData(url=BASE_URL, platform="bestbuy")
        b = ProductData(url=BASE_URL, platform="generic")
        merged = a.merge(b)
        assert merged.platform == "bestbuy"

    def test_all_fields_preserved_from_both(self):
        a = ProductData(url=BASE_URL, title="Widget", price=19.99, currency="USD")
        b = ProductData(url=BASE_URL, image_url="https://cdn.example.com/img.jpg",
                        brand="Acme", category="Electronics")
        merged = a.merge(b)
        assert merged.title == "Widget"
        assert merged.price == 19.99
        assert merged.image_url == "https://cdn.example.com/img.jpg"
        assert merged.brand == "Acme"
        assert merged.category == "Electronics"

    def test_url_always_preserved_from_self(self):
        a = ProductData(url="https://example.com/a")
        b = ProductData(url="https://example.com/b", price=5.0)
        merged = a.merge(b)
        assert merged.url == "https://example.com/a"

    def test_merge_does_not_mutate_originals(self):
        a = ProductData(url=BASE_URL, price=None)
        b = ProductData(url=BASE_URL, price=50.0)
        _ = a.merge(b)
        assert a.price is None  # original unchanged
