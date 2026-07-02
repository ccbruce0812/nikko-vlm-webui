#!/usr/bin/env bash
# ============================================================
# 停止 YOLO 組合（docker compose down）
# ============================================================
set -euo pipefail
echo "=== 停止 YOLO 組合 ==="
cd "$(dirname "$0")/../yolo"
sudo docker compose down
echo "  ✓ yolo + router + webui 已停止"
