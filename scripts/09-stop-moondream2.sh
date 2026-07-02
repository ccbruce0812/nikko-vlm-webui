#!/usr/bin/env bash
# ============================================================
# 停止 moondream2 組合（docker compose down）
# ============================================================
set -euo pipefail
echo "=== 停止 moondream2 組合 ==="
cd "$(dirname "$0")/../moondream2"
sudo docker compose down
echo "  ✓ moondream2 + router + webui 已停止"
