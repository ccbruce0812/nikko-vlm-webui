#!/usr/bin/env bash
# ============================================================
# 建置全部容器
# 對應 README.md → 建置容器
# ============================================================
set -euo pipefail

cd ~/project

echo "=== 拉取基礎映像（llama.cpp）==="
sudo docker pull "$(autotag llama_cpp --quiet)"

echo ""
echo "=== 建置 Router（API 閘道，~168MB）==="
sudo docker build -t router router/

echo ""
echo "=== 建置 WebUI（官方 live-vlm-webui + GPU fix，~1.5GB）==="
sudo docker build -t live-vlm-webui-jetson live-vlm-webui/

echo ""
echo "=== 建置 Cosmos-Reason2（llama.cpp + CUDA + FlashAttention，首次 ~27 分鐘）==="
sudo docker build -t cosmos-reason2 cosmos-reason2/

echo ""
echo "=== 建置 moondream2（llama.cpp + phi2 chat template，重用 cosmos 快取）==="
sudo docker build -t moondream2 moondream2/

echo ""
echo "=== 建置 YOLO（PyTorch + ultralytics + TensorRT，~13GB）==="
sudo docker build -t yolo yolo/

echo ""
echo "=== 建置 Player（GStreamer RTSP 串流，選用，~630MB）==="
sudo docker build -t player player/

echo ""
echo "=== 全部容器建置完成 ==="
sudo docker images | grep -E "router|live-vlm|cosmos|moondream|yolo|player"
