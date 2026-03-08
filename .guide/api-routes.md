# API Routes

## Endpoint Map

| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /api/products | products.py | Import new product (scrapes + saves) |
| GET | /api/products | products.py | List all products (?category=, ?tag=) |
| GET | /api/products/{id} | products.py | Get single product |
| DELETE | /api/products/{id} | products.py | Delete product + cascade |
| GET | /api/products/{id}/prices | prices.py | Price history (?days=30) |
| GET | /api/products/{id}/watch | watch.py | Get watch config |
| PUT | /api/products/{id}/watch | watch.py | Upsert watch config |
| POST | /api/parse | parse.py | Preview scrape without saving |
| PUT | /api/domains/{domain}/cookies | cookies.py | Import cookies from curl |
| GET | /api/domains/{domain}/cookies | cookies.py | Get cookie status (no values) |
| GET | /api/settings | settings.py | Global notification settings |
| PUT | /api/settings | settings.py | Update notify_email |

## Patterns Used

- **`DB` type alias** in `deps.py`: `Annotated[AsyncSession, Depends(get_db)]` — saves repeating
  the `Depends` call in every function signature, just type `db: DB`

- **`from_attributes=True`** on Pydantic models that read from SQLAlchemy ORM objects — without
  this, Pydantic only accepts dicts

- **`selectinload`** for eager loading relationships (e.g. `Product.tags`) — avoids N+1 queries
  when returning lists; import from `sqlalchemy.orm`

- **`_get_product_or_404`** helper shared across products/prices/watch — avoids repeating the
  same "fetch or 404" pattern; imported directly from `products.py`

- **`EmailStr`** from Pydantic validates email format — requires `pydantic[email]` in requirements

- **`/api/parse`** does NOT save to DB — it calls `scrape_product()` which uses the DB only for
  reading domain rules / cookies, not for writing

## Error Codes

| Situation | HTTP status |
|---|---|
| Product not found | 404 |
| SiteBlockedError (no cookies) | 422 |
| CookiesExpiredError | 422 |
| Invalid curl command | 400 |
| curl domain mismatch | 400 |
| Scraper network failure | 502 |
