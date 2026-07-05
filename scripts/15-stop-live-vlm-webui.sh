#!/usr/bin/env bash
# ============================================================
# Stop live-vlm-webui
# ============================================================
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/15-stop-live-vlm-webui.sh"
    echo ""
    echo "  Stop and remove the live-vlm-webui Docker container."
    exit 0
fi

echo "=== Stopping live-vlm-webui ==="
sudo docker rm -f live-vlm-webui 2>/dev/null || echo "(container already stopped)"

echo "✓ live-vlm-webui stopped"
