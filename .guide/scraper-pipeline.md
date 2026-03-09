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

Signal that a site needs this treatment: httpx returns title/image (from OG tags in `<head>`, which are SSR'd) but price is missing and the LLM snippet shows "Loading content" or similar placeholder text.

## Relative Image URLs

Some sites (Gap Factory/Banana Republic) serve product images with relative paths (`/webcontent/...`). `_select_first_attr` returns the raw `src` attribute unchanged. The `extract_by_rules` function now calls `urljoin(url, raw_img)` to resolve them to absolute URLs.

## Bad Case Workflow

1. Add the URL to `backend/tests/badcase/url.md` with the symptom (price/title/image not found, or blocked).
2. Diagnose which layer fails: check if it's a fetch block, missing platform rule, stale selector, or OG gap.
3. Fix in priority order: CSS rule > OG fallback > LLM prompt/context.
4. Sites behind Akamai/PerimeterX require user-imported cookies — no code fix possible.
