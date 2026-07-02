#!/usr/bin/env bash
# ============================================================
# Interactive container launcher — pick one model + optional RTSP
# Only one model at a time (Orin Nano has limited RAM)
# Reference: README.md → Start Services → manual docker run
# ============================================================
set -euo pipefail

echo "============================================"
echo " Container Launcher (interactive)"
echo "============================================"
echo ""

echo "=== Creating shared network ==="
sudo docker network create vlm-net 2>/dev/null || echo "  vlm-net already exists"

echo ""
echo "=== Starting Router (API gateway) ==="
sudo docker rm -f router 2>/dev/null || true
sudo docker run -d --name router --network vlm-net -p 8080:8080 router
echo "  ✓ router :8080"

echo ""
echo "=== Starting WebUI ==="
sudo docker rm -f live-vlm-webui 2>/dev/null || true
sudo docker run -d --name live-vlm-webui --network host --runtime nvidia --privileged \
    -v /sys:/sys:ro -v /run/jtop.sock:/run/jtop.sock:ro live-vlm-webui
echo "  ✓ live-vlm-webui :8090"

echo ""
echo "============================================"
echo " Select model (pick one, cannot run simultaneously)"
echo "============================================"
echo "  1) Reason2        (VLM description, ~2.6GB GPU)"
echo "  2) moondream2     (VLM description, ~2.6GB GPU)"
echo "  3) YOLO           (object detection, ~1.5GB GPU)"
echo "  q) Skip, no model"
echo ""
read -p "  Choose [1/2/3/q]: " choice

# Stop any previously running models
sudo docker rm -f reason2 2>/dev/null || true
sudo docker rm -f moondream2 2>/dev/null || true
sudo docker rm -f yolo 2>/dev/null || true

case "$choice" in
    1)
        echo ""
        echo "=== Starting Reason2 ==="
        sudo docker run -d --name reason2 --runtime nvidia --network vlm-net \
            -v "$(pwd)/models/reason2:/model:ro" reason2
        echo "  Loading model (35s)..."
        sleep 35
        echo "  ✓ reason2 :8002"
        ;;
    2)
        echo ""
        echo "=== Starting moondream2 ==="
        sudo docker run -d --name moondream2 --runtime nvidia --network vlm-net \
            -v "$(pwd)/models/moondream2:/model:ro" moondream2
        echo "  Loading model (15s)..."
        sleep 15
        echo "  ✓ moondream2 :8001"
        ;;
    3)
        echo ""
        echo "=== Starting YOLO ==="
        sudo docker run -d --name yolo --runtime nvidia --network vlm-net \
            -v "$(pwd)/models/yolo:/model:ro" yolo
        echo "  Loading model (10s)..."
        sleep 10
        echo "  ✓ yolo :8003"
        ;;
    *)
        echo "→ Skipping model"
        ;;
esac

echo ""
echo "============================================"
echo " RTSP Server (CSI camera — optional)"
echo "============================================"
read -p "  Start RTSP Server? [y/N]: " yn
case "$yn" in
    [Yy]*)
        sudo docker rm -f rtsp-server 2>/dev/null || true

        read -p "  Resolution [1280x720]: " res
        W="${res%x*}"
        H="${res#*x}"
        W="${W:-1280}"
        H="${H:-720}"
        F="${FPS:-30}"

        if [ ! -e /dev/video0 ]; then
            echo "  ⚠ /dev/video0 not found, CSI camera not configured"
            echo "  Run scripts/02-system-config.sh to set up camera first"
        else
            echo "  Starting RTSP Server (${W}x${H} @ ${F}fps)..."
            sudo docker run -d --name rtsp-server --runtime nvidia --network host \
                --device=/dev/video0 --device=/dev/media0 \
                -v /tmp:/tmp \
                -e WIDTH="$W" -e HEIGHT="$H" -e FPS="$F" rtsp-server
            echo "  ✓ rtsp-server"
            echo "  RTSP: rtsp://$(hostname -I | awk '{print $1}'):8554/stream"
        fi
        ;;
    *)
        echo "→ Skipping RTSP Server"
        ;;
esac

echo ""
echo "============================================"
echo " Container Status"
echo "============================================"
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
