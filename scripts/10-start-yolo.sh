#!/usr/bin/env bash
# ============================================================
# 啟動 YOLO 組合（docker compose）
# 對應 README.md → 啟動服務 → docker-compose
# ============================================================
set -euo pipefail

# 設定 MAXN Super Mode (25W)
echo ""
echo "=== 設定 MAXN Super Mode (25W) ==="
sudo nvpmodel -m 2
echo "→ MAXN mode 2 (Super Mode 25W)"

# 鎖定最高時脈
echo ""
echo "=== 鎖定最高時脈（CPU + GPU + EMC）==="
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

cd yolo
sudo docker compose up -d

echo ""
echo "=== YOLO 組合已啟動 ==="
sudo docker compose ps
echo ""
echo "等待模型載入..."
sleep 15
echo "檢查模型清單："
curl -s http://localhost:8080/v1/models | python3 -m json.tool
