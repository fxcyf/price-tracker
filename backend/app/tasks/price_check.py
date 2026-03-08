"""
Celery tasks for periodic price checking.

Flow:
  Beat fires run_all_price_checks() → one check_product_price() task per active product
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, get_sync_db
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
    Beat entry point. Queries all active products and enqueues
    a check_product_price task for each one.
    """
    with get_sync_db() as db:
        rows = db.execute(
            select(Product.id)
            .join(WatchConfig, WatchConfig.product_id == Product.id)
            .where(WatchConfig.is_active.is_(True))
        ).fetchall()

    product_ids = [str(row[0]) for row in rows]
    for pid in product_ids:
        check_product_price.delay(pid)

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
    and send an alert email if the price crossed a threshold.
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

        old_price = product.current_price

    # --- Scrape (async → sync bridge) ---
    try:
        new_price = asyncio.run(_scrape_price(product.url))
    except CookiesExpiredError as exc:
        logger.warning("Cookies expired for %s: %s", product.url, exc)
        return {"status": "cookies_expired", "url": product.url}
    except Exception as exc:
        logger.error("Scrape failed for %s: %s", product.url, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "error": str(exc)}

    if new_price is None:
        logger.warning("No price extracted for %s", product.url)
        return {"status": "no_price"}

    # --- Persist results ---
    with get_sync_db() as db:
        product = db.get(Product, pid)
        watch = db.execute(
            select(WatchConfig).where(WatchConfig.product_id == pid)
        ).scalar_one_or_none()
        settings = db.get(Settings, SETTINGS_ID)

        db.add(PriceHistory(
            product_id=pid,
            price=new_price,
            currency=product.currency,
        ))

        product.current_price = new_price
        watch.last_checked_at = datetime.now(timezone.utc)

    # --- Price change detection ---
    if old_price is None:
        return {"status": "ok", "price": new_price, "change": "first_check"}

    notify_email = settings.notify_email if settings else None
    alert_triggered = False

    if new_price < old_price:
        drop_pct = (old_price - new_price) / old_price * 100
        if watch and drop_pct >= float(watch.alert_on_drop_pct):
            logger.info(
                "Price drop %.1f%% for %s: %.2f → %.2f",
                drop_pct, product.title, old_price, new_price,
            )
            if notify_email:
                _send_alert(notify_email, product, old_price, new_price)
            alert_triggered = True

    elif new_price > old_price and settings and settings.alert_on_rise:
        logger.info(
            "Price rose for %s: %.2f → %.2f", product.title, old_price, new_price
        )
        if notify_email:
            _send_alert(notify_email, product, old_price, new_price)
        alert_triggered = True

    return {
        "status": "ok",
        "old_price": float(old_price),
        "new_price": float(new_price),
        "alert": alert_triggered,
    }


async def _scrape_price(url: str) -> float | None:
    """Async helper: open a fresh async DB session and call scrape_price_only."""
    async with AsyncSessionLocal() as db:
        return await scrape_price_only(url, db)


def _send_alert(to: str, product: Product, old_price: float, new_price: float) -> None:
    """Fire-and-forget email alert — import here to avoid circular imports."""
    from app.notify.email import send_price_alert
    try:
        send_price_alert(to, product, old_price, new_price)
    except Exception as exc:
        logger.error("Failed to send price alert email: %s", exc)
