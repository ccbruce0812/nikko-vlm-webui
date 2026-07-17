#!/usr/bin/env bash
# ============================================================
# 13-start-live-vlm-webui.sh
# Interactive launcher for browser-based WebRTC frontend.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONTAINER="live-vlm-webui"

# ---- defaults ----
PORT=8090
MODEL="reason2"

# ---- interactive prompts ----
echo "============================================"
echo " live-vlm-webui Launcher"
echo "============================================"
echo "  Press Enter to accept defaults."
echo ""

read -p "  Port         [$PORT]: " v; PORT="${v:-$PORT}"
read -p "  Model        [$MODEL]: " v; MODEL="${v:-$MODEL}"

echo ""
echo "Starting with: port=$PORT model=$MODEL"

# ---- validate port ----
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "✗ Invalid port: $PORT (must be 1–65535)"
    exit 1
fi

# ---- already running? ----
if sudo docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "✗ $CONTAINER is already running. Stop it first: bash scripts/14-stop-live-vlm-webui.sh"
    exit 1
fi

# ---- remove old ----
echo "=== Removing old container ==="
sudo docker rm -f "$CONTAINER" 2>/dev/null || echo "(no existing container)"

# ---- launch ----
echo ""
echo "=== Starting $CONTAINER ==="
sudo docker run -d \
    --name "$CONTAINER" \
    --network host \
    --runtime nvidia \
    --privileged \
    -v /sys:/sys:ro \
    -e PORT="$PORT" \
    "$CONTAINER" \
    --host 0.0.0.0 --port "$PORT" \
    --api-base http://localhost:8080/v1 \
    --api-key "***" \
    --model "$MODEL"

sleep 3

if sudo docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo ""
    echo "✓ $CONTAINER started"
    echo "  Open: http://$(hostname -I | awk '{print $1}'):${PORT}"
else
    echo "✗ Failed to start. Logs:"
    sudo docker logs "$CONTAINER"
    exit 1
fi
