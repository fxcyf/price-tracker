# Environment Isolation: Production vs Local Dev

## Setup

Two isolated Docker Compose stacks on the same machine, different project names → separate networks, volumes, and port bindings.

| Resource      | Production (`prod`) | Dev (`dev`) |
|---------------|---------------------|-------------|
| nginx         | `:80`               | `:8080`     |
| backend (API) | internal only       | `:8001`     |
| postgres      | `:5432`             | `:5433`     |
| redis         | `:6379`             | `:6380`     |
| env file      | `.env`              | `.env.dev`  |
| Cloudflare    | ✅ points here      | ❌ never    |

## Commands

```bash
# Start/keep production running (Cloudflare tunnel points here)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --project-name prod up -d

# Rebuild prod after code changes (stays detached, Cloudflare tunnel unaffected)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --project-name prod up -d --build

# Start local dev stack (debug freely, won't affect online users)
docker compose -f docker-compose.yml -f docker-compose.dev.yml --project-name dev up

# Rebuild dev after code changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml --project-name dev up --build

# Stop dev stack only
docker compose --project-name dev down

# Tear down dev including its volumes (fresh DB)
docker compose --project-name dev down -v
```

## Key points

- **Different project names** = completely separate Docker networks and named volumes, so each stack has its own database with independent data.
- **`DEBUG=true`** in `.env.dev` enables verbose logging and (in FastAPI) detailed error tracebacks in the browser.
- **`SMTP_USER` is empty** in `.env.dev` so no real emails are sent while debugging.
- **Direct backend access** on `:8001` lets you call the API without going through nginx — useful for `curl` / REST clients during debugging.
- `.env.dev` is git-ignored (contains secrets); copy from `.env.dev` template when setting up on a new machine.

## Frontend dev-only UI

Vite exposes `import.meta.env.DEV` as a compile-time boolean (`true` in `vite dev`, `false` in `vite build`). Use it to gate debug UI that should never ship to production — the condition is tree-shaken out of the prod bundle entirely.

Pattern used in `ProductDetailPage`:
- Wrap the component in `{import.meta.env.DEV && <DebugPanel ... />}` — zero cost in prod.
- For data that lives inside child components (e.g. `PriceChart`), pass an optional `onQueryStatus?` callback prop and call it from a `useEffect` watching the query state. The parent only wires the callback when `import.meta.env.DEV` is true, keeping child components clean.
- Avoid `useEffect` pitfalls: always list stable `useCallback` refs in deps rather than inline functions to prevent infinite loops.

## Adding debug/trace data to an existing API response

Pattern used for the scrape trace in `POST /api/parse`:
- Keep the backend function signature stable by adding a parallel `_with_debug` variant that returns `tuple[Data, DebugInfo]`. The original function becomes a one-liner that unpacks and discards the debug. Existing callers are untouched.
- Add the debug payload as an **optional field** (`debug: ... | None = None`) on the existing Pydantic response model — no breaking change to clients that don't consume it.
- Build the trace **at the call site** (dispatcher layer boundaries) using a simple `_track_fields(before, after, layer, selectors, accumulator)` helper that records which layer first filled each field. This avoids polluting the core data model with debug metadata.
- On the frontend, add the debug type as an optional interface field in `client.ts` and render only when `import.meta.env.DEV && data.debug`.
