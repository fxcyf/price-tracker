# Celery Tasks & Beat

## File Map

| File | Role |
|---|---|
| `app/tasks/celery_app.py` | Celery instance + Beat schedule definition |
| `app/tasks/__init__.py` | Re-exports `celery_app` (docker-compose uses `app.tasks.celery_app`) |
| `app/tasks/price_check.py` | `run_all_price_checks` (Beat entry) + `check_product_price` (worker) |
| `app/notify/email.py` | SMTP sender via smtplib + Jinja2 template renderer |
| `app/notify/templates/price_alert.html` | HTML email template |
| `app/core/database.py` | `get_sync_db()` — sync SQLAlchemy session for Celery |

## Scheduling Model

- One global `check_interval_hours` in `settings` table (default 24h), also mirrored in `.env` as `CHECK_INTERVAL_HOURS`
- Beat fires `run_all_price_checks` on that cadence
- All active products are checked together — no per-product intervals
- **Changing the interval** requires restarting the Beat process (schedule is read at startup)

## Sync vs Async Pattern

Celery tasks are synchronous. The DB and scraper are async. Bridge:

```python
# In a Celery task — sync context
with get_sync_db() as db:
    product = db.get(Product, pid)   # sync ORM query

new_price = asyncio.run(_scrape_price(url))  # run async scraper from sync

async def _scrape_price(url):
    async with AsyncSessionLocal() as db:
        return await scrape_price_only(url, db)
```

Rule: use `get_sync_db()` for DB reads/writes inside tasks, use `asyncio.run()` only for the async scraper call.

## Alert Logic

Per-product: `alert_on_drop_pct` (e.g. 5%) — trigger when `(old - new) / old * 100 >= threshold`
Global: `settings.alert_on_rise` — trigger when new price > old price

## Running Locally

```bash
# In separate terminals (after docker-compose up db redis):
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat   --loglevel=info
```

## Pitfall: Beat Schedule Read at Startup

The Beat schedule (`timedelta(hours=N)`) is set once when `celery_app.py` is imported.
Changing `CHECK_INTERVAL_HOURS` in `.env` or `check_interval_hours` in the DB does NOT
update a running Beat process — you must restart it.
