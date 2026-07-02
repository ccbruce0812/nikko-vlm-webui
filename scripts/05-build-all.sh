#!/usr/bin/env bash
# ============================================================
# 建置全部容器
# 對應 README.md → 建置容器
# ============================================================
set -euo pipefail

# 在 nikko-vlm-webui 根目錄執行

echo "=== 拉取基礎映像（L4T PyTorch）==="
sudo docker pull dustynv/l4t-pytorch:r36.4.0

echo ""
echo "=== 建置 Router（API 閘道，~168MB）==="
sudo docker build -t router router/

echo ""
echo "=== 建置 WebUI（官方 live-vlm-webui + GPU fix，~1.5GB）==="
sudo docker build -t live-vlm-webui live-vlm-webui/

echo ""
echo "=== 建置 Reason2（llama-server binaries，~2GB）==="
sudo docker build -t reason2 -f reason2/Dockerfile .

echo ""
echo "=== 建置 moondream2（llama-server binaries，~2GB）==="
sudo docker build -t moondream2 -f moondream2/Dockerfile .

echo ""
echo "=== 建置 YOLO（PyTorch + ultralytics + TensorRT，~13GB）==="
sudo docker build -t yolo yolo/

echo ""
echo "=== 建置 RTSP Server（CSI 攝影機串流，選用，~2GB）==="
sudo docker build -t rtsp-server rtsp-server/

echo ""
echo "=== 全部容器建置完成 ==="
sudo docker images | grep -E "router|live-vlm|reason2|moondream|yolo|rtsp-server"
