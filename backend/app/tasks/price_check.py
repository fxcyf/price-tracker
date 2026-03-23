from __future__ import annotations

"""
Celery tasks for periodic price checking.

Flow:
  Beat fires run_all_price_checks()
    → chord of check_product_price() tasks, one per active product
    → send_price_digest_task() callback receives all results and sends ONE email
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from celery import chord, group
from sqlalchemy import select

from app.core.database import CeleryAsyncSessionLocal, get_sync_db
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.models.settings import SETTINGS_ID, Settings
from app.models.watch_config import WatchConfig
from app.scrapers.dispatcher import scrape_price_only
from app.scrapers.fetcher import CookiesExpiredError
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.price_check.run_all_price_checks")
def run_all_price_checks() -> dict:
    """
    Beat entry point. Queries all active products, dispatches one
    check_product_price task per product, then sends a single digest
    email via a chord callback once all checks complete.
    """
    with get_sync_db() as db:
        rows = db.execute(
            select(Product.id)
            .join(WatchConfig, WatchConfig.product_id == Product.id)
            .where(WatchConfig.is_active.is_(True))
        ).fetchall()

    product_ids = [str(row[0]) for row in rows]
    if not product_ids:
        logger.info("No active products to check")
        return {"dispatched": 0}

    job = chord(
        group(check_product_price.s(pid) for pid in product_ids),
        send_price_digest_task.s(),
    )
    job.delay()

    logger.info("Dispatched price checks for %d products", len(product_ids))
    return {"dispatched": len(product_ids)}


@celery_app.task(
    name="app.tasks.price_check.check_product_price",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def check_product_price(self, product_id: str) -> dict:
    """
    Scrape the current price for one product, save it to history,
    and return alert details — the digest task handles email sending.
    """
    pid = uuid.UUID(product_id)

    with get_sync_db() as db:
        product = db.get(Product, pid)
        if not product:
            logger.warning("check_product_price: product %s not found", product_id)
            return {"status": "not_found"}

        watch = db.execute(
            select(WatchConfig).where(WatchConfig.product_id == pid)
        ).scalar_one_or_none()

        if not watch or not watch.is_active:
            return {"status": "inactive"}

        settings = db.get(Settings, SETTINGS_ID)
        old_price = float(product.current_price) if product.current_price is not None else None
        old_in_stock = product.in_stock
        notify_on_restock = watch.notify_on_restock if watch else False

    # --- Scrape (async → sync bridge) ---
    try:
        new_price, new_in_stock = asyncio.run(_scrape_price(product.url))
    except CookiesExpiredError as exc:
        logger.warning("Cookies expired for %s: %s", product.url, exc)
        return {"status": "cookies_expired", "url": product.url}
    except Exception as exc:
        logger.error("Scrape failed for %s: %s", product.url, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "error": str(exc)}

    # --- Restock detection (computed before early returns) ---
    restock_alert = (
        old_in_stock is False
        and new_in_stock is True
        and notify_on_restock
    )

    if new_price is None:
        # Persist stock status change even when price is unavailable
        if new_in_stock is not None:
            with get_sync_db() as db:
                p = db.get(Product, pid)
                p.in_stock = new_in_stock
                w = db.execute(
                    select(WatchConfig).where(WatchConfig.product_id == pid)
                ).scalar_one_or_none()
                if w:
                    w.last_checked_at = datetime.now(timezone.utc)
        if restock_alert:
            logger.info("Restock detected for %s (no price)", product.title)
            return {
                "status": "no_price",
                "alert": True,
                "title": product.title,
                "url": product.url,
                "image_url": product.image_url,
                "currency": product.currency,
                "direction": "restocked",
            }
        logger.warning("No price extracted for %s", product.url)
        return {"status": "no_price"}

    # --- Persist results ---
    with get_sync_db() as db:
        product = db.get(Product, pid)
        watch = db.execute(
            select(WatchConfig).where(WatchConfig.product_id == pid)
        ).scalar_one_or_none()

        db.add(PriceHistory(
            product_id=pid,
            price=new_price,
            currency=product.currency,
        ))

        product.current_price = new_price
        if new_in_stock is not None:
            product.in_stock = new_in_stock
        watch.last_checked_at = datetime.now(timezone.utc)

    # --- Price change detection ---
    if old_price is None:
        return {"status": "ok", "price": new_price, "change": "first_check"}

    alert_triggered = False
    direction = None
    pct = 0.0

    if new_price < old_price:
        pct = (old_price - new_price) / old_price * 100
        if watch and pct >= float(watch.alert_on_drop_pct):
            alert_triggered = True
            direction = "dropped"
            logger.info(
                "Price drop %.1f%% for %s: %.2f → %.2f",
                pct, product.title, old_price, new_price,
            )

    elif new_price > old_price and settings and settings.alert_on_rise:
        pct = (new_price - old_price) / old_price * 100
        alert_triggered = True
        direction = "increased"
        logger.info(
            "Price rose for %s: %.2f → %.2f", product.title, old_price, new_price
        )

    if restock_alert:
        alert_triggered = True
        direction = "restocked"
        logger.info("Restock detected for %s", product.title)

    result: dict = {
        "status": "ok",
        "old_price": float(old_price),
        "new_price": float(new_price),
        "alert": alert_triggered,
    }

    if alert_triggered:
        result.update({
            "title": product.title,
            "url": product.url,
            "image_url": product.image_url,
            "currency": product.currency,
            "direction": direction,
            "pct": pct,
        })

    return result


@celery_app.task(name="app.tasks.price_check.send_price_digest_task")
def send_price_digest_task(results: list[dict]) -> dict:
    """
    Chord callback: receives all check results and sends one digest email
    if any products triggered an alert.
    """
    alerts = [r for r in results if r and r.get("alert")]

    if not alerts:
        logger.info("No price alerts to send in this cycle")
        return {"emails_sent": 0}

    with get_sync_db() as db:
        settings = db.get(Settings, SETTINGS_ID)

    notify_email = settings.notify_email if settings else None
    if not notify_email:
        logger.warning("No notify_email configured — skipping digest email")
        return {"emails_sent": 0, "alerts": len(alerts)}

    from app.notify.email import send_price_digest
    try:
        send_price_digest(notify_email, alerts)
        logger.info("Digest email sent to %s (%d alert(s))", notify_email, len(alerts))
        return {"emails_sent": 1, "alerts": len(alerts)}
    except Exception as exc:
        logger.error("Failed to send digest email: %s", exc)
        return {"emails_sent": 0, "error": str(exc)}


async def _scrape_price(url: str) -> tuple[float | None, bool | None]:
    """Async helper: open a fresh async DB session and call scrape_price_only.
    Uses CeleryAsyncSessionLocal (NullPool) to avoid inheriting pooled connections
    across Celery's fork() boundary."""
    async with CeleryAsyncSessionLocal() as db:
        return await scrape_price_only(url, db)
