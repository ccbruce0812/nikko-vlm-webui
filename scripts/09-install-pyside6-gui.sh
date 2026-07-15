#!/bin/bash
# ============================================================
# 09-install-pyside6-gui.sh
# Create Python venv and install PySide6 + aiohttp for the
# kiosk VLM GUI and headless validation tool.
#
# Usage:
#   bash scripts/09-install-pyside6-gui.sh
# ============================================================
set -euo pipefail

# ---- help ----
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/09-install-pyside6-gui.sh"
    echo ""
    echo "  Create pyside6-gui-venv with PySide6 + aiohttp."
    echo "  For kiosk GUI and headless validation tool."
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-gui-venv"

# ---- DeepStream env vars + display blanking → ~/.bashrc ----
if ! grep -q "DEEPSTREAM_DIR" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'EOS'
# DeepStream 7.1
export DEEPSTREAM_DIR=/opt/nvidia/deepstream/deepstream-7.1
export PATH=$DEEPSTREAM_DIR/bin:$PATH
export LD_LIBRARY_PATH=$DEEPSTREAM_DIR/lib:$LD_LIBRARY_PATH

# Disable screen blanking for kiosk
export DISPLAY=:0
xset s off -dpms
EOS
fi
export DEEPSTREAM_DIR=/opt/nvidia/deepstream/deepstream-7.1
export PATH="$DEEPSTREAM_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$DEEPSTREAM_DIR/lib:$LD_LIBRARY_PATH"

# Apply immediately (in addition to .bashrc for persistence)
export DISPLAY=:0
xset s off -dpms 2>/dev/null || true

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
