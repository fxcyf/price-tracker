# Architecture Deep-Dive

## What problem this project solves

Price Tracker is a self-hosted web app that monitors e-commerce product prices on a schedule and sends email alerts when prices change. The key design constraint is that it must work against sites that actively resist automated access — PerimeterX, Cloudflare, Akamai, and JS-rendered SPAs — while keeping the common case (static HTML) fast and free.

## The scraper pipeline and why it's layered

The central design decision is a four-layer pipeline (`backend/app/scrapers/dispatcher.py`), where each layer attempts to fill in missing product fields and the first layer to find a field wins. Layers 1–2b are always run unconditionally (they're cheap: no network, no LLM). Only Layer 3 is guarded by `result.is_complete()` because it calls OpenAI. The reason to run all cheap layers even after a "complete" result from Layer 1 is that `is_complete()` only checks `price is not None` — a layer 1 hit on price still leaves `image_url` unfilled unless layers 2a/2b also run.

- **Layer 1 — OpenGraph/JSON-LD** (`extractors/opengraph.py`): Reads `<meta property="og:*">`, `<meta name="twitter:*">`, `<meta itemprop="*">`, and JSON-LD `Product` objects. The key pitfall is that `product:price:amount` uses `property=` not `name=` (OpenGraph Commerce namespace), so the `_meta_content()` helper checks all three attribute names. JSON-LD with `@type: AggregateOffer` must use `lowPrice`, not `price` (which is the high-end price).
- **Layer 2a — Platform rules** (`extractors/rules.py`): Hard-coded `PlatformRule` entries in `PLATFORM_RULES` (keyed by bare hostname, no `www.`). Subdomains match automatically — `bananarepublicfactory.gapfactory.com` hits the `gapfactory.com` rule. Selectors are comma-separated fallback chains.
- **Layer 2b — Learned rules** (`domain_rules` table): CSS selectors LLM-learned from a prior successful scrape, re-applied as a cheap lookup on subsequent scrapes. If a learned price selector stops working, `scrape_price_only` clears it and triggers a full re-scrape to re-learn.
- **Layer 3 — LLM** (`extractors/llm.py`): `preprocess_html()` strips scripts/styles and truncates to 12,000 chars before sending to OpenAI. On success, learned selectors are saved back to `domain_rules` for Layer 2b on future runs.

## Fetch strategy — the hardest part

`fetch_page()` in `fetcher.py` decides *how* to retrieve HTML before extraction begins. The layering is:

1. **curl_cffi + cookies** — PerimeterX and similar systems cryptographically bind their session token (`_px3`) to the browser's TLS fingerprint. httpx produces a different JA3/JA4 fingerprint, so cookie replay via httpx is rejected even with valid cookies. `curl_cffi` reproduces Chrome's exact TLS/HTTP2 handshake. This is the preferred path when cookies are stored.
2. **Playwright + cookies** — fallback when `curl_cffi` is unavailable. For domains in `PLAYWRIGHT_REQUIRED_DOMAINS` (JS-heavy SPAs), this runs before anonymous httpx even when no cookies are present.
3. **Anonymous httpx** — fast, no browser, works for most server-rendered sites. Skipped for `PLAYWRIGHT_REQUIRED_DOMAINS` because these domains serve JS-bundle shells that pass the `_looks_complete()` heuristic (>5000 chars, no bot signals) but contain no actual product data.
4. **Anonymous Playwright** — full headless browser with stealth. Used when httpx fails or the domain requires it.

`SiteBlockedError` means even Playwright got a bot wall. `CookiesExpiredError` means stored cookies returned 403/blocked — the dispatcher marks `cookies_status = EXPIRED` in the DB and the periodic price check skips that product with a logged warning.

## The domain_rules table — dual-purpose cache

`app/models/domain_rule.py` stores two orthogonal things in one table, keyed by bare hostname (no `www.`): **LLM-learned CSS selectors** (`price_selector`, `title_selector`, `image_selector`) and **user-imported browser cookies** (`cookies` JSONB, `cookies_status`). Domain normalization (strip `www.`, lowercase) must be applied consistently — `normalize_domain()` in `dispatcher.py` is the canonical helper. A bug here causes silent misses where cookies exist in the DB but are never found.

## Celery bridge pattern

Celery tasks are sync; the scraper is async. `check_product_price` in `tasks/price_check.py` bridges these worlds with `asyncio.run(_scrape_price(url))`, where `_scrape_price` opens a `CeleryAsyncSessionLocal` (configured with `NullPool`). The `NullPool` is critical: Celery uses `fork()`, and forked processes that inherit SQLAlchemy's connection pool produce silent DB errors. Every Celery task must use `CeleryAsyncSessionLocal` (not `AsyncSessionLocal`) for any DB work inside the async helper.

## Critical invariants

**Do not short-circuit cheap layers.** Checking `is_complete()` before layers 2a/2b causes fields like `image_url` and `brand` to stay empty even when the data is present in the DOM.

**Domain normalization must be consistent.** The `domain_rules` table key is `bare-hostname` (no `www.`). Any code that looks up or writes domain rules must call `normalize_domain()` from `dispatcher.py`, not roll its own stripping logic.

**learned_rule.price_selector = None on miss.** When a learned selector stops returning a price, `scrape_price_only` explicitly clears the selector in the DB before falling through to a full scrape. Without this, a stale selector blocks re-learning indefinitely.

**`PLAYWRIGHT_REQUIRED_DOMAINS` controls httpx bypass.** Adding a domain here skips anonymous httpx and goes straight to Playwright (anonymous or cookie-backed). Without this, JS-rendered shells pass `_looks_complete()` and extraction fails silently.

**`_parse_price` prefers currency-anchored numbers.** The regex first looks for `$`/`€`/`£`/`¥`/`₩` followed by a number. This prevents discount copy like "Save 40%" from being extracted as the price. CSS selectors for sale prices should target the sale-price element specifically (e.g. `[class*="product__price--sale"] > span`) rather than a container that mixes sale and original prices.

## Testing approach

Unit tests (`pytest`, no network) cover extraction logic with HTML fixtures in `tests/`. Live regression tests (`--run-live`) hit real sites and are split into two lanes:

- `test_live_regression.py`: goodcase URLs must return a price; badcase URLs must fail with a known error type. Requires Playwright runtime installed (`playwright install chromium`).
- `test_live_cookie_regression.py`: validates cookie-backed bypass of a specific badcase URL using a curl file from DevTools. Requires `--live-curl-file`. This is the "graduation test" for promoting a badcase URL to goodcase.

`test_scraper.py` at the backend root is a manual debug tool with four modes (fixture / live / live-file / live-curl).
