#!/usr/bin/env bash
# ============================================================
# 11-start-rtsp-server.sh
# Interactive RTSP server launcher — CSI camera streaming.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONTAINER="rtsp-server"

# ---- defaults ----
CAMERA_ID=0
RESOLUTION="1920x1080@30"
PORT=8554
PATH_="/stream"

# ---- interactive prompts ----
echo "============================================"
echo " RTSP Server Launcher"
echo "============================================"
echo "  Press Enter to accept defaults."
echo ""

read -p "  Camera ID    [$CAMERA_ID]: " v; CAMERA_ID="${v:-$CAMERA_ID}"
read -p "  Resolution   [$RESOLUTION]: " v; RESOLUTION="${v:-$RESOLUTION}"
read -p "  Port         [$PORT]: " v; PORT="${v:-$PORT}"
read -p "  Path         [$PATH_]: " v; PATH_="${v:-$PATH_}"

echo ""
echo "Starting with: camera-id=$CAMERA_ID resolution=$RESOLUTION port=$PORT path=$PATH_"

# ---- pre-flight checks ----
if [ ! -e "/dev/video${CAMERA_ID}" ]; then
    echo "✗ /dev/video${CAMERA_ID} not found"
    exit 1
fi

if ! pgrep -x Xorg >/dev/null 2>&1; then
    echo "✗ Xorg is not running. Start it first: bash scripts/01-disable-gui.sh (one-time setup, then reboot)"
    exit 1
fi

echo "=== Restarting nvargus-daemon ==="
sudo systemctl restart nvargus-daemon
sleep 2

echo "=== Setting MAXN Super Mode (25W) ==="
if ! sudo nvpmodel -q 2>/dev/null | grep -q "NV Power Mode: MAXN_SUPER"; then
    sudo nvpmodel -m 2
fi
sudo jetson_clocks

echo "=== Memory tuning ==="
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1

export DISPLAY=:0

# ---- stop existing ----
if sudo docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "=== Removing old container ==="
    sudo docker rm -f "$CONTAINER" 2>/dev/null || true
fi

# ---- launch ----
echo ""
echo "=== Starting $CONTAINER ==="
sudo docker run -d \
    --name "$CONTAINER" \
    --runtime nvidia \
    --network host \
    --device="/dev/video${CAMERA_ID}" \
    --device=/dev/media0 \
    -v /tmp:/tmp \
    "$CONTAINER" \
    python3 rtsp-server.py \
    --camera-id "$CAMERA_ID" \
    --resolution "$RESOLUTION" \
    --port "$PORT" \
    --path "$PATH_"

sleep 3

if sudo docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo ""
    echo "✓ RTSP server started"
    echo "  rtsp://$(hostname -I | awk '{print $1}'):${PORT}${PATH_}"
else
    echo "✗ Failed to start. Logs:"
    sudo docker logs "$CONTAINER"
    exit 1
fi
