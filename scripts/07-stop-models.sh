#!/usr/bin/env bash
# ============================================================
# 07-stop-models.sh
# Stop all model containers and remove vlm-net.
# Does NOT delete Docker images.
# ============================================================
set -euo pipefail

usage() {
    echo "Usage: bash scripts/07-stop-models.sh"
    echo ""
    echo "  Stop and remove all model containers (reason2, moondream2,"
    echo "  yolo, router, live-vlm-webui, rtsp-server) and delete vlm-net."
    echo "  Docker images are NOT removed."
    exit 0
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
fi

echo "============================================"
echo " Stopping All Model Containers"
echo "============================================"

for c in reason2 moondream2 yolo router live-vlm-webui rtsp-server; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "→ Removing $c ..."
        sudo docker rm -f "$c" 2>/dev/null && echo "  ✓" || echo "  ⚠ failed"
    else
        echo "  $c (not running)"
    fi
done

echo ""
echo "=== Removing vlm-net ==="
sudo docker network rm vlm-net 2>/dev/null && echo "  ✓ removed" || echo "  (not found)"

echo ""
echo "✓ All containers stopped"
