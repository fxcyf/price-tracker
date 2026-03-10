import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.sql.expression import nullslast
from sqlalchemy.orm import selectinload

from app.api.deps import DB
from app.models.price_history import PriceHistory
from app.models.product import Product, Tag
from app.models.watch_config import WatchConfig
from app.scrapers.dispatcher import scrape_product
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError

router = APIRouter(tags=["products"])


@router.get("/tags", response_model=list[str])
async def list_tags(db: DB):
    """Return all tag names that are used by at least one product, sorted alphabetically."""
    rows = await db.execute(
        select(Tag.name)
        .join(Tag.products)
        .distinct()
        .order_by(Tag.name)
    )
    return rows.scalars().all()


@router.delete("/tags/{tag_name}", status_code=204)
async def delete_tag(tag_name: str, db: DB):
    """Delete a tag by name. Removes it from all products automatically (cascade)."""
    row = await db.execute(select(Tag).where(Tag.name == tag_name))
    tag = row.scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    await db.delete(tag)
    await db.commit()


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
    brand: str | None
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
        brand=data.brand,
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


_SORT_COLUMNS = {
    "date_added": Product.created_at,
    "price": Product.current_price,
    "brand": Product.brand,
}


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    db: DB,
    category: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
    sort_by: Annotated[str, Query()] = "date_added",
    sort_dir: Annotated[str, Query()] = "desc",
):
    """List all tracked products with optional category/tag filters and sorting."""
    if sort_by not in _SORT_COLUMNS:
        sort_by = "date_added"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    col = _SORT_COLUMNS[sort_by]
    order_expr = nullslast(col.asc() if sort_dir == "asc" else col.desc())

    stmt = select(Product).options(selectinload(Product.tags)).order_by(order_expr)

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


class TagSuggestionsOut(BaseModel):
    suggested_tags: list[str]


@router.post("/products/{product_id}/suggest-tags", response_model=TagSuggestionsOut)
async def suggest_tags(product_id: uuid.UUID, db: DB):
    """
    Ask the LLM to suggest tags for a product based on its title and category.
    Also normalises the raw category string as a side effect.
    Returns suggested tag names only — does not modify the product.
    """
    from app.scrapers.extractors.llm import normalize_and_suggest

    product = await _get_product_or_404(db, product_id)

    # Fetch all existing tag names for context
    tag_rows = await db.execute(
        select(Tag.name).join(Tag.products).distinct().order_by(Tag.name)
    )
    existing_tags = list(tag_rows.scalars().all())

    _, suggested = await normalize_and_suggest(
        title=product.title,
        raw_category=product.category,
        existing_tags=existing_tags,
    )
    return TagSuggestionsOut(suggested_tags=suggested)


class ImageUpdate(BaseModel):
    image_url: str | None


@router.patch("/products/{product_id}/image", response_model=ProductOut)
async def update_product_image(product_id: uuid.UUID, body: ImageUpdate, db: DB):
    """Update the image URL for a product."""
    product = await _get_product_or_404(db, product_id)
    product.image_url = body.image_url
    await db.commit()
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.tags))
    )
    return result.scalar_one()


class TagsUpdate(BaseModel):
    tags: list[str]


@router.patch("/products/{product_id}/tags", response_model=ProductOut)
async def update_product_tags(product_id: uuid.UUID, body: TagsUpdate, db: DB):
    """Replace the tag set for a product."""
    product = await _get_product_or_404(db, product_id)
    product.tags = await _get_or_create_tags(db, body.tags)
    await db.commit()
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.tags))
    )
    return result.scalar_one()


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: uuid.UUID, db: DB):
    """Delete a product and all its price history."""
    product = await _get_product_or_404(db, product_id)
    await db.delete(product)
    await db.commit()
