#!/bin/bash
# ============================================================
# 16-start-pyside6-main.sh
# Launch pyside6-main GUI (Xorg + openbox, same env as pyside6-gui).
#
# Usage:
#   bash scripts/16-start-pyside6-main.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-main-venv"
MAIN_DIR="${PROJECT_DIR}/pyside6-main"

# ---- help ----
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/16-start-pyside6-main.sh [--dpi-scale SCALE]"
    echo ""
    echo "  Launch the pyside6-main GUI (windowed, with title bar)."
    echo "  Requires Xorg + openbox and Router API."
    echo ""
    echo "  --dpi-scale SCALE    Font scale factor (default: 2.0)"
    echo "                       Font = 12 × DPI/96 × scale"
    exit 0
fi

if [ ! -f "${VENV_DIR}/bin/activate" ]; then
    echo "✗ venv not found at ${VENV_DIR}"
    echo "  Run: bash scripts/15-install-pyside6-main.sh"
    exit 1
fi

# ---- Already running? ----
PID_FILE="/tmp/pyside6-main.pid"
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "✗ pyside6-main is already running (PID $OLD_PID)."
        echo "  Close the existing window first."
        exit 1
    fi
    # Stale PID file — clean it
    rm -f "$PID_FILE"
fi

# ---- Xorg + DISPLAY ----
if ! pgrep -x Xorg >/dev/null 2>&1; then
    echo "✗ Xorg is not running."
    echo "  Run: sudo systemctl start xorg"
    exit 1
fi
export DISPLAY=:0

# ---- Argus daemon ----
echo "=== Restarting nvargus-daemon ==="
sudo systemctl restart nvargus-daemon
sleep 2

# ---- MAXN Super Mode (25W) ----
echo "=== Setting MAXN Super Mode (25W) ==="
if ! sudo nvpmodel -q 2>/dev/null | grep -q "NV Power Mode: MAXN_SUPER"; then
    sudo nvpmodel -m 2
fi
sudo jetson_clocks

# ---- Memory tuning ----
echo "=== Memory tuning ==="
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1

# ---- Window manager (required for keyboard input) ----
if ! pgrep -x openbox >/dev/null 2>&1; then
    echo "✗ openbox is not running."
    echo "  Run: sudo systemctl start openbox"
    echo "  Or:  bash scripts/01-disable-gui.sh (one-time setup)"
    exit 1
fi

# ---- Launch ----
export QT_QPA_PLATFORM=xcb
source "${VENV_DIR}/bin/activate"
cd "${MAIN_DIR}"
echo "=== Starting pyside6-main GUI ==="
python main.py "$@"
