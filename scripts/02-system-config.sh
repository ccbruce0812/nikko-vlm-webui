#!/usr/bin/env bash
# ============================================================
# 系統配置（Super Mode + 清除記憶體碎片 + 增加 GPU 可用記憶體）
# 對應 README.md → 前置準備 → 2. 系統配置
#
# Jetson Orin Nano 的 GPU 使用 CMA 從系統 RAM 動態分配。
# 依序：MAXN → 鎖時脈 → 調整 NVMap/kernel 參數 → 清除碎片
# 目標：最大化 GPU 可用的連續記憶體
# ============================================================
set -euo pipefail

echo "============================================"
echo " Super Mode + 記憶體優化"
echo "============================================"
echo ""

# 查看目前狀態 
echo "=== 1. 目前狀態 ==="
echo "nvpmodel 模式:"
sudo nvpmodel -q
echo ""
echo "CMA / GPU 可用記憶體:"
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
echo ""
free -h

# 設定 MAXN 效能模式 
echo ""
echo "=== 2. 設定 MAXN 效能模式 ==="
sudo nvpmodel -m 0
echo "→ MAXN mode 0"

# 鎖定最高時脈 
echo ""
echo "=== 3. 鎖定最高時脈（CPU + GPU + EMC）==="
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
sudo sh -c 'echo 1024 > /sys/kernel/debug/tegra_nvmap/ext_pool_size'

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
echo "調整後 CMA / GPU 可用記憶體:"
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
echo ""
free -h
echo ""
echo "nvpmodel 模式: $(sudo nvpmodel -q 2>/dev/null | grep 'NV Power Mode' || echo 'check with: nvpmodel -q')"

echo ""
echo "============================================"
echo " Super Mode + 記憶體優化完成"
echo "============================================"
