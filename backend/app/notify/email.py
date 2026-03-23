"""
Email notification module using stdlib smtplib + Jinja2 templates.
No extra dependencies beyond what's already in requirements.txt.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


def send_email(to: str, subject: str, html_body: str) -> None:
    """
    Send an HTML email via SMTP.
    Raises RuntimeError if SMTP is not configured (smtp_user is empty).
    """
    settings = get_settings()

    if not settings.smtp_user:
        logger.warning("SMTP not configured — skipping email to %s", to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to], msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
    except smtplib.SMTPException as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        raise


def send_price_alert(
    to: str,
    product,
    old_price: float,
    new_price: float,
) -> None:
    """Render the price alert template and send it."""
    direction = "dropped" if new_price < old_price else "increased"
    pct = abs(old_price - new_price) / old_price * 100

    subject = (
        f"Price {direction}: {product.title or product.url} "
        f"({pct:.1f}% {'↓' if direction == 'dropped' else '↑'})"
    )

    template = _jinja_env.get_template("price_alert.html")
    html_body = template.render(
        product=product,
        old_price=old_price,
        new_price=new_price,
        direction=direction,
        pct=pct,
        currency=product.currency,
    )

    send_email(to, subject, html_body)


def send_price_digest(to: str, alerts: list[dict]) -> None:
    """
    Send a single digest email summarising all price alerts from one check cycle.

    Each item in `alerts` is the result dict returned by check_product_price
    when alert=True:
      { title, url, image_url, currency, old_price, new_price, direction, pct }
    """
    n_dropped = sum(1 for a in alerts if a.get("direction") == "dropped")
    n_risen = sum(1 for a in alerts if a.get("direction") == "increased")
    n_restock = sum(1 for a in alerts if a.get("direction") == "restocked")

    parts = []
    if n_dropped:
        parts.append(f"{n_dropped} dropped")
    if n_risen:
        parts.append(f"{n_risen} rose")
    if n_restock:
        parts.append(f"{n_restock} back in stock")
    subject = f"Price Tracker: {', '.join(parts)} ({len(alerts)} product{'s' if len(alerts) > 1 else ''})"

    template = _jinja_env.get_template("price_digest.html")
    html_body = template.render(alerts=alerts)

    send_email(to, subject, html_body)
