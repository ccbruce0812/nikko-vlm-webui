#!/bin/bash
# ============================================================
# 20-start-pyside6-gui.sh
# Starts Xorg (if needed), nvargus-daemon, then launches GUI.
# Cleans up Xorg on exit only if it was started by this script.
#
# Usage:
#   bash scripts/20-start-pyside6-gui.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-gui-venv"
GUI_DIR="${PROJECT_DIR}/pyside6-gui"

# ---- help ----
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/20-start-pyside6-gui.sh"
    echo ""
    echo "  Launch the kiosk GUI."
    echo "  Handles Xorg lifecycle, nvargus-daemon, DISPLAY automatically."
    exit 0
fi

if [ ! -f "${VENV_DIR}/bin/activate" ]; then
    echo "[ERROR] venv not found at ${VENV_DIR}"
    echo "        Run: bash scripts/19-install-pyside6-gui.sh"
    exit 1
fi

# ---- Xorg life-cycle ----
XORG_STARTED_BY_US=false
cleanup_xorg() {
    if [ "$XORG_STARTED_BY_US" = true ]; then
        echo "[INFO] Stopping Xorg (started by this script)..."
        sudo pkill Xorg 2>/dev/null || true
        sleep 1
    fi
    echo "[INFO] Unset DISPLAY"
    unset DISPLAY
}
trap cleanup_xorg EXIT

if ! pgrep -x Xorg >/dev/null 2>&1; then
    echo "[INFO] Starting Xorg :0 ..."
    sudo Xorg :0 -nolisten tcp -noreset &
    XORG_STARTED_BY_US=true
    sleep 2
fi

export DISPLAY=:0

# ---- Argus daemon ----
echo "[INFO] Restarting nvargus-daemon..."
sudo systemctl restart nvargus-daemon
sleep 2

# ---- Launch ----
source "${VENV_DIR}/bin/activate"
cd "${GUI_DIR}"
python main.py
