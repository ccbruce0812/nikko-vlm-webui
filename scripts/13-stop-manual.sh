#!/usr/bin/env bash
# ============================================================
# Stop all manually started containers
# Reference: scripts/12-start-manual.sh
# ============================================================
set -euo pipefail

echo "============================================"
echo " Stop All Containers"
echo "============================================"

for c in rtsp-server yolo moondream2 reason2 live-vlm-webui router; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "→ Stopping $c ..."
        sudo docker stop "$c" 2>/dev/null && echo "  ✓ stopped" || echo "  ⚠ stop failed"
        sudo docker rm "$c" 2>/dev/null && echo "  ✓ removed" || true
    else
        echo "  $c not running, skip"
    fi
done

echo ""
echo "============================================"
echo " All containers stopped"
echo "============================================"
