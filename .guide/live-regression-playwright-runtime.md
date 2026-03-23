# Live Regression: Test Setup and cases.json

## Overview

Live regression tests are driven by `tests/cases.json` and run via `test_live_cases.py`.
Each entry declares what a URL is expected to yield per field, rather than a flat good/bad split.

## Running tests

```bash
# All cases
python -m pytest --run-live tests/test_live_cases.py -v -s

# Single case by label
python -m pytest --run-live tests/test_live_cases.py -v -s -k "everlane"

# Cookie-backed cases (requires a curl export file)
python -m pytest --run-live --live-curl-file=curl.txt tests/test_live_cases.py -v -s -k "freepeople"
```

## cases.json schema

Each entry has:

| Field | Type | Meaning |
|---|---|---|
| `url` | string | Product page URL |
| `label` | string | Unique identifier used as pytest ID (e.g. `everlane/cardigan-xs-oos`) |
| `fetch` | `"ok"` \| `"blocked"` \| `"needs-cookies"` | Expected fetch outcome |
| `expect` | object | Per-field assertions (see below) |
| `note` | string | Human-readable explanation |

### Fetch expectation values

- `"ok"` — fetch must succeed (default)
- `"blocked"` — `SiteBlockedError` expected; test is skipped (not failed)
- `"needs-cookies"` — `CookiesExpiredError` expected without `--live-curl-file`; test is skipped unless curl file provided

### Field assertion values

For all fields except `in_stock`:
- `"ok"` — field must be non-None
- `"none"` — field must be None
- `null` — no assertion (unknown or irrelevant for this URL)

For `in_stock`:
- `"ok"` — must be `True` or `False` (site exposes availability either way)
- `"true"` — must be `True` (in stock)
- `"false"` — must be `False` (out of stock)
- `"none"` — must be `None` (site doesn't expose availability)
- `null` — no assertion

### Example entry

```json
{
  "url": "https://www.everlane.com/products/womens-crew-cardigan-in-alpaca-heather-gray-mist?variant=43455812304982",
  "label": "everlane/cardigan-xs-oos",
  "fetch": "ok",
  "expect": {
    "price":    "ok",
    "title":    "ok",
    "image":    "ok",
    "brand":    "ok",
    "in_stock": "ok"
  },
  "note": "Everlane ProductGroup with explicit variant= param; XS was OOS when added — tests variant ID matching"
}
```

## Adding a new case

1. Add an entry to `tests/cases.json` with `fetch: "ok"` and all `expect` values as `null`.
2. Run the test: `python -m pytest --run-live tests/test_live_cases.py -v -s -k "your-label"`
3. Inspect output — each field is printed with `✓`/`✗`/`(unchecked)`.
4. Fill in `expect` with `"ok"` for fields that extract cleanly and `"none"` for fields the site doesn't expose.
5. If fetch fails with `SiteBlockedError`, change `fetch` to `"blocked"`. If it requires cookies, set `fetch` to `"needs-cookies"`.

## Graduating a blocked/needs-cookies URL

If a previously blocked URL starts working:
1. Run: `python -m pytest --run-live tests/test_live_cases.py -v -s -k "label"`
2. If fetch succeeds unexpectedly, the test will fail with a message telling you to update `fetch` in `cases.json`.
3. Update `fetch: "ok"` and fill in `expect` assertions.

## Playwright runtime pitfall

Some URLs require Playwright fallback. If the Playwright browser runtime is missing, tests fail with:
```
BrowserType.launch_persistent_context: Executable doesn't exist
```
This is an environment issue. The test runner skips (does not fail) when the Playwright executable is unavailable.

## cookie-backed fetch notes

- `needs-cookies` cases require `--live-curl-file=<path>` to run.
- Cookies are parsed from the curl export and injected as `stored_cookies` into `fetch_page()`.
- JS-heavy domains (`freepeople.com`, `aritzia.com`) route cookie-backed requests directly to Playwright with cookies attached to the browser context.
- `test_scraper.py --live-curl curl.txt` is the fastest way to debug a single cookie-backed URL interactively.

## Deprecated files

`test_live_regression.py` and `test_live_stock_regression.py` are kept for backward compatibility but superseded by `test_live_cases.py`. Do not add new URLs to the old goodcase/badcase text files.
