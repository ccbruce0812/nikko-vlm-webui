#!/usr/bin/env bash
# ============================================================
# Disable GUI (graphical.target) + enable Xorg for nvarguscamerasrc
# Reference: README.md → Prerequisites → 5. Disable GUI
# ============================================================
set -euo pipefail

echo "=== Switch to multi-user.target (text mode) ==="
sudo systemctl set-default multi-user.target
echo "→ Default target: multi-user"

echo ""
echo "=== Create xorg.service (Xorg under multi-user.target) ==="
sudo tee /etc/systemd/system/xorg.service > /dev/null << 'EOF'
[Unit]
Description=Xorg display server
After=multi-user.target

[Service]
ExecStart=/usr/bin/Xorg :0 -nolisten tcp -noreset
Restart=no

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable xorg.service
echo "→ xorg.service enabled (auto-start after reboot)"

echo ""
echo "=== Done ==="
echo "Run 'sudo reboot' to apply. After reboot, verify:"
echo "  systemctl get-default       → multi-user.target"
echo "  pgrep Xorg                  → should show PID"
echo ""
echo "  After System Configuration (02-system-config.sh), test CSI camera:"
echo "  export DISPLAY=:0"
echo "  sudo systemctl restart nvargus-daemon"
echo "  timeout 5 gst-launch-1.0 -v nvarguscamerasrc sensor-id=0 \\"
echo "      ! 'video/x-raw(memory:NVMM),width=1280,height=720,format=NV12,framerate=60/1' \\"
echo "      ! nvvidconv ! fpsdisplaysink video-sink=fakesink"
echo "    → should show ~59 fps (without DISPLAY → ~3 fps)"
echo ""
echo "  timeout 5 gst-launch-1.0 -v nvarguscamerasrc sensor-id=0 \\"
echo "      ! 'video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12,framerate=30/1' \\"
echo "      ! nvvidconv ! fpsdisplaysink video-sink=fakesink"
echo "    → should show ~29 fps"
