#!/usr/bin/env bash
# ============================================================
# 啟動 YOLO 組合（docker compose）
# 對應 README.md → 啟動服務 → docker-compose
# ============================================================
set -euo pipefail

cd ~/project/yolo
sudo docker compose up -d

echo ""
echo "=== YOLO 組合已啟動 ==="
sudo docker compose ps
echo ""
echo "等待模型載入..."
sleep 15
echo "檢查模型清單："
curl -s http://localhost:8080/v1/models | python3 -m json.tool
