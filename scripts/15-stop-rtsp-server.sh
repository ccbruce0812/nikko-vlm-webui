#!/usr/bin/env bash
# ============================================================
# 停止 RTSP Server（docker stop + rm）
# ============================================================
set -euo pipefail
echo "=== 停止 RTSP Server ==="
sudo docker stop rtsp-server 2>/dev/null && echo "  ✓ 已停止" || echo "  未運行"
sudo docker rm rtsp-server 2>/dev/null && echo "  ✓ 已移除" || true
