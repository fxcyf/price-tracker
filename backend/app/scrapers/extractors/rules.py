"""Layer 2a: Platform-specific CSS selector rules for well-known e-commerce sites."""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.scrapers.schemas import ProductData

logger = logging.getLogger(__name__)


@dataclass
class PlatformRule:
    platform: str
    price_selector: str
    title_selector: str
    image_selector: str | None = None
    currency: str = "USD"


# Built-in rules for major platforms
PLATFORM_RULES: dict[str, PlatformRule] = {
    "amazon.com": PlatformRule(
        platform="amazon",
        price_selector=".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice, .apexPriceToPay .a-offscreen",
        title_selector="#productTitle",
        image_selector="#landingImage, #imgBlkFront",
        currency="USD",
    ),
    "jd.com": PlatformRule(
        platform="jd",
        price_selector=".p-price .price, #jd-price",
        title_selector=".sku-name",
        image_selector="#spec-img",
        currency="CNY",
    ),
    "taobao.com": PlatformRule(
        platform="taobao",
        price_selector=".tb-rmb-num",
        title_selector=".main-title",
        image_selector=".J_ImgBooth",
        currency="CNY",
    ),
    "tmall.com": PlatformRule(
        platform="tmall",
        price_selector=".tm-price",
        title_selector=".tb-detail-hd h1",
        image_selector=".tb-img img",
        currency="CNY",
    ),
    "bestbuy.com": PlatformRule(
        platform="bestbuy",
        price_selector=".priceView-customer-price span[aria-hidden='true']",
        title_selector=".sku-title h1",
        image_selector=".primary-image",
        currency="USD",
    ),
    "walmart.com": PlatformRule(
        platform="walmart",
        price_selector="[itemprop='price'], .price-characteristic",
        title_selector="[itemprop='name'], h1.prod-ProductTitle",
        image_selector=".prod-hero-image img",
        currency="USD",
    ),
    "ebay.com": PlatformRule(
        platform="ebay",
        price_selector="#prcIsum, .notranslate[itemprop='price']",
        title_selector="#itemTitle",
        image_selector="#icImg",
        currency="USD",
    ),
}


def _detect_platform(url: str) -> str | None:
    hostname = urlparse(url).hostname or ""
    # Strip "www." prefix for matching
    hostname = hostname.removeprefix("www.")
    for domain, rule in PLATFORM_RULES.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            return domain
    return None


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def _select_first_text(soup: BeautifulSoup, selector: str) -> str | None:
    """Try each comma-separated selector and return the first non-empty text found."""
    for sel in [s.strip() for s in selector.split(",")]:
        try:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True) or el.get("content") or el.get("value")
                if text:
                    return text
        except Exception:
            continue
    return None


def _select_first_attr(soup: BeautifulSoup, selector: str, attr: str) -> str | None:
    for sel in [s.strip() for s in selector.split(",")]:
        try:
            el = soup.select_one(sel)
            if el and el.get(attr):
                return el[attr]
        except Exception:
            continue
    return None


def extract_by_rules(html: str, url: str) -> ProductData:
    data = ProductData(url=url)
    domain = _detect_platform(url)
    if not domain:
        return data

    rule = PLATFORM_RULES[domain]
    data.platform = rule.platform
    data.currency = rule.currency

    soup = BeautifulSoup(html, "lxml")

    price_text = _select_first_text(soup, rule.price_selector)
    data.price = _parse_price(price_text)

    data.title = _select_first_text(soup, rule.title_selector)

    if rule.image_selector:
        data.image_url = _select_first_attr(soup, rule.image_selector, "src")

    return data


def extract_by_learned_rule(
    html: str,
    url: str,
    price_selector: str | None,
    title_selector: str | None,
    image_selector: str | None,
) -> ProductData:
    """Apply a previously learned (LLM-generated) selector rule."""
    data = ProductData(url=url)
    soup = BeautifulSoup(html, "lxml")

    if price_selector:
        price_text = _select_first_text(soup, price_selector)
        data.price = _parse_price(price_text)

    if title_selector:
        data.title = _select_first_text(soup, title_selector)

    if image_selector:
        data.image_url = _select_first_attr(soup, image_selector, "src")

    return data
