from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.api.deps import DB
from app.scrapers.dispatcher import scrape_product
from app.scrapers.fetcher import CookiesExpiredError, SiteBlockedError

router = APIRouter(tags=["parse"])


class ParseRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()


class ParsePreview(BaseModel):
    url: str
    title: str | None
    price: float | None
    currency: str
    image_url: str | None
    category: str | None
    platform: str
    is_complete: bool


@router.post("/parse", response_model=ParsePreview)
async def parse_url(body: ParseRequest, db: DB):
    """
    Preview what would be extracted from a URL without saving to the database.
    Used by the frontend 'Add Product' modal so the user can confirm before importing.
    """
    try:
        data = await scrape_product(body.url, db)
    except SiteBlockedError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except CookiesExpiredError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}")

    return ParsePreview(
        url=data.url,
        title=data.title,
        price=data.price,
        currency=data.currency,
        image_url=data.image_url,
        category=data.category,
        platform=data.platform,
        is_complete=data.is_complete(),
    )
