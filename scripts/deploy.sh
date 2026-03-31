#!/usr/bin/env bash
# deploy.sh — Pull latest code, build frontend, restart Docker stack.
# Called by GitHub Actions self-hosted runner or manually.

set -euo pipefail

REPO_DIR="/home/fxcyf/MyFiles/random/price-tracker"
cd "$REPO_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── Pull latest code ─────────────────────────────────────────────────────────
log "=== Deploy started ==="
log "Pulling latest code..."
git pull origin master
log "Now at $(git rev-parse --short HEAD)"

# Re-exec self after pull so the rest of the script is always the latest version
if [ "${DEPLOY_REEXEC:-}" != "1" ]; then
    log "Re-executing deploy.sh after pull..."
    DEPLOY_REEXEC=1 exec bash "$0" "$@"
fi

# ── Build frontend ───────────────────────────────────────────────────────────
log "Building frontend..."
cd "$REPO_DIR/frontend"
pnpm install --no-frozen-lockfile
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
exit 1
