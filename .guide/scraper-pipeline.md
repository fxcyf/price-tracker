# Scraper Pipeline: Lessons Learned

## Pipeline Architecture

The extraction pipeline has 4 layers in `dispatcher.py`:

```
Layer 1 : OpenGraph / JSON-LD  (opengraph.py)
Layer 2a: Built-in platform CSS rules  (rules.py)
Layer 2b: DB-learned CSS selectors  (domain_rules table)
Layer 3 : LLM fallback  (llm.py)  ← only if price still missing
```

## Key Design Principle: Don't Short-Circuit Cheap Layers

**Pitfall:** Early short-circuit returns on `is_complete()` (which only checks `price is not None`) cause fields like `image_url` to be left empty. For example, Layer 1 OG may find the price but not the image — stopping there means image is never filled in by a later layer.

**Rule:** Always run all cheap layers (1, 2a, 2b) unconditionally and merge their results. Only use `is_complete()` to skip the expensive LLM Layer 3 call.

```python
# Correct pattern:
result = result.merge(extract_opengraph(html, url))
result = result.merge(extract_by_rules(html, url))
# ... layer 2b merge ...
if result.is_complete():   # guards LLM only
    return result
# Layer 3: LLM
```

## Adding Platform CSS Rules

When a known e-commerce site consistently fails extraction, add a `PlatformRule` entry to `PLATFORM_RULES` in `rules.py`. Detection is hostname-based (strips `www.` prefix). Subdomains also match (e.g. `bananarepublicfactory.gapfactory.com` matches `gapfactory.com`).

Provide multiple comma-separated fallback selectors per field in case the site updates their DOM:

```python
"target.com": PlatformRule(
    platform="target",
    price_selector="[data-test='product-price']",
    title_selector="[data-test='product-title'] h1, h1[data-test='product-title']",
    image_selector="[data-test='product-image-hero'] img, [data-test='pdp-media-img'] img",
    currency="USD",
),
```

## Meta Tag Attribute Conventions — `name=` vs `property=` vs `itemprop=`

Different meta tag standards use different HTML attributes. Getting this wrong silently drops data.

| Standard | HTML attribute | Example |
|---|---|---|
| OpenGraph (all `og:*` and namespace extensions like `product:*`) | `property=` | `<meta property="product:price:amount" content="25.99">` |
| Twitter Cards | `name=` | `<meta name="twitter:data1" content="$25.99">` |
| Schema.org Microdata | `itemprop=` | `<meta itemprop="price" content="25.99">` |

**Pitfall:** `product:price:amount` and `product:price:currency` look like they might use `name=` but they are part of the OpenGraph Commerce namespace and use `property=`. The `_meta_content()` helper must check all three attributes to be safe:

```python
def _meta_content(soup, name):
    tag = (
        soup.find("meta", attrs={"name": name})
        or soup.find("meta", attrs={"property": name})   # OG-namespace extensions
        or soup.find("meta", attrs={"itemprop": name})
    )
    return tag.get("content") if tag else None
```

## JSON-LD `AggregateOffer` vs `Offer`

When a product JSON-LD uses `"@type": "AggregateOffer"` (common when a product has multiple variants/sellers), the price field semantics change:

- `Offer`: has a single `price` field
- `AggregateOffer`: has `lowPrice`, `highPrice`, and optionally `price` (which may equal `highPrice`)

**Pitfall:** Reading `offer.get("price")` on an `AggregateOffer` returns the high/reference price. Always check `@type` and use `lowPrice` for aggregate offers:

```python
if offer.get("@type") == "AggregateOffer":
    price_raw = offer.get("lowPrice") or offer.get("price")
else:
    price_raw = offer.get("price")
```

When `offers` is a list, prefer offers where `availability` contains `"InStock"` over others.

## OG Image Fallbacks

Not all sites use `og:image`. Check these sources in order:
1. `og:image` — most common
2. `og:image:secure_url` — preferred on HTTPS sites (e.g. Gap)
3. `twitter:image` / `twitter:image:src` — common on fashion/lifestyle sites
4. `itemprop="image"` on any body element — schema.org fallback

## LLM Context Window

`preprocess_html()` truncates the stripped page text before sending to the LLM. If a site renders the price deep in the DOM (common on JS-heavy SPAs fetched via Playwright), the price text can be cut off. Current limit is **12,000 chars** (increased from 8,000).

## PLAYWRIGHT_REQUIRED_DOMAINS — Forcing Playwright for JS-heavy SPAs

Some sites (Target, Best Buy) serve a convincing HTML shell via httpx (>5000 chars, not "blocked") but all critical data (price, title) is loaded by React/Next.js after JS execution. The `_looks_complete()` check incorrectly passes on these shells, so Playwright never runs.

**Fix:** Add the domain to `PLAYWRIGHT_REQUIRED_DOMAINS` in `fetcher.py`. This set is checked in `fetch_page()` to bypass httpx and go directly to Playwright.

```python
PLAYWRIGHT_REQUIRED_DOMAINS = {
    "target.com",
    "bestbuy.com",
}
```

Signal that a site needs this treatment: the scrape trace shows all fields sourced from LLM even though the browser's DevTools clearly shows correct OG/product meta tags in `<head>`. The giveaway is `data-rh="true"` on those meta tags — this attribute is added by **react-helmet**, meaning the tags are injected by React at runtime, not server-side. httpx gets the bare JS bundle shell (which passes `_looks_complete()` because it's >5000 chars and not blocked), but that shell has no meta tags yet.

Another signal: httpx returns title/image (from OG tags in `<head>`, which are SSR'd) but price is missing and the LLM snippet shows "Loading content" or similar placeholder text.

## Relative Image URLs

Some sites (Gap Factory/Banana Republic) serve product images with relative paths (`/webcontent/...`). `_select_first_attr` returns the raw `src` attribute unchanged. The `extract_by_rules` function now calls `urljoin(url, raw_img)` to resolve them to absolute URLs.

## Adding New Fields to the Pipeline

When adding a new product data field (like `brand`):

1. Add the field to `ProductData` in `schemas.py` and wire it into `merge()`.
2. Extract it in `opengraph.py` from the cheapest sources first: JSON-LD structured data, OG meta tags, `itemprop` microdata.
3. Add it to the LLM `SYSTEM_PROMPT` as a last-resort fallback — only runs when price is still missing after cheap layers.
4. Add it to the SQLAlchemy model and create an Alembic migration (nullable, no data migration needed for new optional fields).
5. Add it to the FastAPI `ProductOut` Pydantic schema and the `create_product` handler.

**JSON-LD brand extraction pattern** (schema.org `Product.brand` can be a string, `Brand` dict, or list):
```python
def _extract_brand(value) -> str | None:
    if isinstance(value, str): return value or None
    if isinstance(value, dict): return value.get("name") or value.get("@id") or None
    if isinstance(value, list) and value: return _extract_brand(value[0])
    return None
```

## Bad Case Workflow

1. Add the URL to `backend/tests/badcase/url.md` with the symptom (price/title/image not found, or blocked).
2. Diagnose which layer fails: check if it's a fetch block, missing platform rule, stale selector, or OG gap.
3. Fix in priority order: CSS rule > OG fallback > LLM prompt/context.
4. Sites behind Akamai/PerimeterX require user-imported cookies — no code fix possible.
