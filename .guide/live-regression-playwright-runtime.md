# Live Regression: Playwright Runtime Pitfall

## What happened

When running `backend/tests/test_live_regression.py` with `--run-live`, some URLs require Playwright fallback.
If the Playwright browser runtime is missing, tests fail with:

- `BrowserType.launch_persistent_context: Executable doesn't exist`

This is an environment issue, not necessarily a scraper regression.

## Workflow to validate goodcase/badcase safely

1. Run with module form to ensure interpreter consistency:
   - `python -m pytest tests/test_live_regression.py --run-live -q`
2. Treat missing browser runtime as infra/setup problem.
3. Keep badcase classifications aligned with runtime behavior:
   - Include `fetch-failed` when generic fetch exceptions are possible.
4. In live tests, skip only the cases blocked by missing Playwright runtime instead of failing the whole suite.

## Code-level lessons

- `test_live_regression.py` should classify `fetch-failed` in badcase assertions.
- Goodcase live tests should skip (not fail) when Playwright executable is unavailable in current environment.
- `fetcher.py` should degrade gracefully when `playwright_stealth` is not installed (warn and continue without stealth).
- For `fetch_with_stored_cookies`, do not require the generic `len(html) >= 5000` completeness gate.
  A short but non-blocked `200` cookie-backed HTML is often still parseable and should be returned to avoid unnecessary Playwright fallback.

## Case list maintenance rule

- If a `goodcase` URL consistently raises `SiteBlockedError` under current live conditions, reclassify it into `badcase` rather than keeping it in `goodcase`.
- Keep `goodcase` focused on URLs that can produce complete extraction without manual cookie import.
- Re-validate with:
  - `python -m pytest tests/test_live_regression.py --run-live -q`

## FreePeople/JS-heavy cookie behavior

- Some domains need both:
  - imported cookies
  - browser rendering (Playwright)
- For JS-heavy domains (`freepeople.com`, `urbanoutfitters.com`, `aritzia.com`), route cookie-backed requests directly to Playwright with cookies attached to browser context, instead of cookie-httpx first.
- This avoids returning shell HTML and improves success rate for anti-bot storefronts.
- If Playwright+cookies is still blocked, retry once with cookie-httpx before failing.
  Different anti-bot paths can block headless rendering while still allowing cookie-backed HTTP response.

## `test_scraper.py` pitfalls

- `--live <url>` never loads stored/imported cookies from DB; it always calls `fetch_page(url)` without cookies.
- To validate cookie-based bypass, use `--live-curl` so cookies are parsed and passed to `fetch_page(..., stored_cookies=...)`.
- On zsh, always quote URLs containing `?`:
  - `python test_scraper.py --live "https://.../?color=011"`

## Graduation test path (badcase -> goodcase)

- Add a dedicated pytest lane for cookie-backed graduation checks:
  - `python -m pytest tests/test_live_cookie_regression.py --run-live --live-curl-file curl -q`
- This lane is intentionally strict:
  - cookie-backed fetch must not raise `SiteBlockedError` / `CookiesExpiredError`
  - extraction must produce a price
- Keep this lane opt-in (requires both `--run-live` and `--live-curl-file`) so normal CI remains stable.
