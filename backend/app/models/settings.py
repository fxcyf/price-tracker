from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

SETTINGS_ID = 1  # Always a single row


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SETTINGS_ID)
    notify_email: Mapped[Optional[str]] = mapped_column(String(255))
    # Price check schedule — all products follow the same global cadence
    check_interval_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    # Alert on price rise (global toggle); per-product drop threshold stays in WatchConfig
    alert_on_rise: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
