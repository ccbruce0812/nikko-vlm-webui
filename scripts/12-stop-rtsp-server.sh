#!/usr/bin/env bash
# ============================================================
# Stop RTSP Server
# ============================================================
set -euo pipefail

echo "=== Stopping rtsp-server ==="
sudo docker rm -f rtsp-server 2>/dev/null || echo "(container already stopped)"

echo "✓ RTSP server stopped"
