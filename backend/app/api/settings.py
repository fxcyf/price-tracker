from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select

from app.api.deps import DB
from app.models.settings import SETTINGS_ID, Settings

router = APIRouter(tags=["settings"])


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notify_email: str | None
    check_interval_hours: int
    alert_on_rise: bool
    updated_at: datetime


class SettingsIn(BaseModel):
    notify_email: EmailStr | None = None
    check_interval_hours: int = Field(default=24, ge=1, le=168)
    alert_on_rise: bool = False


async def _get_or_create_settings(db: DB) -> Settings:
    result = await db.execute(select(Settings).where(Settings.id == SETTINGS_ID))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = Settings(id=SETTINGS_ID)
        db.add(settings)
        await db.flush()
    return settings


@router.get("/settings", response_model=SettingsOut)
async def get_settings(db: DB):
    """Get global notification and schedule settings."""
    return await _get_or_create_settings(db)


@router.put("/settings", response_model=SettingsOut)
async def update_settings(body: SettingsIn, db: DB):
    """
    Update global settings.
    Note: changing check_interval_hours requires restarting the Celery Beat process.
    """
    settings = await _get_or_create_settings(db)
    settings.notify_email = body.notify_email
    settings.check_interval_hours = body.check_interval_hours
    settings.alert_on_rise = body.alert_on_rise
    await db.commit()
    await db.refresh(settings)
    return settings
