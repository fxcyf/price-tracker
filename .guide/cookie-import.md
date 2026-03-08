# Cookie Import Feature

## Pattern: Browser Cookie Bypass

Sites using **PerimeterX** cannot be bypassed by headless browsers because they verify
human interaction signals (mouse movement, event timing, fingerprint consistency).
The reliable workaround is:

1. User visits the site in their real browser (same IP as the server for localhost dev)
2. User copies the request as curl from DevTools → Network tab → Right-click → Copy as cURL
3. Backend parses the curl command to extract cookies
4. httpx uses those cookies for all future fetches of that domain

## Key Design Decisions

- **Cookies stored as JSONB** in `domain_rules` table, alongside CSS selectors
- **`cookies_status`** enum: `none` / `valid` / `expired` — avoids wasteful retries once expired
- **Expiry detection**: if `fetch_with_stored_cookies` gets a 403 or blocked response,
  it raises `CookiesExpiredError` which the dispatcher catches and flips status to `expired`
- **Periodic tasks skip** domains with `cookies_status = "expired"` and return `None`
  (the caller/API should surface this to the user)

## File Map

| File | Role |
|---|---|
| `app/scrapers/curl_parser.py` | Parse raw curl string → `{url, domain, cookies}` |
| `app/scrapers/fetcher.py` | `fetch_with_stored_cookies()` + `CookiesExpiredError` |
| `app/scrapers/dispatcher.py` | `save_domain_cookies()`, cookie lookup, expiry marking |
| `app/models/domain_rule.py` | `cookies`, `cookies_status`, `cookies_updated_at` columns |
| `alembic/versions/0003_add_domain_rule_cookies.py` | DB migration |

## API Endpoint (to be implemented in api-routes task)

```
PUT /api/domains/{domain}/cookies
Body: { "curl": "curl 'https://...' -b '...'" }
```

The endpoint:
1. Calls `parse_curl(curl_string)` from `curl_parser.py`
2. Calls `save_domain_cookies(db, domain, cookies)`
3. Returns the updated domain rule

## Pitfall: Overly Broad BLOCKED_SIGNALS

**Never put generic words like `"captcha"` in `BLOCKED_SIGNALS`.**
Major retailers (Free People, Urban Outfitters, etc.) embed captcha SDKs on *every* page
as a background script — so a 453KB page with real product content will falsely trigger a block.

Only match patterns that appear *exclusively* on dedicated bot-wall pages:
- `"px-captcha"` (PerimeterX block page element, not the background script)
- `"enable javascript and cookies"` (Cloudflare challenge page)
- `"reference #18"` (Akamai error page, with the specific prefix)

Avoid: `"captcha"`, `"robot"`, `"verify"` — all appear on normal pages.

## Pitfall: IP Binding

PerimeterX cookies are typically **IP-bound**. This means:
- Cookies copied from localhost work when the scraper also runs on localhost
- In production (Railway), the user must generate cookies while on the **same IP**
  as the Railway instance — which is impractical

For production, the cookie bypass is mainly useful for:
- Sites where cookies are NOT IP-bound (many Akamai / Cloudflare setups)
- Development/testing environments
