"""Tests for /api/products creation behavior."""

import asyncio
import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.products import ProductCreate, create_product
from app.scrapers.fetcher import SiteBlockedError
from app.scrapers.schemas import ProductData


def _db_mock():
    db = AsyncMock()
    db.add = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = MagicMock()
    db.execute.return_value = result_mock
    return db


def test_create_product_raises_422_when_blocked_without_save_anyway():
    db = _db_mock()
    body = ProductCreate(url="https://www.freepeople.com/shop/p/1", tags=[], save_anyway=False)

    with (
        patch("app.api.products.scrape_product", new=AsyncMock(side_effect=SiteBlockedError("blocked"))),
        patch("app.api.products._get_or_create_tags", new=AsyncMock(return_value=[])),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(create_product(body, db))

    assert exc_info.value.status_code == 422


def test_create_product_saves_minimal_row_when_blocked_with_save_anyway():
    db = _db_mock()
    body = ProductCreate(url="https://www.freepeople.com/shop/p/1", tags=[], save_anyway=True)

    with (
        patch("app.api.products.scrape_product", new=AsyncMock(side_effect=SiteBlockedError("blocked"))),
        patch("app.api.products._get_or_create_tags", new=AsyncMock(return_value=[])),
    ):
        asyncio.run(create_product(body, db))

    first_added = db.add.call_args_list[0].args[0]
    assert first_added.url == body.url
    assert first_added.current_price is None
