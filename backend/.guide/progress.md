# Progress

## Active

- Investigating fetchable cases in `cases.json` for additional field extraction opportunities (brand, in_stock, category)

## Completed

- **2026-03-22** — Initialized `.guide/context.md` and `AGENTS.md`
- **2026-03-22** — Added `in_stock` CSS selector support and `brand` field to `PlatformRule`; added Madewell platform rule (`brand="Madewell"`)
- **2026-03-22** — Fixed opengraph extractor: `@graph` JSON-LD unwrapping, `itemprop="availability"` on non-`<meta>` elements, `itemprop="brand"` `content` attribute
- **2026-03-22** — Tightened `cases.json` expectations: Madewell, COS, Uniqlo, Maison Kitsune now assert `brand: "ok"` and `in_stock: "ok"`
- **2026-03-22** — Marked BestBuy and Urban Outfitters as `fetch: "ok"` (no longer bot-blocked)
- **2026-03-22** — Added stock/availability detection and restock notification system
- **2026-03-22** — Added `in_stock` and `notify_on_restock` fields to data model

## Plans

- [2026-03-22 Improve Extraction for Fetchable Cases](.guide/plans/2026-03-22-fetchable-cases-extraction.md) — Tackle each fetchable case in cases.json to maximize extracted fields (brand, in_stock, etc.)
