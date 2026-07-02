#!/usr/bin/env bash
# ============================================================
# 停止 Reason2 組合（docker compose down）
# ============================================================
set -euo pipefail
echo "=== 停止 Reason2 組合 ==="
cd "$(dirname "$0")/../reason2"
sudo docker compose down
echo "  ✓ reason2 + router + webui 已停止"
