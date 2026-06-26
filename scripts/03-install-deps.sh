#!/usr/bin/env bash
# ============================================================
# 安裝基本套件（Docker 檢查 + huggingface_hub + jetson-containers）
# 對應 README.md → 前置準備 → 3. 安裝基本套件
# ============================================================
set -euo pipefail

echo "=== 確認 nvidia-container-runtime ==="
sudo docker info 2>/dev/null | grep -i runtime || echo "⚠ docker 未安裝或 nvidia-container-runtime 未設定"

echo ""
echo "=== 安裝 huggingface_hub（模型下載用）==="
pip install huggingface_hub

echo ""
echo "=== 安裝 jetson-containers（含 autotag 工具）==="
if [ -d "$HOME/jetson-containers" ]; then
    echo "~/jetson-containers 已存在，跳過 git clone"
    cd "$HOME/jetson-containers"
    git pull --ff-only 2>/dev/null || echo "  (無法 pull，使用現有版本)"
else
    cd "$HOME"
    git clone --depth 1 https://github.com/dusty-nv/jetson-containers.git
    cd jetson-containers
fi

echo ""
echo "=== 執行 install.sh ==="
sudo bash install.sh

echo ""
echo "=== 確認 autotag 可用 ==="
autotag llama_cpp --quiet
echo "autotag OK"
