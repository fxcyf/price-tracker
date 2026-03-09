import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB
from app.models.price_history import PriceHistory
from app.models.product import Product, Tag
from app.models.watch_config import WatchConfig
from app.scrapers.dispatcher import scrape_product
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError

router = APIRouter(tags=["products"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    title: str | None
    image_url: str | None
    category: str | None
    platform: str | None
    current_price: float | None
    currency: str
    tags: list[TagOut]
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    url: str
    tags: list[str] = []

    @field_validator("url")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_tags(db: DB, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in names:
        name = name.strip().lower()
        if not name:
            continue
        result = await db.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            await db.flush()
        tags.append(tag)
    return tags


async def _get_product_or_404(db: DB, product_id: uuid.UUID) -> Product:
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.tags))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductCreate, db: DB):
    """Import a new product by URL. Scrapes title, price, and image automatically."""
    try:
        data = await scrape_product(body.url, db)
    except SiteBlockedError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except CookiesExpiredError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to scrape product: {e}")

    tags = await _get_or_create_tags(db, body.tags)

    product = Product(
        url=body.url,
        title=data.title,
        image_url=data.image_url,
        category=data.category,
        platform=data.platform,
        current_price=data.price,
        currency=data.currency,
        tags=tags,
    )
    db.add(product)
    await db.flush()

    # Record initial price snapshot
    if data.price is not None:
        db.add(PriceHistory(
            product_id=product.id,
            price=data.price,
            currency=data.currency,
        ))

    # Create default watch config so GET /products/{id}/watch never 404s
    db.add(WatchConfig(product_id=product.id))

    await db.commit()
    result = await db.execute(
        select(Product)
        .where(Product.id == product.id)
        .options(selectinload(Product.tags))
    )
    return result.scalar_one()


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    db: DB,
    category: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
):
    """List all tracked products with optional category or tag filter."""
    stmt = select(Product).options(selectinload(Product.tags)).order_by(Product.created_at.desc())

    if category:
        stmt = stmt.where(Product.category.ilike(f"%{category}%"))

    if tag:
        stmt = stmt.join(Product.tags).where(Tag.name == tag.strip().lower())

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, db: DB):
    """Get a single product by ID."""
    return await _get_product_or_404(db, product_id)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: uuid.UUID, db: DB):
    """Delete a product and all its price history."""
    product = await _get_product_or_404(db, product_id)
    await db.delete(product)
    await db.commit()
