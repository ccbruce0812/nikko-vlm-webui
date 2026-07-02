#!/usr/bin/env bash
# ============================================================
# Stop RTSP Server
# ============================================================
set -euo pipefail
echo "=== Stopping RTSP Server ==="
sudo docker stop rtsp-server 2>/dev/null && echo "  ✓ stopped" || echo "  not running"
sudo docker rm rtsp-server 2>/dev/null && echo "  ✓ removed" || true
