from datetime import timedelta

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "price_tracker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.price_check"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry failed tasks up to 3 times with exponential backoff
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Beat schedule: fire run_all_price_checks every check_interval_hours.
# Note: changing check_interval_hours in .env requires a Beat process restart.
celery_app.conf.beat_schedule = {
    "run-all-price-checks": {
        "task": "app.tasks.price_check.run_all_price_checks",
        "schedule": timedelta(hours=settings.check_interval_hours),
    }
}
