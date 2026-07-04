#!/usr/bin/env bash
# ============================================================
# Start moondream2 stack (docker compose)
# Reference: README.md → Start Services → docker-compose
# ============================================================
set -euo pipefail

echo "=== Set MAXN Super (25W) ==="
if ! sudo nvpmodel -q 2>/dev/null | grep -q "NV Power Mode: MAXN_SUPER"; then
    sudo nvpmodel -m 2
fi
sudo jetson_clocks

# ---- update
echo "=== Tune NVMap / kernel params ==="
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sh -c 'echo 1024 > /sys/kernel/debug/tegra_nvmap/ext_pool_size' 2>/dev/null || echo "  (not available on Orin Nano)"

echo ""
echo "=== Compact memory ==="
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1

cd moondream2
sudo docker compose up -d

echo ""
echo "=== moondream2 stack started ==="
sudo docker compose ps
echo ""
echo "Waiting for model to load..."
sleep 30
echo "Model list:"
curl -s http://localhost:8080/v1/models | python3 -m json.tool
