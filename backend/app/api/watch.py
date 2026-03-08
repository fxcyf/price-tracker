import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import DB
from app.api.products import _get_product_or_404
from app.models.watch_config import WatchConfig

router = APIRouter(tags=["watch"])


class WatchConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    alert_on_drop_pct: float
    is_active: bool
    last_checked_at: datetime | None
    created_at: datetime


class WatchConfigIn(BaseModel):
    alert_on_drop_pct: float = Field(default=5.0, ge=0.1, le=100.0)
    is_active: bool = True


@router.get("/products/{product_id}/watch", response_model=WatchConfigOut)
async def get_watch_config(product_id: uuid.UUID, db: DB):
    """Get the watch/alert config for a product."""
    await _get_product_or_404(db, product_id)

    result = await db.execute(
        select(WatchConfig).where(WatchConfig.product_id == product_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Watch config not found for this product")
    return config


@router.put("/products/{product_id}/watch", response_model=WatchConfigOut)
async def upsert_watch_config(product_id: uuid.UUID, body: WatchConfigIn, db: DB):
    """Create or update the watch/alert config for a product."""
    await _get_product_or_404(db, product_id)

    result = await db.execute(
        select(WatchConfig).where(WatchConfig.product_id == product_id)
    )
    config = result.scalar_one_or_none()

    if config:
        config.alert_on_drop_pct = body.alert_on_drop_pct
        config.is_active = body.is_active
    else:
        config = WatchConfig(
            product_id=product_id,
            alert_on_drop_pct=body.alert_on_drop_pct,
            is_active=body.is_active,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)
    return config
