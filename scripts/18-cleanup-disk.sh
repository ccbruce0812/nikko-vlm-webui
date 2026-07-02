#!/usr/bin/env bash
# ============================================================
# Clean up Docker disk space
# Reference: README.md → Troubleshooting → 7. Disk space
# ============================================================
set -euo pipefail

echo "=== Docker disk usage before ==="
sudo docker system df

echo ""
echo "=== Pruning all unused data ==="
sudo docker system prune -af

echo ""
echo "=== Docker disk usage after ==="
sudo docker system df
echo ""
echo "✓ Cleanup complete"
