# Plan: Improve Extraction for Fetchable Cases

**Date:** 2026-03-22
**Status:** in-progress
**Relates to:** tests/cases.json, tests/test_live_cases.py

## Goal

For every case in `cases.json` that has `"fetch": "ok"`, maximize the fields that can be
reliably extracted (price, title, image, brand, in_stock, category) and update the
expectations in `cases.json` to reflect what each site actually exposes.

Currently most fetchable cases declare `brand: null` and `in_stock: null` (no assertion),
meaning we don't know whether the extractor can get those fields.  The goal is to investigate
each site, improve the extraction rules where possible, and tighten the expectations.

## Context

**Fetchable cases** (fetch: "ok") in `tests/cases.json`:

| Label | Site | Has platform rule? | Current gaps |
|---|---|---|---|
| target/pixel-10 | target.com | yes | brand=null, in_stock=null |
| gapfactory/pants | gapfactory.com | yes | brand=null, in_stock=null |
| madewell/bucket-bag | madewell.com | **no** | brand=null, in_stock=null |
| uniqlo/clothing | uniqlo.com | yes | brand=null, in_stock=null |
| cos/linen-trousers | cos.com | **no** | brand=null, in_stock=null |
| everlane/wide-leg-pant | everlane.com | **no** | ✓ brand+in_stock already "ok" |
| everlane/cardigan-xs-oos | everlane.com | **no** | ✓ brand+in_stock already "ok" |
| amazon/book | amazon.com | yes | brand=null, in_stock=null |
| maisonkitsune/cardigan | maisonkitsune.com | **no** | brand=null, in_stock=null |
| tntsupermarket/cookies-gift-set | tntsupermarket.us | **no** | brand=null, in_stock=null |

**Key extractor files:**
- `app/scrapers/extractors/opengraph.py` — Layer 1: OG meta + JSON-LD
- `app/scrapers/extractors/rules.py` — Layer 2a: CSS selector platform rules (`PLATFORM_RULES`)
- `app/scrapers/schemas.py` — `ProductData` dataclass

**Extraction capabilities per layer:**
- OpenGraph already extracts: title, image, price (og:price:amount), brand (og:brand), category (JSON-LD), in_stock (JSON-LD offers.availability, product:availability meta)
- Platform rules currently extract: price, title, image only (no brand/in_stock selectors in `PlatformRule`)
- Shopify sites (Everlane, Madewell, COS, Maison Kitsune) use `ProductGroup` JSON-LD → already handled by `_resolve_product_group_variant` in opengraph.py

## Approach

Work through cases in order of effort — cheapest wins first.

### Step 1 — Madewell (Shopify — JSON-LD likely sufficient)

Madewell runs on Shopify. The opengraph extractor already handles `ProductGroup` JSON-LD
(brand, in_stock from offers.availability). Verify by fetching the page live and checking
what JSON-LD is present.

1. Fetch `madewell/bucket-bag` and inspect its JSON-LD.
2. If ProductGroup/Product JSON-LD has brand + availability: update `cases.json` expectations
   to `"brand": "ok"` and `"in_stock": "ok"`.
3. If title/price only come from JSON-LD (no OG price tag), confirm price still passes.
4. Add a platform rule for `madewell.com` only if JSON-LD alone is insufficient.

### Step 2 — COS (likely H&M Group — JSON-LD structured data)

COS.com is part of the H&M Group. It may expose Product JSON-LD with brand and availability.

1. Fetch `cos/linen-trousers` and inspect JSON-LD + OG tags.
2. If JSON-LD has brand + availability: update `cases.json` to assert them as `"ok"`.
3. If the site uses its own CSS layout for price/title that OG misses: add a `cos.com`
   platform rule.

### Step 3 — Maison Kitsune (Shopify — same path as Madewell)

1. Fetch `maisonkitsune/cardigan` and inspect JSON-LD.
2. Expected: Shopify ProductGroup with brand="Maison Kitsuné" and availability.
3. If confirmed: update `cases.json` expectations. No platform rule needed.

### Step 4 — Target (in_stock via JSON-LD / OG)

Target pages embed JSON-LD but availability data may only appear in the React hydration
payload (not static HTML). The note says "OG price tags" — check whether `product:availability`
meta or JSON-LD offers include availability.

1. Fetch `target/pixel-10` and check for availability signal.
2. If available: update `cases.json` to `"in_stock": "ok"`.
3. Brand on Target: electronics PDPs rarely expose a clean brand; leave `"brand": null` unless
   there's a reliable selector.

### Step 5 — GAP Factory (in_stock + brand via JSON-LD)

gapfactory has a platform rule but the note says "JSON-LD Offer". GAP may expose
`availability` in its JSON-LD.

1. Fetch `gapfactory/pants` and check JSON-LD for availability + brand.
2. If available: update expectations. The existing platform rule may not be needed for price
   if JSON-LD already provides it — but keep it as a backup.

