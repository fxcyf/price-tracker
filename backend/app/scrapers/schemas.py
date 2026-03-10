from dataclasses import dataclass, field


@dataclass
class FieldTrace:
    """Debug info for a single extracted field."""
    value: str | float | None
    source: str  # "opengraph" | "platform_rule" | "learned_rule" | "llm" | "missing"
    selector: str | None


@dataclass
class ScrapeDebug:
    """Full trace of the scrape pipeline for debugging."""
    layers_run: list[str]
    fields: dict[str, FieldTrace]


@dataclass
class ProductData:
    """Structured product data extracted by the scraper pipeline."""

    url: str
    title: str | None = None
    price: float | None = None
    currency: str = "USD"
    image_url: str | None = None
    category: str | None = None
    brand: str | None = None
    platform: str = "generic"

    # CSS selectors returned by LLM (used to populate domain_rules)
    learned_price_selector: str | None = None
    learned_title_selector: str | None = None
    learned_image_selector: str | None = None

    # LLM-suggested tags for this product (shown as pre-selected chips in the UI)
    suggested_tags: list[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        """A result is considered complete when we have at least a price."""
        return self.price is not None

    def merge(self, other: "ProductData") -> "ProductData":
        """Fill missing fields from another ProductData (used to combine layer results)."""
        return ProductData(
            url=self.url,
            title=self.title or other.title,
            price=self.price if self.price is not None else other.price,
            currency=self.currency or other.currency,
            image_url=self.image_url or other.image_url,
            category=self.category or other.category,
            brand=self.brand or other.brand,
            platform=self.platform if self.platform != "generic" else other.platform,
            learned_price_selector=self.learned_price_selector or other.learned_price_selector,
            learned_title_selector=self.learned_title_selector or other.learned_title_selector,
            learned_image_selector=self.learned_image_selector or other.learned_image_selector,
            suggested_tags=self.suggested_tags or other.suggested_tags,
        )
