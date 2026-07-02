#!/usr/bin/env bash
# ============================================================
# Start RTSP Server (optional — CSI camera live streaming)
# CAM0 / IMX219, resolution via WIDTH/HEIGHT env vars
# ============================================================
set -euo pipefail

echo "============================================"
echo " Start RTSP Server (CSI CAM0 / IMX219)"
echo "============================================"

WIDTH="${WIDTH:-1280}"
HEIGHT="${HEIGHT:-720}"
FPS="${FPS:-30}"
RTSP_PORT="${RTSP_PORT:-8554}"

echo "  Resolution: ${WIDTH}x${HEIGHT} @ ${FPS}fps"
echo "  RTSP:   rtsp://<jetson-ip>:${RTSP_PORT}/stream"

if [ ! -e /dev/video0 ]; then
    echo ""
    echo "⚠ /dev/video0 not found!"
    echo "  Run: sudo /opt/nvidia/jetson-io/jetson-io.py"
    echo "  Select \"Configure for compatible camera\" → IMX219 → CAM0"
    echo "  Then reboot"
    exit 1
fi

echo ""
echo "=== Removing old container ==="
sudo docker rm -f rtsp-server 2>/dev/null || true

echo ""
echo "=== Starting rtsp-server ==="
sudo docker run -d \
    --name rtsp-server \
    --runtime nvidia \
    --network host \
    --device=/dev/video0 \
    --device=/dev/media0 \
    -v /tmp:/tmp \
    -e WIDTH="$WIDTH" \
    -e HEIGHT="$HEIGHT" \
    -e FPS="$FPS" \
    -e RTSP_PORT="$RTSP_PORT" \
    rtsp-server

echo ""
echo "=== Waiting for camera... ==="
sleep 3

if sudo docker ps --format '{{.Names}}' | grep -q rtsp-server; then
    echo "✓ rtsp-server started"
    echo "  RTSP stream: rtsp://$(hostname -I | awk '{print $1}'):${RTSP_PORT}/stream"
else
    echo "✗ rtsp-server failed to start, check logs:"
    sudo docker logs rtsp-server
    exit 1
fi
