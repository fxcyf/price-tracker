#!/usr/bin/env python3
"""
Integration test script for Celery and email.

Usage (run inside the worker container):
  docker compose exec worker python test_integrations.py [test]

Tests:
  all        Run all tests (default)
  celery     Test Celery task dispatch + result
  email      Test email sending directly
  pricecheck Trigger a real price check on the first tracked product
"""

import sys
import os
import time

# ── helpers ──────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def ok(msg): print(f"  {GREEN}✓{RESET}  {msg}")
def fail(msg): print(f"  {RED}✗{RESET}  {msg}")
def info(msg): print(f"  {YELLOW}→{RESET}  {msg}")
def header(msg): print(f"\n{'─'*50}\n  {msg}\n{'─'*50}")


# ── Test 1: Celery connectivity ───────────────────────────────────────────────

def test_celery():
    header("Test: Celery connectivity")
    from app.tasks.celery_app import celery_app

    info("Pinging all workers...")
    try:
        response = celery_app.control.ping(timeout=5)
        if response:
            for worker, result in response[0].items():
                ok(f"Worker online: {worker} → {result}")
        else:
            fail("No workers responded to ping (is the worker container running?)")
            return False
    except Exception as e:
        fail(f"Ping failed: {e}")
        return False

    info("Sending a test task (add 2+2)...")
    try:
        # Use a simple built-in debug task
        result = celery_app.send_task("celery.backend_cleanup")
        ok(f"Task enqueued: id={result.id}")
    except Exception as e:
        fail(f"Task dispatch failed: {e}")
        return False

    return True


# ── Test 2: run_all_price_checks dispatch ────────────────────────────────────

def test_price_check_dispatch():
    header("Test: Price check task dispatch")
    from app.tasks.price_check import run_all_price_checks
    from app.core.database import get_sync_db
    from app.models.product import Product
    from app.models.watch_config import WatchConfig
    from sqlalchemy import select

    with get_sync_db() as db:
        rows = db.execute(
            select(Product.id, Product.title, Product.url)
            .join(WatchConfig, WatchConfig.product_id == Product.id)
            .where(WatchConfig.is_active.is_(True))
        ).fetchall()

    if not rows:
        info("No active products in DB — add a product first, then re-run.")
        return None

    info(f"Found {len(rows)} active product(s):")
    for row in rows:
        info(f"  [{row[0]}] {row[1] or row[2]}")

    info("Dispatching run_all_price_checks...")
    try:
        result = run_all_price_checks.delay()
        ok(f"Task dispatched: id={result.id}")
        info("Check worker logs: docker compose logs worker -f")
        info("Check DB for new rows: docker compose exec db psql -U postgres pricetracker -c \"SELECT * FROM price_histories ORDER BY scraped_at DESC LIMIT 5;\"")
    except Exception as e:
        fail(f"Dispatch failed: {e}")
        return False

    return True


# ── Test 3: Direct price check on first product ───────────────────────────────

def test_single_price_check():
    header("Test: Single product price check (synchronous)")
    from app.core.database import get_sync_db
    from app.models.product import Product
    from app.models.watch_config import WatchConfig
    from app.tasks.price_check import check_product_price
    from sqlalchemy import select

    with get_sync_db() as db:
        row = db.execute(
            select(Product.id, Product.title, Product.url)
            .join(WatchConfig, WatchConfig.product_id == Product.id)
            .where(WatchConfig.is_active.is_(True))
        ).first()

    if not row:
        info("No active products found — add a product first.")
        return None

    product_id = str(row[0])
    info(f"Running price check for: {row[1] or row[2]}")
    info(f"Product ID: {product_id}")

    try:
        # Call directly (not via .delay()) so we get the result synchronously
        result = check_product_price(product_id)
        status = result.get("status")
        if status == "ok":
            ok(f"Price check succeeded")
            ok(f"  old_price={result.get('old_price')}  new_price={result.get('new_price')}  alert={result.get('alert')}")
        elif status == "first_check":
            ok(f"First check — price recorded: {result.get('price')}")
        elif status == "no_price":
            fail("Scraper ran but could not extract a price")
        else:
            fail(f"Unexpected status: {result}")
    except Exception as e:
        fail(f"Price check raised an exception: {e}")
        import traceback; traceback.print_exc()
        return False

    return True


# ── Test 4: Email send ────────────────────────────────────────────────────────

def test_email():
    header("Test: Email sending")
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.smtp_user:
        info("SMTP_USER is not set in .env — skipping email test.")
        info("Set SMTP_USER, SMTP_PASSWORD, and SMTP_FROM to enable email alerts.")
        return None

    # notify_email is stored in the DB Settings row, not in config
    from app.core.database import get_sync_db
    from app.models.settings import Settings as DBSettings, SETTINGS_ID
    db_notify_email = None
    with get_sync_db() as db:
        db_settings = db.get(DBSettings, SETTINGS_ID)
        if db_settings:
            db_notify_email = db_settings.notify_email

    recipient = db_notify_email or settings.smtp_user
    info(f"Sending test email to: {recipient}  (set NOTIFY_EMAIL in Settings page to override)")
    info(f"SMTP host: {settings.smtp_host}:{settings.smtp_port}")

    from app.notify.email import send_price_digest

    fake_alerts = [
        {
            "title": "Test Product A (Price Tracker Integration Test)",
            "url": "https://example.com/product-a",
            "image_url": None,
            "currency": "USD",
            "old_price": 100.00,
            "new_price": 79.99,
            "direction": "dropped",
            "pct": 20.01,
        },
        {
            "title": "Test Product B (Price Tracker Integration Test)",
            "url": "https://example.com/product-b",
            "image_url": None,
            "currency": "USD",
            "old_price": 50.00,
            "new_price": 55.00,
            "direction": "increased",
            "pct": 10.00,
        },
    ]

    try:
        send_price_digest(recipient, fake_alerts)
        ok(f"Digest email sent to {recipient}")
        ok("Check your inbox (and spam folder)")
    except Exception as e:
        fail(f"Email failed: {e}")
        info("Common causes:")
        info("  Gmail: use an App Password, not your account password")
        info("  Gmail App Passwords require 2FA to be enabled")
        info("  Check SMTP_HOST / SMTP_PORT / SMTP_FROM in .env")
        return False

    return True


# ── Main ──────────────────────────────────────────────────────────────────────

TESTS = {
    "celery":     test_celery,
    "pricecheck": test_single_price_check,
    "dispatch":   test_price_check_dispatch,
    "email":      test_email,
}

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "all":
        selected = list(TESTS.items())
    elif arg in TESTS:
        selected = [(arg, TESTS[arg])]
    else:
        print(f"Unknown test '{arg}'. Available: all, {', '.join(TESTS)}")
        sys.exit(1)

    results = {}
    for name, fn in selected:
        result = fn()
        results[name] = result

    print(f"\n{'─'*50}")
    print("  Summary")
    print(f"{'─'*50}")
    for name, result in results.items():
        if result is True:
            print(f"  {GREEN}PASS{RESET}  {name}")
        elif result is None:
            print(f"  {YELLOW}SKIP{RESET}  {name}")
        else:
            print(f"  {RED}FAIL{RESET}  {name}")

    print()
    failed = [n for n, r in results.items() if r is False]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
