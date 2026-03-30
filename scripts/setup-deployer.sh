#!/usr/bin/env bash
# setup-deployer.sh — Install/reinstall the deploy webhook as a launchd service.
#
# Usage:
#   1. Edit the plist file: set DEPLOY_WEBHOOK_SECRET to your GitHub webhook secret.
#   2. Run: bash scripts/setup-deployer.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.pricetracker.deploy-webhook"
PLIST_SRC="${SCRIPT_DIR}/${PLIST_NAME}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "=== Price Tracker Deploy Webhook Setup ==="

# Make scripts executable
chmod +x "${SCRIPT_DIR}/deploy.sh"
chmod +x "${SCRIPT_DIR}/deploy-webhook.py"

# Unload existing service if running
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "Unloading existing service..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Copy plist to LaunchAgents
echo "Installing plist to ~/Library/LaunchAgents/..."
cp "$PLIST_SRC" "$PLIST_DST"

# Load service
echo "Loading service..."
launchctl load "$PLIST_DST"

# Verify
sleep 1
if launchctl list | grep -q "$PLIST_NAME"; then
    echo ""
    echo "Webhook service is running on port ${DEPLOY_WEBHOOK_PORT:-9000}."
    echo ""
    echo "Next steps:"
    echo "  1. In Cloudflare Tunnel, add a route: deploy.yourdomain.com -> http://localhost:9000"
    echo "     (bypass Zero Trust for this route — security is handled by webhook secret)"
    echo "  2. In GitHub repo Settings -> Webhooks:"
    echo "     - Payload URL: https://deploy.yourdomain.com/webhook"
    echo "     - Content type: application/json"
    echo "     - Secret: (same as DEPLOY_WEBHOOK_SECRET in the plist)"
    echo "     - Events: Just the push event"
    echo ""
    echo "Useful commands:"
    echo "  Check status:  launchctl list | grep pricetracker"
    echo "  View logs:     tail -f scripts/webhook.stdout.log"
    echo "  Stop service:  launchctl unload ~/Library/LaunchAgents/${PLIST_NAME}.plist"
    echo "  Start service: launchctl load ~/Library/LaunchAgents/${PLIST_NAME}.plist"
else
    echo "ERROR: Service failed to start. Check logs:"
    echo "  cat ${SCRIPT_DIR}/webhook.stderr.log"
    exit 1
fi
