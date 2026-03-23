# Architecture Context

## What this project does and why it's designed this way

This is the backend of a personal price tracker: users paste a product URL, the system scrapes current price/title/image/brand/stock, stores it, and runs periodic checks that trigger email alerts on price drops, rises, or restocks. The central design constraint is that e-commerce sites actively block scrapers, so the fetcher and extractor layers are structured to be adaptive rather than brittle.

## The extraction pipeline (the most important thing to understand)

`dispatcher.py:extract_product_data()` runs four layers in sequence, each filling in any fields the previous layer missed. The merge is always `self.field or other.field` — later layers only contribute when earlier ones came up empty. **`is_complete()` means price is non-None** — the LLM call (the only expensive step) is skipped the moment a price exists.

- **Layer 1 — OpenGraph / JSON-LD** (`extractors/opengraph.py`): Parses `og:*` meta tags, `product:*` meta tags, and `application/ld+json` blocks. Handles `{"@graph": [...]}` wrappers (Uniqlo-style), `ProductGroup` with `hasVariant[]` (Shopify-style, used by Everlane), and `itemprop` microdata as last-resort fallbacks for brand and availability. Most well-structured sites return all fields from this layer alone.

- **Layer 2a — Built-in platform rules** (`extractors/rules.py`): `PLATFORM_RULES` maps domain → `PlatformRule(price_selector, title_selector, image_selector, brand)`. `price_selector` and `title_selector` are optional — Madewell carries only a hardcoded `brand="Madewell"` override because its CSS class names are Next.js module-hashed and unstable. The platform rule brand is applied as an **authoritative override** in the dispatcher after the merge, so it can correct wrong values from JSON-LD (e.g. Madewell's internal code "MW").

- **Layer 2b — Learned domain rules** (`domain_rules` table, `DomainRule` model): CSS selectors the LLM discovered on a prior visit. Stored per domain. On success, `success_count` is incremented; if the learned selector stops finding a price, it's cleared and re-learning is triggered.

- **Layer 3 — LLM fallback** (`extractors/llm.py`): Preprocesses HTML (strips script/style/nav, truncates to 12 KB), calls OpenAI with a JSON-mode prompt, extracts data and CSS selectors. Selectors are saved back to `domain_rules` for future use.

## The fetch strategy and why there are four fetch paths

Bot protection is the main obstacle. `fetcher.py:fetch_page()` tries four strategies in order:

1. **curl_cffi + stored cookies** — Chrome TLS fingerprint impersonation. PerimeterX/Cloudflare bind session cookies (`_px3`, etc.) to the originating TLS fingerprint; httpx fails this check even with valid cookies. curl_cffi reproduces the exact Chrome JA3/JA4 handshake so cookie replay passes.
2. **Playwright + stored cookies** — Full browser render with injected cookies, fallback when curl_cffi isn't installed.
3. **Anonymous httpx** — Fast, works for most static/SSR sites. Skipped for domains in `PLAYWRIGHT_REQUIRED_DOMAINS`.
4. **Anonymous Playwright** — Full browser render with stealth plugin; last resort for JS-heavy SPAs. Each Celery worker process gets its own browser profile directory (keyed by PID) to avoid lock contention.

Domains in `PLAYWRIGHT_REQUIRED_DOMAINS` (Target, BestBuy, J.Crew, Home Depot, Maison Kitsune, T&T, etc.) skip httpx entirely because those sites serve a JS shell with no product data in the initial HTML.

## Cookie lifecycle and the CookieStatus state machine

Users import cookies from their browser via `POST /api/cookies/{domain}` (curl command parse). Cookies are stored as JSONB on `DomainRule.cookies` with status `valid`. On any 401/403 or blocked response, `CookiesExpiredError` is raised, the dispatcher catches it and sets status to `expired`, and the Celery task returns `{"status": "cookies_expired"}` rather than retrying.

## The periodic price check task

`tasks/price_check.py` uses a Celery chord: `run_all_price_checks()` (Beat entry point) fans out one `check_product_price` task per active product, then `send_price_digest_task` runs as the chord callback and sends a single digest email for all alerts. The async scraper is bridged into the synchronous Celery worker via `asyncio.run()` with `CeleryAsyncSessionLocal` which uses `NullPool` to avoid inheriting pooled DB connections across `fork()`.

## Critical invariants

- **Domain normalization** (`dispatcher.py:normalize_domain()`): All domain keys strip `www.` and lowercase. Both `madewell.com` and `www.madewell.com` resolve to the same `DomainRule` row. Breaking this causes duplicate rows and missed cookie lookups.
- **`scrape_price_only` is the hot path**: For recurring price checks, it tries the learned selector first before doing a full scrape. If the selector fails, it clears it (`learned_rule.price_selector = None`) and falls through to `scrape_product()` which re-runs all layers including LLM.
- **`is_complete()` gates the LLM call**: Never change `is_complete()` to require more than price — doing so would cause LLM calls even when price was already found, burning API tokens on every check cycle.
- **Platform rule `brand` overrides OG/JSON-LD**: Applied forcibly in the dispatcher after `result.merge(rules_data)`. This is intentional — some sites (Madewell) emit internal brand codes in their structured data that are worse than the known brand name.
- **The live test suite** (`tests/test_live_cases.py`) is the ground truth for per-site extraction quality. `tests/cases.json` declares what each URL should yield; run with `pytest --run-live`.
