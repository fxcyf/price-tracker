"""
Scraper dispatcher — orchestrates the layered extraction pipeline.

Layer 1  : OpenGraph / JSON-LD meta tags
Layer 2a : Built-in platform CSS selector rules (Amazon, JD, etc.)
Layer 2b : Learned domain rules stored in domain_rules table
Layer 3  : LLM fallback (also saves selectors back to domain_rules)
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain_rule import CookieStatus, DomainRule
from app.scrapers.extractors.llm import extract_with_llm
from app.scrapers.extractors.opengraph import extract_opengraph
from app.scrapers.extractors.rules import extract_by_learned_rule, extract_by_rules
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError, fetch_page, preprocess_html
from app.scrapers.schemas import ProductData

logger = logging.getLogger(__name__)


def _get_domain(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    return hostname.removeprefix("www.")


async def _get_learned_rule(db: AsyncSession, domain: str) -> DomainRule | None:
    result = await db.execute(select(DomainRule).where(DomainRule.domain == domain))
    return result.scalar_one_or_none()


async def save_domain_cookies(db: AsyncSession, domain: str, cookies: dict) -> DomainRule:
    """Store user-imported cookies for a domain. Called from the API cookie-import endpoint."""
    rule = await _get_learned_rule(db, domain)
    if rule:
        rule.cookies = cookies
        rule.cookies_status = CookieStatus.VALID
        rule.cookies_updated_at = datetime.now(timezone.utc)
    else:
        rule = DomainRule(
            domain=domain,
            cookies=cookies,
            cookies_status=CookieStatus.VALID,
            cookies_updated_at=datetime.now(timezone.utc),
        )
        db.add(rule)
    await db.commit()
    logger.info("Saved cookies for domain: %s (%d cookies)", domain, len(cookies))
    return rule


async def _save_learned_rule(db: AsyncSession, domain: str, data: ProductData) -> None:
    """Upsert LLM-learned selectors into domain_rules."""
    if not any([data.learned_price_selector, data.learned_title_selector, data.learned_image_selector]):
        return

    existing = await _get_learned_rule(db, domain)
    if existing:
        if data.learned_price_selector:
            existing.price_selector = data.learned_price_selector
        if data.learned_title_selector:
            existing.title_selector = data.learned_title_selector
        if data.learned_image_selector:
            existing.image_selector = data.learned_image_selector
        existing.success_count += 1
    else:
        rule = DomainRule(
            domain=domain,
            price_selector=data.learned_price_selector,
            title_selector=data.learned_title_selector,
            image_selector=data.learned_image_selector,
        )
        db.add(rule)

    await db.commit()
    logger.info("Saved learned selectors for domain: %s", domain)


async def _mark_cookies_expired(db: AsyncSession, domain: str) -> None:
    rule = await _get_learned_rule(db, domain)
    if rule:
        rule.cookies_status = CookieStatus.EXPIRED
        await db.commit()
        logger.warning("Marked cookies as expired for domain: %s", domain)


async def scrape_product(url: str, db: AsyncSession) -> ProductData:
    """
    Full product scrape: fetches the page, runs extraction, then normalizes
    the category and suggests tags via LLM.
    """
    domain = _get_domain(url)
    rule = await _get_learned_rule(db, domain)
    stored_cookies = (
        rule.cookies
        if rule and rule.cookies and rule.cookies_status == CookieStatus.VALID
        else None
    )

    try:
        html = await fetch_page(url, stored_cookies=stored_cookies)
    except CookiesExpiredError:
        await _mark_cookies_expired(db, domain)
        raise

    return await extract_product_data(html, url, db)


async def extract_product_data(html: str, url: str, db: AsyncSession) -> ProductData:
    """Run the layered extraction pipeline on already-fetched HTML."""
    domain = _get_domain(url)
    result = ProductData(url=url)

    # Layer 1: OpenGraph / JSON-LD
    og_data = extract_opengraph(html, url)
    result = result.merge(og_data)
    if result.is_complete():
        logger.debug("Layer 1 (OpenGraph) succeeded for %s", url)
        return result

    # Layer 2a: Built-in platform rules
    rule_data = extract_by_rules(html, url)
    result = result.merge(rule_data)
    if result.is_complete():
        logger.debug("Layer 2a (platform rules) succeeded for %s", url)
        return result

    # Layer 2b: Learned domain rules
    learned_rule = await _get_learned_rule(db, domain)
    if learned_rule:
        learned_data = extract_by_learned_rule(
            html,
            url,
            learned_rule.price_selector,
            learned_rule.title_selector,
            learned_rule.image_selector,
        )
        result = result.merge(learned_data)
        if result.is_complete():
            logger.debug("Layer 2b (learned rules) succeeded for %s", url)
            # Increment success count
            learned_rule.success_count += 1
            await db.commit()
            return result

    # Layer 3: LLM fallback
    logger.info("Falling back to LLM extraction for %s", url)
    preprocessed = preprocess_html(html)
    llm_data = await extract_with_llm(preprocessed, url)
    result = result.merge(llm_data)

    # Save selectors for future use
    if result.is_complete():
        await _save_learned_rule(db, domain, result)

    return result


async def scrape_price_only(url: str, db: AsyncSession) -> float | None:
    """
    Lightweight price-only scrape used by the periodic price-check task.
    Tries learned/built-in selectors first; falls back to full scrape only if needed.
    """
    domain = _get_domain(url)
    learned_rule = await _get_learned_rule(db, domain)

    # Skip if cookies are known expired — caller should handle notification
    if learned_rule and learned_rule.cookies_status == CookieStatus.EXPIRED:
        logger.info("Skipping price check for %s — cookies expired", domain)
        return None

    stored_cookies = (
        learned_rule.cookies
        if learned_rule and learned_rule.cookies and learned_rule.cookies_status == CookieStatus.VALID
        else None
    )

    # Try learned rule first (most specific, zero LLM cost)
    if learned_rule and learned_rule.price_selector:
        try:
            from bs4 import BeautifulSoup
            from app.scrapers.extractors.rules import _parse_price, _select_first_text

            html = await fetch_page(url, stored_cookies=stored_cookies)
            soup = BeautifulSoup(html, "lxml")
            price_text = _select_first_text(soup, learned_rule.price_selector)
            price = _parse_price(price_text)
            if price is not None:
                logger.debug("Price-only scrape via learned rule succeeded: %s → %s", url, price)
                learned_rule.success_count += 1
                await db.commit()
                return price
            logger.warning("Learned price selector failed for %s, triggering re-learning", url)
            learned_rule.price_selector = None
            await db.commit()
        except CookiesExpiredError:
            await _mark_cookies_expired(db, domain)
            return None
        except Exception as exc:
            logger.warning("Price-only scrape error for %s: %s", url, exc)

    # Full scrape (re-learns selectors if LLM is needed)
    data = await scrape_product(url, db)
    return data.price
