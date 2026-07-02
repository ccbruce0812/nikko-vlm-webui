#!/usr/bin/env bash
# ============================================================
# 手動 docker run 啟動容器（互動式 — 任選一個模型 + 選用 RTSP）
# 三個模型不可同時啟動（記憶體有限），只選一個
# 對應 README.md → 啟動服務 → 手動 docker run
# ============================================================
set -euo pipefail

echo "============================================"
echo " 容器啟動（互動式）"
echo "============================================"
echo ""

# ── 建立共用網路 ──
echo "=== 建立共用網路 ==="
sudo docker network create vlm-net 2>/dev/null || echo "  vlm-net 已存在"

# ── Router（必要） ──
echo ""
echo "=== 啟動 Router（API 閘道）==="
sudo docker rm -f router 2>/dev/null || true
sudo docker run -d --name router --network vlm-net -p 8080:8080 router
echo "  ✓ router :8080"

# ── WebUI（必要） ──
echo ""
echo "=== 啟動 WebUI ==="
sudo docker rm -f live-vlm-webui 2>/dev/null || true
sudo docker run -d --name live-vlm-webui --network host --runtime nvidia --privileged \
    -v /sys:/sys:ro -v /run/jtop.sock:/run/jtop.sock:ro live-vlm-webui
echo "  ✓ live-vlm-webui :8090"

# ── 選擇模型（三選一） ──
echo ""
echo "============================================"
echo " 選擇要啟動的模型（三選一，不可同時啟動）"
echo "============================================"
echo "  1) Reason2 (VLM 描述，~2.6GB GPU)"
echo "  2) moondream2      (VLM 描述，~2.6GB GPU)"
echo "  3) YOLO            (物體偵測，~1.5GB GPU)"
echo "  q) 跳過，不啟動模型"
echo ""
read -p "  請選擇 [1/2/3/q]: " choice

# 先停掉所有可能已啟動的模型容器
sudo docker rm -f reason2 2>/dev/null || true
sudo docker rm -f moondream2 2>/dev/null || true
sudo docker rm -f yolo 2>/dev/null || true

case "$choice" in
    1)
        echo ""
        echo "=== 啟動 Reason2 ==="
        sudo docker run -d --name reason2 --runtime nvidia --network vlm-net \
            -v "$(pwd)/models/reason2:/model:ro" reason2
        echo "  等待模型載入 (35 秒)..."
        sleep 35
        echo "  ✓ reason2 :8002"
        ;;
    2)
        echo ""
        echo "=== 啟動 moondream2 ==="
        sudo docker run -d --name moondream2 --runtime nvidia --network vlm-net \
            -v "$(pwd)/models/moondream2:/model:ro" moondream2
        echo "  等待模型載入 (15 秒)..."
        sleep 15
        echo "  ✓ moondream2 :8001"
        ;;
    3)
        echo ""
        echo "=== 啟動 YOLO ==="
        sudo docker run -d --name yolo --runtime nvidia --network vlm-net \
            -v "$(pwd)/models/yolo:/model:ro" yolo
        echo "  等待模型載入 (10 秒)..."
        sleep 10
        echo "  ✓ yolo :8003"
        ;;
    *)
        echo "→ 跳過模型啟動"
        ;;
esac

# ── RTSP Server（選用） ──
echo ""
echo "============================================"
echo " RTSP Server（CSI 攝影機串流 — 選用）"
echo "============================================"
read -p "  是否啟動 RTSP Server？[y/N]: " yn
case "$yn" in
    [Yy]*)
        sudo docker rm -f rtsp-server 2>/dev/null || true

        read -p "  解析度 [1280x720]: " res
        W="${res%x*}"
        H="${res#*x}"
        W="${W:-1280}"
        H="${H:-720}"
        F="${FPS:-30}"

        if [ ! -e /dev/video0 ]; then
            echo "  ⚠ /dev/video0 不存在，CSI 攝影機未設定"
            echo "  請先執行 scripts/02-system-config.sh 設定攝影機"
        else
            echo "  啟動 RTSP Server (${W}x${H} @ ${F}fps)..."
            sudo docker run -d --name rtsp-server --runtime nvidia --network host \
                --device=/dev/video0 --device=/dev/media0 \
                -v /tmp:/tmp \
                -e WIDTH="$W" -e HEIGHT="$H" -e FPS="$F" rtsp-server
            echo "  ✓ rtsp-server"
            echo "  RTSP: rtsp://$(hostname -I | awk '{print $1}'):8554/stream"
        fi
        ;;
    *)
        echo "→ 跳過 RTSP Server"
        ;;
esac

# ── 狀態 ──
echo ""
echo "============================================"
echo " 容器狀態"
echo "============================================"
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
