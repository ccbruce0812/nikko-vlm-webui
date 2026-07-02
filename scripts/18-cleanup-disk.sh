#!/usr/bin/env bash
# ============================================================
# 磁碟空間清理
# 對應 README.md → 疑難排解 → 磁碟空間不足
# ============================================================
set -euo pipefail

echo "=== 清理前磁碟使用量 ==="
df -h / | tail -1
echo ""

echo "=== Docker 磁碟使用量 ==="
sudo docker system df

echo ""
echo "=== 執行清理（移除未使用的映像、容器、快取）==="
sudo docker system prune -af

echo ""
echo "=== 清理後磁碟使用量 ==="
df -h / | tail -1
sudo docker system df
