#!/usr/bin/env bash
# ============================================================
# Stop live-vlm-webui
# ============================================================
set -euo pipefail

echo "=== Stopping live-vlm-webui ==="
sudo docker rm -f live-vlm-webui 2>/dev/null || echo "(container already stopped)"

echo "✓ live-vlm-webui stopped"
