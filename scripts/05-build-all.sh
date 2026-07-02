#!/usr/bin/env bash
# ============================================================
# Build all containers
# Reference: README.md → Build Containers
# ============================================================
set -euo pipefail

# Run from nikko-vlm-webui root

echo "=== Pull base image (L4T PyTorch) ==="
sudo docker pull dustynv/l4t-pytorch:r36.4.0

echo ""
echo "=== Build Router (API gateway, ~168MB) ==="
sudo docker build -t router router/

echo ""
echo "=== Build WebUI (official live-vlm-webui + GPU fix, ~1.5GB) ==="
sudo docker build -t live-vlm-webui live-vlm-webui/

echo ""
echo "=== Build Reason2 (llama-server binaries, ~2GB) ==="
sudo docker build -t reason2 -f reason2/Dockerfile .

echo ""
echo "=== Build moondream2 (llama-server binaries, ~2GB) ==="
sudo docker build -t moondream2 -f moondream2/Dockerfile .

echo ""
echo "=== Build YOLO (PyTorch + ultralytics + TensorRT, ~13GB) ==="
sudo docker build -t yolo yolo/

echo ""
echo "=== Build RTSP Server (CSI camera, optional, ~2GB) ==="
sudo docker build -t rtsp-server rtsp-server/

echo ""
echo "=== All images built ==="
sudo docker images | grep -E "router|live-vlm|reason2|moondream|yolo|rtsp-server"
