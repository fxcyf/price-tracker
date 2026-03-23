# Progress

## Active

No active work item.

## Completed

- 2026-03-22 — Stock info feature completed: `in_stock` extraction (JSON-LD + OG meta), `ProductGroup` variant resolution for Shopify/Everlane, DB columns, Celery restock alerts, frontend badges + toggle, Alembic migrations (0006, 0007)
- 2026-03-22 — Live regression tests migrated to `tests/cases.json` manifest with per-field assertions; `test_live_cases.py` supersedes `test_live_regression.py`; `.guide/live-regression-playwright-runtime.md` updated
- 2026-03-22 — Browser favicon fixed (was missing `/vite.svg`); created `frontend/public/favicon.svg` based on TrendingDown icon
- 2026-03-22 — `AGENTS.md` refreshed and `.guide/context.md` created (architecture deep-dive)
- 2026-03-22 — `curl_cffi` Chrome TLS impersonation added as Layer 0 for cookie-backed fetches (bypasses PerimeterX `_px3` fingerprint check)
- 2026-03-22 — `_parse_price` improved: currency-symbol anchor prevents discount percentages ("Save 40%") from being returned as price
- 2026-03-22 — JCrew `price_selector` updated to target `[class*="product__price--sale"] > span` directly, isolating sale price from strikethrough original price
- 2026-03-22 — Added `homedepot.com`, `maisonkitsune.com`, `tntsupermarket.us` to `PLAYWRIGHT_REQUIRED_DOMAINS`; added CSS rules for `urbanoutfitters.com`, `freepeople.com`, `aritzia.com`
- 2026-03-22 — `AGENTS.md` + `.guide/progress.md` initialized; `CLAUDE.md` created at project root
- 2026-03-22 — `fetch_page` cookie path restructured: curl_cffi first, Playwright+cookies fallback, httpx last
- 2026-03-22 — `save_anyway` bypass added: creating a product URL skips `SiteBlockedError` on first import
- 2026-03-22 — Cookie domain normalization fixed (strips `www.` for consistent DB lookup)
- 2026-03-22 — Python 3.9 typing compatibility fixes across backend modules

## Plans

- 2026-03-22 — [Stock info scraping & restock notifications](plans/2026-03-22-stock-info.md)
