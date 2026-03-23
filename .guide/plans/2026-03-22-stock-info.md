# Plan: Stock Information Scraping & Restock Notifications

**Date:** 2026-03-22
**Status:** implemented
**Relates to:** `todos/stock-info.md`, `celery-tasks.md`, `scraper-pipeline.md`

## Goal

Extract `in_stock` status during scraping and alert users when a previously out-of-stock product becomes available again.

## Approach

1. Added `in_stock: bool | None` to `ProductData` dataclass + `merge()`
2. Added `_parse_availability()` to `opengraph.py`; populates `in_stock` from JSON-LD offer and OG `product:availability` meta tag
3. Added `in_stock` nullable column to `products` table (migration 0006)
4. Added `notify_on_restock: bool` column to `watch_configs` (migration 0007, default false, opt-in)
5. Changed `scrape_price_only()` return type to `tuple[float | None, bool | None]`
6. `check_product_price` task detects `old_in_stock=False → new_in_stock=True` and builds `direction="restocked"` alert
7. Email digest counts restocks in subject; template renders "Back in stock" badge for restocked direction
8. `ProductOut` API schema includes `in_stock`; watch config API exposes `notify_on_restock`

## Decision log

| Decision | Rationale |
|---|---|
| `notify_on_restock` opt-in (default False) | Avoids emailing existing users for a new alert type |
| `"restocked"` as third `direction` value | Reuses existing digest loop without a separate email path |
| No `StockHistory` table | Last-known snapshot is sufficient for transition detection |
| No CSS stock selectors | JSON-LD/OG meta coverage is sufficient; CSS is brittle per-platform |
