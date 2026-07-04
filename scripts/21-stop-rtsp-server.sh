#!/usr/bin/env bash
# ============================================================
# Stop RTSP Server
# ============================================================
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/21-stop-rtsp-server.sh"
    echo ""
    echo "  Stop and remove the RTSP server Docker container."
    exit 0
fi

echo "=== Stopping rtsp-server ==="
sudo docker rm -f rtsp-server 2>/dev/null || echo "(container already stopped)"

echo "✓ RTSP server stopped"
