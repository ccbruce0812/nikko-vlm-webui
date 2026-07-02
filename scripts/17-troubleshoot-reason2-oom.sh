#!/usr/bin/env bash
# ============================================================
# Troubleshoot: Reason2 OOM (CUDA out of memory)
# Reference: README.md → Troubleshooting → 1. Reason2 OOM
# Stop other models, start Reason2, then restore
# ============================================================
set -euo pipefail

echo "=== Stopping other models ==="
sudo docker stop yolo moondream2 2>/dev/null || true
echo "→ other models stopped"

echo ""
echo "=== Starting Reason2 ==="
sudo docker start reason2
echo "→ Reason2 starting (wait 35s)..."
sleep 35

echo ""
echo "=== Restoring other models ==="
sudo docker start yolo moondream2 2>/dev/null || true
echo "→ other models restored"

echo ""
echo "=== Done ==="
curl -s http://localhost:8080/v1/models | python3 -m json.tool
