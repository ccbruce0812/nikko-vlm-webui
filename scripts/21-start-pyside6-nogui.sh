#!/bin/bash
# ============================================================
# 21-start-pyside6-nogui.sh
# Starts Xorg (if needed), nvargus-daemon, then headless mode.
# Cleans up Xorg on exit only if it was started by this script.
#
# Usage:
#   bash scripts/21-start-pyside6-nogui.sh [args...]
#
#   bash scripts/21-start-pyside6-nogui.sh \
#       --camera-id 0 --resolution 1280x720@60 \
#       --model yolo --interval 5 --max-tokens 200
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-gui-venv"
GUI_DIR="${PROJECT_DIR}/pyside6-gui"

# ---- help ----
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/21-start-pyside6-nogui.sh [OPTIONS]"
    echo ""
    echo "  Headless validation mode — GStreamer + Router API, no window."
    echo "  Handles Xorg lifecycle, nvargus-daemon, DISPLAY automatically."
    echo ""
    echo "Options (forwarded to main_nogui.py):"
    echo "  --camera-id N       /dev/videoN index (default: 0)"
    echo "  --resolution WxH@FPS  e.g. 1920x1080@30, 1280x720 (default: 1920x1080)"
    echo "  --model NAME        reason2 | moondream2 | yolo (default: reason2)"
    echo "  --interval N        seconds between inference (default: 1)"
    echo "  --prompt TEXT       prompt sent to VLM"
    echo "  --max-tokens N      response token limit 1–2048 (default: 512)"
    echo "  --help, -h          show this message"
    echo ""
    echo "Examples:"
    echo "  bash scripts/21-start-pyside6-nogui.sh"
    echo "  bash scripts/21-start-pyside6-nogui.sh --camera-id 0 --resolution 1280x720@60"
    echo "  bash scripts/21-start-pyside6-nogui.sh -h"
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

# ---- Launch (offscreen Qt — no window needed) ----
export QT_QPA_PLATFORM=offscreen

source "${VENV_DIR}/bin/activate"
cd "${GUI_DIR}"
python main_nogui.py "$@"
