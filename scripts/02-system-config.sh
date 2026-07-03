#!/usr/bin/env bash
# ============================================================
# System config: CSI camera + Super Mode 25W + memory tuning
# Reference: README.md → Prerequisites → 2. System Config
#
# CSI camera: CAM0 / IMX219, configured via jetson-io.py
# Super Mode: JetPack 6.1+, delete nvpmodel.conf → reboot → nvpmodel -m 2 (25W)
# Memory: NVMap/kernel tuning + CMA compaction
# ============================================================
set -euo pipefail

echo "============================================"
echo " CSI Camera + Super Mode (25W) + Memory Tuning"
echo "============================================"
echo ""

echo "=== 1. Current Status ==="
echo "nvpmodel mode:"
sudo nvpmodel -q
echo ""
echo "CSI camera:"
ls -la /dev/video* 2>/dev/null || echo "  No /dev/video* detected"
echo ""
echo "CMA / GPU available memory:"
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
echo ""
free -h

echo ""
echo "=== 2. CSI Camera Setup (IMX219) ==="
if [ -e /dev/video0 ]; then
    echo "✓ /dev/video0 present"
    if v4l2-ctl -d /dev/video0 --list-formats 2>/dev/null | head -5; then
        echo "✓ /dev/video0 accessible (for nvarguscamerasrc)"
    fi
else
    echo "⚠ /dev/video0 not found. Configure IMX219 camera:"
    echo ""
    echo "  1. Ensure IMX219 is connected to CAM0 or CAM1 (CSI connector near power jack)"
    echo "  2. sudo /opt/nvidia/jetson-io/jetson-io.py"
    echo "     Select \"Configure for compatible camera\""
    echo "     → Check \"Camera IMX219 Dual (CAM0 + CAM1)\" or \"Camera IMX219 A (CAM0)\""
    echo "     → Save and reboot to reconfigure pins"
    echo "  3. After reboot, /dev/video0 will appear"
    echo ""
    read -p "  Run jetson-io.py now? [y/N] " yn
    case "$yn" in
        [Yy]*)
            echo "→ Starting jetson-io.py (interactive)..."
            sudo /opt/nvidia/jetson-io/jetson-io.py
            echo "→ Please reboot manually after setup"
            ;;
        *)
            echo "→ Skipped (rtsp-server will not be usable)"
            ;;
    esac
fi

echo ""
echo "=== 3. Check Super Mode (25W) Support ==="
if sudo nvpmodel -q 2>/dev/null | grep -q "25W\|MAXN Super"; then
    echo "✓ nvpmodel.conf already supports Super Mode (25W)"
else
    echo "⚠ Current nvpmodel.conf only supports standard 15W MAXN"
    echo ""
    echo "  To enable Super Mode (25W):"
    echo "  1. Verify JetPack 6.1+ SD card image (with Super Mode support)"
    echo "  2. sudo rm -rf /etc/nvpmodel.conf    # delete old config"
    echo "  3. sudo reboot                        # system regenerates 25W nvpmodel.conf"
    echo ""
    echo "  Re-run this script after reboot."
    echo ""
    read -p "  Delete nvpmodel.conf and reboot now? [y/N] " yn
    case "$yn" in
        [Yy]*)
            echo "→ Removing /etc/nvpmodel.conf ..."
            sudo rm -rf /etc/nvpmodel.conf
            echo "→ Rebooting in 3 seconds..."
            sleep 3
            sudo reboot
            ;;
        *)
            echo "→ Skipped, continuing with standard 15W MAXN"
            ;;
    esac
fi

echo ""
echo "=== 4. Set MAXN Super Mode (25W) ==="
sudo nvpmodel -m 2
echo "→ MAXN mode 2 (Super Mode 25W)"

echo ""
echo "=== 5. Lock Max Clocks (CPU + GPU + EMC) ==="
sudo jetson_clocks
echo "→ clocks locked"

echo ""
echo "=== Tuning NVMap / kernel params (increase CMA allocatable space) ==="
echo "  vm.swappiness: 60 → 10 (reduce swap, keep GPU data in RAM)"
sudo sysctl -w vm.swappiness=10
echo "  vm.vfs_cache_pressure: 100 → 200 (reclaim cache faster for CMA)"
sudo sysctl -w vm.vfs_cache_pressure=200
echo "  vm.min_free_kbytes → 65536 (reserve more contiguous free pages)"
sudo sysctl -w vm.min_free_kbytes=65536
echo "  tegra_nvmap ext_pool_size → 1024 (limit GPU userspace pool)"
sudo sh -c 'echo 1024 > /sys/kernel/debug/tegra_nvmap/ext_pool_size' 2>/dev/null || echo "  (not available on Orin Nano, skipping)"

echo ""
echo "=== Compact memory (maximize CMA contiguous blocks) ==="
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1
echo "→ cache dropped + memory compacted"

echo ""
echo "=== Verify ==="
echo "CSI camera: $(ls /dev/video0 2>/dev/null && echo '✓ /dev/video0' || echo '✗ not detected')"
echo "CMA / GPU available memory after tuning:"
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
echo ""
free -h
echo ""
echo "nvpmodel mode: $(sudo nvpmodel -q 2>/dev/null | grep 'NV Power Mode' || echo 'check with: nvpmodel -q')"

echo ""
echo "============================================"
echo " CSI Camera + Super Mode (25W) + Memory Tuning complete"
echo "============================================"
