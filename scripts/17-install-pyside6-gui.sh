#!/bin/bash
# ============================================================
# 17-install-pyside6-gui.sh
# Create Python venv and install PySide6 + aiohttp for the
# kiosk VLM GUI and headless validation tool.
#
# Usage:
#   bash scripts/17-install-pyside6-gui.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-gui-venv"

echo "=== Create Python venv (--system-site-packages) ==="
rm -rf "${VENV_DIR}"
python3 -m venv --system-site-packages "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip setuptools wheel
pip install pyside6 aiohttp

echo ""
echo "Python: $(python3 --version)"
echo "pip:    $(pip --version)"
echo "venv:   ${VENV_DIR}"
echo ""
echo "✓ pyside6-gui venv ready"
echo "  source ${VENV_DIR}/bin/activate"
