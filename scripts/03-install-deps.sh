#!/usr/bin/env bash
# ============================================================
# 安裝基本套件（Docker 檢查 + python3-venv）
# 對應 README.md → 前置準備 → 3. 安裝基本套件
# ============================================================
set -euo pipefail

echo "=== 確認 nvidia-container-runtime ==="
sudo docker info 2>/dev/null | grep -i runtime || echo "⚠ docker 未安裝或 nvidia-container-runtime 未設定"

echo ""
echo "=== 安裝 python3-venv（模型下載腳本需要）==="
sudo apt-get install -y python3-venv
echo "✓ python3-venv 已安裝"
