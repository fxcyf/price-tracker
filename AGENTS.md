# AGENTS.md

> A self-hosted product price tracker: paste a URL, the app scrapes the price on a schedule and emails you when it drops below your target.

## Orientation

| | |
|---|---|
| **What it does** | Monitors e-commerce product prices; sends email alerts on price drops |
| **Who uses it** | Single-user / self-hosted |
| **Stack** | FastAPI + SQLAlchemy (backend), React 19 + Vite (frontend), Celery + Redis (task queue), PostgreSQL, Docker Compose |

## Key commands

```bash
# Backend tests (from backend/)
python -m pytest                                              # unit tests only, no network
python -m pytest --run-live tests/test_live_cases.py -v -s   # live per-field regression (all cases)
python -m pytest --run-live tests/test_live_cases.py -v -s -k "everlane"  # single case by label
python -m pytest --run-live --live-curl-file=curl.txt tests/test_live_cases.py -v -s -k "freepeople"  # cookie-backed case

# Debug a single URL
python test_scraper.py --live "https://..."              # anonymous fetch
python test_scraper.py --live-curl curl.txt              # fetch with browser cookies

# Dev stack (isolated from prod, different ports)
docker compose -f docker-compose.yml -f docker-compose.dev.yml --project-name dev up --build

# Frontend hot-reload
cd frontend && npm run dev   # :5173, proxies /api → :8001
```

## Architecture

The backend's core is a **layered scraper pipeline** (`backend/app/scrapers/`). Every product scrape runs through four layers in sequence: OpenGraph/JSON-LD metadata, hard-coded platform CSS rules, learned rules cached in the `domain_rules` DB table, and an OpenAI LLM fallback. Each layer fills in missing fields; the first layer to find a field wins. A scrape is "complete" when a price is found.

Fetching is handled separately in `fetcher.py` and decides *how* to retrieve the HTML before extraction begins. The fetch priority is: `curl_cffi` with Chrome TLS impersonation + user cookies (bypasses PerimeterX `_px3` binding) → Playwright + cookies → anonymous httpx → anonymous Playwright. Domains in `PLAYWRIGHT_REQUIRED_DOMAINS` skip httpx entirely. `SiteBlockedError` signals a hard bot-wall; `CookiesExpiredError` signals that stored cookies need refreshing.

Periodic price checks run as Celery tasks. `run_all_price_checks` (Beat entry point) fans out a `chord` of per-product `check_product_price` tasks, then collects results in `send_price_digest_task` to send a single email. Because Celery tasks are sync but the scraper is async, there is a deliberate `asyncio.run()` bridge inside `check_product_price` using `CeleryAsyncSessionLocal` (NullPool) to avoid connection-pool issues across `fork()`.

The `domain_rules` table serves double duty: it stores LLM-learned CSS selectors (auto-populated after a successful Layer 3 scrape, reused as Layer 2b) and user-imported browser cookies (imported via `PUT /api/domains/{domain}/cookies` or `test_scraper.py --live-curl`).

## Guide index

| File | What it covers |
|---|---|
| `.guide/context.md` | Architecture deep-dive (pipeline, fetch strategy, invariants) |
| `.guide/scraper-pipeline.md` | Scraper pipeline lessons and design decisions |
| `.guide/cookie-import.md` | Browser cookie bypass workflow (PerimeterX, Cloudflare) |
| `.guide/live-regression-playwright-runtime.md` | Live test setup, cases.json schema, graduation path |
| `.guide/crawler-effectiveness-workflow.md` | How to diagnose and fix failing URLs |
| `.guide/celery-tasks.md` | Celery + Beat task structure |
| `.guide/api-routes.md` | FastAPI endpoint reference |
| `.guide/environments.md` | Dev vs prod Docker stack isolation |
| `.guide/frontend-product-list.md` | Frontend patterns |
| `.guide/mobile-ux.md` | Mobile UX notes |
| `.guide/progress.md` | What's done, what's active |
| `.guide/plans/` | Pre-implementation plans (one file per task) |

## Keeping .guide/ up to date

After completing any significant change, update the relevant `.guide/` files:
- Add a line to `## Completed` in `.guide/progress.md`
- Update `.guide/context.md` if the architecture or any critical invariant changed
- Update the relevant topic file (e.g. `scraper-pipeline.md`, `cookie-import.md`) if lessons were learned
- Create a new plan file in `.guide/plans/` before starting non-trivial work (use `/make-plan`)
