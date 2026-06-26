#!/usr/bin/env bash
# ============================================================
# 疑難排解：cosmos 啟動失敗（CUDA out of memory）
# 對應 README.md → 疑難排解 → cosmos 啟動失敗
# 解法：先停其他模型，啟動 cosmos，再恢復
# ============================================================
set -euo pipefail

echo "=== 停止佔用 GPU 的容器 ==="
sudo docker stop yolo 2>/dev/null || echo "yolo 未執行"
sudo docker stop moondream2 2>/dev/null || echo "moondream2 未執行"

echo ""
echo "=== 啟動 Cosmos-Reason2 ==="
sudo docker start cosmos-reason2

echo "等待 Cosmos 載入 (35 秒)..."
sleep 35

echo ""
echo "=== 恢復其他模型 ==="
sudo docker start yolo 2>/dev/null || echo "yolo 無容器"
sudo docker start moondream2 2>/dev/null || echo "moondream2 無容器"

echo ""
echo "=== 目前執行中的容器 ==="
sudo docker ps --format "table {{.Names}}\t{{.Status}}"
