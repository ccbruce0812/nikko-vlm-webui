#!/usr/bin/env bash
# ============================================================
# 05-build-all.sh
# Interactive container builder — select one or more images.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "============================================"
echo " Select images to build (comma-separated)"
echo "============================================"
echo ""
echo "  1) router         (API gateway)"
echo "  2) llama-cpp      (llama.cpp CUDA)"
echo "  3) yolo           (object detection)"
echo "  4) live-vlm-webui (Web UI)"
echo "  5) rtsp-server    (CSI camera streaming)"
echo "  a) All"
echo ""

read -p "  Choose [e.g. 1,3 or a or Enter to skip]: " choice

BUILD_ROUTER=false
BUILD_LLAMA=false
BUILD_YOLO=false
BUILD_WEBUI=false
BUILD_RTSP=false

IFS=',' read -ra ITEMS <<< "$choice"
for item in "${ITEMS[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    case "$item" in
        1) BUILD_ROUTER=true ;;
        2) BUILD_LLAMA=true ;;
        3) BUILD_YOLO=true ;;
        4) BUILD_WEBUI=true ;;
        5) BUILD_RTSP=true ;;
        a|A) BUILD_ROUTER=true; BUILD_LLAMA=true; BUILD_YOLO=true; BUILD_WEBUI=true; BUILD_RTSP=true; break ;;
    esac
done

if ! $BUILD_ROUTER && ! $BUILD_LLAMA && ! $BUILD_YOLO && ! $BUILD_WEBUI && ! $BUILD_RTSP; then
    echo "Nothing selected."
    exit 0
fi

echo ""
echo "=== Cleaning up ==="
sudo docker rm -f $(sudo docker ps -aq) 2>/dev/null || true
sudo docker system prune -af --volumes
sudo docker builder prune -af
sudo docker network prune -f
echo ""
echo "=== Building selected images ==="

if $BUILD_ROUTER; then
    echo ""
    echo "=== Build router ==="
    sudo docker build -t router router/
    echo "  ✓ router"
fi

if $BUILD_LLAMA; then
    echo ""
    echo "=== Build llama-cpp ==="
    sudo docker build -t llama-cpp llama-cpp/
    echo "  ✓ llama-cpp"
fi

if $BUILD_YOLO; then
    echo ""
    echo "=== Build yolo ==="
    sudo docker build -t yolo yolo/
    echo "  ✓ yolo"
fi

if $BUILD_WEBUI; then
    echo ""
    echo "=== Build live-vlm-webui ==="
    sudo docker build -t live-vlm-webui live-vlm-webui/
    echo "  ✓ live-vlm-webui"
fi

if $BUILD_RTSP; then
    echo ""
    echo "=== Build rtsp-server ==="
    sudo docker build -t rtsp-server rtsp-server/
    echo "  ✓ rtsp-server"
fi

echo ""
echo "=== Built images ==="
sudo docker images | grep -E "router|llama-cpp|yolo|live-vlm-webui|rtsp-server" || echo "  (none)"
echo ""
echo "✓ Done"
