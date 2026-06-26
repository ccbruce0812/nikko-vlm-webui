#!/usr/bin/env bash
# ============================================================
# 手動 docker run 啟動全部容器
# 對應 README.md → 啟動服務 → 手動 docker run
# ============================================================
set -euo pipefail

echo "=== 建立共用網路 ==="
sudo docker network create vlm-net 2>/dev/null || echo "vlm-net 已存在"

echo ""
echo "=== 啟動 Router ==="
sudo docker rm -f router 2>/dev/null || true
sudo docker run -d --name router --network vlm-net -p 8080:8080 router

echo ""
echo "=== 啟動 Cosmos-Reason2 ==="
sudo docker rm -f cosmos-reason2 2>/dev/null || true
sudo docker run -d --name cosmos-reason2 --runtime nvidia --network vlm-net \
    -v /home/brucehsu/project/models/cosmos-reason2:/model:ro cosmos-reason2

echo "  等待 Cosmos 載入 (35 秒)..."
sleep 35

echo ""
echo "=== 啟動 moondream2 ==="
sudo docker rm -f moondream2 2>/dev/null || true
sudo docker run -d --name moondream2 --runtime nvidia --network vlm-net \
    -v /home/brucehsu/project/models/moondream2:/model:ro moondream2

echo ""
echo "=== 啟動 YOLO ==="
sudo docker rm -f yolo 2>/dev/null || true
sudo docker run -d --name yolo --runtime nvidia --network vlm-net \
    -v /home/brucehsu/project/models/yolo:/model:ro yolo

echo ""
echo "=== 啟動 WebUI ==="
sudo docker rm -f live-vlm-webui 2>/dev/null || true
sudo docker run -d --name live-vlm-webui --network host --runtime nvidia --privileged \
    -v /sys:/sys:ro -v /run/jtop.sock:/run/jtop.sock:ro live-vlm-webui-jetson

echo ""
echo "=== 啟動 Player（選用，RTSP 串流）==="
sudo docker rm -f player 2>/dev/null || true
sudo docker run -d --name player -p 8554:8554 \
    -v /home/brucehsu/project/videos:/videos:ro -e VIDEO_FILE=/videos/demo.mp4 player

echo ""
echo "=== 全部容器狀態 ==="
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
