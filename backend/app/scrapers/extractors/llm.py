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
