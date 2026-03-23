# AGENTS.md

> A personal price tracker backend that scrapes e-commerce product pages, stores price history, and sends email alerts on price drops, rises, and restocks.

## Orientation

| | |
|---|---|
| **What it does** | Accepts product URLs, scrapes price/title/image/brand/stock via a layered extraction pipeline, stores history in Postgres, and runs periodic Celery price checks that trigger email digests |
| **Who uses it** | Single personal user; paired with a React frontend |
| **Stack** | FastAPI · SQLAlchemy (async) · PostgreSQL · Celery + Redis · Playwright · httpx · curl_cffi · OpenAI (LLM fallback) · Alembic |

## Key commands

```bash
# Run unit tests (fast, no network)
pytest tests/ --ignore=tests/test_live_cases.py --ignore=tests/test_live_regression.py --ignore=tests/test_live_stock_regression.py --ignore=tests/test_live_cookie_regression.py

# Run live regression suite (hits real sites, needs internet)
pytest --run-live tests/test_live_cases.py -v -s

# Run live suite with user cookies (for cookie-gated sites)
pytest --run-live --live-curl-file=/path/to/curl.txt tests/test_live_cases.py -v -s

# Start the API server
uvicorn app.main:app --reload

# Run Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# Run database migrations
alembic upgrade head
```

## Architecture

The scraper has two independent concerns: **fetching** and **extracting**. `fetcher.py:fetch_page()` tries four strategies in order — curl_cffi with cookies (Chrome TLS impersonation), Playwright with cookies, anonymous httpx, anonymous Playwright — choosing the cheapest path that succeeds. Domains in `PLAYWRIGHT_REQUIRED_DOMAINS` skip httpx because they serve JS shells with no product data in static HTML.

`dispatcher.py:extract_product_data()` runs a four-layer extraction pipeline on the fetched HTML. Layer 1 (OpenGraph/JSON-LD) handles most well-structured sites. Layer 2a applies built-in platform CSS selector rules from `PLATFORM_RULES` in `extractors/rules.py`; each rule can carry an authoritative `brand` field that overrides whatever JSON-LD returned. Layer 2b applies LLM-learned CSS selectors stored per domain in the `domain_rules` table. Layer 3 falls back to an OpenAI call, which also returns CSS selectors saved back to `domain_rules` for future visits. The LLM call is skipped as soon as a price is found.

The periodic price check uses a Celery chord: `run_all_price_checks()` fans out one `check_product_price` task per active product, then `send_price_digest_task` collects all results and sends a single email for any alerts (price drop, price rise if configured, or restock). Bot-blocked sites require users to import browser cookies via `POST /api/cookies/{domain}`, which are stored as JSONB on the `domain_rules` table and injected into all subsequent requests.

## Guide index

| File | What it covers |
|---|---|
| `.guide/context.md` | Architecture deep-dive — extraction layers, fetch strategy, cookie lifecycle, critical invariants |
| `.guide/progress.md` | What's done, what's active, links to plans |
| `.guide/plans/` | Pre-implementation plans (one file per task) |

## Keeping .guide/ up to date

After completing any significant change:
- Add a line to `## Completed` in `.guide/progress.md`
- Update `.guide/context.md` if the architecture or any critical invariant changed (especially the extraction layer ordering or `PLAYWRIGHT_REQUIRED_DOMAINS` logic)
- Update plan status in `.guide/plans/` when a plan's steps are finished
- Create a new plan file in `.guide/plans/` before starting non-trivial work (`/make-plan`)
