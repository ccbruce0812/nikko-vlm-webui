#!/bin/bash
# ============================================================
# 18-start-pyside6-gui.sh
# Starts Xorg (if needed), nvargus-daemon, then launches GUI.
# Cleans up Xorg on exit only if it was started by this script.
#
# Usage:
#   bash scripts/18-start-pyside6-gui.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-gui-venv"
GUI_DIR="${PROJECT_DIR}/pyside6-gui"

# ---- help ----
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/18-start-pyside6-gui.sh"
    echo ""
    echo "  Launch the kiosk GUI."
    echo "  Requires Xorg (xorg.service) and nvargus-daemon."
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

# ---- Launch ----
source "${VENV_DIR}/bin/activate"
cd "${GUI_DIR}"
python main.py
