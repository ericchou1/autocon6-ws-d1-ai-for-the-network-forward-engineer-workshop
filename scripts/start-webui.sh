#!/usr/bin/env bash
#
# start-webui.sh — launch Open WebUI as a sibling container to Ollama.
#
# Idempotent: safe to run multiple times.
#   - If container is running: prints status and exits 0
#   - If container exists but stopped: starts it
#   - If container doesn't exist: creates and starts
#
# Open WebUI binds to host's port 8080 (via --network host) and talks to
# Ollama via localhost:11434 inside the same network namespace. The
# Codespace forwards port 8080 to the attendee's browser automatically
# (see .devcontainer/devcontainer.json).

set -euo pipefail

CONTAINER_NAME="open-webui"
IMAGE="ghcr.io/open-webui/open-webui:v0.9.5"
VOLUME="open-webui-data"

# Wait briefly for the Docker daemon (postCreate.sh already waits for it,
# but if someone runs this manually right after Codespace boot, be defensive).
for i in {1..10}; do
    if docker info > /dev/null 2>&1; then
        break
    fi
    echo "Waiting for Docker daemon... ($i/10)"
    sleep 1
done

# Already running?
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Open WebUI is already running."
    echo "  → Open the 'Open WebUI' tab in the VS Code Ports panel."
    exit 0
fi

# Exists but stopped?
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Open WebUI container exists but is stopped — starting it..."
    docker start "$CONTAINER_NAME"
    echo "Open WebUI restarted on port 8080."
    exit 0
fi

# Doesn't exist — create from scratch.
#
# Key env vars:
#   OLLAMA_BASE_URL  — point Open WebUI at the Ollama daemon running in
#                      the Codespace (same network namespace via --network host)
#   WEBUI_AUTH=False — skip the first-time signup flow; for a workshop
#                      environment, account creation is friction we don't
#                      want. DO NOT use this in any deployment where the
#                      UI is reachable from the public internet.
#   PORT=8080        — Open WebUI's listen port (default; explicit for clarity)
echo "Creating Open WebUI container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    -v "${VOLUME}:/app/backend/data" \
    -e OLLAMA_BASE_URL="http://localhost:11434" \
    -e WEBUI_AUTH=False \
    -e PORT=8080 \
    --restart unless-stopped \
    "$IMAGE" > /dev/null

echo ""
echo "Open WebUI starting at http://localhost:8080"
echo "  → First load takes ~15-20 seconds while the app initializes."
echo "  → Codespace forwards port 8080 — check the 'Ports' panel in VS Code."
echo ""
echo "If you don't see your Ollama models in the UI immediately:"
echo "  1. Make sure 'ollama serve' is running (Lab 1 starts it)"
echo "  2. Refresh the Open WebUI page after starting Ollama"