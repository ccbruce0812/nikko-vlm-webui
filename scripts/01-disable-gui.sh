#!/usr/bin/env bash
# ============================================================
# Disable GUI (graphical.target) + enable WiFi auto-login
# Reference: README.md → Prerequisites → 1. Disable GUI
# ============================================================
set -euo pipefail

echo "=== Switch to multi-user.target (no GUI) ==="
sudo systemctl set-default multi-user.target
echo "→ Default target: multi-user"

echo ""
echo "=== Verify NetworkManager enabled in multi-user ==="
if sudo systemctl is-enabled NetworkManager | grep -q enabled; then
    echo "✓ NetworkManager already enabled"
else
    echo "→ Enabling NetworkManager..."
    sudo systemctl enable NetworkManager
fi

echo ""
echo "=== Set serial console auto-login (UART) ==="
sudo mkdir -p /etc/systemd/system/serial-getty@.service.d
sudo tee /etc/systemd/system/serial-getty@.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin brucehsu --keep-baud 115200,57600,38400,9600 %I $TERM
EOF
echo "→ Auto-login configured for brucehsu"

echo ""
echo "=== Done ==="
echo "Run 'sudo reboot' to apply. After reboot, verify:"
echo "  systemctl get-default     → multi-user.target"
echo "  nmcli -t -f ACTIVE,SSID dev wifi  → yes:YOUR_SSID"
echo "  free -h                   → +400-500MB available"
