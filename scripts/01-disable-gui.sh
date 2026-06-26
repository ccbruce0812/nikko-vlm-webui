#!/usr/bin/env bash
# ============================================================
# 關閉圖形化登入 + 確保 WiFi 自動啟動 + 自動登入
# 對應 README.md → 前置準備 → 1. 關閉圖形化登入 + 確保 WiFi 與自動登入
# ============================================================
set -euo pipefail

echo "切換開機目標為 multi-user.target（關閉圖形化桌面）"
sudo systemctl set-default multi-user.target

echo ""
echo "確認 NetworkManager 在 multi-user.target 下已啟用 "
NM_STATUS=$(sudo systemctl is-enabled NetworkManager 2>/dev/null || echo "unknown")
echo "NetworkManager is-enabled: $NM_STATUS"
if [ "$NM_STATUS" != "enabled" ]; then
    echo "→ 手動啟用 NetworkManager"
    sudo systemctl enable NetworkManager
fi

echo ""
echo "設定 WiFi 自動連線"
echo "可用 WiFi 清單："
nmcli dev wifi list || echo "  (無 WiFi 介面或已連線)"

echo ""
echo "若需連線到新 WiFi，請執行："
echo "  sudo nmcli dev wifi connect \"SSID\" password \"YOUR_PASSWORD\""
echo "（已連線過的 WiFi 會在開機時自動重連，不需重新設定）"

echo ""
echo "設定 serial console 自動登入"
sudo mkdir -p /etc/systemd/system/serial-getty@.service.d
sudo tee /etc/systemd/system/serial-getty@.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin brucehsu --keep-baud 115200,57600,38400,9600 %I $TERM
EOF

echo ""
echo "完成！準備重開機"
echo "重開機後請執行以下驗證："
echo "  systemctl get-default             # → multi-user.target"
echo '  nmcli -t -f ACTIVE,SSID dev wifi  # → 應顯示 yes:你的SSID'
echo "  free -h                           # → available 應比原先多 ~400-500MB"
echo ""
read -rp "是否立即重開機？(y/N) " answer
if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    sudo reboot
fi