### Step 6 — Uniqlo (brand hardcode / in_stock selector)

The note says "no availability data". Uniqlo does not expose stock through OG/JSON-LD in
static HTML (it's API-driven). Brand is always "UNIQLO".

1. Confirm that in_stock remains `None` from static HTML → leave `"in_stock": null`.
2. Option: add a hardcoded `brand="UNIQLO"` to the `uniqlo.com` `PlatformRule`
   (new `brand` field on `PlatformRule`, or a `brand_selector`).
3. If that brand field is added: update `cases.json` to `"brand": "ok"`.

> **Design decision:** Adding a `brand` field to `PlatformRule` is a minor schema change.
> Alternative: let the LLM layer infer brand. Prefer the deterministic approach.

### Step 7 — Amazon (brand + in_stock investigation)

Amazon book pages include JSON-LD. Availability in JSON-LD is inconsistent for books.
Brand is ambiguous for books (publisher ≠ brand in traditional sense).

1. Fetch `amazon/book` and check JSON-LD offers for availability.
2. If consistent: update expectations. If not: leave `null`.
3. Leave `"brand": null` — Amazon books don't have a meaningful brand.

### Step 8 — T&T Supermarket (JS-heavy — likely limited without cookies)

The note says "JS-heavy; requires Playwright + fresh cookies". Without cookies the fetcher
may get a bot-challenge page with no product data beyond OG title/image.

1. Confirm what is extractable from the static/Playwright HTML without cookies.
2. If only title+price+image work: leave `"brand": null` and `"in_stock": null`.
3. If a `product:availability` meta is present in OG: update to `"in_stock": "ok"`.

### Step 9 — Add `in_stock` CSS selector support to `PlatformRule` (if needed)

If any site exposes stock status only via CSS (not JSON-LD/OG), add an optional
`in_stock_selector` field to `PlatformRule` and handle it in `extract_by_rules()`.

This step is only executed if Steps 1–8 find sites where in_stock requires CSS parsing.

### Step 10 — Update cases.json and run live validation

After completing each site investigation and extractor change:
1. Update `tests/cases.json` expectations to reflect the improved extraction.
2. Run `pytest --run-live tests/test_live_cases.py -v -s` to validate all cases pass.

## Files to change

| File | Change |
|---|---|
| `tests/cases.json` | Update expectations per site as improvements land |
| `app/scrapers/extractors/rules.py` | Add platform rules for Madewell, COS, Maison Kitsune (if needed); optionally add `brand` and `in_stock_selector` to `PlatformRule` |
| `app/scrapers/extractors/opengraph.py` | No changes anticipated (already handles Shopify ProductGroup, JSON-LD brand/availability) |
| `app/scrapers/schemas.py` | No changes anticipated |

## Out of scope

- Blocked sites (bestbuy, homedepot, urbanoutfitters, freepeople, aritzia) — not addressed in this plan.
- LLM-learned rules — not changed; the goal is deterministic extractor improvements.
- Category extraction improvements — not in scope for this iteration.
- Celery task or API changes — extraction only.

## Open questions

- [ ] Does Madewell's static HTML include the full Shopify JSON-LD, or is it loaded via JS?
- [ ] Does COS expose `availability` in its JSON-LD or only in client-side state?
- [ ] Is it worth adding a `brand` field to `PlatformRule` for hardcoded brands like Uniqlo?
- [ ] Does T&T return any usable HTML (OG tags at minimum) without cookies/Playwright?

## Decision log

| Decision | Rationale | Alternative considered |
|---|---|---|
| Tackle Shopify sites first | They share the same JSON-LD structure already handled by opengraph.py; likely zero-code wins | Writing new platform rules first |
| Leave LLM fallback unchanged | Deterministic rules are verifiable and free; LLM is expensive and non-deterministic | Using LLM to fill brand/in_stock |
| Work case-by-case and update cases.json incrementally | Keeps changes reviewable; avoids a big-bang update | Batch all changes then validate |

---

## Session log

### 2026-03-22
- Fetched each `fetch: "ok"` site live and inspected JSON-LD / OG / itemprop signals
- Fixed `opengraph.py`: unwrap `@graph` wrapper (Uniqlo), check `content` attr in itemprop brand fallback (Maison Kitsune), add `itemprop="availability"` fallback on non-meta elements (Maison Kitsune)
- Added `brand` field to `PlatformRule`; made `price_selector`/`title_selector` optional; added `madewell.com` rule with `brand="Madewell"` to override internal JSON-LD code "MW"
- Updated dispatcher to apply platform rule brand as authoritative override after merge
- Updated `cases.json`: Madewell, COS, Uniqlo, Maison Kitsune now assert `brand: "ok"` and `in_stock: "ok"`
- Remaining fetchable cases (Target, GAP Factory, Amazon, T&T) have no extractable brand/in_stock in static HTML — left as `null`
- BestBuy and Urban Outfitters updated to `fetch: "ok"` (user confirmed no longer blocked)
