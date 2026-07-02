#!/usr/bin/env bash
# ============================================================
# Stop Reason2 stack (docker compose down)
# ============================================================
set -euo pipefail
echo "=== Stopping Reason2 stack ==="
cd "$(dirname "$0")/../reason2"
sudo docker compose down
echo "  ✓ reason2 + router + webui stopped"
