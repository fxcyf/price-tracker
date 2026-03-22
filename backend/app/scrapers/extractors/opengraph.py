from __future__ import annotations

"""Layer 1: Extract product data from OpenGraph meta tags and JSON-LD structured data."""

import json
import logging
import re

from bs4 import BeautifulSoup

from app.scrapers.schemas import ProductData

logger = logging.getLogger(__name__)


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
            # Could be a list or single object
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if item.get("@type") in ("Product", "IndividualProduct"):
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
                    break
        except Exception:
            continue

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
            data.brand = (name_tag.get_text(strip=True) if name_tag else brand_tag.get_text(strip=True)) or None

    return data


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
