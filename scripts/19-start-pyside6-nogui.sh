#!/bin/bash
# ============================================================
# 19-start-pyside6-nogui.sh
# Starts Xorg (if needed), nvargus-daemon, then headless mode.
# Cleans up Xorg on exit only if it was started by this script.
#
# Usage:
#   bash scripts/19-start-pyside6-nogui.sh [args...]
#
#   bash scripts/19-start-pyside6-nogui.sh \
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
    echo "Usage: bash scripts/19-start-pyside6-nogui.sh [OPTIONS]"
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
    echo "  bash scripts/19-start-pyside6-nogui.sh"
    echo "  bash scripts/19-start-pyside6-nogui.sh --camera-id 0 --resolution 1280x720@60"
    echo "  bash scripts/19-start-pyside6-nogui.sh -h"
    exit 0
fi

if [ ! -f "${VENV_DIR}/bin/activate" ]; then
    echo "[ERROR] venv not found at ${VENV_DIR}"
    echo "        Run: bash scripts/17-install-pyside6-gui.sh"
    exit 1
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
sudo nvpmodel -m 2
sudo jetson_clocks

# ---- Memory tuning ----
echo "[INFO] Memory tuning (CMA optimization)..."
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1

# ---- Launch (offscreen Qt — no window needed) ----
export QT_QPA_PLATFORM=offscreen

source "${VENV_DIR}/bin/activate"
cd "${GUI_DIR}"
python main_nogui.py "$@"
