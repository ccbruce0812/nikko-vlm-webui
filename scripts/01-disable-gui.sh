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
echo "=== Install openbox (window manager, required for kiosk GUI) ==="
sudo apt install -y openbox

echo ""
echo "=== Create xorg.service (Xorg under multi-user.target) ==="
sudo tee /etc/systemd/system/xorg.service > /dev/null << 'EOF'
[Unit]
Description=Xorg display server
Before=openbox.service

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
echo "=== Create openbox.service (window manager) ==="
sudo tee /etc/systemd/system/openbox.service > /dev/null << EOF
[Unit]
Description=Openbox window manager
After=xorg.service
Requires=xorg.service

[Service]
Type=simple
ExecStart=/usr/bin/openbox
Environment=DISPLAY=:0
User=${USER}
Restart=no

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable openbox.service
echo "→ openbox.service enabled"

mkdir -p ~/.config/openbox
cat > ~/.config/openbox/rc.xml << 'RCEOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config>
  <keyboard>
    <chainQuitKey>C-g</chainQuitKey>
  </keyboard>
  <applications>
    <application name="Kiosk VLM GUI" class="main.py">
      <decor>no</decor>
    </application>
  </applications>
</openbox_config>
RCEOF
echo "→ openbox RC configured (undecorated kiosk window)"

# xterm auto-scale launcher (font follows screen height)
mkdir -p ~/.config/openbox
cat > ~/.config/openbox/autostart << 'AUTOSTART'
#!/bin/bash
# Auto-scale xterm font: fs = screen_height / 30
H=$(xrandr 2>/dev/null | grep '*' | head -1 | awk '{print $1}' | cut -d'x' -f2)
FS=$(( ${H:-1080} / 30 ))
xterm -fullscreen -fa 'Monospace' -fs "$FS" -bg black -fg white &
AUTOSTART
chmod +x ~/.config/openbox/autostart
echo "→ openbox autostart: xterm with fs=$(( ( $(xrandr 2>/dev/null | grep '*' | head -1 | awk '{print $1}' | cut -d'x' -f2; echo 1080) / 30 ))) (auto-scale)"

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
