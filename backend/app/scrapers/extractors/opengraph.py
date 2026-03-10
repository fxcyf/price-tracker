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
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[^\d.]", "", str(raw).strip())
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
                        offer = offers[0] if isinstance(offers, list) else offers
                        data.price = data.price or _parse_price(str(offer.get("price", "")))
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
    tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"itemprop": name})
    return tag.get("content") if tag else None


def _first(value) -> str | None:
    if isinstance(value, list):
        return value[0] if value else None
    return value
