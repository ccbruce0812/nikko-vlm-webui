#!/usr/bin/env bash
# ============================================================
# Stop moondream2 stack (docker compose down)
# ============================================================
set -euo pipefail
echo "=== Stopping moondream2 stack ==="
cd "$(dirname "$0")/../moondream2"
sudo docker compose down
echo "  ✓ moondream2 + router + webui stopped"
