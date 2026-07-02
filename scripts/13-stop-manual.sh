#!/usr/bin/env bash
# ============================================================
# 停止所有手動啟動的容器（router + webui + 模型 + RTSP）
# 對應 scripts/12-start-manual.sh
# ============================================================
set -euo pipefail

echo "============================================"
echo " 停止所有容器"
echo "============================================"

for c in rtsp-server yolo moondream2 reason2 live-vlm-webui router; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "→ 停止 $c ..."
        sudo docker stop "$c" 2>/dev/null && echo "  ✓ 已停止" || echo "  ⚠ 停止失敗"
        sudo docker rm "$c" 2>/dev/null && echo "  ✓ 已移除" || true
    else
        echo "  $c 未運行，跳過"
    fi
done

echo ""
echo "============================================"
echo " 所有容器已停止"
echo "============================================"
