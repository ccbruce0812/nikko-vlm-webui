#!/usr/bin/env bash
# ============================================================
# 系統配置（CSI 攝影機 + Super Mode 25W + 記憶體優化）
# 對應 README.md → 前置準備 → 2. 系統配置
#
# Jetson Orin Nano Super Mode 說明：
#   標準 MAXN = 15W，Super Mode = 25W（需 JetPack 6.1+）
#   啟用方式：刪除舊 nvpmodel.conf → reboot 重新產生 → nvpmodel -m 2
#
# CSI 攝影機：CAM0 / IMX219，透過 jetson-io.py 設定 device tree overlay
#
# 依序：狀態 → CSI 攝影機 → Super Mode → MAXN (25W) → 鎖時脈 → NVMap/kernel → 清除碎片
# 目標：最大化 GPU 可用的連續記憶體
# ============================================================
set -euo pipefail

echo "============================================"
echo " CSI 攝影機 + Super Mode (25W) + 記憶體優化"
echo "============================================"
echo ""

# 查看目前狀態
echo "=== 1. 目前狀態 ==="
echo "nvpmodel 模式:"
sudo nvpmodel -q
echo ""
echo "CSI 攝影機:"
ls -la /dev/video* 2>/dev/null || echo "  未偵測到 /dev/video*"
echo ""
echo "CMA / GPU 可用記憶體:"
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
echo ""
free -h

# ── CSI 攝影機設定（CAM0 / IMX219） ──
echo ""
echo "=== 2. CSI 攝影機設定（CAM0 / IMX219）==="
if [ -e /dev/video0 ]; then
    echo "✓ /dev/video0 已存在"
    # 確認是 IMX219
    if v4l2-ctl -d /dev/video0 --list-formats 2>/dev/null | head -5; then
        echo "✓ /dev/video0 可存取（供 nvarguscamerasrc 使用）"
    fi
else
    echo "⚠ /dev/video0 不存在，需設定 IMX219 攝影機"
    echo ""
    echo "  設定步驟："
    echo "  1. 確認 IMX219 已接在 CAM0（靠近電源孔的 CSI 接頭）"
    echo "  2. sudo /opt/nvidia/jetson-io/jetson-io.py"
    echo "     選擇「Configure for compatible camera」"
    echo "     → 勾選「Camera IMX219 Dual」或「Camera IMX219 Single」"
    echo "     → 選擇「Save and reboot to reconfigure pins」"
    echo "  3. 重開機後 /dev/video0 會出現"
    echo ""
    read -p "  是否現在執行 jetson-io.py 設定？[y/N] " yn
    case "$yn" in
        [Yy]*)
            echo "→ 啟動 jetson-io.py（互動式，請在終端機中操作）..."
            sudo /opt/nvidia/jetson-io/jetson-io.py
            echo "→ 設定完成，請手動 reboot"
            ;;
        *)
            echo "→ 跳過 CSI 攝影機設定（rtsp-server 將無法使用）"
            ;;
    esac
fi

# 檢查 nvpmodel.conf 是否已支援 Super Mode (25W)
echo ""
echo "=== 3. 檢查 Super Mode (25W) 支援 ==="
if sudo nvpmodel -q 2>/dev/null | grep -q "25W\|MAXN Super"; then
    echo "✓ nvpmodel.conf 已支援 Super Mode (25W)"
else
    echo "⚠ 目前 nvpmodel.conf 僅支援標準 15W MAXN"
    echo ""
    echo "  啟用 Super Mode (25W) 步驟："
    echo "  1. 確認已刷入 JetPack 6.1+ SD 卡映像（含 Super Mode 支援）"
    echo "  2. sudo rm -rf /etc/nvpmodel.conf    # 刪除舊設定"
    echo "  3. sudo reboot                        # 重開機後自動產生 25W nvpmodel.conf"
    echo ""
    echo "  重開機後再執行一次本腳本即可。"
    echo ""
    read -p "  是否現在刪除 nvpmodel.conf 並重開機？[y/N] " yn
    case "$yn" in
        [Yy]*)
            echo "→ 刪除 /etc/nvpmodel.conf ..."
            sudo rm -rf /etc/nvpmodel.conf
            echo "→ 3 秒後重開機..."
            sleep 3
            sudo reboot
            ;;
        *)
            echo "→ 跳過，繼續以標準 15W MAXN 執行（非 Super Mode）"
            ;;
    esac
fi

# 設定 MAXN Super Mode (25W)
echo ""
echo "=== 4. 設定 MAXN Super Mode (25W) ==="
sudo nvpmodel -m 2
echo "→ MAXN mode 2 (Super Mode 25W)"

# 鎖定最高時脈
echo ""
echo "=== 5. 鎖定最高時脈（CPU + GPU + EMC）==="
sudo jetson_clocks
echo "→ clocks locked"

# 調整 NVMap / kernel 參數
echo ""
echo "調整 NVMap / kernel 參數（增加 CMA 可分配空間）"
echo "  vm.swappiness: 60 → 10（降低 swap 傾向，避免 GPU 資料被 swap）"
sudo sysctl -w vm.swappiness=10
echo "  vm.vfs_cache_pressure: 100 → 200（提高 cache 回收壓力，釋放 RAM 給 CMA）"
sudo sysctl -w vm.vfs_cache_pressure=200
echo "  vm.min_free_kbytes → 65536（保留更多連續 free page 供 CMA 分配）"
sudo sysctl -w vm.min_free_kbytes=65536
echo "  tegra_nvmap ext_pool_size → 1024（限制 GPU 用戶態記憶體池，防止耗盡 CMA）"
sudo sh -c 'echo 1024 > /sys/kernel/debug/tegra_nvmap/ext_pool_size' 2>/dev/null || echo "  (ext_pool_size 不存在於 Orin Nano，跳過)"

# 清除記憶體碎片
echo ""
echo "清除記憶體碎片（最大化 CMA 連續區塊）"
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1
echo "→ cache dropped + memory compacted"

# 驗證
echo ""
echo "驗證"
echo "CSI 攝影機: $(ls /dev/video0 2>/dev/null && echo '✓ /dev/video0' || echo '✗ 未偵測')"
echo "調整後 CMA / GPU 可用記憶體:"
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
echo ""
free -h
echo ""
echo "nvpmodel 模式: $(sudo nvpmodel -q 2>/dev/null | grep 'NV Power Mode' || echo 'check with: nvpmodel -q')"

echo ""
echo "============================================"
echo " CSI 攝影機 + Super Mode (25W) + 記憶體優化完成"
echo "============================================"
