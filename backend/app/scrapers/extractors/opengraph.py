from __future__ import annotations

"""Layer 1: Extract product data from OpenGraph meta tags and JSON-LD structured data."""

import json
import logging
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from app.scrapers.schemas import ProductData

logger = logging.getLogger(__name__)


def _parse_availability(raw: str) -> bool | None:
    """Normalize schema.org / OG availability strings to True/False/None."""
    if not raw:
        return None
    normalized = raw.strip().lower().replace(" ", "").replace("-", "")
    # Handle full URIs like https://schema.org/InStock → "instock"
    normalized = normalized.split("/")[-1]
    if normalized in {"instock", "preorder", "presale", "onlineonly", "limitedavailability"}:
        return True
    if normalized in {"outofstock", "discontinued", "soldout", "unavailable"}:
        return False
    return None


def _parse_price(raw: str | None) -> float | None:
    if not raw:
        return None
    match = re.search(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", str(raw).strip())
    if not match:
        return None
    cleaned = match.group(0).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_opengraph(html: str, url: str) -> ProductData:
    soup = BeautifulSoup(html, "lxml")
    data = ProductData(url=url)

    # --- OpenGraph meta tags ---
    def og(prop: str) -> str | None:
        tag = soup.find("meta", property=f"og:{prop}") or soup.find("meta", attrs={"name": f"og:{prop}"})
        return tag.get("content") if tag else None

    data.title = og("title")
    # Try multiple image sources in priority order
    data.image_url = (
        og("image")
        or og("image:secure_url")
        or _meta_content(soup, "twitter:image")
        or _meta_content(soup, "twitter:image:src")
    )

    # Product-specific OG price tags
    price_amount = (
        og("price:amount")
        or _meta_content(soup, "product:price:amount")
        or _meta_content(soup, "twitter:data1")
    )
    data.price = _parse_price(price_amount)

    currency = og("price:currency") or _meta_content(soup, "product:price:currency")
    if currency:
        data.currency = currency.upper()

    # og:brand (OpenGraph extension used by some platforms)
    data.brand = og("brand")

    # --- JSON-LD structured data (schema.org/Product) ---
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "")
            # Could be a list, a bare object, or a {"@graph": [...]} wrapper
            if isinstance(payload, list):
                items = payload
            elif isinstance(payload, dict) and "@graph" in payload:
                items = payload["@graph"]
            else:
                items = [payload]
            for item in items:
                item_type = item.get("@type")

                # Shopify / some platforms wrap variants in a ProductGroup
                if item_type == "ProductGroup":
                    product_item = _resolve_product_group_variant(item, url)
                    if product_item is None:
                        continue
                    item = product_item
                    item_type = item.get("@type")

                if item_type in ("Product", "IndividualProduct"):
                    data.title = data.title or item.get("name")
                    data.image_url = data.image_url or _first(item.get("image"))
                    data.category = data.category or _extract_category(item.get("category"))
                    data.brand = data.brand or _extract_brand(item.get("brand"))

                    offers = item.get("offers") or item.get("Offers")
                    if offers:
                        if isinstance(offers, list):
                            # Prefer InStock offers; fall back to first
                            instock = [o for o in offers if "InStock" in str(o.get("availability", ""))]
                            offer = instock[0] if instock else offers[0]
                        else:
                            offer = offers
                        # AggregateOffer uses lowPrice/highPrice, not a single price field
                        if offer.get("@type") == "AggregateOffer":
                            price_raw = offer.get("lowPrice") or offer.get("price")
                        else:
                            price_raw = offer.get("price")
                        data.price = data.price or _parse_price(str(price_raw or ""))
                        data.currency = data.currency or str(offer.get("priceCurrency", "USD")).upper()
                        if data.in_stock is None:
                            data.in_stock = _parse_availability(str(offer.get("availability", "")))
                    break
        except Exception:
            continue

    # OG product:availability meta tag
    if data.in_stock is None:
        avail_raw = _meta_content(soup, "product:availability")
        if avail_raw:
            data.in_stock = _parse_availability(avail_raw)

    # Microdata itemprop="availability" on non-<meta> elements (e.g. Maison Kitsune)
    if data.in_stock is None:
        avail_tag = soup.find(attrs={"itemprop": "availability"})
        if avail_tag:
            avail_raw = avail_tag.get("content") or avail_tag.get("href")
            if avail_raw:
                data.in_stock = _parse_availability(str(avail_raw))

    # Last-resort: itemprop="image" anywhere in the body
    if not data.image_url:
        img_tag = soup.find(attrs={"itemprop": "image"})
        if img_tag:
            data.image_url = img_tag.get("src") or img_tag.get("content")

    # itemprop="brand" microdata fallback
    if not data.brand:
        brand_tag = soup.find(attrs={"itemprop": "brand"})
        if brand_tag:
            name_tag = brand_tag.find(attrs={"itemprop": "name"})
            if name_tag:
                data.brand = name_tag.get("content") or name_tag.get_text(strip=True) or None
            else:
                data.brand = brand_tag.get("content") or brand_tag.get_text(strip=True) or None

    return data


