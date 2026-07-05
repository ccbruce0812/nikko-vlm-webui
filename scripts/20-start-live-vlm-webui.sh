#!/usr/bin/env bash
# ============================================================
# Start live-vlm-webui (browser-based WebRTC frontend)
# Requires: RTSP server running, Router running, model container running
# ============================================================
set -euo pipefail

# ---- defaults ----
PORT=8090

usage() {
    echo "Usage: bash scripts/20-start-live-vlm-webui.sh [OPTIONS]"
    echo ""
    echo "  Start the browser-based VLM WebUI (WebRTC relay + Router client)."
    echo ""
    echo "Options:"
    echo "  --port N             WebUI listening port (default: 8090)"
    echo "  --help, -h           show this message"
    echo ""
    echo "Examples:"
    echo "  bash scripts/20-start-live-vlm-webui.sh"
    echo "  bash scripts/20-start-live-vlm-webui.sh --port 8091"
    exit 0
}

# ---- parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h) usage ;;
        --port) PORT="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

echo "============================================"
echo " Start live-vlm-webui"
echo "============================================"
echo "  Port: ${PORT}"
echo "  URL:  http://<jetson-ip>:${PORT}"

# ---- Already running? ----
if sudo docker ps --format '{{.Names}}' | grep -q '^live-vlm-webui$'; then
    echo ""
    echo "✗ live-vlm-webui is already running."
    echo "  Stop it first: bash scripts/21-stop-live-vlm-webui.sh"
    exit 1
fi

# ---- validate port ----
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo ""
    echo "✗ Invalid port: $PORT (must be 1–65535)"
    exit 1
fi

echo ""
echo "=== Removing old container (if any) ==="
sudo docker rm -f live-vlm-webui 2>/dev/null || echo "(no existing container)"

echo ""
echo "=== Starting live-vlm-webui ==="
sudo docker run -d \
    --name live-vlm-webui \
    --network host \
    --runtime nvidia \
    --privileged \
    -e PORT="$PORT" \
    live-vlm-webui \
    --host 0.0.0.0 --port "$PORT" \
    --api-base http://localhost:8080/v1 \
    --api-key "***" \
    --model reason2

echo ""
echo "=== Waiting for startup... ==="
sleep 3

if sudo docker ps --format '{{.Names}}' | grep -q '^live-vlm-webui$'; then
    echo "✓ live-vlm-webui started"
    echo "  Open: http://$(hostname -I | awk '{print $1}'):${PORT}"
else
    echo "✗ live-vlm-webui failed to start, check logs:"
    sudo docker logs live-vlm-webui 2>/dev/null || true
    exit 1
fi
