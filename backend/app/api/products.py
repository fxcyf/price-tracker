from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func as sa_func, or_, select
from sqlalchemy.sql.expression import nullslast
from sqlalchemy.orm import selectinload

from app.api.deps import DB
from app.models.price_history import PriceHistory
from app.models.product import Product, Tag
from app.models.watch_config import WatchConfig
from app.scrapers.dispatcher import scrape_product
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError
from app.scrapers.schemas import ProductData

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
    title: Optional[str]
    image_url: Optional[str]
    category: Optional[str]
    platform: Optional[str]
    brand: Optional[str]
    current_price: Optional[float]
    currency: str
    in_stock: Optional[bool]
    tags: list[TagOut]
    created_at: datetime
    updated_at: datetime
    price_change_pct: Optional[float] = None


class ProductCreate(BaseModel):
    url: str
    tags: list[str] = []
    save_anyway: bool = False

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
    except (SiteBlockedError, CookiesExpiredError) as e:
        if not body.save_anyway:
            raise HTTPException(status_code=422, detail=str(e))
        # "Save anyway" stores a minimal product row when scraping is blocked.
        data = ProductData(url=body.url)
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
        in_stock=data.in_stock,
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
    q: Annotated[Optional[str], Query()] = None,
    category: Annotated[Optional[str], Query()] = None,
    tag: Annotated[Optional[str], Query()] = None,
    brand: Annotated[Optional[str], Query()] = None,
    platform: Annotated[Optional[str], Query()] = None,
    in_stock: Annotated[Optional[bool], Query()] = None,
    sort_by: Annotated[str, Query()] = "date_added",
    sort_dir: Annotated[str, Query()] = "desc",
):
    """List all tracked products with optional filters and sorting."""
    if sort_by not in _SORT_COLUMNS:
        sort_by = "date_added"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    col = _SORT_COLUMNS[sort_by]
    order_expr = nullslast(col.asc() if sort_dir == "asc" else col.desc())

    stmt = select(Product).options(selectinload(Product.tags)).order_by(order_expr)

    # Global search — matches title, brand, or category
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Product.title.ilike(pattern),
                Product.brand.ilike(pattern),
                Product.category.ilike(pattern),
            )
        )

    # Legacy category filter (kept for backwards compat)
    if category:
        stmt = stmt.where(Product.category.ilike(f"%{category}%"))

    if tag:
        stmt = stmt.join(Product.tags).where(Tag.name == tag.strip().lower())

    if brand:
        stmt = stmt.where(Product.brand == brand)

    if platform:
        stmt = stmt.where(Product.platform == platform)

    if in_stock is not None:
        stmt = stmt.where(Product.in_stock == in_stock)

    result = await db.execute(stmt)
    products = result.scalars().all()

    # Compute price_change_pct for each product from the two most recent price records
    product_ids = [p.id for p in products]
    pct_map: dict[uuid.UUID, float | None] = {}
    if product_ids:
        for pid in product_ids:
            rows = await db.execute(
                select(PriceHistory.price)
                .where(PriceHistory.product_id == pid)
                .order_by(PriceHistory.scraped_at.desc())
                .limit(2)
            )
            prices = rows.scalars().all()
            if len(prices) >= 2 and prices[1] and prices[1] != 0:
                pct_map[pid] = round((prices[0] - prices[1]) / prices[1] * 100, 2)

    # Build response with price_change_pct
    out: list[dict] = []
    for p in products:
        d = ProductOut.model_validate(p).model_dump()
        d["price_change_pct"] = pct_map.get(p.id)
        out.append(d)
    return out


class FacetsOut(BaseModel):
    brands: list[str]
    platforms: list[str]
    in_stock_count: int
    out_of_stock_count: int


@router.get("/products/facets", response_model=FacetsOut)
async def product_facets(db: DB):
    """Return available filter options (brands, platforms, stock counts)."""
    brand_rows = await db.execute(
        select(Product.brand)
        .where(Product.brand.is_not(None))
        .distinct()
        .order_by(Product.brand)
    )
    brands = brand_rows.scalars().all()

    platform_rows = await db.execute(
        select(Product.platform)
        .where(Product.platform.is_not(None))
        .distinct()
        .order_by(Product.platform)
    )
    platforms = platform_rows.scalars().all()

    in_stock_row = await db.execute(
        select(sa_func.count()).select_from(Product).where(Product.in_stock == True)  # noqa: E712
    )
    in_stock_count = in_stock_row.scalar() or 0

    out_of_stock_row = await db.execute(
        select(sa_func.count()).select_from(Product).where(Product.in_stock == False)  # noqa: E712
    )
    out_of_stock_count = out_of_stock_row.scalar() or 0

    return FacetsOut(
        brands=brands,
        platforms=platforms,
        in_stock_count=in_stock_count,
        out_of_stock_count=out_of_stock_count,
    )


class StatsOut(BaseModel):
    total: int
    in_stock: int
    price_dropped_today: int


@router.get("/products/stats", response_model=StatsOut)
async def product_stats(db: DB):
    """Quick stats for the product list header."""
    total_row = await db.execute(select(sa_func.count()).select_from(Product))
    total = total_row.scalar() or 0

    in_stock_row = await db.execute(
        select(sa_func.count()).select_from(Product).where(Product.in_stock == True)  # noqa: E712
    )
    in_stock = in_stock_row.scalar() or 0

    # Count products whose price dropped in the last 24h
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    # Subquery: for each product, get the latest price before 'since' and the latest price after
    dropped = 0
    product_ids_rows = await db.execute(select(Product.id))
    for (pid,) in product_ids_rows.all():
        old_row = await db.execute(
            select(PriceHistory.price)
            .where(PriceHistory.product_id == pid, PriceHistory.scraped_at < since)
            .order_by(PriceHistory.scraped_at.desc())
            .limit(1)
        )
        new_row = await db.execute(
            select(PriceHistory.price)
            .where(PriceHistory.product_id == pid, PriceHistory.scraped_at >= since)
            .order_by(PriceHistory.scraped_at.desc())
            .limit(1)
        )
        old_price = old_row.scalar()
        new_price = new_row.scalar()
        if old_price and new_price and new_price < old_price:
            dropped += 1

    return StatsOut(total=total, in_stock=in_stock, price_dropped_today=dropped)


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
    image_url: Optional[str]


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