def _resolve_product_group_variant(group: dict, url: str) -> dict | None:
    """
    Resolve the best Product variant from a schema.org/ProductGroup.

    Shopify and similar platforms use ProductGroup with hasVariant[] where each
    entry is a full Product with its own offers/availability.

    Resolution order:
    1. Variant whose offer URL or @id matches the `variant=` query param in the URL
    2. First in-stock variant (availability contains "InStock")
    3. First variant in the list (regardless of stock status)

    Fields missing from the variant (e.g. category, brand) are patched in from
    the group so the caller can treat the returned item as a normal Product.
    """
    variants = group.get("hasVariant") or []
    if not variants or not isinstance(variants, list):
        return None

    # Extract variant query param from URL (e.g. ?variant=43455812304982)
    variant_id = None
    qs = parse_qs(urlparse(url).query)
    if "variant" in qs:
        variant_id = qs["variant"][0]

    chosen = None

    # 1. Match by variant ID in @id or offers.url
    if variant_id:
        for v in variants:
            v_id = str(v.get("@id", ""))
            offer = v.get("offers") or {}
            offer_url = str(offer.get("url", "")) if isinstance(offer, dict) else ""
            if variant_id in v_id or variant_id in offer_url:
                chosen = v
                break

    # 2. First in-stock variant
    if chosen is None:
        for v in variants:
            offer = v.get("offers") or {}
            if isinstance(offer, dict) and "InStock" in str(offer.get("availability", "")):
                chosen = v
                break

    # 3. First variant
    if chosen is None:
        chosen = variants[0]

    # Patch group-level fields onto the variant so the caller gets a complete item
    result = dict(chosen)
    result.setdefault("@type", "Product")
    for field in ("category", "brand"):
        if field not in result and field in group:
            result[field] = group[field]

    return result


def _extract_brand(value) -> str | None:
    """Normalize brand from JSON-LD — can be a string, dict (Brand/Organization), or list."""
    if not value:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return value.get("name") or value.get("@id") or None
    if isinstance(value, list) and value:
        return _extract_brand(value[0])
    return None


def _extract_category(value) -> str | None:
    """Normalize category from JSON-LD — can be a string, dict, or list."""
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("name") or value.get("@id")
    if isinstance(value, list) and value:
        return _extract_category(value[0])
    return str(value)


def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
    # Check name=, property= (OG-namespace extensions like product:price:amount use property=),
    # and itemprop= (schema.org microdata)
    tag = (
        soup.find("meta", attrs={"name": name})
        or soup.find("meta", attrs={"property": name})
        or soup.find("meta", attrs={"itemprop": name})
    )
    return tag.get("content") if tag else None


def _first(value) -> str | None:
    if isinstance(value, list):
        return value[0] if value else None
    return value
