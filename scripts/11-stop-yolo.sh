#!/usr/bin/env bash
# ============================================================
# Stop YOLO stack (docker compose down)
# ============================================================
set -euo pipefail
echo "=== Stopping YOLO stack ==="
cd "$(dirname "$0")/../yolo"
sudo docker compose down
echo "  ✓ yolo + router + webui stopped"
