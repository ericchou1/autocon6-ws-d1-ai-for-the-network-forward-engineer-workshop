#!/usr/bin/env bash
#
# postCreate.sh — runs once on Codespace first-create.
#
# Responsibilities:
#  1. Wait for Docker daemon (docker-in-docker feature) to be ready
#  2. Load SR Linux image from baked-in tarball
#  3. Load Open WebUI image — ONLY on the "GitHub Pro" image (tarball present)
#  4. Seed .env from .env.example if missing
#  5. Start Open WebUI container — ONLY on the "GitHub Pro" image
#  6. Print welcome banner (variant-aware)
#
# One script serves BOTH images; it detects which by /opt/images/open-webui.tar.

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Wait for Docker daemon
#
# The docker-in-docker feature starts Docker during Codespace startup, but
# postCreateCommand might fire before the daemon is fully up. Poll briefly.
# ---------------------------------------------------------------------------
echo "==> Waiting for Docker daemon..."
for i in $(seq 1 30); do
    if docker info > /dev/null 2>&1; then
        echo "    Docker is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "    ERROR: Docker daemon not ready after 30 seconds."
        exit 1
    fi
    sleep 1
done

# ---------------------------------------------------------------------------
# Detect image variant: the GitHub Pro image bakes in open-webui.tar; the
# default (slim) image does not. Everything Open-WebUI-related is gated on this.
# ---------------------------------------------------------------------------
WEBUI_TAR="/opt/images/open-webui.tar"
HAS_WEBUI=false
[ -f "$WEBUI_TAR" ] && HAS_WEBUI=true

# ---------------------------------------------------------------------------
# 2. Load SR Linux image from baked-in tarball
# ---------------------------------------------------------------------------
SRLINUX_TAR="/opt/images/srlinux.tar"

if [ -f "$SRLINUX_TAR" ]; then
    echo ""
    echo "==> Loading SR Linux image from $SRLINUX_TAR..."
    docker load -i "$SRLINUX_TAR"
    echo ""
    docker images ghcr.io/nokia/srlinux
else
    echo ""
    echo "WARNING: $SRLINUX_TAR not found."
    echo "         Containerlab topology won't deploy without it."
fi

# ---------------------------------------------------------------------------
# 3. Load Open WebUI image — GitHub Pro image only
# ---------------------------------------------------------------------------
if [ "$HAS_WEBUI" = true ]; then
    echo ""
    echo "==> Loading Open WebUI image from $WEBUI_TAR..."
    docker load -i "$WEBUI_TAR"
    echo ""
    docker images ghcr.io/open-webui/open-webui
fi
# (Default/slim image has no open-webui.tar — nothing to load. Not an error.)

# ---------------------------------------------------------------------------
# 4. Seed .env from .env.example if missing
# ---------------------------------------------------------------------------
echo ""
echo "==> Setting up .env..."
if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    echo "    Created .env from .env.example."
    echo "    Edit .env and add your OPENAI_API_KEY before running OpenAI labs."
elif [ -f .env ]; then
    echo "    .env already exists; leaving it alone."
else
    echo "    No .env.example found; skipping."
fi

# ---------------------------------------------------------------------------
# 5. Start Open WebUI container — GitHub Pro image only
#
# Wrapped in `if ! ...` so a failure here doesn't halt postCreate.sh — the
# workshop must remain usable even if the GUI hiccups. Attendees can always
# run scripts/start-webui.sh manually later.
# ---------------------------------------------------------------------------
if [ "$HAS_WEBUI" = true ]; then
    echo ""
    echo "==> Starting Open WebUI..."
    if [ -f scripts/start-webui.sh ]; then
        if ! bash scripts/start-webui.sh; then
            echo "    WARNING: Open WebUI failed to start — continuing without GUI."
            echo "             Try 'bash scripts/start-webui.sh' manually later."
        fi
    else
        echo "    scripts/start-webui.sh not found; skipping GUI startup."
    fi
fi

# ---------------------------------------------------------------------------
# 6. Welcome banner (variant-aware)
# ---------------------------------------------------------------------------
echo ""
echo "=================================================="
echo "  AutoCon 6 AI Workshop — environment ready!"
echo "=================================================="
echo ""
echo "Quick sanity checks:"
echo "  ollama --version           # expect 0.23.1"
echo "  containerlab version       # expect 0.74.3"
if [ "$HAS_WEBUI" = true ]; then
    echo "  docker images              # SR Linux + Open WebUI should be listed"
    echo ""
    echo "Open WebUI (chat GUI for Ollama):"
    echo "  -> http://localhost:8080"
    echo "  -> VS Code auto-opens this in the 'Ports' panel preview pane."
    echo "  -> Models appear once 'ollama serve' is running (covered in Lab 1)."
else
    echo "  docker images              # SR Linux should be listed"
    echo ""
    echo "Local LLM chat is via the CLI on this image:"
    echo "  -> ollama serve >/tmp/ollama.log 2>&1 &   # start the daemon"
    echo "  -> ollama run qwen3:4b-q4_K_M --think=false \"Explain BGP in one sentence.\""
    echo "  (The Open WebUI GUI is on the GitHub Pro image — see Lab 1 Step 8.)"
fi
echo ""
echo "Next steps:"
echo "  1. Edit .env to add your OpenAI API key (and your Arize Space ID + API key for Labs 3-5)"
echo "  2. See README.md for the lab walkthrough order"
echo "  3. Workshop FAQ: WORKSHOP_FAQ.md"
echo ""
echo "=================================================="
echo ""
