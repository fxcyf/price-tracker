#!/usr/bin/env bash
# deploy.sh — Pull latest code, build frontend, restart Docker stack.
# Called by the webhook service or manually.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCK_FILE="/tmp/price-tracker-deploy.lock"
LOG_FILE="${REPO_DIR}/scripts/deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── Concurrency guard ────────────────────────────────────────────────────────
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || true)
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        log "Deploy already running (PID $LOCK_PID), skipping."
        exit 0
    fi
    log "Stale lock file found, removing."
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ── Pull latest code ─────────────────────────────────────────────────────────
log "=== Deploy started ==="
cd "$REPO_DIR"

log "Pulling latest code..."
git fetch origin master
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date ($LOCAL). Nothing to deploy."
    exit 0
fi

git pull origin master
log "Updated from ${LOCAL:0:7} to $(git rev-parse --short HEAD)"

# ── Build frontend ───────────────────────────────────────────────────────────
log "Building frontend..."
cd "$REPO_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build
cd "$REPO_DIR"
log "Frontend build complete."

# ── Restart Docker stack ─────────────────────────────────────────────────────
log "Restarting Docker Compose stack..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --project-name prod up -d --build
log "Docker stack restarted."

# ── Health check ─────────────────────────────────────────────────────────────
log "Waiting for backend health check..."
for i in $(seq 1 30); do
    if curl -sf http://localhost/api/health > /dev/null 2>&1; then
        log "Backend is healthy."
        log "=== Deploy finished successfully ==="
        exit 0
    fi
    sleep 2
done

log "WARNING: Backend did not become healthy within 60s."
log "=== Deploy finished with warnings ==="
exit 1
