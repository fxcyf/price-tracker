#!/usr/bin/env python3
"""
deploy-webhook.py — Lightweight GitHub webhook receiver.

Listens for push events on the master branch and triggers deploy.sh.
Runs on the host machine (NOT inside Docker) via launchd.

Environment variables:
    DEPLOY_WEBHOOK_SECRET  — GitHub webhook secret (required)
    DEPLOY_WEBHOOK_PORT    — Port to listen on (default: 9000)
"""

import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Config ───────────────────────────────────────────────────────────────────
WEBHOOK_SECRET = os.environ.get("DEPLOY_WEBHOOK_SECRET", "")
PORT = int(os.environ.get("DEPLOY_WEBHOOK_PORT", "9000"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_SCRIPT = os.path.join(SCRIPT_DIR, "deploy.sh")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("deploy-webhook")


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub HMAC-SHA256 signature."""
    if not WEBHOOK_SECRET:
        log.warning("No DEPLOY_WEBHOOK_SECRET set — skipping signature check!")
        return True
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/webhook":
            self._respond(404, {"error": "not found"})
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(body, signature):
            log.warning("Invalid signature — rejecting request.")
            self._respond(403, {"error": "invalid signature"})
            return

        # Parse event
        event = self.headers.get("X-GitHub-Event", "")
        if event == "ping":
            log.info("Received ping event.")
            self._respond(200, {"message": "pong"})
            return

        if event != "push":
            log.info(f"Ignoring event: {event}")
            self._respond(200, {"message": f"ignored event: {event}"})
            return

        # Only deploy on master branch pushes
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid JSON"})
            return

        ref = payload.get("ref", "")
        if ref != "refs/heads/master":
            log.info(f"Ignoring push to {ref} (not master).")
            self._respond(200, {"message": f"ignored ref: {ref}"})
            return

        pusher = payload.get("pusher", {}).get("name", "unknown")
        head_commit = payload.get("head_commit", {}).get("id", "unknown")[:7]
        log.info(f"Push to master by {pusher} ({head_commit}) — triggering deploy.")

        # Trigger deploy in background
        try:
            subprocess.Popen(
                ["bash", DEPLOY_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._respond(200, {"message": "deploy triggered"})
        except Exception as e:
            log.error(f"Failed to trigger deploy: {e}")
            self._respond(500, {"error": str(e)})

    def _respond(self, status: int, body: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format, *args):
        """Override default logging to use our logger."""
        log.info(f"{self.client_address[0]} - {format % args}")


def main():
    if not WEBHOOK_SECRET:
        log.warning(
            "DEPLOY_WEBHOOK_SECRET is not set! "
            "Webhook signature verification is DISABLED. "
            "Set this env var for production use."
        )

    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    log.info(f"Webhook server listening on port {PORT}")
    log.info(f"Deploy script: {DEPLOY_SCRIPT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
