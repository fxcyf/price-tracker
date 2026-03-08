import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.deps import DB
from app.api.products import _get_product_or_404
from app.models.price_history import PriceHistory

router = APIRouter(tags=["prices"])


class PricePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price: float
    currency: str
    scraped_at: datetime


@router.get("/products/{product_id}/prices", response_model=list[PricePoint])
async def get_price_history(
    product_id: uuid.UUID,
    db: DB,
    days: Annotated[int, Query(ge=1, le=3650)] = 30,
):
    """Return price history for a product. Defaults to the last 30 days."""
    await _get_product_or_404(db, product_id)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.product_id == product_id,
            PriceHistory.scraped_at >= since,
        )
        .order_by(PriceHistory.scraped_at.asc())
    )
    return result.scalars().all()
