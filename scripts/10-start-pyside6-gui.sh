#!/bin/bash
# ============================================================
# 10-start-pyside6-gui.sh
# Starts Xorg (if needed), nvargus-daemon, then launches GUI.
# Cleans up Xorg on exit only if it was started by this script.
#
# Usage:
#   bash scripts/10-start-pyside6-gui.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-gui-venv"
GUI_DIR="${PROJECT_DIR}/pyside6-gui"

# ---- help ----
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/10-start-pyside6-gui.sh [--dpi-scale SCALE]"
    echo ""
    echo "  Launch the kiosk GUI (PySide6 fullscreen window)."
    echo "  Requires Xorg (xorg.service) and openbox.service."
    echo ""
    echo "  --dpi-scale SCALE    Font scale factor (default: 2.0)"
    echo "                       Font = 12 × DPI/96 × scale"
    exit 0
fi

if [ ! -f "${VENV_DIR}/bin/activate" ]; then
    echo "[ERROR] venv not found at ${VENV_DIR}"
    echo "        Run: bash scripts/09-install-pyside6-gui.sh"
    exit 1
fi

# ---- Already running? ----
PID_FILE="/tmp/pyside6-gui.pid"
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[ERROR] pyside6-gui is already running (PID $OLD_PID)."
        echo "        Stop it first: Alt+Q or kill $OLD_PID"
        exit 1
    fi
    # Stale PID file — clean it
    rm -f "$PID_FILE"
fi

# ---- Xorg (required by nvarguscamerasrc) ----
if ! pgrep -x Xorg >/dev/null 2>&1; then
    echo "[ERROR] Xorg is not running."
    echo "        Run: sudo systemctl start xorg"
    echo "        Or:  bash scripts/01-disable-gui.sh (one-time setup)"
    exit 1
fi

export DISPLAY=:0

# ---- Argus daemon ----
echo "[INFO] Restarting nvargus-daemon..."
sudo systemctl restart nvargus-daemon
sleep 2

# ---- MAXN Super Mode (25W) ----
echo "[INFO] Setting MAXN Super Mode (25W)..."
if ! sudo nvpmodel -q 2>/dev/null | grep -q "NV Power Mode: MAXN_SUPER"; then
    sudo nvpmodel -m 2
fi
sudo jetson_clocks

# ---- Memory tuning ----
echo "[INFO] Memory tuning (CMA optimization)..."
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1

# ---- Window manager (required for keyboard input) ----
if ! pgrep -x openbox >/dev/null 2>&1; then
    echo "[ERROR] openbox is not running."
    echo "        Run: sudo systemctl start openbox"
    echo "        Or:  bash scripts/01-disable-gui.sh (one-time setup)"
    exit 1
fi

# ---- Launch ----
export QT_QPA_PLATFORM=xcb
source "${VENV_DIR}/bin/activate"
cd "${GUI_DIR}"
python main.py "$@"
