"""Layer 2a: Platform-specific CSS selector rules for well-known e-commerce sites."""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

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
        price_selector=(
            ".priceView-hero-price span[aria-hidden='true'], "
            ".priceView-customer-price span[aria-hidden='true'], "
            "[data-testid='customer-price'] span[aria-hidden='true'], "
            "[data-testid='customer-price'] span"
        ),
        title_selector=(
            "h1.h4, "
            ".sku-title h1, "
            "h1[class*='sku-title'], "
            "h1[itemprop='name'], "
            "[itemprop='name'] h1"
        ),
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
    "homedepot.com": PlatformRule(
        platform="homedepot",
        price_selector=(
            ".price-format__main-price, "
            "[class*='price-format__large'], "
            "[data-testid='price-format__main-price']"
        ),
        title_selector=(
            "h1[class*='product-details'], "
            "h1.product-details__badge-title, "
            "[data-testid='product-detail-title'] h1"
        ),
        image_selector=(
            "[class*='mediagallery__mainimage'] img, "
            "[class*='product-image'] img, "
            "[data-testid='product-image'] img"
        ),
        currency="USD",
    ),
    "target.com": PlatformRule(
        platform="target",
        price_selector="[data-test='product-price']",
        title_selector="[data-test='product-title'] h1, h1[data-test='product-title']",
        image_selector="[data-test='product-image-hero'] img, [data-test='pdp-media-img'] img",
        currency="USD",
    ),
    "uniqlo.com": PlatformRule(
        platform="uniqlo",
        # fr-ec-price-text--large is the main PDP price; --middle is used on recommendation tiles
        price_selector="p.fr-ec-price-text--large, div.fr-ec-price p",
        title_selector=(
            "div.ito-margin-bottom-16 div[class*='ito-font-weight'], "
            "div[class*='gutter-container'] div[class*='ito-font-family-uq']"
        ),
        image_selector=None,  # OG meta always carries the correct product image
        currency="USD",
    ),
    "gapfactory.com": PlatformRule(
        platform="gapfactory",
        price_selector=(
            "span.fds__core-web-purchase-price, "
            "span.current-sale-price, "
            ".pdp-title-price-wrapper .current-sale-price, "
            "[itemprop='price']"
        ),
        title_selector=(
            "h1.pdp-product-title, "
            "h1[class*='pdp-product'], "
            "h1[class*='fds__core-web-title'], "
            "[itemprop='name']"
        ),
        image_selector="[class*='pdp-photo-single-column-image'] img, [class*='pdp__image-gallery'] img",
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
        raw_img = _select_first_attr(soup, rule.image_selector, "src")
        if raw_img:
            # Resolve relative URLs against the page origin
            data.image_url = urljoin(url, raw_img)

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
