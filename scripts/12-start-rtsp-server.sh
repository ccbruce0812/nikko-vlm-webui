#!/usr/bin/env bash
# ============================================================
# Start RTSP Server (CSI camera live streaming)
# CAM0 / IMX219, resolution via CLI args or environment variables.
#
# nvarguscamerasrc requires Xorg + DISPLAY for full speed.
# ============================================================
set -euo pipefail

# ---- defaults ----
CAMERA_ID=0
WIDTH=1920
HEIGHT=1080
FPS=30
RTSP_PORT=8554
RTSP_PATH=/stream

usage() {
    echo "Usage: bash scripts/20-start-rtsp-server.sh [OPTIONS]"
    echo ""
    echo "  Start the CSI camera RTSP server."
    echo ""
    echo "Options:"
    echo "  --camera-id N        CSI camera sensor (default: 0)"
    echo "  --resolution WxH@FPS  e.g. 1920x1080@30, 1280x720@60 (default: 1920x1080@30)"
    echo "  --port N             RTSP listening port (default: 8554)"
    echo "  --path PATH          RTSP mount path (default: /stream)"
    echo "  --help, -h           show this message"
    echo ""
    echo "Examples:"
    echo "  bash scripts/20-start-rtsp-server.sh"
    echo "  bash scripts/20-start-rtsp-server.sh --resolution 1920x1080@30 --port 8555"
    echo "  bash scripts/20-start-rtsp-server.sh --camera-id 0 --path /cam0"
    exit 0
}

# ---- parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h) usage ;;
        --camera-id) CAMERA_ID="$2"; shift 2 ;;
        --resolution)
            # parse WxH@FPS
            if [[ "$2" =~ ^([0-9]+)x([0-9]+)@([0-9]+)$ ]]; then
                WIDTH="${BASH_REMATCH[1]}"
                HEIGHT="${BASH_REMATCH[2]}"
                FPS="${BASH_REMATCH[3]}"
            else
                echo "ERROR: --resolution must be WxH@FPS (e.g. 1920x1080@30)"
                exit 1
            fi
            shift 2 ;;
        --port) RTSP_PORT="$2"; shift 2 ;;
        --path) RTSP_PATH="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

echo "============================================"
echo " Start RTSP Server (CSI CAM0 / IMX219)"
echo "============================================"
echo "  Sensor:    camera-id=${CAMERA_ID}"
echo "  Resolution: ${WIDTH}x${HEIGHT} @ ${FPS}fps"
echo "  RTSP:      rtsp://<jetson-ip>:${RTSP_PORT}${RTSP_PATH}"

if [ ! -e /dev/video${CAMERA_ID} ]; then
    echo ""
    echo "✗ /dev/video${CAMERA_ID} not found!"
    echo "  Run: sudo /opt/nvidia/jetson-io/jetson-io.py"
    echo "  Select \"Configure for compatible camera\" → IMX219-A → CAM0"
    echo "  Then reboot"
    exit 1
fi

# ---- Xorg (required by nvarguscamerasrc) ----
if ! pgrep -x Xorg >/dev/null 2>&1; then
    echo ""
    echo "✗ Xorg is not running."
    echo "  Xorg is required by nvarguscamerasrc for full-speed capture."
    echo "  Run: sudo systemctl start xorg"
    echo "  Or:  bash scripts/01-disable-gui.sh (one-time setup, then reboot)"
    exit 1
fi
echo "[INFO] Xorg is running"

export DISPLAY=:0

# ---- Argus daemon ----
echo "[INFO] Restarting nvargus-daemon..."
sudo systemctl restart nvargus-daemon
sleep 2

# ---- MAXN Super Mode (25W) ----
echo "[INFO] Setting MAXN Super Mode (25W)..."
if ! sudo nvpmodel -q 2>/dev/null | grep -q "NV Power Mode: MAXN_SUPER"; then
    sudo nvpmodel -m 2
fi
sudo jetson_clocks

# ---- Memory tuning ----
echo "[INFO] Memory tuning (CMA optimization)..."
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1

echo ""
echo "=== Removing old container ==="
if sudo docker ps -a --format '{{.Names}}' | grep -q rtsp-server; then
    STATUS=$(sudo docker inspect -f '{{.State.Status}}' rtsp-server 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "running" ]; then
        echo "✗ rtsp-server is already running. Stop it first: bash scripts/20-stop-rtsp-server.sh"
        exit 1
    fi
    sudo docker rm -f rtsp-server 2>/dev/null || true
else
    echo "(no existing container)"
fi

echo ""
echo "=== Starting rtsp-server ==="
sudo docker run -d \
    --name rtsp-server \
    --runtime nvidia \
    --network host \
    --device=/dev/video${CAMERA_ID} \
    --device=/dev/media0 \
    -v /tmp:/tmp \
    -e SENSOR_ID="$CAMERA_ID" \
    -e WIDTH="$WIDTH" \
    -e HEIGHT="$HEIGHT" \
    -e FPS="$FPS" \
    -e RTSP_PORT="$RTSP_PORT" \
    -e RTSP_PATH="$RTSP_PATH" \
    rtsp-server

echo ""
echo "=== Waiting for camera... ==="
sleep 3

if sudo docker ps --format '{{.Names}}' | grep -q rtsp-server; then
    echo "✓ rtsp-server started"
    echo "  RTSP stream: rtsp://$(hostname -I | awk '{print $1}'):${RTSP_PORT}${RTSP_PATH}"
else
    echo "✗ rtsp-server failed to start, check logs:"
    sudo docker logs rtsp-server
    exit 1
fi
