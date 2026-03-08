import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CookieStatus:
    NONE = "none"
    VALID = "valid"
    EXPIRED = "expired"


class DomainRule(Base):
    """CSS selectors and cookies for a domain, keyed by domain hostname.

    - Selectors are learned from LLM extraction (Layer 2b).
    - Cookies are imported by the user from their real browser session,
      used to bypass PerimeterX / Cloudflare bot protection.
    """

    __tablename__ = "domain_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)

    # LLM-learned CSS selectors
    price_selector: Mapped[str | None] = mapped_column(Text)
    title_selector: Mapped[str | None] = mapped_column(Text)
    image_selector: Mapped[str | None] = mapped_column(Text)
    success_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # User-imported cookies for bot-protected sites
    # Stored as JSON dict: {"_px3": "...", "bm_sz": "...", ...}
    cookies: Mapped[dict | None] = mapped_column(JSONB)
    cookies_status: Mapped[str] = mapped_column(
        String(20), default=CookieStatus.NONE, nullable=False
    )
    cookies_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
