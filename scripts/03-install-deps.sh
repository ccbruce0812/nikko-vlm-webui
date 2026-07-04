#!/usr/bin/env bash
# ============================================================
# Install basic packages (Docker check + python3-venv)
# Reference: README.md → Prerequisites → 3. Install packages
# ============================================================
set -euo pipefail

echo "=== Verify nvidia-container-runtime ==="
sudo docker info 2>/dev/null | grep -i runtime || echo "⚠ Docker not installed or nvidia-container-runtime missing"

echo ""
echo "=== Install python3-venv (required by model download script) ==="
sudo apt-get install -y python3-venv v4l-utils libxcb-cursor0 python3-pip jetson-stats
echo "✓ python3-venv installed"
