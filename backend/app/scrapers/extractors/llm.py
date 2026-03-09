"""Layer 3: LLM-based extraction as a fallback. Also returns CSS selectors for future reuse."""

import json
import logging

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.scrapers.schemas import ProductData

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an e-commerce data extraction assistant.
Given a preprocessed webpage text snippet, extract product information and return a JSON object.
Also identify the CSS selectors where each piece of information was found in the original page.

Return ONLY valid JSON with this exact structure:
{
  "title": "product title or null",
  "price": 29.99,
  "currency": "USD",
  "category": "category or null",
  "image_url": "url or null",
  "selectors": {
    "price": "CSS selector that contains the price, or null",
    "title": "CSS selector that contains the title, or null",
    "image": "CSS selector for the main product image, or null"
  }
}

Rules:
- price must be a number (not a string), or null if not found
- currency should be the ISO 4217 code (USD, CNY, EUR, etc.)
- For selectors, use the most specific stable selector (prefer id or data attributes over generic classes)
- If you cannot find a field, set it to null
"""

NORMALIZE_SUGGEST_PROMPT = """You are a product categorization assistant for a personal shopping price tracker.

Given a product title and a raw category string (which may be a messy breadcrumb path like "Women > Clothing > Tops"),
return a clean short category label and a list of relevant tags.

Return ONLY valid JSON with this exact structure:
{
  "category": "clean 1-3 word category label, e.g. Blouses / Sneakers / Handbags / null if unknown",
  "suggested_tags": ["tag1", "tag2"]
}

Rules for category:
- Normalize breadcrumbs by taking the most specific meaningful segment
- Use title-case, 1-3 words max
- If genuinely unknown, return null

Rules for suggested_tags:
- Return 2-5 short lowercase tags
- Prefer tags from the existing_tags list if they fit the product
- You may also suggest new tags not in the list if clearly relevant
- Good tags describe: product type, use case, occasion, or style (e.g. "sale", "casual", "sneakers", "wishlist")
- Do NOT repeat the category as a tag
"""


async def extract_with_llm(preprocessed_text: str, url: str) -> ProductData:
    settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set, skipping LLM extraction for %s", url)
        return ProductData(url=url)

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"URL: {url}\n\nPage content:\n{preprocessed_text}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=500,
        )

        raw = response.choices[0].message.content or "{}"
        payload = json.loads(raw)
    except Exception as exc:
        logger.error("LLM extraction failed for %s: %s", url, exc)
        return ProductData(url=url)

    selectors = payload.get("selectors") or {}

    price_raw = payload.get("price")
    try:
        price = float(price_raw) if price_raw is not None else None
    except (TypeError, ValueError):
        price = None

    return ProductData(
        url=url,
        title=payload.get("title"),
        price=price,
        currency=str(payload.get("currency") or "USD").upper(),
        image_url=payload.get("image_url"),
        category=payload.get("category"),
        learned_price_selector=selectors.get("price"),
        learned_title_selector=selectors.get("title"),
        learned_image_selector=selectors.get("image"),
    )


async def normalize_and_suggest(
    title: str | None,
    raw_category: str | None,
    existing_tags: list[str],
) -> tuple[str | None, list[str]]:
    """
    Call LLM to normalize a raw category string and suggest relevant tags.
    Returns (normalized_category, suggested_tags).
    Falls back gracefully if LLM is unavailable.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set, skipping normalize_and_suggest")
        return raw_category, []

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    user_content = (
        f"Product title: {title or 'unknown'}\n"
        f"Raw category: {raw_category or 'unknown'}\n"
        f"Existing tags in system: {existing_tags or []}"
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": NORMALIZE_SUGGEST_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content or "{}"
        payload = json.loads(raw)
    except Exception as exc:
        logger.error("normalize_and_suggest failed: %s", exc)
        return raw_category, []

    normalized = payload.get("category") or raw_category
    suggested = [t.strip().lower() for t in (payload.get("suggested_tags") or []) if t.strip()]
    return normalized, suggested
