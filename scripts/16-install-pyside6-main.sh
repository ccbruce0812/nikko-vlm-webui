#!/bin/bash
# ============================================================
# 16-install-pyside6-main.sh
# Create Python venv and install PySide6 + aiohttp for
# pyside6-main GUI (runs under Xorg + openbox, same as pyside6-gui).
#
# Usage:
#   bash scripts/16-install-pyside6-main.sh
# ============================================================
set -euo pipefail

# ---- help ----
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/16-install-pyside6-main.sh"
    echo ""
    echo "  Create pyside6-main-venv with PySide6 + aiohttp."
    echo "  Runs under Xorg + openbox (no graphical.target needed)."
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-main-venv"

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
echo "✓ pyside6-main venv ready"
echo "  source ${VENV_DIR}/bin/activate"
