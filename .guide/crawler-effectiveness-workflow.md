# Crawler Effectiveness Workflow

## What to run first

1. Add/refresh URLs in:
   - `backend/tests/goodcase/url.txt`
   - `backend/tests/badcase/url.txt`
2. Run unit tests first (`test_fetcher.py`, `test_rules.py`, `test_opengraph.py`).
3. Run live regression only when needed:
   - `pytest tests/test_live_regression.py --run-live`

The live suite is intentionally gated because real sites are flaky and slow.

## Failure classification for badcase

Use one of these outcomes so triage is consistent:

- `blocked`: anti-bot wall detected (`SiteBlockedError`)
- `needs-cookies`: imported cookies are expired (`CookiesExpiredError`)
- `parse-failed`: page fetched but extractor still has no price
- `parsed`: case recovered and now extracts a price

This keeps badcase useful even when some sites are intentionally hard to scrape.

## Cookie domain canonicalization (important)

Domain keys in `domain_rules` must always be canonicalized to avoid cookie misses:

- lowercase
- host only (no path/query)
- strip `www.` prefix

Example: `www.freepeople.com` and `freepeople.com` must map to the same key (`freepeople.com`).
If this is not enforced on both import and lookup, users can import valid cookies and still get blocked during scrape.

## Save-anyway contract

`POST /api/products` supports a `save_anyway` flag.

- `save_anyway = false` (default): scraping must succeed; blocked/cookie-expired returns 422.
- `save_anyway = true`: if scraping is blocked, still create a minimal product record with URL and default fields so the user can track it later.

UI note: the "Save URL anyway" action must send `save_anyway: true`. Otherwise the button only skips preview but still fails on create.

## Common parser pitfalls

- Currency prefix bug: `USD 29.99` must parse to `29.99`, not `2999`.
- Thousand separator bug: `1,299.00` must parse to `1299.00`.
- Never encode known-bug outputs as test expectations.

If a parser fix is made, always update both `rules` and `opengraph` tests to lock behavior.

## Fetch reliability defaults

Fetch reliability is now configured in settings:

- `fetch_http_timeout_seconds`
- `fetch_playwright_origin_timeout_ms`
- `fetch_playwright_nav_timeout_ms`
- `fetch_playwright_settle_timeout_ms`
- `fetch_retry_attempts`
- `fetch_retry_backoff_seconds`

Use retries only for transient failures (timeouts, connect errors, 5xx). Do not retry explicit blocked/cookie-expired signals.

## When to add PLAYWRIGHT-required domains

Add a domain to `PLAYWRIGHT_REQUIRED_DOMAINS` only if:

1. httpx consistently returns a large JS shell,
2. `_looks_complete()` passes, but
3. extracted product price is still missing.

This avoids forcing Playwright for domains where lightweight httpx still works.
