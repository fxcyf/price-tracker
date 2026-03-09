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
