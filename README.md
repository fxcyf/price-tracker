# Price Tracker

A self-hosted product price tracker. Paste a product URL, and the app scrapes the price on a schedule, records the history, and emails you when the price drops below your target.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite, Tailwind CSS, shadcn/ui, TanStack Query, Recharts |
| Backend | FastAPI (async), SQLAlchemy 2, Alembic |
| Scraping | httpx + BeautifulSoup, Playwright (JS-rendered pages), OpenAI fallback |
| Task queue | Celery + Redis (worker + beat) |
| Database | PostgreSQL 16 |
| Reverse proxy | nginx |
| Containers | Docker Compose |

## Project Structure

```
price-tracker/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── core/         # Settings, DB session, dependencies
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── scrapers/     # HTTP + Playwright + LLM extractors
│   │   ├── tasks/        # Celery app, beat schedule, price-check task
│   │   └── notify/       # Email alert logic
│   ├── alembic/          # DB migrations
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/          # axios client + API calls
│       ├── components/   # Reusable UI components
│       ├── pages/        # Route-level page components
│       └── hooks/        # Custom React hooks
├── docker-compose.yml        # Production stack
├── docker-compose.dev.yml    # Dev overrides (different ports, debug mode)
├── nginx.conf
├── .env                  # Production env vars (git-ignored)
├── .env.dev              # Dev env vars (git-ignored)
└── .env.example          # Template — copy to .env to get started
```

## Getting Started

### Prerequisites

- Docker + Docker Compose
- (Optional) OpenAI API key for LLM-based price extraction on unsupported sites

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in SMTP credentials, OPENAI_API_KEY, FRONTEND_URL
```

### 2. Build the frontend

The nginx container serves a pre-built static bundle.

```bash
cd frontend
npm install
npm run build   # outputs to frontend/dist/
```

### 3. Start the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --project-name prod up -d

# Restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml --project-name prod up -d --build
```

The app is now available at `http://localhost` (port 80).

### 4. Run DB migrations

Migrations run automatically via the backend `entrypoint.sh` on startup. To run manually:

```bash
docker compose exec backend alembic upgrade head
```

---

## Development

### Isolated dev stack

Use `docker-compose.dev.yml` to spin up a **separate** stack on different ports so production (and any Cloudflare tunnel pointing at port 80) is never disturbed.

```bash
# Start local dev stack
docker compose -f docker-compose.yml -f docker-compose.dev.yml --project-name dev up

# Rebuild after code changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml --project-name dev up --build

# Stop dev stack
docker compose --project-name dev down

# Tear down dev including its database volume
docker compose --project-name dev down -v
```

Because the project name differs (`dev` vs `prod`), Docker creates completely separate networks, named volumes, and containers — the two stacks share nothing.

**Dev port mapping:**

| Service | Dev port | Prod port |
|---|---|---|
| Frontend (nginx) | `http://localhost:8080` | `http://localhost:80` |
| Backend API (direct) | `http://localhost:8001` | internal only |
| PostgreSQL | `localhost:5433` | `localhost:5432` |
| Redis | `localhost:6380` | `localhost:6379` |

**Dev environment differences (`.env.dev`):**
- `DEBUG=true` — verbose FastAPI error tracebacks
- `SMTP_USER` is empty — no real emails sent
- `FRONTEND_URL=http://localhost:8080`
- Celery workers run with `--loglevel=debug` and reduced concurrency

### Frontend dev server (hot reload)

To iterate on the UI without rebuilding the dist bundle each time, run the Vite dev server pointing at the backend:

```bash
cd frontend
npm run dev   # starts at http://localhost:5173, proxies /api → http://localhost:8001
```

`frontend/.env` already sets `VITE_API_URL=http://localhost:8000` for this purpose.

### Running tests

```bash
# From repo root — runs with the local .venv
cd backend
python -m pytest
```

---

## Auto Deploy

Push to `master` triggers automatic deployment via a GitHub webhook.

### Architecture

```
GitHub push → Cloudflare Tunnel → localhost:9000 (webhook) → deploy.sh
```

The webhook service runs on the **host machine** (not in Docker) via macOS launchd. It receives GitHub push events, verifies the webhook secret, and runs `deploy.sh` which pulls code, builds the frontend, and restarts the Docker stack.

### Setup

1. **Edit the webhook secret** in `scripts/com.pricetracker.deploy-webhook.plist`:
   ```xml
   <key>DEPLOY_WEBHOOK_SECRET</key>
   <string>your-secret-here</string>
   ```

2. **Install the launchd service**:
   ```bash
   bash scripts/setup-deployer.sh
   ```

3. **Add a Cloudflare Tunnel route** for the webhook:
   - Service: `http://localhost:9000`
   - Bypass Zero Trust for this route (security is via webhook secret)

4. **Add a GitHub Webhook** (repo Settings → Webhooks):
   - Payload URL: `https://deploy.yourdomain.com/webhook`
   - Content type: `application/json`
   - Secret: same as `DEPLOY_WEBHOOK_SECRET`
   - Events: Just the push event

### Useful commands

```bash
# Check service status
launchctl list | grep pricetracker

# View logs
tail -f scripts/webhook.stdout.log
tail -f scripts/deploy.log

# Manual deploy
bash scripts/deploy.sh

# Stop/start service
launchctl unload ~/Library/LaunchAgents/com.pricetracker.deploy-webhook.plist
launchctl load ~/Library/LaunchAgents/com.pricetracker.deploy-webhook.plist
```

---

## API Reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/products` | Import a new product (scrapes + saves) |
| `GET` | `/api/products` | List all products (`?category=`, `?tag=`) |
| `GET` | `/api/products/{id}` | Get a single product |
| `DELETE` | `/api/products/{id}` | Delete product and cascade |
| `GET` | `/api/products/{id}/prices` | Price history (`?days=30`) |
| `GET` | `/api/products/{id}/watch` | Get watch/alert config |
| `PUT` | `/api/products/{id}/watch` | Upsert watch/alert config |
| `POST` | `/api/parse` | Preview scrape without saving |
| `PUT` | `/api/domains/{domain}/cookies` | Import cookies from a curl command |
| `GET` | `/api/domains/{domain}/cookies` | Check cookie status |
| `GET` | `/api/settings` | Global notification settings |
| `PUT` | `/api/settings` | Update notification email |

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Async SQLAlchemy connection string | `postgresql+asyncpg://...` |
| `DATABASE_URL_SYNC` | Sync connection string (Alembic) | `postgresql://...` |
| `REDIS_URL` | Redis URL | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | Celery broker | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://redis:6379/1` |
| `CHECK_INTERVAL_HOURS` | How often to re-scrape prices | `24` |
| `SMTP_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username (leave empty to disable email) | `you@gmail.com` |
| `SMTP_PASSWORD` | SMTP password / app password | |
| `SMTP_FROM` | Display name + address for outgoing mail | `Price Tracker <you@gmail.com>` |
| `OPENAI_API_KEY` | OpenAI key for LLM-based extraction fallback | `sk-...` |
| `OPENAI_MODEL` | Model to use for extraction | `gpt-4o-mini` |
| `DEBUG` | Enable debug mode | `false` |
| `FRONTEND_URL` | Used in email alert links | `https://example.com` |
| `DEPLOY_WEBHOOK_SECRET` | GitHub webhook secret (host-side, not Docker) | |
| `DEPLOY_WEBHOOK_PORT` | Webhook listener port (host-side) | `9000` |

See `.env.example` for a ready-to-copy template.
